from collections.abc import Callable
from pathlib import Path

import pytest
from app.workspace import (
    AGENT_INSTRUCTIONS_FILENAME,
    STUDY_GUIDELINES_FILENAME,
    WorkspaceInitializationError,
    load_agent_instructions,
    load_study_guidelines,
)

RuntimeDocumentLoader = Callable[[Path], str]
RUNTIME_DOCUMENTS = (
    (load_agent_instructions, AGENT_INSTRUCTIONS_FILENAME),
    (load_study_guidelines, STUDY_GUIDELINES_FILENAME),
)


def test_loads_required_runtime_documents(tmp_path: Path) -> None:
    (tmp_path / AGENT_INSTRUCTIONS_FILENAME).write_text(
        "영어 튜터 지침",
        encoding="utf-8",
    )
    (tmp_path / STUDY_GUIDELINES_FILENAME).write_text(
        "영어 학습 가이드라인",
        encoding="utf-8",
    )

    assert load_agent_instructions(tmp_path) == "영어 튜터 지침"
    assert load_study_guidelines(tmp_path) == "영어 학습 가이드라인"


@pytest.mark.parametrize(("loader", "filename"), RUNTIME_DOCUMENTS)
def test_rejects_missing_runtime_document(
    tmp_path: Path,
    loader: RuntimeDocumentLoader,
    filename: str,
) -> None:
    with pytest.raises(
        WorkspaceInitializationError,
        match="필수 런타임 문서가 없습니다",
    ):
        loader(tmp_path)


@pytest.mark.parametrize(("loader", "filename"), RUNTIME_DOCUMENTS)
def test_rejects_empty_runtime_document(
    tmp_path: Path,
    loader: RuntimeDocumentLoader,
    filename: str,
) -> None:
    (tmp_path / filename).write_text("   \n", encoding="utf-8")

    with pytest.raises(
        WorkspaceInitializationError,
        match="비어 있을 수 없습니다",
    ):
        loader(tmp_path)


@pytest.mark.parametrize(("loader", "filename"), RUNTIME_DOCUMENTS)
def test_rejects_runtime_document_symlink(
    tmp_path: Path,
    loader: RuntimeDocumentLoader,
    filename: str,
) -> None:
    outside_path = tmp_path.parent / f"outside-{filename}"
    outside_path.write_text("workspace 밖의 내용", encoding="utf-8")
    (tmp_path / filename).symlink_to(outside_path)

    with pytest.raises(
        WorkspaceInitializationError,
        match="심볼릭 링크",
    ):
        loader(tmp_path)
