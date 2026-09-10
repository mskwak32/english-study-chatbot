from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from app.database import (
    Message,
    add_proficiency_test,
    add_study_record,
    initialize_database,
    save_learning_profile,
    save_review_word,
)
from app.services import PromptError, build_chat_prompt


def _prepare_database(tmp_path: Path) -> str:
    """프롬프트 테스트용 빈 DB를 준비합니다."""
    database_url = f"sqlite:///{tmp_path / 'data' / 'chat.db'}"
    initialize_database(database_url)
    return database_url


def _message(message_id: int, role: str, content: str) -> Message:
    """저장된 대화를 대신할 테스트용 Message를 만듭니다."""
    return Message(
        id=message_id,
        chat_id=1,
        role=role,
        content=content,
        sequence=message_id,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


def test_build_chat_prompt_uses_empty_learning_state_for_new_user(
    tmp_path: Path,
) -> None:
    database_url = _prepare_database(tmp_path)

    prompt = build_chat_prompt(
        database_url,
        "영어 튜터 지침",
        "초기 테스트와 주제 로테이션을 적용합니다.",
        [_message(1, "user", "영어 공부 시작")],
    )

    assert prompt[0].role == "system"
    assert "학습 프로필 없음" in prompt[0].content
    assert "실력 테스트 결과 없음" in prompt[0].content
    assert "복습 단어 없음" in prompt[0].content
    assert "학습 이력 없음" in prompt[0].content
    assert "초기 테스트와 주제 로테이션" in prompt[0].content
    assert prompt[1].content == "영어 공부 시작"


def test_build_chat_prompt_combines_database_learning_data_and_full_chat(
    tmp_path: Path,
) -> None:
    database_url = _prepare_database(tmp_path)
    now = datetime(2026, 9, 9, tzinfo=UTC)

    save_learning_profile(
        database_url,
        learner_name="학습자",
        learning_goals="여행 회화",
        current_level="A2",
        strengths="기본 어휘",
        weaknesses="자유 작문",
        updated_at=now,
    )
    add_proficiency_test(
        database_url,
        tested_on=date(2026, 9, 9),
        final_level="A2",
        score_earned=9,
        score_total=13,
        created_at=now,
    )
    save_review_word(
        database_url,
        term="recommend",
        explanation="추천하다",
        last_wrong_on=date(2026, 9, 9),
        correct_streak=0,
        updated_at=now,
    )
    records = [
        add_study_record(
            database_url,
            study_date=date(2026, 9, day),
            topic=f"주제 {day}",
            created_at=datetime(2026, 9, day, tzinfo=UTC),
        )
        for day in range(1, 7)
    ]
    conversation = [
        _message(
            index,
            "user" if index % 2 == 1 else "assistant",
            f"메시지 {index}",
        )
        for index in range(1, 10)
    ]

    prompt = build_chat_prompt(
        database_url,
        "영어 튜터 지침",
        "초기 테스트와 주제 로테이션을 적용합니다.",
        conversation,
    )

    system_context = prompt[0].content
    assert "현재 레벨: A2" in system_context
    assert "점수: 9/13" in system_context
    assert "recommend: 추천하다" in system_context
    assert records[0].topic not in system_context
    assert all(record.topic in system_context for record in records[1:])

    # 최근 8개로 자르지 않고 같은 채팅의 전체 메시지를 유지합니다.
    assert [message.content for message in prompt[1:]] == [
        f"메시지 {index}" for index in range(1, 10)
    ]


def test_build_chat_prompt_rejects_invalid_current_message(
    tmp_path: Path,
) -> None:
    database_url = _prepare_database(tmp_path)

    with pytest.raises(PromptError, match="마지막 메시지"):
        build_chat_prompt(
            database_url,
            "영어 튜터 지침",
            "영어 학습 가이드라인",
            [_message(1, "assistant", "사용자 입력이 아님")],
        )

    with pytest.raises(PromptError, match="4,000자"):
        build_chat_prompt(
            database_url,
            "영어 튜터 지침",
            "영어 학습 가이드라인",
            [_message(1, "user", "a" * 4_001)],
        )
