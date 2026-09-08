from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Barrier

from app.database import (
    Chat,
    connect_database,
    create_additional_chat,
    delete_chat,
    get_chat,
    get_or_create_default_chat,
    initialize_database,
    list_chats,
)


def test_get_or_create_default_chat_returns_one_chat_per_date(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"
    study_date = date(2026, 9, 7)

    initialize_database(database_url)

    first_chat = get_or_create_default_chat(
        database_url,
        study_date,
        datetime(2026, 9, 7, 9, 0, tzinfo=UTC),
    )
    second_chat = get_or_create_default_chat(
        database_url,
        study_date,
        datetime(2026, 9, 7, 10, 0, tzinfo=UTC),
    )

    connection = connect_database(database_url)

    try:
        chat_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM chats
            WHERE study_date = ? AND kind = 'default'
            """,
            (study_date.isoformat(),),
        ).fetchone()[0]
    finally:
        connection.close()

    assert first_chat == second_chat
    assert first_chat.study_date == study_date
    assert first_chat.title == "2026-09-07 영어 학습"
    assert chat_count == 1


def test_get_or_create_default_chat_creates_chats_for_different_dates(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    initialize_database(database_url)

    first_chat = get_or_create_default_chat(
        database_url, date(2026, 9, 7), datetime(2026, 9, 7, 9, 0, tzinfo=UTC)
    )
    second_chat = get_or_create_default_chat(
        database_url, date(2026, 9, 8), datetime(2026, 9, 8, 9, 0, tzinfo=UTC)
    )

    assert first_chat.id != second_chat.id
    assert second_chat.title == "2026-09-08 영어 학습"


def test_create_additional_chat_assign_increasing_numbers(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"
    study_date = date(2026, 9, 7)

    initialize_database(database_url)

    first_chat = create_additional_chat(
        database_url, study_date, datetime(2026, 9, 7, 10, 0, tzinfo=UTC)
    )
    second_chat = create_additional_chat(
        database_url, study_date, datetime(2026, 9, 7, 10, 0, tzinfo=UTC)
    )

    assert first_chat.kind == "extra"
    assert first_chat.extra_number == 1
    assert first_chat.title == "2026-09-07 영어 학습 - 추가 학습 (1)"
    assert second_chat.extra_number == 2
    assert second_chat.title == "2026-09-07 영어 학습 - 추가 학습 (2)"


def test_create_additional_chat_reuses_deleted_number(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"
    study_date = date(2026, 9, 7)

    initialize_database(database_url)

    first_chat = create_additional_chat(
        database_url, study_date, datetime(2026, 9, 7, 10, 0, tzinfo=UTC)
    )
    second_chat = create_additional_chat(
        database_url, study_date, datetime(2026, 9, 7, 11, 0, tzinfo=UTC)
    )

    connection = connect_database(database_url)

    try:
        connection.execute("DELETE FROM chats WHERE id = ?", (first_chat.id,))
        connection.commit()
    finally:
        connection.close()

    replacement_chat = create_additional_chat(
        database_url, study_date, datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    )

    assert second_chat.extra_number == 2
    assert replacement_chat.extra_number == 1
    assert replacement_chat.title == "2026-09-07 영어 학습 - 추가 학습 (1)"


def test_get_chat_returns_chat_or_none(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    initialize_database(database_url)

    saved_chat = create_additional_chat(
        database_url,
        date(2026, 9, 7),
        datetime(2026, 9, 7, 10, 0, tzinfo=UTC),
    )

    assert get_chat(database_url, saved_chat.id) == saved_chat
    assert get_chat(database_url, 999) is None


def test_list_chats_orders_dates_newest_first(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    initialize_database(database_url)

    older_default_chat = get_or_create_default_chat(
        database_url,
        date(2026, 9, 7),
        datetime(2026, 9, 7, 9, 0, tzinfo=UTC),
    )
    older_extra_chat = create_additional_chat(
        database_url,
        date(2026, 9, 7),
        datetime(2026, 9, 7, 10, 0, tzinfo=UTC),
    )
    newer_default_chat = get_or_create_default_chat(
        database_url,
        date(2026, 9, 8),
        datetime(2026, 9, 8, 9, 0, tzinfo=UTC),
    )

    chats = list_chats(database_url)

    assert [chat.id for chat in chats] == [
        newer_default_chat.id,
        older_default_chat.id,
        older_extra_chat.id,
    ]


def test_delete_chat_returns_whether_a_chat_was_deleted(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    initialize_database(database_url)

    default_chat = get_or_create_default_chat(
        database_url,
        date(2026, 9, 7),
        datetime(2026, 9, 7, 9, 0, tzinfo=UTC),
    )
    extra_chat = create_additional_chat(
        database_url,
        date(2026, 9, 7),
        datetime(2026, 9, 7, 10, 0, tzinfo=UTC),
    )

    deleted = delete_chat(database_url, default_chat.id)

    assert deleted is True
    assert get_chat(database_url, default_chat.id) is None
    assert list_chats(database_url) == [extra_chat]
    assert delete_chat(database_url, default_chat.id) is False


def test_delete_chat_does_not_modify_workspace_files(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()

    study_history_path = workspace_path / "영어_학습이력.md"
    original_content = "# 영어 학습 이력\n\n삭제하면 안 되는 학습 기록입니다.\n"
    study_history_path.write_text(original_content, encoding="utf-8")

    initialize_database(database_url)

    chat = get_or_create_default_chat(
        database_url,
        date(2026, 9, 8),
        datetime(2026, 9, 7, 15, 0, tzinfo=UTC),
    )

    deleted = delete_chat(database_url, chat.id)

    assert deleted is True
    assert get_chat(database_url, chat.id) is None
    assert study_history_path.read_text(encoding="utf-8") == original_content


def test_concurrent_default_chat_requests_return_one_chat(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"
    study_date = date(2026, 9, 7)
    created_at = datetime(2026, 9, 7, 9, 0, tzinfo=UTC)
    worker_count = 8
    start_barrier = Barrier(worker_count)

    initialize_database(database_url)

    def create_chat() -> Chat:
        start_barrier.wait(timeout=5)
        return get_or_create_default_chat(
            database_url,
            study_date,
            created_at,
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(create_chat) for _ in range(worker_count)]
        chats = [future.result(timeout=10) for future in futures]

    assert len({chat.id for chat in chats}) == 1
    assert len(list_chats(database_url)) == 1


def test_concurrent_additional_chat_requests_use_distinct_numbers(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"
    study_date = date(2026, 9, 7)
    created_at = datetime(2026, 9, 7, 10, 0, tzinfo=UTC)
    worker_count = 4
    start_barrier = Barrier(worker_count)

    initialize_database(database_url)

    def create_chat() -> Chat:
        start_barrier.wait(timeout=5)
        return create_additional_chat(
            database_url,
            study_date,
            created_at,
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(create_chat) for _ in range(worker_count)]
        chats = [future.result(timeout=10) for future in futures]

    assert sorted(chat.extra_number for chat in chats) == [1, 2, 3, 4]
    assert len({chat.id for chat in chats}) == worker_count
