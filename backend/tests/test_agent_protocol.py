import pytest

from app.agent.protocol import (
    AgentReply,
    AgentResponseError,
    SaveReviewWordToolCall,
    parse_agent_response,
)


def test_parse_agent_response_returns_reply() -> None:
    """일반 답변 JSON을 AgentReply로 변환합니다."""
    response = parse_agent_response(
        {
            "action": "reply",
            "message": "오늘은 과거형을 연습하겠습니다.",
        }
    )

    assert isinstance(response, AgentReply)
    assert response.message == "오늘은 과거형을 연습하겠습니다."


def test_parse_agent_response_returns_tool_call() -> None:
    """복습 단어 저장 요청을 검증된 도구 호출로 변환합니다."""
    response = parse_agent_response(
        {
            "action": "save_review_word",
            "arguments": {
                "term": "  hesitate ",
                "explanation": " 망설이다 ",
            },
        }
    )

    assert isinstance(response, SaveReviewWordToolCall)
    assert response.arguments.term == "hesitate"
    assert response.arguments.explanation == "망설이다"


@pytest.mark.parametrize(
    "content",
    [
        {
            "action": "delete_database",
            "message": "DB를 삭제합니다.",
        },
        {
            "action": "save_review_word",
            "arguments": {
                "term": "hesitate",
            },
        },
        {
            "action": "save_review_word",
            "arguments": {
                "term": "hesitate",
                "explanation": "망설이다",
                "database_url": "sqlite:////other/database.db",
            },
        },
        {
            "action": "save_review_word",
            "message": "저장했습니다.",
            "arguments": {
                "term": "hesitate",
                "explanation": "망설이다",
            },
        },
    ],
)
def test_parse_agent_response_rejects_invalid_content(
    content: dict[str, object],
) -> None:
    """알 수 없는 요청, 누락된 값, 추가 필드를 거부합니다."""
    with pytest.raises(
        AgentResponseError,
        match="정해진 형식과 맞지 않습니다",
    ):
        parse_agent_response(content)
