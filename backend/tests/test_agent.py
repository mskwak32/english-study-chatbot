import asyncio
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from app.agent import (
    AgentLoopError,
    run_agent,
)
from app.agent.protocol import (
    AGENT_RESPONSE_SCHEMA,
    INITIAL_ASSESSMENT_IN_PROGRESS_RESPONSE_SCHEMA,
)
from app.database import (
    add_message,
    get_learning_profile,
    get_or_create_default_chat,
    initialize_database,
    list_proficiency_tests,
    list_review_words,
    start_initial_assessment,
)
from app.llm import (
    LLMMessage,
    LLMStructuredResponse,
)


class FakeLLMClient:
    """미리 준비한 응답을 순서대로 반환하는 테스트용 LLM입니다."""

    def __init__(
        self,
        responses: list[dict[str, object]],
    ) -> None:
        self._responses = list(responses)
        self.calls: list[
            tuple[
                list[LLMMessage],
                dict[str, object],
            ]
        ] = []

    async def chat_structured(
        self,
        messages: Sequence[LLMMessage],
        response_schema: dict[str, object],
    ) -> LLMStructuredResponse:
        """요청 내용을 기록하고 다음 가짜 응답을 반환합니다."""
        self.calls.append(
            (
                list(messages),
                response_schema,
            )
        )

        return LLMStructuredResponse(
            content=self._responses.pop(0),
        )


def _database_url(tmp_path: Path) -> str:
    """각 테스트가 독립적으로 사용할 SQLite URL을 만듭니다."""
    return f"sqlite:///{tmp_path / 'data' / 'chat.db'}"


def _start_initial_assessment(database_url: str) -> int:
    """14개 답변을 저장할 테스트 전용 채팅을 만들고 반환합니다."""
    current_time = datetime(2026, 9, 10, tzinfo=UTC)
    chat = get_or_create_default_chat(
        database_url, study_date=date(2026, 9, 10), created_at=current_time
    )
    start_initial_assessment(database_url, chat.id, current_time)
    return chat.id


def _add_initial_assessment_answers(database_url: str, chat_id: int) -> None:
    """완료 조건을 만족하는 14개의 사용자 답변을 저장합니다."""
    current_time = datetime(2026, 9, 10, tzinfo=UTC)
    for number in range(14):
        add_message(
            database_url,
            chat_id,
            role="user",
            content=f"답변 {number + 1}",
            created_at=current_time,
        )


def test_run_agent_returns_direct_reply(
    tmp_path: Path,
) -> None:
    """첫 응답이 일반 답변이면 도구를 실행하지 않고 반환합니다."""
    database_url = _database_url(tmp_path)
    initialize_database(database_url)

    llm_client = FakeLLMClient(
        responses=[
            {
                "action": "reply",
                "message": "오늘은 과거형을 연습하겠습니다.",
            }
        ]
    )

    reply = asyncio.run(
        run_agent(
            llm_client,
            messages=[
                LLMMessage(
                    role="user",
                    content="오늘은 무엇을 공부하나요?",
                )
            ],
            database_url=database_url,
            study_date=date(2026, 9, 10),
            current_time=datetime(2026, 9, 10, tzinfo=UTC),
        )
    )

    assert reply == "오늘은 과거형을 연습하겠습니다."
    assert len(llm_client.calls) == 1
    assert llm_client.calls[0][1] == AGENT_RESPONSE_SCHEMA
    assert list_review_words(database_url) == []


def test_run_agent_executes_tool_and_requests_final_reply(
    tmp_path: Path,
) -> None:
    """도구 실행 결과를 LLM에 전달하고 최종 답변을 반환합니다."""
    database_url = _database_url(tmp_path)
    initialize_database(database_url)

    llm_client = FakeLLMClient(
        responses=[
            {
                "action": "save_review_word",
                "arguments": {
                    "term": "hesitate",
                    "explanation": "망설이다",
                },
            },
            {
                "action": "reply",
                "message": "hesitate를 복습 단어에 저장했습니다.",
            },
        ]
    )

    reply = asyncio.run(
        run_agent(
            llm_client,
            messages=[
                LLMMessage(
                    role="user",
                    content="hesitate를 복습 단어에 저장해 주세요.",
                )
            ],
            database_url=database_url,
            study_date=date(2026, 9, 10),
            current_time=datetime(2026, 9, 10, 1, 30, tzinfo=UTC),
        )
    )

    assert reply == "hesitate를 복습 단어에 저장했습니다."
    assert len(llm_client.calls) == 2

    second_request_messages = llm_client.calls[1][0]

    assert second_request_messages[-2].role == "assistant"
    assert '"action": "save_review_word"' in (second_request_messages[-2].content)

    assert second_request_messages[-1].role == "system"
    assert '"saved": true' in second_request_messages[-1].content
    assert "최종 답변을 반환하세요" in second_request_messages[-1].content

    review_words = list_review_words(database_url)

    assert len(review_words) == 1
    assert review_words[0].term == "hesitate"


def test_run_agent_hides_completion_action_until_all_answers_are_saved(
    tmp_path: Path,
) -> None:
    """초기 테스트의 첫 문제에서는 완료 도구를 LLM 선택지에서 제외합니다."""
    database_url = _database_url(tmp_path)
    initialize_database(database_url)
    chat_id = _start_initial_assessment(database_url)
    llm_client = FakeLLMClient(
        responses=[{"action": "reply", "message": "첫 번째 어휘 문제입니다."}]
    )

    reply = asyncio.run(
        run_agent(
            llm_client,
            messages=[LLMMessage(role="user", content="학습 프로필 만들기")],
            database_url=database_url,
            study_date=date(2026, 9, 10),
            current_time=datetime(2026, 9, 10, tzinfo=UTC),
            chat_id=chat_id,
        )
    )

    assert reply == "첫 번째 어휘 문제입니다."
    assert llm_client.calls[0][1] == INITIAL_ASSESSMENT_IN_PROGRESS_RESPONSE_SCHEMA


def test_run_agent_completes_initial_assessment_before_returning_reply(
    tmp_path: Path,
) -> None:
    """초기 테스트 완료 도구는 저장 결과를 본 뒤 최종 안내를 반환합니다."""
    database_url = _database_url(tmp_path)
    initialize_database(database_url)
    chat_id = _start_initial_assessment(database_url)
    _add_initial_assessment_answers(database_url, chat_id)
    llm_client = FakeLLMClient(
        responses=[
            {
                "action": "complete_initial_assessment",
                "arguments": {
                    "final_level": "B1",
                    "score_earned": 12,
                    "vocabulary_result": "어휘 결과",
                    "grammar_result": "문법 결과",
                    "reading_result": "독해 결과",
                    "self_expression_result": "자기표현 결과",
                    "strengths": "문장 이해",
                    "weaknesses": "시제 정확성",
                    "level_note": "초기 테스트 12/14점",
                },
            },
            {
                "action": "reply",
                "message": "초기 실력 테스트를 완료했습니다.",
            },
        ]
    )

    reply = asyncio.run(
        run_agent(
            llm_client,
            messages=[LLMMessage(role="user", content="마지막 답변입니다.")],
            database_url=database_url,
            study_date=date(2026, 9, 10),
            current_time=datetime(2026, 9, 10, tzinfo=UTC),
            chat_id=chat_id,
        )
    )

    assert reply == "초기 실력 테스트를 완료했습니다."
    assert len(llm_client.calls) == 2
    assert llm_client.calls[0][1] == AGENT_RESPONSE_SCHEMA
    assert get_learning_profile(database_url) is not None
    assert [test.final_level for test in list_proficiency_tests(database_url)] == ["B1"]


def test_run_agent_stops_before_exceeding_tool_call_limit(
    tmp_path: Path,
) -> None:
    """제한을 초과한 도구 호출은 실행하지 않습니다."""
    database_url = _database_url(tmp_path)
    initialize_database(database_url)

    llm_client = FakeLLMClient(
        responses=[
            {
                "action": "save_review_word",
                "arguments": {
                    "term": "hesitate",
                    "explanation": "망설이다",
                },
            },
            {
                "action": "save_review_word",
                "arguments": {
                    "term": "postpone",
                    "explanation": "미루다",
                },
            },
        ]
    )

    with pytest.raises(
        AgentLoopError,
        match="제한 횟수 안에",
    ):
        asyncio.run(
            run_agent(
                llm_client,
                messages=[
                    LLMMessage(
                        role="user",
                        content="복습 단어를 저장해 주세요.",
                    )
                ],
                database_url=database_url,
                study_date=date(2026, 9, 10),
                current_time=datetime(2026, 9, 10, tzinfo=UTC),
                max_tool_calls=1,
            )
        )

    review_words = list_review_words(database_url)

    assert [word.term for word in review_words] == ["hesitate"]
