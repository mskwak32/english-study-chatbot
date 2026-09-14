"""초기 실력 테스트의 진행 상태와 완료 가능 조건을 SQLite에 저장합니다."""

from datetime import datetime

from app.study_time import to_utc

from .connection import connect_database

INITIAL_ASSESSMENT_ANSWER_COUNT = 14


class InitialAssessmentError(ValueError):
    """초기 실력 테스트 세션을 시작하거나 완료할 수 없을 때 발생합니다."""


def start_initial_assessment(
    database_url: str, chat_id: int, started_at: datetime
) -> None:
    """채팅을 초기 실력 테스트 세션으로 등록합니다.

    같은 채팅에서 다시 시작을 요청해도 기존 세션과 답변 수는 유지합니다.
    """
    connection = connect_database(database_url)

    try:
        connection.execute("BEGIN IMMEDIATE")
        chat_exists = connection.execute(
            "SELECT 1 FROM chats WHERE id = ?", (chat_id,)
        ).fetchone()
        if chat_exists is None:
            raise InitialAssessmentError(
                "초기 실력 테스트를 시작할 채팅을 찾을 수 없습니다."
            )

        connection.execute(
            """
            INSERT INTO initial_assessment_sessions (chat_id, started_at)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO NOTHING
            """,
            (chat_id, to_utc(started_at).isoformat()),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def is_initial_assessment_active(database_url: str, chat_id: int) -> bool:
    """채팅이 아직 완료되지 않은 초기 실력 테스트 세션인지 확인합니다."""
    connection = connect_database(database_url)

    try:
        row = connection.execute(
            """
            SELECT 1
            FROM initial_assessment_sessions
            WHERE chat_id = ? AND completed_at IS NULL
            """,
            (chat_id,),
        ).fetchone()
    finally:
        connection.close()

    return row is not None


def can_complete_initial_assessment(database_url: str, chat_id: int) -> bool:
    """활성 테스트 세션에 사용자 답변 14개가 쌓였는지 확인합니다."""
    if not is_initial_assessment_active(database_url, chat_id):
        return False

    connection = connect_database(database_url)

    try:
        answer_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM messages
            WHERE chat_id = ? AND role = 'user'
            """,
            (chat_id,),
        ).fetchone()[0]
    finally:
        connection.close()

    return answer_count >= INITIAL_ASSESSMENT_ANSWER_COUNT


def require_initial_assessment_completion(
    database_url: str, chat_id: int | None
) -> None:
    """초기 테스트 완료 저장 전에 세션과 답변 수를 다시 검증합니다."""
    if chat_id is None or not is_initial_assessment_active(database_url, chat_id):
        raise InitialAssessmentError(
            "초기 실력 테스트 세션에서만 학습 프로필을 만들 수 있습니다."
        )
    if not can_complete_initial_assessment(database_url, chat_id):
        raise InitialAssessmentError(
            f"초기 실력 테스트는 사용자 답변 {INITIAL_ASSESSMENT_ANSWER_COUNT}개가 필요합니다."
        )


def finish_initial_assessment(
    database_url: str, chat_id: int, completed_at: datetime
) -> None:
    """완료된 초기 실력 테스트 세션을 닫아 이후 완료 도구 호출을 막습니다."""
    connection = connect_database(database_url)

    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            UPDATE initial_assessment_sessions
            SET completed_at = ?
            WHERE chat_id = ? AND completed_at IS NULL
            """,
            (to_utc(completed_at).isoformat(), chat_id),
        )
        if cursor.rowcount != 1:
            raise InitialAssessmentError(
                "완료할 초기 실력 테스트 세션을 찾을 수 없습니다."
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
