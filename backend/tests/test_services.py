from datetime import UTC, date, datetime
from pathlib import Path

from app.database import initialize_database, list_chats
from app.services.chats import get_or_create_today_chat


def test_get_or_create_today_chat_reuses_default_chat_for_same_study_date(
    tmp_path: Path,
) -> None:
    """같은 학습일에 요청한 기본 채팅은 하나만 생성합니다."""
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"

    initialize_database(database_url)

    first_chat = get_or_create_today_chat(
        database_url,
        "Asia/Seoul",
        now=datetime(2026, 9, 8, 1, 0, tzinfo=UTC),
    )
    second_chat = get_or_create_today_chat(
        database_url,
        "Asia/Seoul",
        now=datetime(2026, 9, 8, 2, 0, tzinfo=UTC),
    )

    assert first_chat == second_chat
    assert first_chat.study_date == date(2026, 9, 8)
    assert list_chats(database_url) == [first_chat]
