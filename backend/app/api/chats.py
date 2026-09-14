"""채팅 관리와 메시지 처리를 위한 HTTP API를 제공합니다."""

import logging
from datetime import date, datetime
from typing import Annotated, Literal, Never

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.agent import AgentLoopError
from app.agent.protocol import AgentResponseError
from app.config import settings
from app.database import (
    ChatError,
    DatabaseError,
    InitialAssessmentError,
    LearningProfileError,
    MessageError,
    ReviewWordError,
    delete_chat,
    get_chat,
    list_chats,
    list_messages,
)
from app.llm import LLMConnectionError, LLMResponseError, ModelUnavailableError
from app.services import (
    ConversationError,
    PromptError,
    create_today_additional_chat,
    get_or_create_today_chat,
    get_today_chat,
    respond_to_chat,
    start_profile_setup,
    start_today_learning,
)
from app.services.prompts import USER_MESSAGE_CHARACTER_LIMIT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chats"])


class ChatResponse(BaseModel):
    """저장된 채팅 한 건의 메타데이터를 반환하는 API 응답입니다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    study_date: date
    kind: Literal["default", "extra"]
    extra_number: int | None
    title: str
    created_at: datetime


class MessageResponse(BaseModel):
    """저장된 채팅 메시지 한 건을 반환하는 API 응답입니다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    role: Literal["user", "assistant"]
    content: str
    sequence: int
    created_at: datetime


class ChatMessageRequest(BaseModel):
    """사용자가 채팅에 보낼 메시지 본문입니다."""

    content: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=USER_MESSAGE_CHARACTER_LIMIT
        ),
    ]


@router.get(
    "/today",
    response_model=ChatResponse | None,
    status_code=status.HTTP_200_OK,
)
def read_today_chat() -> ChatResponse | None:
    """오늘의 기본 학습 채팅을 생성하지 않고 조회합니다."""
    try:
        chat = get_today_chat(
            settings.database_url,
            settings.timezone,
        )
    except (ChatError, DatabaseError) as error:
        logger.exception("오늘의 학습 채팅을 불러오지 못했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="오늘의 학습 채팅을 불러오지 못했습니다.",
        ) from error

    if chat is None:
        return None

    return ChatResponse.model_validate(chat)


@router.post(
    "/today",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
def create_today_chat() -> ChatResponse:
    """오늘의 기본 학습 채팅을 생성하거나 기존 채팅을 반환합니다."""
    try:
        chat = get_or_create_today_chat(
            settings.database_url,
            settings.timezone,
        )
    except (ChatError, DatabaseError) as error:
        logger.exception("오늘의 학습 채팅을 준비하지 못했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="오늘의 학습 채팅을 준비하지 못했습니다.",
        ) from error

    return ChatResponse.model_validate(chat)


def _raise_conversation_http_error(error: Exception) -> Never:
    """모델 연결, 응답 형식, 입력 오류를 알맞은 HTTP 상태 코드로 변환합니다."""
    if isinstance(error, (LLMConnectionError, ModelUnavailableError)):
        logger.info("LLM을 사용할 수 없습니다: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="현재 영어 학습 모델에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        ) from error

    if isinstance(error, (LLMResponseError, AgentResponseError, AgentLoopError)):
        logger.warning("LLM 응답을 처리하지 못했습니다.", exc_info=error)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="영어 학습 모델의 응답을 처리하지 못했습니다. 다시 시도해 주세요.",
        ) from error

    if isinstance(error, ConversationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error

    raise TypeError(f"지원하지 않는 대화 오류입니다: {type(error).__name__}")


@router.post(
    "/today/start",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def start_today_chat(request: Request) -> ChatResponse:
    """학습 프로필이 있으면 오늘 채팅을 열고 빈 채팅에 첫 튜터 답변을 만듭니다."""
    try:
        chat = await start_today_learning(
            request.app.state.llm_client,
            database_url=settings.database_url,
            agent_instructions=request.app.state.agent_instructions,
            study_guidelines=request.app.state.study_guidelines,
            timezone_name=settings.timezone,
        )
    except (
        LLMConnectionError,
        ModelUnavailableError,
        LLMResponseError,
        AgentResponseError,
        AgentLoopError,
        ConversationError,
    ) as error:
        _raise_conversation_http_error(error)
    except (
        ChatError,
        DatabaseError,
        InitialAssessmentError,
        LearningProfileError,
        MessageError,
        PromptError,
        ReviewWordError,
    ) as error:
        logger.exception("오늘의 학습을 시작하지 못했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="오늘의 학습을 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        ) from error

    return ChatResponse.model_validate(chat)


@router.post(
    "/today/profile-setup",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def start_profile_setup_chat(request: Request) -> ChatResponse:
    """프로필이 없는 학습자의 오늘 채팅을 열고 빈 채팅에 첫 테스트 문제를 만듭니다."""
    try:
        chat = await start_profile_setup(
            request.app.state.llm_client,
            database_url=settings.database_url,
            agent_instructions=request.app.state.agent_instructions,
            study_guidelines=request.app.state.study_guidelines,
            timezone_name=settings.timezone,
        )
    except (
        LLMConnectionError,
        ModelUnavailableError,
        LLMResponseError,
        AgentResponseError,
        AgentLoopError,
        ConversationError,
    ) as error:
        _raise_conversation_http_error(error)
    except (
        ChatError,
        DatabaseError,
        InitialAssessmentError,
        LearningProfileError,
        MessageError,
        PromptError,
        ReviewWordError,
    ) as error:
        logger.exception("초기 실력 테스트를 시작하지 못했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="초기 실력 테스트를 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        ) from error

    return ChatResponse.model_validate(chat)


@router.get("", response_model=list[ChatResponse], status_code=status.HTTP_200_OK)
def read_chats() -> list[ChatResponse]:
    """저장된 모든 채팅을 최근 학습 날짜부터 반환합니다."""
    try:
        chats = list_chats(settings.database_url)
    except DatabaseError as error:
        logger.exception("채팅 목록을 불러오지 못했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="채팅 목록을 불러오지 못했습니다.",
        ) from error

    return [ChatResponse.model_validate(chat) for chat in chats]


@router.post(
    "/additional", response_model=ChatResponse, status_code=status.HTTP_201_CREATED
)
def create_additional_chat() -> ChatResponse:
    """오늘의 추가 학습을 생성합니다."""
    try:
        chat = create_today_additional_chat(settings.database_url, settings.timezone)
    except (ChatError, DatabaseError) as error:
        logger.exception("추가 학습 채팅을 만들지 못했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="추가 학습 채팅을 만들지 못했습니다.",
        ) from error

    return ChatResponse.model_validate(chat)


@router.get(
    "/{chat_id}/messages",
    response_model=list[MessageResponse],
    status_code=status.HTTP_200_OK,
)
def read_chat_messages(chat_id: int) -> list[MessageResponse]:
    """지정한 채팅의 메시지를 저장 순서대로 반환합니다."""
    try:
        chat = get_chat(settings.database_url, chat_id)

        if chat is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="채팅을 찾을 수 없습니다."
            )

        messages = list_messages(settings.database_url, chat_id)
    except HTTPException:
        raise
    except (DatabaseError, MessageError) as error:
        logger.exception("채팅 메시지를 불러오지 못했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="채팅 메시지를 불러오지 못했습니다.",
        ) from error

    return [MessageResponse.model_validate(message) for message in messages]


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_chat(chat_id: int) -> Response:
    """채팅과 메시지를 삭제하고 연결된 학습 기록의 채팅 참조만 비웁니다."""
    try:
        deleted = delete_chat(settings.database_url, chat_id)
    except DatabaseError as error:
        logger.exception("채팅을 삭제하지 못했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="채팅을 삭제하지 못했습니다.",
        ) from error

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="채팅을 찾을 수 없습니다."
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{chat_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
async def create_chat_message(
    chat_id: int, body: ChatMessageRequest, request: Request
) -> MessageResponse:
    """사용자 메시지와 그에 대한 튜터 답변을 저장하고 튜터 메시지를 반환합니다."""
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
            timezone_name=settings.timezone,
        )
    except (
        LLMConnectionError,
        ModelUnavailableError,
        LLMResponseError,
        AgentResponseError,
        AgentLoopError,
        ConversationError,
    ) as error:
        _raise_conversation_http_error(error)
    except (
        DatabaseError,
        InitialAssessmentError,
        LearningProfileError,
        MessageError,
        PromptError,
        ReviewWordError,
    ) as error:
        logger.exception("대화 요청 처리에 실패했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="대화를 저장하거나 처리하지 못했습니다. 잠시 후 다시 시도해주세요.",
        ) from error

    return MessageResponse(
        id=assistant_message.id,
        chat_id=assistant_message.chat_id,
        role="assistant",
        content=assistant_message.content,
        sequence=assistant_message.sequence,
        created_at=assistant_message.created_at,
    )
