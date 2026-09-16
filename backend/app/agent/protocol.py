"""LLM의 최종 답변과 도구 호출에 사용할 구조화 응답 형식을 정의합니다."""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
)


class AgentResponseError(ValueError):
    """LLM 응답이 정해진 형식과 맞지 않을 때 발생합니다."""


class _StrictBaseModel(BaseModel):
    """정의하지 않은 필드를 허용하지 않는 기본 Pydantic 모델입니다."""

    # 모델에 정의되지 않은 추가 필드 거부하도록 설정
    model_config = ConfigDict(extra="forbid")


class AgentReply(_StrictBaseModel):
    """사용자에게 바로 반환할 최종 답변입니다."""

    action: Literal["reply"]
    message: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=8_000,
        ),
    ]


class SaveReviewWordArguments(_StrictBaseModel):
    """save_review_word 도구 호출에 필요한 인자입니다."""

    term: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=100,
        ),
    ]
    explanation: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=1_000,
        ),
    ]


class SaveReviewWordToolCall(_StrictBaseModel):
    """복습 단어 저장을 요청하는 도구 호출입니다."""

    action: Literal["save_review_word"]
    arguments: SaveReviewWordArguments


class SaveStudyRecordArguments(_StrictBaseModel):
    """save_study_record 도구 호출에 필요한 학습 요약입니다."""

    topic: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    new_words: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=2_000)
    ] = ""
    expression: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=2_000)
    ] = ""
    notes: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=2_000)
    ] = ""


class SaveStudyRecordToolCall(_StrictBaseModel):
    """현재 채팅의 학습 진도 저장을 요청합니다."""

    action: Literal["save_study_record"]
    arguments: SaveStudyRecordArguments


class ChangeLearningLevelArguments(_StrictBaseModel):
    """change_learning_level 도구 호출에 필요한 레벨과 근거입니다."""

    new_level: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
    ]


class ChangeLearningLevelToolCall(_StrictBaseModel):
    """사용자가 요청한 레벨 변경 저장을 요청합니다."""

    action: Literal["change_learning_level"]
    arguments: ChangeLearningLevelArguments


class CompleteInitialAssessmentArguments(_StrictBaseModel):
    """LLM이 초기 실력 테스트를 마친 뒤 제출할 평가 항목을 검증합니다."""

    final_level: Literal["A1", "A2", "B1"]
    score_earned: Annotated[int, Field(ge=0, le=14, strict=True)]
    vocabulary_result: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
    ]
    grammar_result: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
    ]
    reading_result: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
    ]
    self_expression_result: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
    ]
    strengths: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
    ]
    weaknesses: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
    ]
    level_note: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
    ]


class CompleteInitialAssessmentToolCall(_StrictBaseModel):
    """검증된 초기 테스트 결과로 학습 프로필 생성을 요청합니다."""

    action: Literal["complete_initial_assessment"]
    arguments: CompleteInitialAssessmentArguments


# 일반 학습에서는 레벨 변경 도구를 제공하지 않습니다.
AgentResponse = Annotated[
    AgentReply
    | SaveReviewWordToolCall
    | SaveStudyRecordToolCall
    | CompleteInitialAssessmentToolCall,
    Field(discriminator="action"),
]

LevelChangeAgentResponse = Annotated[
    AgentReply
    | SaveReviewWordToolCall
    | SaveStudyRecordToolCall
    | ChangeLearningLevelToolCall
    | CompleteInitialAssessmentToolCall,
    Field(discriminator="action"),
]

_AGENT_RESPONSE_ADAPTER = TypeAdapter(AgentResponse)
_LEVEL_CHANGE_AGENT_RESPONSE_ADAPTER = TypeAdapter(LevelChangeAgentResponse)

InitialAssessmentInProgressResponse = AgentReply
InitialAssessmentCompletionResponse = CompleteInitialAssessmentToolCall

# 동일한 정의를 Ollama의 출력 스키마와 Python 입력 검증에 사용
# 이렇게 하면 Ollama에게 전달할 JSON 스키마와
# Ollama가 반환한 JSON 검증 규칙이 달라지는 문제를 줄일 수 있음
AGENT_RESPONSE_SCHEMA: dict[str, object] = _AGENT_RESPONSE_ADAPTER.json_schema()
LEVEL_CHANGE_AGENT_RESPONSE_SCHEMA: dict[str, object] = (
    _LEVEL_CHANGE_AGENT_RESPONSE_ADAPTER.json_schema()
)
INITIAL_ASSESSMENT_IN_PROGRESS_RESPONSE_SCHEMA: dict[str, object] = (
    InitialAssessmentInProgressResponse.model_json_schema()
)
INITIAL_ASSESSMENT_COMPLETION_RESPONSE_SCHEMA: dict[str, object] = (
    InitialAssessmentCompletionResponse.model_json_schema()
)

_INITIAL_ASSESSMENT_IN_PROGRESS_RESPONSE_ADAPTER = TypeAdapter(
    InitialAssessmentInProgressResponse
)
_INITIAL_ASSESSMENT_COMPLETION_RESPONSE_ADAPTER = TypeAdapter(
    InitialAssessmentCompletionResponse
)


def parse_agent_response(
    content: dict[str, object],
) -> AgentResponse:
    """Ollama의 JSON 객체를 검증된 Agent 응답으로 변환합니다."""
    try:
        return _AGENT_RESPONSE_ADAPTER.validate_python(content)
    except ValidationError as error:
        raise AgentResponseError("모델 응답이 정해진 형식과 맞지 않습니다.") from error


def parse_level_change_agent_response(
    content: dict[str, object],
) -> LevelChangeAgentResponse:
    """레벨 변경 요청 대화에서만 허용되는 응답을 검증합니다."""
    try:
        return _LEVEL_CHANGE_AGENT_RESPONSE_ADAPTER.validate_python(content)
    except ValidationError as error:
        raise AgentResponseError("모델 응답이 정해진 형식과 맞지 않습니다.") from error


def parse_initial_assessment_in_progress_response(
    content: dict[str, object],
) -> AgentReply:
    """완료 전 초기 테스트에서는 문제 안내 답변만 허용."""
    try:
        return _INITIAL_ASSESSMENT_IN_PROGRESS_RESPONSE_ADAPTER.validate_python(content)
    except ValidationError as error:
        raise AgentResponseError("초기 실력 테스트 진행 중에는 답변만 반환할 수 있습니다.") from error


def parse_initial_assessment_completion_response(
    content: dict[str, object],
) -> CompleteInitialAssessmentToolCall:
    """답변 14개 뒤 활성 초기 테스트에서는 완료 도구만 허용."""
    try:
        return _INITIAL_ASSESSMENT_COMPLETION_RESPONSE_ADAPTER.validate_python(content)
    except ValidationError as error:
        raise AgentResponseError(
            "초기 실력 테스트 완료 전에는 완료 도구를 호출해야 합니다."
        ) from error
