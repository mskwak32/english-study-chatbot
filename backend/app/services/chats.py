"""사용자 날짜를 기준으로 오늘의 기본 채팅과 추가 채팅을 관리합니다."""

from datetime import UTC, date, datetime

from app.database import (
    Chat,
    create_additional_chat,
    get_default_chat,
    get_learning_profile,
    get_or_create_default_chat,
    list_messages,
    list_proficiency_tests,
)
from app.llm import LLMClient
from app.study_time import study_date_for, to_utc

from .conversations import ConversationError, respond_to_initial_chat
from .prompts import INITIAL_LEARNING_TRIGGER, PROFILE_SETUP_TRIGGER


def _current_study_time(now: datetime | None) -> datetime:
    """현재 시각을 채팅 생성 시각에 쓸 UTC 시각으로 변환합니다."""
    current_time = now if now is not None else datetime.now(UTC)

    return to_utc(current_time)


def _today_study_date(timezone_name: str, current_time: datetime) -> date:
    """UTC 현재 시각에서 사용자 타임존 기준 오늘의 학습일을 구합니다."""
    return study_date_for(current_time, timezone_name)


def get_today_chat(
    database_url: str, timezone_name: str, now: datetime | None = None
) -> Chat | None:
    """사용자 타임존 기준 오늘의 기본 학습 채팅을 생성하지 않고 조회합니다."""
    current_time = _current_study_time(now)
    study_date = _today_study_date(timezone_name, current_time)

    return get_default_chat(database_url, study_date)


def get_or_create_today_chat(
    database_url: str, timezone_name: str, now: datetime | None = None
) -> Chat:
    """사용자 타임존 기준 오늘의 기본 학습 채팅을 조회하거나 생성합니다."""
    created_at = _current_study_time(now)
    study_date = _today_study_date(timezone_name, created_at)

    return get_or_create_default_chat(database_url, study_date, created_at)


async def start_today_learning(
    llm_client: LLMClient,
    *,
    database_url: str,
    agent_instructions: str,
    study_guidelines: str,
    timezone_name: str,
    now: datetime | None = None,
) -> Chat:
    """프로필이 있는 학습자의 오늘 채팅을 열고 첫 튜터 안내를 준비합니다.

    프로필이 없으면 학습을 시작하지 않습니다. 기존 메시지가 있는 채팅은 그대로
    반환하며, 메시지가 하나도 없을 때만 LLM에 첫 답변을 요청합니다.
    """
    if get_learning_profile(database_url) is None:
        raise ConversationError("학습 프로필을 먼저 만들어 주세요.")

    return await _start_empty_today_chat(
        llm_client,
        database_url=database_url,
        agent_instructions=agent_instructions,
        study_guidelines=study_guidelines,
        timezone_name=timezone_name,
        now=now,
    )


async def start_profile_setup(
    llm_client: LLMClient,
    *,
    database_url: str,
    agent_instructions: str,
    study_guidelines: str,
    timezone_name: str,
    now: datetime | None = None,
) -> Chat:
    """프로필이 없는 학습자의 오늘 채팅을 열고 첫 테스트 문제를 준비합니다.

    이미 프로필이나 테스트 이력이 있으면 새 테스트를 시작하지 않습니다. 빈 채팅일
    때만 LLM에 첫 문제를 요청합니다.
    """
    if get_learning_profile(database_url) is not None or list_proficiency_tests(
        database_url
    ):
        raise ConversationError(
            "학습 프로필이 이미 있어 초기 실력 테스트를 다시 시작할 수 없습니다."
        )

    return await _start_empty_today_chat(
        llm_client,
        database_url=database_url,
        agent_instructions=agent_instructions,
        study_guidelines=study_guidelines,
        timezone_name=timezone_name,
        trigger=PROFILE_SETUP_TRIGGER,
        now=now,
    )


async def _start_empty_today_chat(
    llm_client: LLMClient,
    *,
    database_url: str,
    agent_instructions: str,
    study_guidelines: str,
    timezone_name: str,
    trigger: str = INITIAL_LEARNING_TRIGGER,
    now: datetime | None = None,
) -> Chat:
    """오늘 채팅을 생성하거나 열고, 비어 있을 때만 LLM의 첫 답변을 저장합니다."""
    current_time = _current_study_time(now)
    chat = get_or_create_today_chat(database_url, timezone_name, current_time)

    if list_messages(database_url, chat.id):
        return chat

    await respond_to_initial_chat(
        llm_client,
        database_url=database_url,
        chat_id=chat.id,
        agent_instructions=agent_instructions,
        study_guidelines=study_guidelines,
        timezone_name=timezone_name,
        trigger=trigger,
        now=current_time,
    )

    return chat


def create_today_additional_chat(
    database_url: str,
    timezone_name: str,
    now: datetime | None = None,
) -> Chat:
    """사용자 타임존 기준 오늘의 추가 학습 채팅을 생성합니다."""
    created_at = _current_study_time(now)
    study_date = _today_study_date(timezone_name, created_at)

    return create_additional_chat(database_url, study_date, created_at)
