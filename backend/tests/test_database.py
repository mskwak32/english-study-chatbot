from pathlib import Path

import pytest
from app.database import (
    DatabaseError,
    connect_database,
    database_path_from_url,
    initialize_database,
)


def test_database_path_from_url_returns_absolute_path(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    result = database_path_from_url(database_url)

    assert result == database_path


def test_database_path_from_url_rejects_relative_path() -> None:
    with pytest.raises(DatabaseError, match="절대 경로"):
        database_path_from_url("sqlite:///data/chat.db")


def test_connect_database_creates_parent_directory_and_enables_foreign_keys(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    connection = connect_database(database_url)

    try:
        foreign_keys_enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    finally:
        connection.close()

    assert database_path.parent.is_dir()
    assert foreign_keys_enabled == 1


def test_initialize_database_is_idempotent_and_preserves_data(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    initialize_database(database_url)

    connection = connect_database(database_url)

    try:
        connection.execute(
            """
            INSERT INTO chats (
                study_date,
                kind,
                extra_number,
                title,
                created_at
            ) VALUES (?,?,?,?,?)
            """,
            (
                "2026-09-07",
                "default",
                None,
                "2026-09-07 영어 학습",
                "2026-09-07T09:00:00+09:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    initialize_database(database_url)
    connection = connect_database(database_url)

    try:
        table_names = {
            row[0]
            for row in connection.execute(
                """SELECT name FROM sqlite_master WHERE type = 'table'"""
            )
        }
        chat_titles = connection.execute("SELECT title FROM chats").fetchall()

    finally:
        connection.close()

    assert {
        "chats",
        "messages",
        "learning_profiles",
        "proficiency_tests",
        "level_changes",
        "review_words",
        "study_records",
    } <= table_names
    assert chat_titles == [("2026-09-07 영어 학습",)]


def test_initialize_database_records_initial_migration_once(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    # 초기화를 반복해도 이미 적용한 버전은 다시 기록하지 않습니다.
    initialize_database(database_url)
    initialize_database(database_url)

    connection = connect_database(database_url)

    try:
        migration_versions = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()
    finally:
        connection.close()

    assert migration_versions == [(1,)]
