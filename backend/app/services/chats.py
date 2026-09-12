"""현재 시각과 채팅 저장소를 조합한 학습 채팅 작업을 처리합니다."""

from datetime import UTC, date, datetime

from app.database import Chat, create_additional_chat, get_or_create_default_chat
from app.study_time import study_date_for, to_utc


def _current_study_time(
        timezone_name: str,
        now: datetime | None
) -> tuple[datetime, date]:
    """현재 시각을 UTC 생성 시각과 사용자 기준 학습일로 변환합니다."""
    current_time = now if now is not None else datetime.now(UTC)
    created_at = to_utc(current_time)
    study_date = study_date_for(created_at, timezone_name)

    return created_at, study_date

def get_or_create_today_chat(
    database_url: str, timezone_name: str, now: datetime | None = None
) -> Chat:
    """사용자 타임존 기준 오늘의 기본 학습 채팅을 조회하거나 생성합니다."""
    created_at, study_date = _current_study_time(timezone_name, now)

    return get_or_create_default_chat(database_url, study_date, created_at)

def create_today_additional_chat(
        database_url: str,
        timezone_name: str,
        now: datetime | None = None
) -> Chat:
    """사용자 타임존 기준 오늘의 추가 학습 채팅을 생성합니다."""
    created_at, study_date = _current_study_time(timezone_name, now)

    return create_additional_chat(database_url, study_date, created_at)
