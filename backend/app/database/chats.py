"""날짜 기반 학습 채팅을 저장하고 조회합니다."""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from app.study_time import to_utc

from .connection import connect_database


@dataclass(frozen=True)
class Chat:
    """DB에 저장된 채팅 한 건을 표현합니다."""

    id: int
    study_date: date
    kind: str
    extra_number: int | None
    title: str
    created_at: datetime


class ChatError(RuntimeError):
    """채팅을 조회하거나 생성할 수 없을 때 발생합니다."""


def default_chat_title(study_date: date) -> str:
    """날짜별 기본 학습 채팅의 제목을 만듭니다."""
    return f"{study_date.isoformat()} 영어 학습"


def _chat_from_row(row: tuple[int, str, str, int | None, str, str]) -> Chat:
    """SQLite 조회 행을 Chat 객체로 변환합니다."""
    return Chat(
        id=row[0],
        study_date=date.fromisoformat(row[1]),
        kind=row[2],
        extra_number=row[3],
        title=row[4],
        created_at=datetime.fromisoformat(row[5]),
    )


def get_or_create_default_chat(
    database_url: str, study_date: date, created_at: datetime
) -> Chat:
    """지정한 날짜의 기본 학습 채팅을 조회하거나 생성합니다."""
    created_at_utc = to_utc(created_at)
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
            ) VALUES (?, 'default', NULL, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            (
                study_date.isoformat(),
                default_chat_title(study_date),
                created_at_utc.isoformat(),
            ),
        )
        row = connection.execute(
            """
            SELECT
                id,
                study_date,
                kind,
                extra_number,
                title,
                created_at
            FROM chats
            WHERE study_date = ? AND kind = 'default'
            """,
            (study_date.isoformat(),),
        ).fetchone()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    if row is None:
        raise ChatError("기본 학습 채팅을 찾을 수 없습니다.")

    return _chat_from_row(row)


def get_default_chat(database_url: str, study_date: date) -> Chat | None:
    """지정한 날짜의 기본 학습 채팅만 조회하고 없으면 생성하지 않고 None을 반환합니다."""
    connection = connect_database(database_url)

    try:
        row = connection.execute(
            """
            SELECT
                id,
                study_date,
                kind,
                extra_number,
                title,
                created_at
            FROM chats
            WHERE study_date = ? AND kind = 'default'
            """,
            (study_date.isoformat(),),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    return _chat_from_row(row)


def additional_chat_title(study_date: date, extra_number: int) -> str:
    """날짜와 번호를 사용해 추가 학습 채팅의 제목을 만듭니다."""
    return f"{default_chat_title(study_date)} - 추가 학습 ({extra_number})"


def _next_extra_number(connection: sqlite3.Connection, study_date: date) -> int:
    """지정한 날짜에 사용할 가장 작은 빈 추가 학습 번호를 찾습니다."""
    rows = connection.execute(
        """
        SELECT extra_number
        FROM chats
        WHERE study_date = ? AND kind = 'extra'
        """,
        (study_date.isoformat(),),
    ).fetchall()

    used_numbers = {row[0] for row in rows}
    extra_number = 1

    while extra_number in used_numbers:
        extra_number += 1

    return extra_number


def create_additional_chat(
    database_url: str, study_date: date, created_at: datetime
) -> Chat:
    """가장 작은 빈 번호로 추가 채팅을 만들고 번호 선택과 저장을 직렬화합니다."""
    created_at_utc = to_utc(created_at)
    connection = connect_database(database_url)

    try:
        connection.execute("BEGIN IMMEDIATE")

        extra_number = _next_extra_number(connection, study_date)
        cursor = connection.execute(
            """
            INSERT INTO chats (
                study_date,
                kind,
                extra_number,
                title,
                created_at
            ) VALUES (?, 'extra', ?, ?, ?)
            """,
            (
                study_date.isoformat(),
                extra_number,
                additional_chat_title(study_date, extra_number),
                created_at_utc.isoformat(),
            ),
        )

        chat_id = cursor.lastrowid

        if chat_id is None:
            raise ChatError("추가 학습 채팅 ID를 만들 수 없습니다.")

        row = connection.execute(
            """
            SELECT
                id,
                study_date,
                kind,
                extra_number,
                title,
                created_at
            FROM chats
            WHERE id = ?
            """,
            (chat_id,),
        ).fetchone()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    if row is None:
        raise ChatError("추가 학습 채팅을 찾을 수 없습니다.")

    return _chat_from_row(row)


def get_chat(database_url: str, chat_id: int) -> Chat | None:
    """ID로 채팅을 조회하고, 없으면 None을 반환합니다."""
    connection = connect_database(database_url)

    try:
        row = connection.execute(
            """
            SELECT
                id,
                study_date,
                kind,
                extra_number,
                title,
                created_at
            FROM chats
            WHERE id = ?
            """,
            (chat_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    return _chat_from_row(row)


def list_chats(database_url: str) -> list[Chat]:
    """최근 학습 날짜부터 모든 채팅을 반환합니다."""
    connection = connect_database(database_url)

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                study_date,
                kind,
                extra_number,
                title,
                created_at
            FROM chats
            ORDER BY study_date DESC, created_at ASC
            """
        ).fetchall()
    finally:
        connection.close()

    return [_chat_from_row(row) for row in rows]


def delete_chat(database_url: str, chat_id: int) -> bool:
    """채팅을 삭제하고 실제 삭제 여부를 반환합니다."""
    connection = connect_database(database_url)

    try:
        cursor = connection.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        connection.commit()
    except:
        connection.rollback()
        raise
    finally:
        connection.close()

    return cursor.rowcount == 1
