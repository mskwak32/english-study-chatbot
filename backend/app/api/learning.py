"""학습 프로필과 학습 자료를 조회하는 HTTP API를 제공합니다."""

import logging
import sqlite3
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.config import settings
from app.database import (
    DatabaseError,
    LearningProfileError,
    ReviewWordError,
    StudyRecordError,
    get_learning_profile,
    list_recent_study_records,
    list_review_words,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"])


class LearningProfileResponse(BaseModel):
    """현재 학습 프로필을 반환하는 API 응답입니다."""

    model_config = ConfigDict(from_attributes=True)

    learner_name: str
    target_language: str
    learning_goals: str
    session_started_on: date | None
    current_level: str | None
    level_updated_on: date | None
    level_note: str
    strengths: str
    weaknesses: str
    updated_at: datetime


class StudyRecordResponse(BaseModel):
    """학습 이력 한 건을 반환하는 API 응답입니다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int | None
    study_date: date
    topic: str
    new_words: str
    expression: str
    notes: str
    created_at: datetime


class ReviewWordResponse(BaseModel):
    """복습 단어 또는 표현 한 건을 반환하는 API 응답입니다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    term: str
    explanation: str
    last_wrong_on: date
    correct_streak: int
    created_at: datetime
    updated_at: datetime


@router.get(
    "/profile",
    response_model=LearningProfileResponse | None,
    status_code=status.HTTP_200_OK,
)
def read_learning_profile() -> LearningProfileResponse | None:
    """현재 학습 프로필을 반환하고, 없으면 null을 반환합니다."""
    try:
        profile = get_learning_profile(settings.database_url)
    except (DatabaseError, LearningProfileError, sqlite3.Error) as error:
        logger.exception("학습 프로필을 불러오지 못했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="학습 프로필을 불러오지 못했습니다.",
        ) from error

    return LearningProfileResponse.model_validate(profile) if profile else None


@router.get(
    "/study-records",
    response_model=list[StudyRecordResponse],
    status_code=status.HTTP_200_OK,
)
def read_study_records() -> list[StudyRecordResponse]:
    """최근 학습 이력 최대 20건을 최신순으로 반환합니다."""
    try:
        records = list_recent_study_records(settings.database_url, limit=20)
    except (DatabaseError, StudyRecordError, sqlite3.Error) as error:
        logger.exception("학습 이력을 불러오지 못했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="학습 이력을 불러오지 못했습니다.",
        ) from error

    return [StudyRecordResponse.model_validate(record) for record in reversed(records)]


@router.get(
    "/review-words",
    response_model=list[ReviewWordResponse],
    status_code=status.HTTP_200_OK,
)
def read_review_words() -> list[ReviewWordResponse]:
    """저장된 복습 단어와 표현을 저장 계층 순서대로 반환합니다."""
    try:
        review_words = list_review_words(settings.database_url)
    except (DatabaseError, ReviewWordError, sqlite3.Error) as error:
        logger.exception("복습 단어를 불러오지 못했습니다.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="복습 단어를 불러오지 못했습니다.",
        ) from error

    return [ReviewWordResponse.model_validate(review_word) for review_word in review_words]
