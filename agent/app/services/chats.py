"""현재 시각과 채팅 저장소를 조합한 학습 채팅 작업을 처리합니다."""

from datetime import UTC, datetime

from app.database import Chat, get_or_create_default_chat
from app.study_time import study_date_for, to_utc


def get_or_create_today_chat(
    database_url: str, timezone_name: str, now: datetime | None = None
) -> Chat:
    """사용자 타임존 기준 오늘의 기본 학습 채팅을 조회하거나 생성합니다."""
    # 기본값을 함수 정의 시점에 만들지 않고, 호출 시점의 현재 UTC를 사용
    current_time = now if now is not None else datetime.now(UTC)

    created_at = to_utc(current_time)

    # 날짜별 학습 정책에는 사용자 타임존 기준 날짜를 사용
    study_date = study_date_for(created_at, timezone_name)

    return get_or_create_default_chat(database_url, study_date, created_at)
