"""채팅 메시지 요청을 대화 서비스로 연결하는 HTTP API를 제공합니다."""

import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, StringConstraints

from app.agent import AgentLoopError
from app.agent.protocol import AgentResponseError
from app.config import settings
from app.database import DatabaseError, MessageError, ReviewWordError, get_chat
from app.llm import LLMConnectionError, LLMResponseError, ModelUnavailableError
from app.services import ConversationError, PromptError, respond_to_chat
from app.services.prompts import USER_MESSAGE_CHARACTER_LIMIT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chats"])


class ChatMessageRequest(BaseModel):
    """사용자가 채팅에 보낼 메시지 본문입니다."""

    content: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=USER_MESSAGE_CHARACTER_LIMIT
        ),
    ]


class ChatMessageResponse(BaseModel):
    """저장된 assistant 메시지를 API 응답 형식으로 표현합니다."""

    id: int
    chat_id: int
    role: Literal["assistant"]
    content: str
    sequence: int
    created_at: datetime


@router.post(
    "/{chat_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
)
async def create_chat_message(
    chat_id: int, body: ChatMessageRequest, request: Request
) -> ChatMessageResponse:
    """사용자 메시지를 처리하고 저장된 assistant 응답을 반환합니다."""
    chat = get_chat(settings.database_url, chat_id)

    if chat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="채팅을 찾을 수 없습니다."
        )

    try:
        assistant_message = await respond_to_chat(
            request.app.state.llm_client,
            database_url=settings.database_url,
            chat_id=chat_id,
            user_content=body.content,
            agent_instructions=request.app.state.agent_instructions,
            study_guidelines=request.app.state.study_guidelines,
            timezone_name=settings.tz,
        )
    except (LLMConnectionError, ModelUnavailableError) as error:
        logger.info("LLM을 사용할 수 없습니다: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="현재 영어 학습 모델에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        ) from error
    except (LLMResponseError, AgentResponseError, AgentLoopError) as error:
        logger.warning("LLM 응답을 처리하지 못했습니다.", exc_info=error)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="영어 학습 모델의 응답을 처리하지 못했습니다. 다시 시도해 주세요.",
        ) from error
    except ConversationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    except (DatabaseError, MessageError, PromptError, ReviewWordError) as error:
        logger.exception("대화 요청 처리에 실패했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="대화를 저장하거나 처리하지 못했습니다. 잠시 후 다시 시도해주세요.",
        ) from error

    return ChatMessageResponse(
        id=assistant_message.id,
        chat_id=assistant_message.chat_id,
        role="assistant",
        content=assistant_message.content,
        sequence=assistant_message.sequence,
        created_at=assistant_message.created_at,
    )
