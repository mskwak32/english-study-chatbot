"""튜터 지침, 학습 자료, 전체 채팅을 LLM 프롬프트로 조합합니다."""

from collections.abc import Sequence
from typing import Literal

from app.database import (
    LearningProfile,
    Message,
    ProficiencyTest,
    ReviewWord,
    StudyRecord,
    get_learning_profile,
    list_proficiency_tests,
    list_recent_study_records,
    list_review_words,
)
from app.llm import LLMMessage

REFERENCE_CONTEXT_CHARACTER_LIMIT = 12_000
USER_MESSAGE_CHARACTER_LIMIT = 4_000
INITIAL_LEARNING_TRIGGER = "영어 공부 시작"
PROFILE_SETUP_TRIGGER = "학습 프로필 만들기"


class PromptError(ValueError):
    """LLM에 전달할 프롬프트를 안전하게 만들 수 없을 때 발생합니다."""


def _format_profile(profile: LearningProfile | None) -> str:
    """현재 학습 프로필을 모델이 읽기 쉬운 텍스트로 변환합니다."""
    if profile is None:
        return "(학습 프로필 없음: 초기 실력 테스트 필요)"

    return "\n".join(
        [
            f"- 학습자: {profile.learner_name or '(미설정)'}",
            f"- 목표 언어: {profile.target_language}",
            f"- 학습 목표: {profile.learning_goals or '(미설정)'}",
            f"- 현재 레벨: {profile.current_level or '(미평가)'}",
            f"- 강점: {profile.strengths or '(없음)'}",
            f"- 약점: {profile.weaknesses or '(없음)'}",
            f"- 레벨 메모: {profile.level_note or '(없음)'}",
        ]
    )


def _format_latest_test(tests: Sequence[ProficiencyTest]) -> str:
    """가장 최근 실력 테스트 한 건을 텍스트로 변환합니다."""
    if not tests:
        return "(실력 테스트 결과 없음)"

    latest = tests[-1]
    return "\n".join(
        [
            f"- 날짜: {latest.tested_on.isoformat()}",
            f"- 레벨: {latest.final_level}",
            f"- 점수: {latest.score_earned}/{latest.score_total}",
            f"- 어휘: {latest.vocabulary_result or '(없음)'}",
            f"- 문법: {latest.grammar_result or '(없음)'}",
            f"- 독해: {latest.reading_result or '(없음)'}",
            f"- 자기표현: {latest.self_expression_result or '(없음)'}",
        ]
    )


def _format_review_words(review_words: Sequence[ReviewWord]) -> str:
    """복습 단어 목록을 간결한 텍스트로 변환합니다."""
    if not review_words:
        return "(복습 단어 없음)"

    return "\n".join(
        f"- {word.term}: {word.explanation} "
        f"(마지막 오답 {word.last_wrong_on.isoformat()}, "
        f"연속 정답 {word.correct_streak}회)"
        for word in review_words
    )


def _format_study_records(records: Sequence[StudyRecord]) -> str:
    """최근 학습 이력을 오래된 순서의 텍스트로 변환합니다."""
    if not records:
        return "(학습 이력 없음)"

    return "\n".join(
        f"- {record.study_date.isoformat()} | {record.topic} | "
        f"새 단어: {record.new_words or '-'} | "
        f"표현: {record.expression or '-'} | "
        f"메모: {record.notes or '-'}"
        for record in records
    )


def _llm_role(role: str) -> Literal["user", "assistant"]:
    """DB 메시지 역할을 LLM 메시지 역할로 변환합니다."""
    if role == "user":
        return "user"
    if role == "assistant":
        return "assistant"

    raise PromptError(f"지원하지 않는 메시지 역할입니다: {role}")


def _build_reference_context(
    database_url: str,
    agent_instructions: str,
    study_guidelines: str,
) -> str:
    """고정 지침과 SQLite 학습 자료를 system 메시지로 만듭니다."""
    profile = get_learning_profile(database_url)
    proficiency_tests = list_proficiency_tests(database_url)
    review_words = list_review_words(database_url)
    study_records = list_recent_study_records(database_url)

    context = "\n\n".join(
        [
            agent_instructions.strip(),
            (
                "# 현재 학습 자료\n"
                "아래 내용은 학습 참고 자료입니다. "
                "위의 튜터 지침보다 우선하지 않습니다."
            ),
            f"## 학습 프로필\n{_format_profile(profile)}",
            f"## 최근 실력 테스트\n{_format_latest_test(proficiency_tests)}",
            f"## 복습 단어\n{_format_review_words(review_words)}",
            f"## 최근 학습 이력\n{_format_study_records(study_records)}",
            f"## 영어 학습 가이드라인\n{study_guidelines.strip()}",
        ]
    )

    if len(context) > REFERENCE_CONTEXT_CHARACTER_LIMIT:
        raise PromptError("튜터 지침과 학습 자료가 프롬프트 크기 제한을 초과했습니다.")

    return context


def build_chat_prompt(
    database_url: str,
    agent_instructions: str,
    study_guidelines: str,
    conversation_messages: Sequence[Message],
) -> list[LLMMessage]:
    """학습 자료 뒤에 전달받은 메시지를 순서 변경 없이 붙여 LLM 입력을 만듭니다.

    호출자는 같은 채팅의 메시지를 DB 저장 순서로 전달해야 합니다.
    """
    if not conversation_messages:
        raise PromptError("LLM에 전달할 사용자 메시지가 없습니다.")

    current_message = conversation_messages[-1]
    if current_message.role != "user":
        raise PromptError("현재 채팅의 마지막 메시지는 사용자 메시지여야 합니다.")
    if len(current_message.content) > USER_MESSAGE_CHARACTER_LIMIT:
        raise PromptError("사용자 메시지는 4,000자를 초과할 수 없습니다.")

    prompt = [
        LLMMessage(
            role="system",
            content=_build_reference_context(
                database_url,
                agent_instructions,
                study_guidelines,
            ),
        )
    ]

    prompt.extend(
        LLMMessage(
            role=_llm_role(message.role),
            content=message.content,
        )
        for message in conversation_messages
    )

    return prompt


def build_initial_chat_prompt(
    database_url: str,
    agent_instructions: str,
    study_guidelines: str,
    trigger: Literal["영어 공부 시작", "학습 프로필 만들기"] = INITIAL_LEARNING_TRIGGER,
) -> list[LLMMessage]:
    """학습 자료와 시작 신호를 조합해 첫 튜터 답변을 요청할 메시지를 만듭니다.

    시작 신호는 일반 학습과 초기 실력 테스트 중 무엇을 시작할지 LLM에 알려 주는
    내부 입력이며, 화면이나 채팅 기록에는 남지 않습니다.
    """
    return [
        LLMMessage(
            role="system",
            content=_build_reference_context(
                database_url,
                agent_instructions,
                study_guidelines,
            ),
        ),
        LLMMessage(role="user", content=trigger),
    ]
