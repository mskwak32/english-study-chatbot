from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from app.database import (
    MessageError,
    add_message,
    delete_chat,
    get_or_create_default_chat,
    initialize_database,
    list_messages,
)


def test_add_message_saves_messages_in_sequence_and_utc(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    initialize_database(database_url)

    chat = get_or_create_default_chat(
        database_url,
        date(2026, 9, 8),
        datetime(2026, 9, 7, 15, 0, tzinfo=UTC),
    )
    user_message = add_message(
        database_url,
        chat.id,
        "user",
        "Hello!",
        datetime(
            2026,
            9,
            8,
            0,
            30,
            tzinfo=ZoneInfo("Asia/Seoul"),
        ),
    )
    assistant_message = add_message(
        database_url,
        chat.id,
        "assistant",
        "Hello! How can I help you study today?",
        datetime(2026, 9, 7, 15, 31, tzinfo=UTC),
    )

    assert user_message.sequence == 1
    assert assistant_message.sequence == 2
    assert user_message.created_at == datetime(
        2026,
        9,
        7,
        15,
        30,
        tzinfo=UTC,
    )
    assert list_messages(database_url, chat.id) == [
        user_message,
        assistant_message,
    ]


def test_add_message_rejects_invalid_role_and_empty_content(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    initialize_database(database_url)

    chat = get_or_create_default_chat(
        database_url,
        date(2026, 9, 8),
        datetime(2026, 9, 7, 15, 0, tzinfo=UTC),
    )

    with pytest.raises(MessageError, match="역할"):
        add_message(
            database_url,
            chat.id,
            "system",
            "허용되지 않는 역할",
            datetime(2026, 9, 7, 15, 1, tzinfo=UTC),
        )

    with pytest.raises(MessageError, match="비어"):
        add_message(
            database_url,
            chat.id,
            "user",
            "   ",
            datetime(2026, 9, 7, 15, 1, tzinfo=UTC),
        )


def test_add_message_rejects_missing_chat(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    initialize_database(database_url)

    with pytest.raises(MessageError, match="채팅을 찾을 수 없습니다"):
        add_message(
            database_url,
            999,
            "user",
            "존재하지 않는 채팅에 저장하려는 메시지",
            datetime(2026, 9, 7, 15, 0, tzinfo=UTC),
        )


def test_deleting_chat_cascades_to_its_messages(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    initialize_database(database_url)

    deleted_chat = get_or_create_default_chat(
        database_url,
        date(2026, 9, 8),
        datetime(2026, 9, 7, 15, 0, tzinfo=UTC),
    )
    preserved_chat = get_or_create_default_chat(
        database_url,
        date(2026, 9, 9),
        datetime(2026, 9, 8, 15, 0, tzinfo=UTC),
    )
    add_message(
        database_url,
        deleted_chat.id,
        "user",
        "삭제될 메시지",
        datetime(2026, 9, 7, 15, 1, tzinfo=UTC),
    )
    preserved_message = add_message(
        database_url,
        preserved_chat.id,
        "assistant",
        "유지될 메시지",
        datetime(2026, 9, 8, 15, 1, tzinfo=UTC),
    )

    deleted = delete_chat(database_url, deleted_chat.id)

    assert deleted is True
    assert list_messages(database_url, deleted_chat.id) == []
    assert list_messages(database_url, preserved_chat.id) == [preserved_message]


def test_concurrent_message_requests_use_distinct_sequences(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"
    worker_count = 4
    start_barrier = Barrier(worker_count)

    initialize_database(database_url)

    chat = get_or_create_default_chat(
        database_url,
        date(2026, 9, 8),
        datetime(2026, 9, 7, 15, 0, tzinfo=UTC),
    )

    def create_message(index: int):
        # 모든 작업 스레드가 준비된 뒤 같은 시점에 저장을 시작합니다.
        start_barrier.wait(timeout=5)

        return add_message(
            database_url,
            chat.id,
            "user",
            f"동시 메시지 {index}",
            datetime(2026, 9, 7, 15, index, tzinfo=UTC),
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(create_message, index) for index in range(worker_count)
        ]
        messages = [future.result(timeout=10) for future in futures]

    assert sorted(message.sequence for message in messages) == [
        1,
        2,
        3,
        4,
    ]
