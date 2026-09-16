"""단일 사용자의 학습 프로필, 실력 테스트, 레벨 변경을 저장합니다."""

from dataclasses import dataclass
from datetime import date, datetime

from app.study_time import to_utc

from .connection import connect_database

CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}


@dataclass(frozen=True)
class LearningProfile:
    """DB에 저장된 현재 학습 프로필을 표현합니다."""

    learner_name: str
    target_language: str
    learning_goals: str
    session_started_on: date | None
    current_level: str | None
    level_updated_on: date | None
    level_note: str
    strengths: str
    weaknesses: str
    updated_at: datetime


@dataclass(frozen=True)
class ProficiencyTest:
    """DB에 저장된 실력 테스트 결과를 표현합니다."""

    id: int
    tested_on: date
    final_level: str
    score_earned: int
    score_total: int
    vocabulary_result: str
    grammar_result: str
    reading_result: str
    self_expression_result: str
    created_at: datetime


@dataclass(frozen=True)
class LevelChange:
    """DB에 저장된 레벨 변경 이력을 표현합니다."""

    id: int
    changed_on: date
    previous_level: str | None
    new_level: str
    reason: str
    created_at: datetime


class LearningProfileError(ValueError):
    """학습 프로필 데이터가 올바르지 않을 때 발생합니다."""


def _validate_level(level: str | None, field_name: str) -> None:
    """CEFR 레벨이 비어 있거나 지원하는 값인지 검사합니다."""
    if level is not None and level not in CEFR_LEVELS:
        raise LearningProfileError(
            f"{field_name}은 A1, A2, B1, B2, C1, C2 중 하나여야 합니다."
        )


def _optional_date(value: str | None) -> date | None:
    """SQLite의 선택적 날짜 문자열을 date로 변환합니다."""
    return date.fromisoformat(value) if value is not None else None


def _profile_from_row(
    row: tuple[str, str, str, str | None, str | None, str | None, str, str, str, str],
) -> LearningProfile:
    """SQLite 조회 행을 LearningProfile로 변환합니다."""
    return LearningProfile(
        learner_name=row[0],
        target_language=row[1],
        learning_goals=row[2],
        session_started_on=_optional_date(row[3]),
        current_level=row[4],
        level_updated_on=_optional_date(row[5]),
        level_note=row[6],
        strengths=row[7],
        weaknesses=row[8],
        updated_at=datetime.fromisoformat(row[9]),
    )


def get_learning_profile(database_url: str) -> LearningProfile | None:
    """현재 학습 프로필을 반환하고, 아직 없으면 None을 반환합니다."""
    connection = connect_database(database_url)

    try:
        row = connection.execute(
            """
            SELECT
                learner_name,
                target_language,
                learning_goals,
                session_started_on,
                current_level,
                level_updated_on,
                level_note,
                strengths,
                weaknesses,
                updated_at
            FROM learning_profiles
            WHERE id = 1
            """
        ).fetchone()
    finally:
        connection.close()

    return _profile_from_row(row) if row is not None else None


def save_learning_profile(
    database_url: str,
    *,
    learner_name: str = "",
    target_language: str = "영어",
    learning_goals: str = "",
    session_started_on: date | None = None,
    current_level: str | None = None,
    level_updated_on: date | None = None,
    level_note: str = "",
    strengths: str = "",
    weaknesses: str = "",
    updated_at: datetime,
) -> LearningProfile:
    """단일 사용자의 현재 학습 프로필을 생성하거나 교체합니다."""
    if not target_language.strip():
        raise LearningProfileError("목표 언어는 비어 있을 수 없습니다.")

    _validate_level(current_level, "현재 레벨")
    updated_at_utc = to_utc(updated_at)
    connection = connect_database(database_url)

    try:
        connection.execute(
            """
            INSERT INTO learning_profiles (
                id,
                learner_name,
                target_language,
                learning_goals,
                session_started_on,
                current_level,
                level_updated_on,
                level_note,
                strengths,
                weaknesses,
                updated_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                learner_name = excluded.learner_name,
                target_language = excluded.target_language,
                learning_goals = excluded.learning_goals,
                session_started_on = excluded.session_started_on,
                current_level = excluded.current_level,
                level_updated_on = excluded.level_updated_on,
                level_note = excluded.level_note,
                strengths = excluded.strengths,
                weaknesses = excluded.weaknesses,
                updated_at = excluded.updated_at
            """,
            (
                learner_name.strip(),
                target_language.strip(),
                learning_goals.strip(),
                session_started_on.isoformat() if session_started_on else None,
                current_level,
                level_updated_on.isoformat() if level_updated_on else None,
                level_note.strip(),
                strengths.strip(),
                weaknesses.strip(),
                updated_at_utc.isoformat(),
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    profile = get_learning_profile(database_url)
    if profile is None:
        raise LearningProfileError("저장한 학습 프로필을 찾을 수 없습니다.")

    return profile


def add_proficiency_test(
    database_url: str,
    *,
    tested_on: date,
    final_level: str,
    score_earned: int,
    score_total: int,
    vocabulary_result: str = "",
    grammar_result: str = "",
    reading_result: str = "",
    self_expression_result: str = "",
    created_at: datetime,
) -> ProficiencyTest:
    """현재 프로필에 실력 테스트 결과를 추가합니다."""
    _validate_level(final_level, "최종 레벨")
    if score_total <= 0 or score_earned < 0 or score_earned > score_total:
        raise LearningProfileError("실력 테스트 점수 범위가 올바르지 않습니다.")

    created_at_utc = to_utc(created_at)
    connection = connect_database(database_url)

    try:
        cursor = connection.execute(
            """
            INSERT INTO proficiency_tests (
                profile_id,
                tested_on,
                final_level,
                score_earned,
                score_total,
                vocabulary_result,
                grammar_result,
                reading_result,
                self_expression_result,
                created_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tested_on.isoformat(),
                final_level,
                score_earned,
                score_total,
                vocabulary_result.strip(),
                grammar_result.strip(),
                reading_result.strip(),
                self_expression_result.strip(),
                created_at_utc.isoformat(),
            ),
        )
        test_id = cursor.lastrowid
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    if test_id is None:
        raise LearningProfileError("실력 테스트 ID를 만들 수 없습니다.")

    return ProficiencyTest(
        id=test_id,
        tested_on=tested_on,
        final_level=final_level,
        score_earned=score_earned,
        score_total=score_total,
        vocabulary_result=vocabulary_result.strip(),
        grammar_result=grammar_result.strip(),
        reading_result=reading_result.strip(),
        self_expression_result=self_expression_result.strip(),
        created_at=created_at_utc,
    )


def list_proficiency_tests(database_url: str) -> list[ProficiencyTest]:
    """실력 테스트 결과를 오래된 순서대로 반환합니다."""
    connection = connect_database(database_url)

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                tested_on,
                final_level,
                score_earned,
                score_total,
                vocabulary_result,
                grammar_result,
                reading_result,
                self_expression_result,
                created_at
            FROM proficiency_tests
            ORDER BY tested_on ASC, id ASC
            """
        ).fetchall()
    finally:
        connection.close()

    return [
        ProficiencyTest(
            id=row[0],
            tested_on=date.fromisoformat(row[1]),
            final_level=row[2],
            score_earned=row[3],
            score_total=row[4],
            vocabulary_result=row[5],
            grammar_result=row[6],
            reading_result=row[7],
            self_expression_result=row[8],
            created_at=datetime.fromisoformat(row[9]),
        )
        for row in rows
    ]


def add_level_change(
    database_url: str,
    *,
    changed_on: date,
    previous_level: str | None,
    new_level: str,
    reason: str,
    created_at: datetime,
) -> LevelChange:
    """현재 프로필에 레벨 변경 이력을 추가합니다."""
    _validate_level(previous_level, "이전 레벨")
    _validate_level(new_level, "새 레벨")
    if not reason.strip():
        raise LearningProfileError("레벨 변경 근거는 비어 있을 수 없습니다.")

    created_at_utc = to_utc(created_at)
    connection = connect_database(database_url)

    try:
        cursor = connection.execute(
            """
            INSERT INTO level_changes (
                profile_id,
                changed_on,
                previous_level,
                new_level,
                reason,
                created_at
            ) VALUES (1, ?, ?, ?, ?, ?)
            """,
            (
                changed_on.isoformat(),
                previous_level,
                new_level,
                reason.strip(),
                created_at_utc.isoformat(),
            ),
        )
        change_id = cursor.lastrowid
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    if change_id is None:
        raise LearningProfileError("레벨 변경 이력 ID를 만들 수 없습니다.")

    return LevelChange(
        id=change_id,
        changed_on=changed_on,
        previous_level=previous_level,
        new_level=new_level,
        reason=reason.strip(),
        created_at=created_at_utc,
    )


def change_learning_level(
    database_url: str,
    *,
    changed_on: date,
    new_level: str,
    reason: str,
    updated_at: datetime,
) -> LevelChange:
    """기존 프로필의 레벨을 바꾸고 변경 이력을 하나의 작업으로 저장합니다."""
    _validate_level(new_level, "새 레벨")
    if not reason.strip():
        raise LearningProfileError("레벨 변경 근거는 비어 있을 수 없습니다.")

    updated_at_utc = to_utc(updated_at)
    connection = connect_database(database_url)

    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT current_level FROM learning_profiles WHERE id = 1"
        ).fetchone()
        if row is None:
            raise LearningProfileError("레벨을 변경할 학습 프로필이 없습니다.")

        previous_level = row[0]
        if previous_level == new_level:
            raise LearningProfileError("현재 레벨과 같은 레벨로 변경할 수 없습니다.")

        connection.execute(
            """
            UPDATE learning_profiles
            SET
                current_level = ?,
                level_updated_on = ?,
                level_note = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                new_level,
                changed_on.isoformat(),
                reason.strip(),
                updated_at_utc.isoformat(),
            ),
        )
        cursor = connection.execute(
            """
            INSERT INTO level_changes (
                profile_id,
                changed_on,
                previous_level,
                new_level,
                reason,
                created_at
            ) VALUES (1, ?, ?, ?, ?, ?)
            """,
            (
                changed_on.isoformat(),
                previous_level,
                new_level,
                reason.strip(),
                updated_at_utc.isoformat(),
            ),
        )
        change_id = cursor.lastrowid
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    if change_id is None:
        raise LearningProfileError("레벨 변경 이력 ID를 만들 수 없습니다.")

    return LevelChange(
        id=change_id,
        changed_on=changed_on,
        previous_level=previous_level,
        new_level=new_level,
        reason=reason.strip(),
        created_at=updated_at_utc,
    )


def list_level_changes(database_url: str) -> list[LevelChange]:
    """레벨 변경 이력을 오래된 순서대로 반환합니다."""
    connection = connect_database(database_url)

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                changed_on,
                previous_level,
                new_level,
                reason,
                created_at
            FROM level_changes
            ORDER BY changed_on ASC, id ASC
            """
        ).fetchall()
    finally:
        connection.close()

    return [
        LevelChange(
            id=row[0],
            changed_on=date.fromisoformat(row[1]),
            previous_level=row[2],
            new_level=row[3],
            reason=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )
        for row in rows
    ]
