"""사용자와 assistant 메시지의 저장과 조회를 처리합니다."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from app.study_time import to_utc

from .connection import connect_database

MESSAGE_ROLES = {"user", "assistant"}


@dataclass(frozen=True)
class Message:
    """DB에 저장된 메시지 한 건을 표현합니다."""

    id: int
    chat_id: int
    role: str
    content: str
    sequence: int
    created_at: datetime


class MessageError(ValueError):
    """메시지를 저장하거나 조회할 수 없을 때 발생합니다."""


def _message_from_row(row: tuple[int, int, str, str, int, str]) -> Message:
    """SQLite 조회 행을 Message 객체로 변환합니다."""

    return Message(
        id=row[0],
        chat_id=row[1],
        role=row[2],
        content=row[3],
        sequence=row[4],
        created_at=datetime.fromisoformat(row[5]),
    )


def _validate_message(role: str, content: str) -> None:
    """메시지 역할과 내용을 검증합니다."""
    if role not in MESSAGE_ROLES:
        raise MessageError("메시지 역할은 user 또는 assistant여야 합니다.")

    if not content.strip():
        raise MessageError("메시지 내용은 비어 있을 수 없습니다.")


def _next_message_sequence(connection: sqlite3.Connection, chat_id: int) -> int:
    """채팅 안에서 다음 메시지 순서를 계산합니다."""
    maximum_sequence = connection.execute(
        """
        SELECT COALESCE(MAX(sequence), 0)
        FROM messages
        WHERE chat_id = ?
        """,
        (chat_id,),
    ).fetchone()[0]

    return maximum_sequence + 1


def add_message(
    database_url: str, chat_id: int, role: str, content: str, created_at: datetime
) -> Message:
    """채팅에 사용자 또는 assistant 메시지를 저장합니다."""
    _validate_message(role, content)
    created_at_utc = to_utc(created_at)
    connection = connect_database(database_url)

    try:
        connection.execute("BEGIN IMMEDIATE")

        chat_exists = connection.execute(
            "SELECT 1 FROM chats WHERE id = ?", (chat_id,)
        ).fetchone()

        if chat_exists is None:
            raise MessageError("메시지를 저장할 채팅을 찾을 수 없습니다.")

        sequence = _next_message_sequence(connection, chat_id)
        cursor = connection.execute(
            """
            INSERT INTO messages (
                chat_id,
                role,
                content,
                sequence,
                created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, role, content, sequence, created_at_utc.isoformat()),
        )

        message_id = cursor.lastrowid

        if message_id is None:
            raise MessageError("메시지 ID를 만들 수 없습니다.")

        row = connection.execute(
            """
            SELECT
                id,
                chat_id,
                role,
                content,
                sequence,
                created_at
            FROM messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    if row is None:
        raise MessageError("저장한 메시지를 찾을 수 없습니다.")

    return _message_from_row(row)


def list_messages(database_url: str, chat_id: int) -> list[Message]:
    """채팅의 메시지를 저장 순서대로 반환합니다."""
    connection = connect_database(database_url)

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                chat_id,
                role,
                content,
                sequence,
                created_at
            FROM messages
            WHERE chat_id = ?
            ORDER BY sequence ASC
            """,
            (chat_id,),
        ).fetchall()
    finally:
        connection.close()

    return [_message_from_row(row) for row in rows]
