"""현재 시각과 채팅 저장소를 조합한 학습 채팅 작업을 처리합니다."""

from datetime import UTC, date, datetime

from app.database import (
    Chat,
    create_additional_chat,
    get_default_chat,
    get_or_create_default_chat,
)
from app.study_time import study_date_for, to_utc


def _current_study_time(now: datetime | None) -> datetime:
    """현재 시각을 채팅 생성 시각에 쓸 UTC 시각으로 변환합니다."""
    current_time = now if now is not None else datetime.now(UTC)

    return to_utc(current_time)


def _today_study_date(timezone_name: str, current_time: datetime) -> date:
    """UTC 현재 시각에서 사용자 타임존 기준 오늘의 학습일을 구합니다."""
    return study_date_for(current_time, timezone_name)


def get_today_chat(
    database_url: str, timezone_name: str, now: datetime | None = None
) -> Chat | None:
    """사용자 타임존 기준 오늘의 기본 학습 채팅을 생성하지 않고 조회합니다."""
    current_time = _current_study_time(now)
    study_date = _today_study_date(timezone_name, current_time)

    return get_default_chat(database_url, study_date)


def get_or_create_today_chat(
    database_url: str, timezone_name: str, now: datetime | None = None
) -> Chat:
    """사용자 타임존 기준 오늘의 기본 학습 채팅을 조회하거나 생성합니다."""
    created_at = _current_study_time(now)
    study_date = _today_study_date(timezone_name, created_at)

    return get_or_create_default_chat(database_url, study_date, created_at)


def create_today_additional_chat(
    database_url: str,
    timezone_name: str,
    now: datetime | None = None,
) -> Chat:
    """사용자 타임존 기준 오늘의 추가 학습 채팅을 생성합니다."""
    created_at = _current_study_time(now)
    study_date = _today_study_date(timezone_name, created_at)

    return create_additional_chat(database_url, study_date, created_at)
