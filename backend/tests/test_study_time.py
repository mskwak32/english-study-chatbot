from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.study_time import (
    StudyTimeError,
    study_date_for,
    to_utc,
)


def test_to_utc_converts_an_aware_datetime() -> None:
    seoul_time = datetime(2026, 9, 8, 0, 30, tzinfo=ZoneInfo("Asia/Seoul"))

    result = to_utc(seoul_time)

    assert result == datetime(2026, 9, 7, 15, 30, tzinfo=UTC)


def test_to_utc_rejects_a_naive_datetime() -> None:
    # 타임존이 없는 datetime을 거부하는지 확인하기 위해 의도적으로 생성
    naive_datetime = datetime(2026, 9, 8, 0, 30)  # noqa: DTZ001

    with pytest.raises(StudyTimeError, match="타임존 정보"):
        to_utc(naive_datetime)


def test_study_date_for_uses_korean_date_boundary() -> None:
    before_midnight_utc = datetime(2026, 9, 7, 14, 59, tzinfo=UTC)
    after_midnight_utc = datetime(2026, 9, 7, 15, 0, tzinfo=UTC)

    before_date = study_date_for(before_midnight_utc, "Asia/Seoul")
    after_date = study_date_for(after_midnight_utc, "Asia/Seoul")

    assert before_date == date(2026, 9, 7)
    assert after_date == date(2026, 9, 8)
