"""학습 정보 조회 HTTP API를 검증합니다."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from app import main
from app.database import add_study_record, save_learning_profile, save_review_word
from fastapi.testclient import TestClient


@pytest.fixture
def configured_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, str]]:
    """각 테스트가 별도의 SQLite DB를 사용하도록 API 클라이언트를 만듭니다."""
    database_url = f"sqlite:///{tmp_path / 'data' / 'learning.db'}"
    instructions_path = tmp_path / "instructions"
    instructions_path.mkdir()
    (instructions_path / "AGENT.md").write_text("테스트용 튜터 지침", encoding="utf-8")
    (instructions_path / "영어_가이드라인.md").write_text(
        "테스트용 학습 가이드라인", encoding="utf-8"
    )

    monkeypatch.setattr(main.settings, "database_url", database_url)
    monkeypatch.setattr(main.settings, "instructions_path", instructions_path)

    with TestClient(main.app) as client:
        yield client, database_url


def test_learning_endpoints_return_seeded_learning_data(
    configured_client: tuple[TestClient, str],
) -> None:
    """저장한 학습 자료가 각 조회 API에서 전체 필드로 반환됩니다."""
    client, database_url = configured_client
    saved_at = datetime(2026, 9, 14, 1, 30, tzinfo=UTC)

    profile = save_learning_profile(
        database_url,
        learner_name="민수",
        target_language="영어",
        learning_goals="여행 회화",
        session_started_on=date(2026, 9, 1),
        current_level="A2",
        level_updated_on=date(2026, 9, 10),
        level_note="현재완료를 연습합니다.",
        strengths="기본 어휘",
        weaknesses="자유 작문",
        updated_at=saved_at,
    )
    older_record = add_study_record(
        database_url,
        study_date=date(2026, 9, 12),
        topic="현재완료",
        new_words="already",
        expression="I have finished.",
        notes="문장을 완성했습니다.",
        created_at=saved_at,
    )
    newer_record = add_study_record(
        database_url,
        study_date=date(2026, 9, 13),
        topic="여행 회화",
        new_words="reservation",
        expression="I have a reservation.",
        notes="호텔 표현을 연습했습니다.",
        created_at=saved_at,
    )
    review_word = save_review_word(
        database_url,
        term="reservation",
        explanation="예약",
        last_wrong_on=date(2026, 9, 13),
        correct_streak=2,
        updated_at=saved_at,
    )

    profile_response = client.get("/learning/profile")
    records_response = client.get("/learning/study-records")
    words_response = client.get("/learning/review-words")

    assert profile_response.status_code == 200
    assert profile_response.json() == {
        "learner_name": profile.learner_name,
        "target_language": profile.target_language,
        "learning_goals": profile.learning_goals,
        "session_started_on": "2026-09-01",
        "current_level": profile.current_level,
        "level_updated_on": "2026-09-10",
        "level_note": profile.level_note,
        "strengths": profile.strengths,
        "weaknesses": profile.weaknesses,
        "updated_at": "2026-09-14T01:30:00Z",
    }
    assert records_response.status_code == 200
    assert records_response.json() == [
        {
            "id": newer_record.id,
            "chat_id": None,
            "study_date": "2026-09-13",
            "topic": newer_record.topic,
            "new_words": newer_record.new_words,
            "expression": newer_record.expression,
            "notes": newer_record.notes,
            "created_at": "2026-09-14T01:30:00Z",
        },
        {
            "id": older_record.id,
            "chat_id": None,
            "study_date": "2026-09-12",
            "topic": older_record.topic,
            "new_words": older_record.new_words,
            "expression": older_record.expression,
            "notes": older_record.notes,
            "created_at": "2026-09-14T01:30:00Z",
        },
    ]
    assert words_response.status_code == 200
    assert words_response.json() == [
        {
            "id": review_word.id,
            "term": review_word.term,
            "explanation": review_word.explanation,
            "last_wrong_on": "2026-09-13",
            "correct_streak": review_word.correct_streak,
            "created_at": "2026-09-14T01:30:00Z",
            "updated_at": "2026-09-14T01:30:00Z",
        }
    ]


def test_read_learning_profile_returns_null_when_not_created(
    configured_client: tuple[TestClient, str],
) -> None:
    """학습 프로필이 없으면 200 상태와 JSON null을 반환합니다."""
    client, _ = configured_client

    response = client.get("/learning/profile")

    assert response.status_code == 200
    assert response.json() is None
