"""사용자 메시지를 LLM에 전달하고 튜터 답변까지 채팅에 저장합니다."""

from datetime import UTC, datetime

from app.agent import run_agent
from app.database import Message, add_message, list_messages
from app.llm import LLMClient
from app.study_time import study_date_for, to_utc

from .prompts import (
    INITIAL_LEARNING_TRIGGER,
    USER_MESSAGE_CHARACTER_LIMIT,
    build_chat_prompt,
    build_initial_chat_prompt,
)


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
    """사용자 메시지를 저장하고, 전체 대화를 바탕으로 만든 튜터 답변도 저장합니다.

    튜터 답변 생성이나 저장이 실패해도 먼저 저장한 사용자 메시지는 남습니다.
    """
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
        chat_id=chat_id,
    )

    return add_message(
        database_url,
        chat_id,
        role="assistant",
        content=assistant_content,
        created_at=current_time,
    )


async def respond_to_initial_chat(
    llm_client: LLMClient,
    *,
    database_url: str,
    chat_id: int,
    agent_instructions: str,
    study_guidelines: str,
    timezone_name: str,
    trigger: str = INITIAL_LEARNING_TRIGGER,
    now: datetime | None = None,
) -> Message:
    """학습 시작 신호를 LLM에 보내 첫 튜터 안내 또는 테스트 문제를 저장합니다.

    시작 신호는 LLM을 작동시키기 위한 내부 입력이므로 채팅에는 저장하지 않습니다.
    LLM이 만든 튜터 답변만 저장되어 화면에 표시됩니다.
    """
    current_time = to_utc(now if now is not None else datetime.now(UTC))
    study_date = study_date_for(current_time, timezone_name)
    prompt = build_initial_chat_prompt(
        database_url,
        agent_instructions,
        study_guidelines,
        trigger,
    )

    assistant_content = await run_agent(
        llm_client,
        messages=prompt,
        database_url=database_url,
        study_date=study_date,
        current_time=current_time,
        chat_id=chat_id,
    )

    return add_message(
        database_url,
        chat_id,
        role="assistant",
        content=assistant_content,
        created_at=current_time,
    )
