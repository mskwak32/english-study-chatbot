"""사용자가 메시지를 저장하고 LLM 응답을 생성·저장하는 대화 흐름을 제공합니다."""

from datetime import UTC, datetime

from app.agent import run_agent
from app.database import Message, add_message, list_messages
from app.llm import LLMClient
from app.study_time import study_date_for, to_utc

from .prompts import USER_MESSAGE_CHARACTER_LIMIT, build_chat_prompt


class ConversationError(ValueError):
    """대화 요청을 안전하게 처리할 수 없을 때 발생합니다."""


async def respond_to_chat(
    llm_client: LLMClient,
    *,
    database_url: str,
    chat_id: int,
    user_content: str,
    agent_instructions: str,
    study_guidelines: str,
    timezone_name: str,
    now: datetime | None = None,
) -> Message:
    """사용자 메시지에 대한 assistant 응답을 생성하고 저장합니다."""
    if len(user_content) > USER_MESSAGE_CHARACTER_LIMIT:
        raise ConversationError(
            f"사용자 메시지는 {USER_MESSAGE_CHARACTER_LIMIT:,}자를 초과할 수 없습니다."
        )

    current_time = to_utc(now if now is not None else datetime.now(UTC))
    study_date = study_date_for(current_time, timezone_name)

    # 모델 요청 전에 사용자 메시지를 저장
    add_message(
        database_url,
        chat_id,
        role="user",
        content=user_content,
        created_at=current_time,
    )

    conversation_messages = list_messages(database_url, chat_id)
    prompt = build_chat_prompt(
        database_url, agent_instructions, study_guidelines, conversation_messages
    )

    assistant_content = await run_agent(
        llm_client,
        messages=prompt,
        database_url=database_url,
        study_date=study_date,
        current_time=current_time,
    )

    return add_message(
        database_url,
        chat_id,
        role="assistant",
        content=assistant_content,
        created_at=current_time,
    )
