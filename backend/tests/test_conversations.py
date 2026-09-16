import asyncio
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.database import (
    get_or_create_default_chat,
    initialize_database,
    list_messages,
    start_initial_assessment,
)
from app.llm import (
    LLMConnectionError,
    LLMMessage,
    LLMStructuredResponse,
)
from app.services import ConversationError, respond_to_chat
from app.services.conversations import _is_level_change_requested
from app.services.prompts import USER_MESSAGE_CHARACTER_LIMIT


class FakeLLMClient:
    """준비된 구조화 응답을 순서대로 반환하는 테스트용 LLM입니다."""

    def __init__(
        self,
        responses: list[dict[str, object]],
    ) -> None:
        self._responses = list(responses)
        self.calls: list[list[LLMMessage]] = []

    async def chat_structured(
        self,
        messages: Sequence[LLMMessage],
        response_schema: dict[str, object],
    ) -> LLMStructuredResponse:
        """요청 메시지를 기록하고 다음 가짜 응답을 반환합니다."""
        self.calls.append(list(messages))

        return LLMStructuredResponse(
            content=self._responses.pop(0),
        )


class FailingLLMClient:
    """연결 실패를 재현하는 테스트용 LLM입니다."""

    async def chat_structured(
        self,
        messages: Sequence[LLMMessage],
        response_schema: dict[str, object],
    ) -> LLMStructuredResponse:
        """모델 연결 실패를 발생시킵니다."""
        raise LLMConnectionError("Ollama 서버에 연결할 수 없습니다.")


def _database_url(tmp_path: Path) -> str:
    """각 테스트가 독립적으로 사용할 SQLite URL을 만듭니다."""
    return f"sqlite:///{tmp_path / 'data' / 'chat.db'}"


def _create_chat(database_url: str) -> int:
    """테스트용 기본 학습 채팅을 만들고 ID를 반환합니다."""
    chat = get_or_create_default_chat(
        database_url,
        study_date=date(2026, 9, 10),
        created_at=datetime(2026, 9, 10, tzinfo=UTC),
    )
    return chat.id


def test_level_change_permission_requires_level_and_direct_action() -> None:
    """레벨 변경 도구는 현재 입력의 명시적 요청에서만 노출합니다."""
    assert _is_level_change_requested("현재 레벨을 올려 주세요.")
    assert _is_level_change_requested("레벨 재평가를 해 주세요.")
    assert not _is_level_change_requested("오늘 레벨에 맞는 문제를 내 주세요.")
    assert not _is_level_change_requested("문법 난이도를 올려 주세요.")


def test_respond_to_chat_saves_user_and_assistant_messages(
    tmp_path: Path,
) -> None:
    """사용자 메시지와 assistant 응답을 순서대로 저장합니다."""
    database_url = _database_url(tmp_path)
    initialize_database(database_url)
    chat_id = _create_chat(database_url)

    llm_client = FakeLLMClient(
        responses=[
            {
                "action": "reply",
                "message": "오늘은 과거형을 연습하겠습니다.",
            }
        ]
    )

    assistant_message = asyncio.run(
        respond_to_chat(
            llm_client,
            database_url=database_url,
            chat_id=chat_id,
            user_content="오늘은 무엇을 공부하나요?",
            agent_instructions="당신은 영어 튜터입니다.",
            study_guidelines="학습자의 답변을 기다립니다.",
            initial_assessment_instructions="초기 평가 전용 지침",
            timezone_name="Asia/Seoul",
            now=datetime(2026, 9, 10, 1, 30, tzinfo=UTC),
        )
    )

    assert assistant_message.role == "assistant"
    assert assistant_message.content == "오늘은 과거형을 연습하겠습니다."

    messages = list_messages(database_url, chat_id)

    assert [(message.role, message.content) for message in messages] == [
        ("user", "오늘은 무엇을 공부하나요?"),
        ("assistant", "오늘은 과거형을 연습하겠습니다."),
    ]
    assert [message.sequence for message in messages] == [1, 2]

    assert len(llm_client.calls) == 1
    assert "초기 평가 전용 지침" not in llm_client.calls[0][0].content
    assert llm_client.calls[0][-1] == LLMMessage(
        role="user",
        content="오늘은 무엇을 공부하나요?",
    )


def test_respond_to_chat_rejects_too_long_message_before_saving(
    tmp_path: Path,
) -> None:
    """길이 제한을 넘는 사용자 메시지는 DB와 LLM에 전달하지 않습니다."""
    database_url = _database_url(tmp_path)
    initialize_database(database_url)
    chat_id = _create_chat(database_url)

    llm_client = FakeLLMClient(responses=[])

    with pytest.raises(
        ConversationError,
        match="사용자 메시지는 4,000자를 초과할 수 없습니다",
    ):
        asyncio.run(
            respond_to_chat(
                llm_client,
                database_url=database_url,
                chat_id=chat_id,
                user_content="a" * (USER_MESSAGE_CHARACTER_LIMIT + 1),
                agent_instructions="당신은 영어 튜터입니다.",
                study_guidelines="학습자의 답변을 기다립니다.",
                initial_assessment_instructions="초기 평가 전용 지침",
                timezone_name="Asia/Seoul",
            )
        )

    assert list_messages(database_url, chat_id) == []
    assert llm_client.calls == []


def test_respond_to_chat_keeps_user_message_when_model_fails(
    tmp_path: Path,
) -> None:
    """모델 오류가 나도 이미 받은 사용자 메시지는 보존합니다."""
    database_url = _database_url(tmp_path)
    initialize_database(database_url)
    chat_id = _create_chat(database_url)

    with pytest.raises(
        LLMConnectionError,
        match="연결할 수 없습니다",
    ):
        asyncio.run(
            respond_to_chat(
                FailingLLMClient(),
                database_url=database_url,
                chat_id=chat_id,
                user_content="오늘 학습을 시작할게요.",
                agent_instructions="당신은 영어 튜터입니다.",
                study_guidelines="학습자의 답변을 기다립니다.",
                initial_assessment_instructions="초기 평가 전용 지침",
                timezone_name="Asia/Seoul",
                now=datetime(2026, 9, 10, tzinfo=UTC),
            )
        )

    messages = list_messages(database_url, chat_id)

    assert [(message.role, message.content) for message in messages] == [
        ("user", "오늘 학습을 시작할게요."),
    ]


def test_respond_to_chat_includes_initial_assessment_instructions_for_active_session(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path)
    initialize_database(database_url)
    chat_id = _create_chat(database_url)
    start_initial_assessment(database_url, chat_id, datetime(2026, 9, 10, tzinfo=UTC))
    llm_client = FakeLLMClient(
        responses=[{"action": "reply", "message": "첫 문제에 답해 주세요."}]
    )

    asyncio.run(
        respond_to_chat(
            llm_client,
            database_url=database_url,
            chat_id=chat_id,
            user_content="선택지 2번입니다.",
            agent_instructions="당신은 영어 튜터입니다.",
            study_guidelines="일반 학습 가이드라인",
            initial_assessment_instructions="초기 평가 전용 지침",
            timezone_name="Asia/Seoul",
            now=datetime(2026, 9, 10, tzinfo=UTC),
        )
    )

    assert "초기 평가 전용 지침" in llm_client.calls[0][0].content
    assert "일반 학습 가이드라인" not in llm_client.calls[0][0].content
