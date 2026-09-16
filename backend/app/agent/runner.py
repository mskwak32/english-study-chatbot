"""LLM 응답 검증과 도구 호출 반복을 조정해 최종 답변을 생성합니다."""

import json
from collections.abc import Sequence
from datetime import date, datetime

from app.agent.protocol import (
    AGENT_RESPONSE_SCHEMA,
    INITIAL_ASSESSMENT_COMPLETION_RESPONSE_SCHEMA,
    INITIAL_ASSESSMENT_IN_PROGRESS_RESPONSE_SCHEMA,
    LEVEL_CHANGE_AGENT_RESPONSE_SCHEMA,
    AgentReply,
    ChangeLearningLevelToolCall,
    CompleteInitialAssessmentToolCall,
    SaveReviewWordToolCall,
    SaveStudyRecordToolCall,
    parse_agent_response,
    parse_initial_assessment_completion_response,
    parse_initial_assessment_in_progress_response,
    parse_level_change_agent_response,
)
from app.database import can_complete_initial_assessment, is_initial_assessment_active
from app.llm import LLMClient, LLMMessage
from app.llm_tools import (
    ToolResult,
    execute_change_learning_level,
    execute_complete_initial_assessment,
    execute_save_review_word,
    execute_save_study_record,
)


class AgentLoopError(RuntimeError):
    """Agent가 제한 횟수 안에 최종 답변을 만들지 못했을 때 발생합니다."""


def _assistant_response_message(content: dict[str, object]) -> LLMMessage:
    """LLM의 구조화 응답을 다음 요청에 포함할 메시지로 변환합니다."""
    return LLMMessage(role="assistant", content=json.dumps(content, ensure_ascii=False))


def _tool_result_message(result: ToolResult) -> LLMMessage:
    """도구 실행 결과와 다음 행동 지침을 LLM에 보낼 system 메시지로 만듭니다."""
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


def _response_schema_for_chat(
    database_url: str,
    chat_id: int | None,
    *,
    reply_only: bool,
    level_change_requested: bool,
) -> dict[str, object]:
    """초기 테스트 답변 수에 따라 LLM이 선택할 수 있는 행동을 제한합니다."""
    if reply_only:
        return INITIAL_ASSESSMENT_IN_PROGRESS_RESPONSE_SCHEMA
    if (
        chat_id is not None
        and is_initial_assessment_active(database_url, chat_id)
    ):
        if can_complete_initial_assessment(database_url, chat_id):
            return INITIAL_ASSESSMENT_COMPLETION_RESPONSE_SCHEMA
        return INITIAL_ASSESSMENT_IN_PROGRESS_RESPONSE_SCHEMA

    if level_change_requested:
        return LEVEL_CHANGE_AGENT_RESPONSE_SCHEMA
    return AGENT_RESPONSE_SCHEMA


def _parse_response_for_chat(
    content: dict[str, object],
    database_url: str,
    chat_id: int | None,
    *,
    reply_only: bool,
    level_change_requested: bool,
) -> (
    AgentReply
    | SaveReviewWordToolCall
    | SaveStudyRecordToolCall
    | ChangeLearningLevelToolCall
    | CompleteInitialAssessmentToolCall
):
    """현재 초기 테스트 상태에 맞지 않는 LLM 행동을 서버에서 거부."""
    if reply_only:
        return parse_initial_assessment_in_progress_response(content)
    if (
        chat_id is not None
        and is_initial_assessment_active(database_url, chat_id)
    ):
        if can_complete_initial_assessment(database_url, chat_id):
            return parse_initial_assessment_completion_response(content)
        return parse_initial_assessment_in_progress_response(content)
    if level_change_requested:
        return parse_level_change_agent_response(content)
    return parse_agent_response(content)


async def run_agent(
    llm_client: LLMClient,
    *,
    messages: Sequence[LLMMessage],
    database_url: str,
    study_date: date,
    current_time: datetime,
    chat_id: int | None = None,
    level_change_requested: bool = False,
    max_tool_calls: int = 3,
) -> str:
    """LLM이 사용자에게 보여줄 최종 답변을 만들 때까지 응답을 처리합니다.

    LLM이 ``reply``를 반환하면 답변 문구를 즉시 반환합니다. 도구 호출을
    반환하면 해당 저장 작업을 실행하고 그 결과를 LLM에 알려 다시 답변을
    요청합니다. 무한 반복을 막기 위해 도구 실행은 ``max_tool_calls``회로 제한합니다.
    """
    if not messages:
        raise ValueError("Agent에 전달할 메시지는 하나 이상이어야 합니다.")
    if max_tool_calls <= 0:
        raise ValueError("도구 호출 제한 횟수는 1 이상이어야 합니다.")

    # 호출자가 전달한 원본 목록을 변경하지 않도록 복사
    working_messages = list(messages)
    tool_call_count = 0
    reply_only = False

    while True:
        llm_response = await llm_client.chat_structured(
            messages=working_messages,
            response_schema=_response_schema_for_chat(
                database_url,
                chat_id,
                reply_only=reply_only,
                level_change_requested=level_change_requested,
            ),
        )
        agent_response = _parse_response_for_chat(
            llm_response.content,
            database_url,
            chat_id,
            reply_only=reply_only,
            level_change_requested=level_change_requested,
        )

        if isinstance(agent_response, AgentReply):
            return agent_response.message

        # 이미 허용된 횟수만큼 실행했다면 다음 도구 호출은 실행하지 않습니다.
        if tool_call_count >= max_tool_calls:
            raise AgentLoopError(
                "Agent가 도구 호출 제한 횟수 안에 최종 답변을 만들지 못했습니다."
            )

        if isinstance(agent_response, SaveReviewWordToolCall):
            result = execute_save_review_word(
                database_url,
                tool_call=agent_response,
                study_date=study_date,
                current_time=current_time,
            )
        elif isinstance(agent_response, SaveStudyRecordToolCall):
            result = execute_save_study_record(
                database_url,
                tool_call=agent_response,
                study_date=study_date,
                current_time=current_time,
                chat_id=chat_id,
            )
        elif isinstance(agent_response, ChangeLearningLevelToolCall):
            result = execute_change_learning_level(
                database_url,
                tool_call=agent_response,
                study_date=study_date,
                current_time=current_time,
            )
        elif isinstance(agent_response, CompleteInitialAssessmentToolCall):
            result = execute_complete_initial_assessment(
                database_url,
                tool_call=agent_response,
                study_date=study_date,
                current_time=current_time,
                chat_id=chat_id,
            )
            reply_only = True
        else:
            raise TypeError(
                f"지원하지 않는 도구 호출입니다: {type(agent_response).__name__}"
            )
        tool_call_count += 1

        # LLM이 자신이 요청했던 도구 호출과 실행 결과를 함께 볼 수 있도록
        # 다음 요청의 임시 대화 기록에 추가합니다.
        working_messages.append(_assistant_response_message(llm_response.content))
        working_messages.append(_tool_result_message(result))
