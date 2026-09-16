"""검증된 학습 데이터 도구 호출을 SQLite 저장 함수와 연결합니다."""

from dataclasses import dataclass
from datetime import date, datetime

from app.agent.protocol import (
    ChangeLearningLevelToolCall,
    CompleteInitialAssessmentToolCall,
    SaveReviewWordToolCall,
    SaveStudyRecordToolCall,
)
from app.database import (
    InitialAssessmentError,
    LearningProfileError,
    add_proficiency_test,
    change_learning_level,
    finish_initial_assessment,
    get_learning_profile,
    list_proficiency_tests,
    require_initial_assessment_completion,
    save_learning_profile,
    save_review_word,
    upsert_study_record,
)


@dataclass(frozen=True)
class ToolResult:
    """실행한 도구 이름과 LLM에 알려 줄 저장 결과를 담습니다."""

    name: str
    content: dict[str, object]


def _level_for_initial_assessment_score(score_earned: int) -> str:
    """14점 만점 점수를 고정 기준에 따라 A1, A2 또는 B1으로 변환합니다."""
    if 0 <= score_earned <= 6:
        return "A1"
    if 7 <= score_earned <= 10:
        return "A2"
    if 11 <= score_earned <= 14:
        return "B1"
    raise LearningProfileError("초기 실력 테스트 점수는 0점에서 14점 사이여야 합니다.")


def execute_save_review_word(
    database_url: str,
    *,
    tool_call: SaveReviewWordToolCall,
    study_date: date,
    current_time: datetime,
) -> ToolResult:
    """검증된 save_review_word 도구 호출을 SQLite에 저장합니다.

    날짜와 시각은 앱이 결정하며, 저장할 ``correct_streak``은 0으로 설정합니다.
    """
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


def execute_save_study_record(
    database_url: str,
    *,
    tool_call: SaveStudyRecordToolCall,
    study_date: date,
    current_time: datetime,
    chat_id: int | None,
) -> ToolResult:
    """현재 채팅의 학습 진도를 서버 날짜와 시각으로 저장합니다."""
    if chat_id is None:
        raise LearningProfileError("학습 진도를 저장할 채팅을 찾을 수 없습니다.")

    record = upsert_study_record(
        database_url,
        chat_id=chat_id,
        study_date=study_date,
        topic=tool_call.arguments.topic,
        new_words=tool_call.arguments.new_words,
        expression=tool_call.arguments.expression,
        notes=tool_call.arguments.notes,
        created_at=current_time,
    )

    return ToolResult(
        name=tool_call.action,
        content={
            "saved": True,
            "study_record_id": record.id,
            "topic": record.topic,
        },
    )


def execute_change_learning_level(
    database_url: str,
    *,
    tool_call: ChangeLearningLevelToolCall,
    study_date: date,
    current_time: datetime,
) -> ToolResult:
    """검증된 레벨 변경을 현재 프로필과 변경 이력에 함께 저장합니다."""
    change = change_learning_level(
        database_url,
        changed_on=study_date,
        new_level=tool_call.arguments.new_level,
        reason=tool_call.arguments.reason,
        updated_at=current_time,
    )

    return ToolResult(
        name=tool_call.action,
        content={
            "saved": True,
            "previous_level": change.previous_level,
            "current_level": change.new_level,
        },
    )


def execute_complete_initial_assessment(
    database_url: str,
    *,
    tool_call: CompleteInitialAssessmentToolCall,
    study_date: date,
    current_time: datetime,
    chat_id: int | None,
) -> ToolResult:
    """LLM이 제출한 초기 테스트 결과로 첫 프로필과 테스트 이력을 만듭니다.

    점수로 계산한 레벨과 제출한 레벨이 다르면 저장하지 않습니다. 기존 프로필이나
    테스트 이력이 있어도 덮어쓰지 않고 오류를 발생시킵니다.
    """
    require_initial_assessment_completion(database_url, chat_id)
    arguments = tool_call.arguments
    expected_level = _level_for_initial_assessment_score(arguments.score_earned)
    if arguments.final_level != expected_level:
        raise LearningProfileError(
            "초기 실력 테스트의 최종 레벨이 서버 점수 기준과 일치하지 않습니다."
        )

    if get_learning_profile(database_url) is not None or list_proficiency_tests(
        database_url
    ):
        raise LearningProfileError(
            "이미 학습 프로필 또는 초기 실력 테스트 결과가 있어 덮어쓸 수 없습니다."
        )

    profile = save_learning_profile(
        database_url,
        target_language="영어",
        session_started_on=study_date,
        current_level=arguments.final_level,
        level_updated_on=study_date,
        level_note=arguments.level_note,
        strengths=arguments.strengths,
        weaknesses=arguments.weaknesses,
        updated_at=current_time,
    )
    proficiency_test = add_proficiency_test(
        database_url,
        tested_on=study_date,
        final_level=arguments.final_level,
        score_earned=arguments.score_earned,
        score_total=14,
        vocabulary_result=arguments.vocabulary_result,
        grammar_result=arguments.grammar_result,
        reading_result=arguments.reading_result,
        self_expression_result=arguments.self_expression_result,
        created_at=current_time,
    )
    if chat_id is None:
        raise InitialAssessmentError("초기 실력 테스트 채팅을 찾을 수 없습니다.")
    finish_initial_assessment(database_url, chat_id, current_time)

    return ToolResult(
        name=tool_call.action,
        content={
            "saved": True,
            "current_level": profile.current_level,
            "proficiency_test_id": proficiency_test.id,
        },
    )
