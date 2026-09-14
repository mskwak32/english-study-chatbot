from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app import main
from app.database import add_message, get_chat
from fastapi.testclient import TestClient


@pytest.fixture
def configured_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, str]]:
    """각 테스트가 별도의 SQLite DB를 사용하도록 API 클라이언트를 만듭니다."""
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
    monkeypatch.setattr(main.settings, "timezone", "Asia/Seoul")

    with TestClient(main.app) as client:
        yield client, database_url


def test_today_chat_is_created_only_by_post_and_then_reused(
    configured_client: tuple[TestClient, str],
) -> None:
    """GET은 생성하지 않고 POST가 오늘 기본 채팅을 생성하거나 재사용합니다."""
    client, _ = configured_client

    empty_response = client.get("/chats/today")
    first_response = client.post("/chats/today")
    second_response = client.post("/chats/today")
    read_response = client.get("/chats/today")

    assert empty_response.status_code == 200
    assert empty_response.json() is None
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert read_response.status_code == 200
    assert first_response.json() == second_response.json()
    assert first_response.json() == read_response.json()
    assert first_response.json()["kind"] == "default"
    assert first_response.json()["extra_number"] is None


def test_create_additional_chat_and_list_chats(
    configured_client: tuple[TestClient, str],
) -> None:
    """추가 학습 채팅을 만들면 전체 채팅 목록에 함께 표시됩니다."""
    client, _ = configured_client
    default_chat = client.post("/chats/today").json()

    create_response = client.post("/chats/additional")

    assert create_response.status_code == 201

    additional_chat = create_response.json()

    assert additional_chat["kind"] == "extra"
    assert additional_chat["extra_number"] == 1
    assert additional_chat["study_date"] == default_chat["study_date"]
    assert additional_chat["title"].endswith("추가 학습 (1)")

    list_response = client.get("/chats")

    assert list_response.status_code == 200
    assert list_response.json() == [default_chat, additional_chat]


def test_read_chat_messages_returns_saved_order(
    configured_client: tuple[TestClient, str],
) -> None:
    """채팅 메시지를 역할과 저장 순서 그대로 반환합니다."""
    client, database_url = configured_client
    chat_id = client.post("/chats/today").json()["id"]

    add_message(
        database_url,
        chat_id,
        "user",
        "오늘은 현재완료를 연습하고 싶어요.",
        datetime(2026, 9, 12, 1, 0, tzinfo=UTC),
    )
    add_message(
        database_url,
        chat_id,
        "assistant",
        "I have studied English today.",
        datetime(2026, 9, 12, 1, 1, tzinfo=UTC),
    )

    response = client.get(f"/chats/{chat_id}/messages")

    assert response.status_code == 200
    assert [
        (message["role"], message["content"], message["sequence"])
        for message in response.json()
    ] == [
        ("user", "오늘은 현재완료를 연습하고 싶어요.", 1),
        ("assistant", "I have studied English today.", 2),
    ]


def test_read_chat_messages_returns_404_for_missing_chat(
    configured_client: tuple[TestClient, str],
) -> None:
    """존재하지 않는 채팅의 메시지는 조회할 수 없습니다."""
    client, _ = configured_client

    response = client.get("/chats/999/messages")

    assert response.status_code == 404
    assert response.json() == {"detail": "채팅을 찾을 수 없습니다."}


def test_delete_chat_removes_existing_chat(
    configured_client: tuple[TestClient, str],
) -> None:
    """채팅을 삭제하면 빈 본문과 204 상태를 반환합니다."""
    client, database_url = configured_client
    chat_id = client.post("/chats/additional").json()["id"]

    response = client.delete(f"/chats/{chat_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert get_chat(database_url, chat_id) is None


def test_delete_default_chat_does_not_recreate_it_on_get(
    configured_client: tuple[TestClient, str],
) -> None:
    """기본 학습을 삭제한 뒤 GET은 새 채팅을 만들지 않고 null을 반환합니다."""
    client, database_url = configured_client
    chat_id = client.post("/chats/today").json()["id"]

    delete_response = client.delete(f"/chats/{chat_id}")
    read_response = client.get("/chats/today")

    assert delete_response.status_code == 204
    assert read_response.status_code == 200
    assert read_response.json() is None
    assert get_chat(database_url, chat_id) is None


def test_delete_chat_returns_404_for_missing_chat(
    configured_client: tuple[TestClient, str],
) -> None:
    """존재하지 않는 채팅을 삭제하면 404를 반환합니다."""
    client, _ = configured_client

    response = client.delete("/chats/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "채팅을 찾을 수 없습니다."}
