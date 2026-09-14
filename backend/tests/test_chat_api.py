from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from app import main
from app.database import (
    get_or_create_default_chat,
    list_messages,
    save_learning_profile,
)
from app.llm import (
    LLMConnectionError,
    LLMMessage,
    LLMStructuredResponse,
)
from fastapi.testclient import TestClient


class FakeLLMClient:
    """준비된 구조화 응답을 반환하는 테스트용 LLM입니다."""

    def __init__(
        self,
        response: dict[str, object],
    ) -> None:
        self._response = response
        self.calls: list[list[LLMMessage]] = []

    async def chat_structured(
        self,
        messages: Sequence[LLMMessage],
        response_schema: dict[str, object],
    ) -> LLMStructuredResponse:
        """요청 메시지를 기록하고 준비된 응답을 반환합니다."""
        self.calls.append(list(messages))

        return LLMStructuredResponse(content=self._response)


class FailingLLMClient:
    """연결 실패를 재현하는 테스트용 LLM입니다."""

    async def chat_structured(
        self,
        messages: Sequence[LLMMessage],
        response_schema: dict[str, object],
    ) -> LLMStructuredResponse:
        """모델 연결 실패를 발생시킵니다."""
        raise LLMConnectionError("Ollama 서버에 연결할 수 없습니다.")


@pytest.fixture
def configured_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, str]]:
    """독립적인 DB와 런타임 지침을 사용하는 API 클라이언트를 제공합니다."""
    database_url = f"sqlite:///{tmp_path / 'data' / 'chat.db'}"
    instructions_path = tmp_path / "instructions"
    instructions_path.mkdir()

    (instructions_path / "AGENT.md").write_text(
        "테스트용 영어 튜터 지침",
        encoding="utf-8",
    )
    (instructions_path / "영어_가이드라인.md").write_text(
        "테스트용 학습 가이드라인",
        encoding="utf-8",
    )

    monkeypatch.setattr(main.settings, "database_url", database_url)
    monkeypatch.setattr(main.settings, "instructions_path", instructions_path)

    with TestClient(main.app) as client:
        yield client, database_url


def _create_chat(database_url: str) -> int:
    """테스트용 기본 학습 채팅을 만들고 ID를 반환합니다."""
    chat = get_or_create_default_chat(
        database_url,
        study_date=date(2026, 9, 10),
        created_at=datetime(2026, 9, 10, tzinfo=UTC),
    )
    return chat.id


def test_create_chat_message_returns_assistant_reply(
    configured_client: tuple[TestClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """정상 응답을 HTTP 200의 assistant 메시지로 반환합니다."""
    client, database_url = configured_client
    chat_id = _create_chat(database_url)
    llm_client = FakeLLMClient(
        {
            "action": "reply",
            "message": "오늘은 과거형을 연습하겠습니다.",
        }
    )
    monkeypatch.setattr(main.app.state, "llm_client", llm_client)

    response = client.post(
        f"/chats/{chat_id}/messages",
        json={"content": "오늘은 무엇을 공부하나요?"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "assistant"
    assert response.json()["content"] == "오늘은 과거형을 연습하겠습니다."
    assert response.json()["sequence"] == 2


def test_start_today_chat_saves_one_tutor_greeting_without_internal_trigger(
    configured_client: tuple[TestClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """오늘 학습 시작은 첫 안내만 저장하고 다시 시작해도 중복 생성하지 않습니다."""
    client, database_url = configured_client
    save_learning_profile(
        database_url,
        current_level="A1",
        session_started_on=date(2026, 9, 10),
        level_updated_on=date(2026, 9, 10),
        updated_at=datetime(2026, 9, 10, tzinfo=UTC),
    )
    llm_client = FakeLLMClient(
        {
            "action": "reply",
            "message": "안녕하세요. 오늘의 영어 학습을 시작하겠습니다.",
        }
    )
    monkeypatch.setattr(main.app.state, "llm_client", llm_client)

    first_response = client.post("/chats/today/start")
    second_response = client.post("/chats/today/start")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json() == second_response.json()
    assert len(llm_client.calls) == 1
    assert llm_client.calls[0][-1] == LLMMessage(role="user", content="영어 공부 시작")
    messages = list_messages(database_url, first_response.json()["id"])
    assert [
        (message.role, message.content, message.sequence) for message in messages
    ] == [
        (
            "assistant",
            "안녕하세요. 오늘의 영어 학습을 시작하겠습니다.",
            1,
        )
    ]


def test_profile_setup_starts_once_before_a_learning_profile_exists(
    configured_client: tuple[TestClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """프로필이 없으면 일반 학습 대신 초기 테스트 첫 문제만 시작합니다."""
    client, database_url = configured_client
    llm_client = FakeLLMClient(
        {
            "action": "reply",
            "message": "현재 수준을 확인하겠습니다. 첫 어휘 문제입니다.",
        }
    )
    monkeypatch.setattr(main.app.state, "llm_client", llm_client)

    blocked_response = client.post("/chats/today/start")
    first_response = client.post("/chats/today/profile-setup")
    second_response = client.post("/chats/today/profile-setup")

    assert blocked_response.status_code == 422
    assert blocked_response.json() == {"detail": "학습 프로필을 먼저 만들어 주세요."}
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json() == second_response.json()
    assert len(llm_client.calls) == 1
    assert llm_client.calls[0][-1] == LLMMessage(
        role="user", content="학습 프로필 만들기"
    )
    messages = list_messages(database_url, first_response.json()["id"])
    assert [
        (message.role, message.content, message.sequence) for message in messages
    ] == [("assistant", "현재 수준을 확인하겠습니다. 첫 어휘 문제입니다.", 1)]


def test_create_chat_message_returns_404_before_calling_llm(
    configured_client: tuple[TestClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """없는 채팅에는 LLM을 호출하지 않고 404를 반환합니다."""
    client, _ = configured_client
    llm_client = FakeLLMClient(
        {
            "action": "reply",
            "message": "사용되지 않는 응답입니다.",
        }
    )
    monkeypatch.setattr(main.app.state, "llm_client", llm_client)

    response = client.post(
        "/chats/999/messages",
        json={"content": "영어를 공부하고 싶어요."},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "채팅을 찾을 수 없습니다."}
    assert llm_client.calls == []


def test_create_chat_message_returns_503_for_model_connection_error(
    configured_client: tuple[TestClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """모델 연결 실패를 사용자가 이해할 수 있는 503 응답으로 바꿉니다."""
    client, database_url = configured_client
    chat_id = _create_chat(database_url)
    monkeypatch.setattr(
        main.app.state,
        "llm_client",
        FailingLLMClient(),
    )

    response = client.post(
        f"/chats/{chat_id}/messages",
        json={"content": "오늘 학습을 시작할게요."},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "현재 영어 학습 모델에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
        )
    }


def test_create_chat_message_returns_502_for_invalid_model_response(
    configured_client: tuple[TestClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """허용되지 않은 구조화 응답은 502로 처리합니다."""
    client, database_url = configured_client
    chat_id = _create_chat(database_url)
    llm_client = FakeLLMClient(
        {
            "action": "delete_database",
        }
    )
    monkeypatch.setattr(main.app.state, "llm_client", llm_client)

    response = client.post(
        f"/chats/{chat_id}/messages",
        json={"content": "오늘 학습을 시작할게요."},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": ("영어 학습 모델의 응답을 처리하지 못했습니다. 다시 시도해 주세요.")
    }

    messages = list_messages(database_url, chat_id)

    assert [(message.role, message.content) for message in messages] == [
        ("user", "오늘 학습을 시작할게요."),
    ]
