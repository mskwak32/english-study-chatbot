"""복습할 영어 단어와 표현의 상태를 저장하고 조회합니다."""

from dataclasses import dataclass
from datetime import date, datetime

from app.study_time import to_utc

from .connection import connect_database


@dataclass(frozen=True)
class ReviewWord:
    """DB에 저장된 복습 단어 또는 표현을 나타냅니다."""

    id: int
    term: str
    explanation: str
    last_wrong_on: date
    correct_streak: int
    created_at: datetime
    updated_at: datetime


class ReviewWordError(ValueError):
    """복습 단어 데이터가 올바르지 않을 때 발생합니다."""


def _review_word_from_row(
    row: tuple[int, str, str, str, int, str, str],
) -> ReviewWord:
    """SQLite 조회 행을 ReviewWord로 변환합니다."""
    return ReviewWord(
        id=row[0],
        term=row[1],
        explanation=row[2],
        last_wrong_on=date.fromisoformat(row[3]),
        correct_streak=row[4],
        created_at=datetime.fromisoformat(row[5]),
        updated_at=datetime.fromisoformat(row[6]),
    )


def save_review_word(
    database_url: str,
    *,
    term: str,
    explanation: str,
    last_wrong_on: date,
    correct_streak: int,
    updated_at: datetime,
) -> ReviewWord:
    """복습 단어를 추가하고, 같은 단어가 있으면 현재 상태로 갱신합니다."""
    normalized_term = term.strip()
    if not normalized_term:
        raise ReviewWordError("복습 단어 또는 표현은 비어 있을 수 없습니다.")
    if not explanation.strip():
        raise ReviewWordError("복습 단어 설명은 비어 있을 수 없습니다.")
    if correct_streak < 0:
        raise ReviewWordError("연속 정답 횟수는 0 이상이어야 합니다.")

    updated_at_utc = to_utc(updated_at)
    connection = connect_database(database_url)

    try:
        connection.execute(
            """
            INSERT INTO review_words (
                term,
                explanation,
                last_wrong_on,
                correct_streak,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (term) DO UPDATE SET
                explanation = excluded.explanation,
                last_wrong_on = excluded.last_wrong_on,
                correct_streak = excluded.correct_streak,
                updated_at = excluded.updated_at
            """,
            (
                normalized_term,
                explanation.strip(),
                last_wrong_on.isoformat(),
                correct_streak,
                updated_at_utc.isoformat(),
                updated_at_utc.isoformat(),
            ),
        )
        row = connection.execute(
            """
            SELECT
                id,
                term,
                explanation,
                last_wrong_on,
                correct_streak,
                created_at,
                updated_at
            FROM review_words
            WHERE term = ? COLLATE NOCASE
            """,
            (normalized_term,),
        ).fetchone()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    if row is None:
        raise ReviewWordError("저장한 복습 단어를 찾을 수 없습니다.")

    return _review_word_from_row(row)


def list_review_words(database_url: str) -> list[ReviewWord]:
    """복습 단어를 최근 오답 날짜와 저장 순서로 반환합니다."""
    connection = connect_database(database_url)

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                term,
                explanation,
                last_wrong_on,
                correct_streak,
                created_at,
                updated_at
            FROM review_words
            ORDER BY last_wrong_on DESC, id ASC
            """
        ).fetchall()
    finally:
        connection.close()

    return [_review_word_from_row(row) for row in rows]


def delete_review_word(database_url: str, review_word_id: int) -> bool:
    """ID로 복습 단어를 삭제하고 실제 삭제 여부를 반환합니다."""
    connection = connect_database(database_url)

    try:
        cursor = connection.execute(
            "DELETE FROM review_words WHERE id = ?",
            (review_word_id,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return cursor.rowcount == 1
