"""완료한 영어 학습 세션의 요약 기록을 저장하고 조회합니다."""

from dataclasses import dataclass
from datetime import date, datetime

from app.study_time import to_utc

from .connection import connect_database


@dataclass(frozen=True)
class StudyRecord:
    """DB에 저장된 학습 세션 요약을 표현합니다."""

    id: int
    chat_id: int | None
    study_date: date
    topic: str
    new_words: str
    expression: str
    notes: str
    created_at: datetime


class StudyRecordError(ValueError):
    """학습 이력 데이터가 올바르지 않을 때 발생합니다."""


def _study_record_from_row(
    row: tuple[int, int | None, str, str, str, str, str, str],
) -> StudyRecord:
    """SQLite 조회 행을 StudyRecord로 변환합니다."""
    return StudyRecord(
        id=row[0],
        chat_id=row[1],
        study_date=date.fromisoformat(row[2]),
        topic=row[3],
        new_words=row[4],
        expression=row[5],
        notes=row[6],
        created_at=datetime.fromisoformat(row[7]),
    )


def add_study_record(
    database_url: str,
    *,
    study_date: date,
    topic: str,
    created_at: datetime,
    chat_id: int | None = None,
    new_words: str = "",
    expression: str = "",
    notes: str = "",
) -> StudyRecord:
    """완료한 학습 세션의 요약 기록을 추가합니다."""
    if not topic.strip():
        raise StudyRecordError("학습 주제는 비어 있을 수 없습니다.")

    created_at_utc = to_utc(created_at)
    connection = connect_database(database_url)

    try:
        cursor = connection.execute(
            """
            INSERT INTO study_records (
                chat_id,
                study_date,
                topic,
                new_words,
                expression,
                notes,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                study_date.isoformat(),
                topic.strip(),
                new_words.strip(),
                expression.strip(),
                notes.strip(),
                created_at_utc.isoformat(),
            ),
        )
        record_id = cursor.lastrowid
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    if record_id is None:
        raise StudyRecordError("학습 이력 ID를 만들 수 없습니다.")

    return StudyRecord(
        id=record_id,
        chat_id=chat_id,
        study_date=study_date,
        topic=topic.strip(),
        new_words=new_words.strip(),
        expression=expression.strip(),
        notes=notes.strip(),
        created_at=created_at_utc,
    )


def upsert_study_record(
    database_url: str,
    *,
    chat_id: int,
    study_date: date,
    topic: str,
    created_at: datetime,
    new_words: str = "",
    expression: str = "",
    notes: str = "",
) -> StudyRecord:
    """채팅별 학습 요약을 생성하거나 최신 요약으로 갱신합니다."""
    if chat_id <= 0:
        raise StudyRecordError("채팅 ID는 1 이상이어야 합니다.")
    if not topic.strip():
        raise StudyRecordError("학습 주제는 비어 있을 수 없습니다.")

    created_at_utc = to_utc(created_at)
    connection = connect_database(database_url)

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO study_records (
                chat_id,
                study_date,
                topic,
                new_words,
                expression,
                notes,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (chat_id) DO UPDATE SET
                study_date = excluded.study_date,
                topic = excluded.topic,
                new_words = excluded.new_words,
                expression = excluded.expression,
                notes = excluded.notes,
                created_at = excluded.created_at
            """,
            (
                chat_id,
                study_date.isoformat(),
                topic.strip(),
                new_words.strip(),
                expression.strip(),
                notes.strip(),
                created_at_utc.isoformat(),
            ),
        )
        row = connection.execute(
            """
            SELECT
                id,
                chat_id,
                study_date,
                topic,
                new_words,
                expression,
                notes,
                created_at
            FROM study_records
            WHERE chat_id = ?
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
        raise StudyRecordError("저장한 학습 이력을 찾을 수 없습니다.")

    return _study_record_from_row(row)


def list_recent_study_records(
    database_url: str,
    limit: int = 5,
) -> list[StudyRecord]:
    """최근 학습 이력을 최대 limit개까지 오래된 순서로 반환합니다."""
    if limit <= 0:
        raise StudyRecordError("최근 학습 이력 개수는 1 이상이어야 합니다.")

    connection = connect_database(database_url)

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                chat_id,
                study_date,
                topic,
                new_words,
                expression,
                notes,
                created_at
            FROM (
                SELECT
                    id,
                    chat_id,
                    study_date,
                    topic,
                    new_words,
                    expression,
                    notes,
                    created_at
                FROM study_records
                ORDER BY study_date DESC, id DESC
                LIMIT ?
            )
            ORDER BY study_date ASC, id ASC
            """,
            (limit,),
        ).fetchall()
    finally:
        connection.close()

    return [_study_record_from_row(row) for row in rows]
