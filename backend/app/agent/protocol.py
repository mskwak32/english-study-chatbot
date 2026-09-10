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
    message: Annotated[             # str이 실제 자료형. StringConstraints는 자료형에 붙이는 추가 정보
        str,
        StringConstraints(          # 문자열에 적용할 규칙
            strip_whitespace=True,  # 모든 문자열 양쪽 공백 제거
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


# LLM은 최종 답변 또는 복습 단어 저장 요청 중 하나를 반환할 수 있음.
# action 필드를 기준으로 사용할 Pydantic 모델을 선택합니다.
AgentResponse = Annotated[
    AgentReply | SaveReviewWordToolCall,    # 실제 자료형
    Field(discriminator="action"),          # 추가 정보
]

_AGENT_RESPONSE_ADAPTER = TypeAdapter(AgentResponse)

# 동일한 정의를 Ollama의 출력 스키마와 Python 입력 검증에 사용
# 이렇게 하면 Ollama에게 전달할 JSON 스키마와
# Ollama가 반환한 JSON 검증 규칙이 달라지는 문제를 줄일 수 있음
AGENT_RESPONSE_SCHEMA: dict[str, object] = (
    _AGENT_RESPONSE_ADAPTER.json_schema()
)

def parse_agent_response(
    content: dict[str, object],
) -> AgentResponse:
    """Ollama의 JSON 객체를 검증된 Agent 응답으로 변환합니다."""
    try:
        return _AGENT_RESPONSE_ADAPTER.validate_python(content)
    except ValidationError as error:
        raise AgentResponseError(
            "모델 응답이 정해진 형식과 맞지 않습니다."
        ) from error
