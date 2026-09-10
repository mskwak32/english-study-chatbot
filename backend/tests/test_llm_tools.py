from datetime import UTC, date, datetime
from pathlib import Path

from app.agent.protocol import (
    SaveReviewWordToolCall,
    parse_agent_response,
)
from app.database import (
    initialize_database,
    list_review_words,
)
from app.llm_tools import execute_save_review_word


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
