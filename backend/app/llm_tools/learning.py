"""검증된 학습 데이터 도구 호출을 SQLite 저장 함수와 연결합니다."""

from dataclasses import dataclass
from datetime import date, datetime

from app.agent.protocol import SaveReviewWordToolCall
from app.database import save_review_word


@dataclass(frozen=True)
class ToolResult:
    """도구 호출 실행 결과를 LLM에 전달하기 위한 객체입니다."""

    name: str
    content: dict[str, object]


def execute_save_review_word(
    database_url: str,
    *,
    tool_call: SaveReviewWordToolCall,
    study_date: date,
    current_time: datetime,
) -> ToolResult:
    """검증된 save_review_word 도구 호출을 실행합니다."""
    review_word = save_review_word(
        database_url,
        term=tool_call.arguments.term,
        explanation=tool_call.arguments.explanation,
        # 날짜와 시각은 LLM이 아니라 애플리케이션이 결정합니다.
        last_wrong_on=study_date,
        correct_streak=0,
        updated_at=current_time,
    )

    return ToolResult(
        name=tool_call.action,
        content={
            "saved": True,
            "review_word_id": review_word.id,
            "term": review_word.term,
        },
    )
