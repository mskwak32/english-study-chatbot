"""UTC 시각 변환과 학습 날짜 계산을 처리합니다."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


class StudyTimeError(ValueError):
    """학습 시간 정보가 올바르지 않을 때 발생합니다."""


def to_utc(timestamp: datetime) -> datetime:
    """타임존 정보가 있는 시각을 UTC 시각으로 변환합니다."""
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise StudyTimeError("시각에는 타임존 정보가 있어야 합니다.")

    return timestamp.astimezone(UTC)


def study_date_for(timestamp: datetime, timezone_name: str) -> date:
    """사용자 타임존을 기준으로 학습 날짜를 계산합니다."""

    # 타임존 유무 검사
    to_utc(timestamp)
    timezone = ZoneInfo(timezone_name)

    return timestamp.astimezone(timezone).date()
