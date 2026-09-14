from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from app.agent.protocol import (
    CompleteInitialAssessmentToolCall,
    SaveReviewWordToolCall,
    parse_agent_response,
)
from app.database import (
    LearningProfileError,
    get_learning_profile,
    initialize_database,
    list_proficiency_tests,
    list_review_words,
)
from app.llm_tools import (
    execute_complete_initial_assessment,
    execute_save_review_word,
)


def _database_url(tmp_path: Path) -> str:
    """각 테스트가 독립적으로 사용할 SQLite URL을 만듭니다."""
    return f"sqlite:///{tmp_path / 'data' / 'chat.db'}"


def test_execute_save_review_word_uses_server_values(
    tmp_path: Path,
) -> None:
    """도구 인자와 서버가 관리하는 값으로 복습 단어를 저장합니다."""
    database_url = _database_url(tmp_path)
    initialize_database(database_url)

    response = parse_agent_response(
        {
            "action": "save_review_word",
            "arguments": {
                "term": "hesitate",
                "explanation": "망설이다",
            },
        }
    )
    assert isinstance(response, SaveReviewWordToolCall)

    current_time = datetime(2026, 9, 10, 1, 30, tzinfo=UTC)

    result = execute_save_review_word(
        database_url,
        tool_call=response,
        study_date=date(2026, 9, 10),
        current_time=current_time,
    )

    assert result.name == "save_review_word"
    assert result.content == {
        "saved": True,
        "review_word_id": 1,
        "term": "hesitate",
    }

    review_words = list_review_words(database_url)

    assert len(review_words) == 1
    assert review_words[0].term == "hesitate"
    assert review_words[0].explanation == "망설이다"
    assert review_words[0].last_wrong_on == date(2026, 9, 10)
    assert review_words[0].correct_streak == 0
    assert review_words[0].updated_at == current_time


def test_complete_initial_assessment_saves_validated_profile_and_result(
    tmp_path: Path,
) -> None:
    """초기 테스트 도구는 서버 점수 기준으로 프로필과 결과를 함께 저장합니다."""
    database_url = _database_url(tmp_path)
    initialize_database(database_url)
    response = parse_agent_response(
        {
            "action": "complete_initial_assessment",
            "arguments": {
                "final_level": "A2",
                "score_earned": 9,
                "vocabulary_result": "어휘 5문제 중 3문제 정답",
                "grammar_result": "문법 5문제 중 3문제 정답",
                "reading_result": "독해 3문제 중 2문제 정답",
                "self_expression_result": "자기표현 문제를 완성했습니다.",
                "strengths": "기본 어휘를 이해합니다.",
                "weaknesses": "시제 사용을 연습해야 합니다.",
                "level_note": "초기 실력 테스트 9/14점",
            },
        }
    )
    assert isinstance(response, CompleteInitialAssessmentToolCall)
    current_time = datetime(2026, 9, 10, 1, 30, tzinfo=UTC)

    result = execute_complete_initial_assessment(
        database_url,
        tool_call=response,
        study_date=date(2026, 9, 10),
        current_time=current_time,
    )

    assert result.content == {
        "saved": True,
        "current_level": "A2",
        "proficiency_test_id": 1,
    }
    profile = get_learning_profile(database_url)
    assert profile is not None
    assert profile.current_level == "A2"
    assert profile.strengths == "기본 어휘를 이해합니다."
    assert profile.weaknesses == "시제 사용을 연습해야 합니다."
    tests = list_proficiency_tests(database_url)
    assert [
        (test.score_earned, test.score_total, test.final_level) for test in tests
    ] == [(9, 14, "A2")]


def test_complete_initial_assessment_rejects_a_level_that_does_not_match_score(
    tmp_path: Path,
) -> None:
    """모델이 점수와 다른 레벨을 요청하면 프로필을 저장하지 않습니다."""
    database_url = _database_url(tmp_path)
    initialize_database(database_url)
    response = parse_agent_response(
        {
            "action": "complete_initial_assessment",
            "arguments": {
                "final_level": "A1",
                "score_earned": 9,
                "vocabulary_result": "어휘 결과",
                "grammar_result": "문법 결과",
                "reading_result": "독해 결과",
                "self_expression_result": "자기표현 결과",
                "strengths": "강점",
                "weaknesses": "보완점",
                "level_note": "메모",
            },
        }
    )
    assert isinstance(response, CompleteInitialAssessmentToolCall)

    with pytest.raises(LearningProfileError, match="점수 기준과 일치하지 않습니다"):
        execute_complete_initial_assessment(
            database_url,
            tool_call=response,
            study_date=date(2026, 9, 10),
            current_time=datetime(2026, 9, 10, tzinfo=UTC),
        )

    assert get_learning_profile(database_url) is None
