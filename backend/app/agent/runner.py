"""LLM 응답 검증과 도구 호출 반복을 조정해 최종 답변을 생성합니다."""

import json
from collections.abc import Sequence
from datetime import date, datetime

from app.agent.protocol import AGENT_RESPONSE_SCHEMA, AgentReply, parse_agent_response
from app.llm import LLMClient, LLMMessage
from app.llm_tools import ToolResult, execute_save_review_word


class AgentLoopError(RuntimeError):
    """Agent가 제한 횟수 안에 최종 답변을 만들지 못했을 때 발생합니다."""


def _assistant_response_message(content: dict[str, object]) -> LLMMessage:
    """LLM의 구조화 응답을 다음 요청에 포함할 메시지로 변환합니다."""
    return LLMMessage(role="assistant", content=json.dumps(content, ensure_ascii=False))


def _tool_result_message(result: ToolResult) -> LLMMessage:
    """도구 실행 결과와 다음 응답 지침을 LLM 메시지로 전달합니다."""
    result_json = json.dumps(
        {"tool": result.name, "result": result.content}, ensure_ascii=False
    )

    return LLMMessage(
        role="system",
        content=(
            "다음은 애플리케이션이 실행한 도구 결과입니다.\n"
            f"{result_json}\n"
            "추가 도구 호출이 필요하지 않다면 "
            "action이 reply인 최종 답변을 반환하세요."
        ),
    )


async def run_agent(
    llm_client: LLMClient,
    *,
    messages: Sequence[LLMMessage],
    database_url: str,
    study_date: date,
    current_time: datetime,
    max_tool_calls: int = 3,
) -> str:
    """LLM과 도구를 반복 호출해 사용자에게 보낼 최종 답변을 만듭니다."""
    if not messages:
        raise ValueError("Agent에 전달할 메시지는 하나 이상이어야 합니다.")
    if max_tool_calls <= 0:
        raise ValueError("도구 호출 제한 횟수는 1 이상이어야 합니다.")

    # 호출자가 전달한 원본 목록을 변경하지 않도록 복사
    working_messages = list(messages)
    tool_call_count = 0

    while True:
        llm_response = await llm_client.chat_structured(
            messages=working_messages, response_schema=AGENT_RESPONSE_SCHEMA
        )
        agent_response = parse_agent_response(llm_response.content)

        if isinstance(agent_response, AgentReply):
            return agent_response.message

        # 이미 허용된 횟수만큼 실행했다면 다음 도구 호출은 실행하지 않습니다.
        if tool_call_count >= max_tool_calls:
            raise AgentLoopError(
                "Agent가 도구 호출 제한 횟수 안에 최종 답변을 만들지 못했습니다."
            )

        result = execute_save_review_word(
            database_url,
            tool_call=agent_response,
            study_date=study_date,
            current_time=current_time,
        )
        tool_call_count += 1

        # LLM이 자신이 요청했던 도구 호출과 실행 결과를 함께 볼 수 있도록
        # 다음 요청의 임시 대화 기록에 추가합니다.
        working_messages.append(_assistant_response_message(llm_response.content))
        working_messages.append(_tool_result_message(result))
