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
    """버전 1의 채팅, 메시지, 학습 데이터 스키마를 만듭니다."""
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

    # 현재 서비스는 단일 사용자이므로 프로필 ID는 1만 허용합니다.
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_profiles (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            learner_name TEXT NOT NULL DEFAULT '',
            target_language TEXT NOT NULL DEFAULT '영어',
            learning_goals TEXT NOT NULL DEFAULT '',
            session_started_on TEXT,
            current_level TEXT CHECK (
                current_level IS NULL
                OR current_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')
            ),
            level_updated_on TEXT,
            level_note TEXT NOT NULL DEFAULT '',
            strengths TEXT NOT NULL DEFAULT '',
            weaknesses TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS proficiency_tests (
            id INTEGER PRIMARY KEY,
            profile_id INTEGER NOT NULL DEFAULT 1,
            tested_on TEXT NOT NULL,
            final_level TEXT NOT NULL CHECK (
                final_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')
            ),
            score_earned INTEGER NOT NULL CHECK (score_earned >= 0),
            score_total INTEGER NOT NULL CHECK (score_total > 0),
            vocabulary_result TEXT NOT NULL DEFAULT '',
            grammar_result TEXT NOT NULL DEFAULT '',
            reading_result TEXT NOT NULL DEFAULT '',
            self_expression_result TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (profile_id)
                REFERENCES learning_profiles (id)
                ON DELETE CASCADE,
            CHECK (score_earned <= score_total)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS level_changes (
            id INTEGER PRIMARY KEY,
            profile_id INTEGER NOT NULL DEFAULT 1,
            changed_on TEXT NOT NULL,
            previous_level TEXT CHECK (
                previous_level IS NULL
                OR previous_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')
            ),
            new_level TEXT NOT NULL CHECK (
                new_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')
            ),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (profile_id)
                REFERENCES learning_profiles (id)
                ON DELETE CASCADE
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS level_changes_by_date
        ON level_changes (changed_on, id)
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS review_words (
            id INTEGER PRIMARY KEY,
            term TEXT NOT NULL COLLATE NOCASE UNIQUE,
            explanation TEXT NOT NULL,
            last_wrong_on TEXT NOT NULL,
            correct_streak INTEGER NOT NULL DEFAULT 0
                CHECK (correct_streak >= 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS review_words_by_last_wrong_date
        ON review_words (last_wrong_on, id)
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS study_records (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER UNIQUE,
            study_date TEXT NOT NULL,
            topic TEXT NOT NULL,
            new_words TEXT NOT NULL DEFAULT '',
            expression TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (chat_id)
                REFERENCES chats (id)
                ON DELETE SET NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS study_records_by_date
        ON study_records (study_date, id)
        """
    )


def _applied_migration_version(connection: sqlite3.Connection) -> set[int]:
    """이미 적용된 마이그레이션 버전을 반환합니다."""
    rows = connection.execute("SELECT version FROM schema_migrations").fetchall()

    return {row[0] for row in rows}


def _create_initial_assessment_sessions(connection: sqlite3.Connection) -> None:
    """버전 2의 초기 실력 테스트 진행 상태 테이블을 만듭니다."""
    connection.execute(
        """
        CREATE TABLE initial_assessment_sessions (
            chat_id INTEGER PRIMARY KEY,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE
        )
        """
    )


MIGRATIONS = (
    (1, _create_initial_schema),
    (2, _create_initial_assessment_sessions),
)
