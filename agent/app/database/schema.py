"""SQLite 스키마 초기화와 마이그레이션을 처리합니다."""

import sqlite3

from .connection import connect_database


def initialize_database(database_url: str) -> None:
    """
    채팅과 메시지 저장에 필요한 SQLite 스키마를 준비합니다.
    아직 적용하지 않은 마이그레이션을 순서대로 적용합니다.
    """
    connection = connect_database(database_url)

    try:
        _create_migration_table(connection)
        connection.commit()

        # 버전 확인과 마이그레이션 적용을 하나의 쓰기 작업으로 묶습니다.
        connection.execute("BEGIN IMMEDIATE")

        applied_versions = _applied_migration_version(connection)

        for version, migration in MIGRATIONS:
            if version in applied_versions:
                continue

            migration(connection)

            connection.execute(
                """
                INSERT INTO schema_migrations (version)
                VALUES (?)
                """,
                (version,),
            )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _create_migration_table(connection: sqlite3.Connection) -> None:
    """적용한 스키마 버전을 기록할 테이블을 준비합니다."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY CHECK (version > 0),
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _create_initial_schema(connection: sqlite3.Connection) -> None:
    """버전 1의 chats와 messages 스키마를 만듭니다."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY,
            study_date TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('default', 'extra')),
            extra_number INTEGER,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            CHECK (
                (kind = 'default' AND extra_number IS NULL)
                OR (
                    kind = 'extra'
                    AND extra_number IS NOT NULL
                    AND extra_number >= 1
                )
            ),
            UNIQUE (study_date, extra_number)
        )
        """
    )

    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS chat_one_default_per_day
        ON chats (study_date) WHERE kind = 'default'
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE,
            UNIQUE (chat_id, sequence)
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS messages_by_chat_sequence
        ON messages (chat_id, sequence)
        """
    )


def _applied_migration_version(connection: sqlite3.Connection) -> set[int]:
    """이미 적용된 마이그레이션 버전을 반환합니다."""
    rows = connection.execute("SELECT version FROM schema_migrations").fetchall()

    return {row[0] for row in rows}


MIGRATIONS = ((1, _create_initial_schema),)
