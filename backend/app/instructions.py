"""영어 튜터의 고정 런타임 지침을 읽고 검증합니다."""

from pathlib import Path

AGENT_INSTRUCTIONS_FILENAME = "AGENT.md"
STUDY_GUIDELINES_FILENAME = "영어_가이드라인.md"
INITIAL_ASSESSMENT_INSTRUCTIONS_FILENAME = "초기_실력_테스트.md"


class InstructionLoadingError(RuntimeError):
    """필수 런타임 문서를 읽을 수 없을 때 발생합니다."""


def _load_required_document(instructions_path: Path, filename: str) -> str:
    """필수 UTF-8 지침 문서를 읽고 비어 있지 않은지 확인합니다."""
    document_path = instructions_path.resolve() / filename

    # 지정 디렉터리의 고정 파일명만 읽고, 최종 파일의 심볼릭 링크는 거부합니다.
    if document_path.is_symlink():
        raise InstructionLoadingError(f"{filename}은 심볼릭 링크일 수 없습니다.")

    if not document_path.is_file():
        raise InstructionLoadingError(f"필수 런타임 문서가 없습니다: {document_path}")

    try:
        content = document_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise InstructionLoadingError(
            f"{filename}은 UTF-8 텍스트여야 합니다."
        ) from error
    except OSError as error:
        raise InstructionLoadingError(
            f"필수 런타임 문서를 읽을 수 없습니다: {document_path}"
        ) from error

    if not content.strip():
        raise InstructionLoadingError(f"{filename}은 비어 있을 수 없습니다.")

    return content


def load_agent_instructions(instructions_path: Path) -> str:
    """영어 튜터의 고정 런타임 지침을 반환합니다."""
    return _load_required_document(
        instructions_path,
        AGENT_INSTRUCTIONS_FILENAME,
    )


def load_study_guidelines(instructions_path: Path) -> str:
    """일반 학습 세션의 레벨과 주제 선택 지침을 반환합니다."""
    return _load_required_document(
        instructions_path,
        STUDY_GUIDELINES_FILENAME,
    )


def load_initial_assessment_instructions(instructions_path: Path) -> str:
    """초기 실력 테스트 세션 전용 지침을 반환합니다."""
    return _load_required_document(
        instructions_path,
        INITIAL_ASSESSMENT_INSTRUCTIONS_FILENAME,
    )
