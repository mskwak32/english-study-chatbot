from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from app.database import (
    LearningProfileError,
    ReviewWordError,
    StudyRecordError,
    add_level_change,
    add_proficiency_test,
    add_study_record,
    delete_chat,
    delete_review_word,
    get_learning_profile,
    get_or_create_default_chat,
    initialize_database,
    list_level_changes,
    list_proficiency_tests,
    list_recent_study_records,
    list_review_words,
    save_learning_profile,
    save_review_word,
)


def _database_url(tmp_path: Path) -> str:
    """각 테스트가 독립적으로 사용할 SQLite URL을 만듭니다."""
    return f"sqlite:///{tmp_path / 'data' / 'chat.db'}"


def test_new_database_starts_with_empty_learning_data(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)

    initialize_database(database_url)

    assert get_learning_profile(database_url) is None
    assert list_proficiency_tests(database_url) == []
    assert list_level_changes(database_url) == []
    assert list_review_words(database_url) == []
    assert list_recent_study_records(database_url) == []


def test_learning_profile_and_assessment_history_are_saved(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path)
    initialize_database(database_url)

    profile = save_learning_profile(
        database_url,
        learner_name="새 학습자",
        target_language="영어",
        learning_goals="여행 회화",
        session_started_on=date(2026, 9, 9),
        current_level="A2",
        level_updated_on=date(2026, 9, 9),
        strengths="기본 어휘",
        weaknesses="자유 작문",
        updated_at=datetime(
            2026,
            9,
            9,
            9,
            tzinfo=ZoneInfo("Asia/Seoul"),
        ),
    )
    proficiency_test = add_proficiency_test(
        database_url,
        tested_on=date(2026, 9, 9),
        final_level="A2",
        score_earned=9,
        score_total=13,
        vocabulary_result="4/5",
        grammar_result="3/5",
        reading_result="2/3",
        self_expression_result="기본 문장 작성 가능",
        created_at=datetime(2026, 9, 9, 0, 10, tzinfo=UTC),
    )
    level_change = add_level_change(
        database_url,
        changed_on=date(2026, 9, 9),
        previous_level=None,
        new_level="A2",
        reason="초기 실력 테스트",
        created_at=datetime(2026, 9, 9, 0, 11, tzinfo=UTC),
    )

    assert profile.current_level == "A2"
    assert profile.updated_at == datetime(2026, 9, 9, 0, 0, tzinfo=UTC)
    assert get_learning_profile(database_url) == profile
    assert list_proficiency_tests(database_url) == [proficiency_test]
    assert list_level_changes(database_url) == [level_change]


def test_learning_profile_rejects_invalid_level_and_score(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path)
    initialize_database(database_url)

    with pytest.raises(LearningProfileError, match="현재 레벨"):
        save_learning_profile(
            database_url,
            current_level="초급",
            updated_at=datetime(2026, 9, 9, tzinfo=UTC),
        )

    save_learning_profile(
        database_url,
        updated_at=datetime(2026, 9, 9, tzinfo=UTC),
    )

    with pytest.raises(LearningProfileError, match="점수 범위"):
        add_proficiency_test(
            database_url,
            tested_on=date(2026, 9, 9),
            final_level="A1",
            score_earned=14,
            score_total=13,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )


def test_review_word_is_updated_case_insensitively_and_deleted(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path)
    initialize_database(database_url)

    first = save_review_word(
        database_url,
        term="recommend",
        explanation="추천하다",
        last_wrong_on=date(2026, 9, 8),
        correct_streak=0,
        updated_at=datetime(2026, 9, 8, tzinfo=UTC),
    )
    updated = save_review_word(
        database_url,
        term="Recommend",
        explanation="추천하거나 권하다",
        last_wrong_on=date(2026, 9, 9),
        correct_streak=1,
        updated_at=datetime(2026, 9, 9, tzinfo=UTC),
    )

    assert updated.id == first.id
    assert updated.explanation == "추천하거나 권하다"
    assert updated.correct_streak == 1
    assert list_review_words(database_url) == [updated]
    assert delete_review_word(database_url, updated.id) is True
    assert list_review_words(database_url) == []


def test_review_word_rejects_invalid_values(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    initialize_database(database_url)

    with pytest.raises(ReviewWordError, match="비어"):
        save_review_word(
            database_url,
            term=" ",
            explanation="설명",
            last_wrong_on=date(2026, 9, 9),
            correct_streak=0,
            updated_at=datetime(2026, 9, 9, tzinfo=UTC),
        )

    with pytest.raises(ReviewWordError, match="0 이상"):
        save_review_word(
            database_url,
            term="word",
            explanation="설명",
            last_wrong_on=date(2026, 9, 9),
            correct_streak=-1,
            updated_at=datetime(2026, 9, 9, tzinfo=UTC),
        )


def test_recent_study_records_return_latest_five_in_study_order(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path)
    initialize_database(database_url)

    records = [
        add_study_record(
            database_url,
            study_date=date(2026, 9, day),
            topic=f"주제 {day}",
            new_words=f"word-{day}",
            created_at=datetime(2026, 9, day, tzinfo=UTC),
        )
        for day in range(1, 7)
    ]

    assert list_recent_study_records(database_url) == records[1:]


def test_deleting_chat_preserves_study_record(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    initialize_database(database_url)
    chat = get_or_create_default_chat(
        database_url,
        date(2026, 9, 9),
        datetime(2026, 9, 9, tzinfo=UTC),
    )
    record = add_study_record(
        database_url,
        chat_id=chat.id,
        study_date=chat.study_date,
        topic="공항 영어",
        created_at=datetime(2026, 9, 9, 0, 30, tzinfo=UTC),
    )

    assert delete_chat(database_url, chat.id) is True

    saved_record = list_recent_study_records(database_url)[0]
    assert saved_record.id == record.id
    assert saved_record.chat_id is None


def test_study_record_rejects_empty_topic_and_invalid_limit(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path)
    initialize_database(database_url)

    with pytest.raises(StudyRecordError, match="학습 주제"):
        add_study_record(
            database_url,
            study_date=date(2026, 9, 9),
            topic=" ",
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )

    with pytest.raises(StudyRecordError, match="1 이상"):
        list_recent_study_records(database_url, limit=0)
