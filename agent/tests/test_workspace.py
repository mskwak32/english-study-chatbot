from pathlib import Path

import pytest

from app.workspace import (
    AGENT_INSTRUCTIONS_FILENAME,
    TEMPLATE_FILENAMES,
    WorkspaceInitializationError,
    initialize_learning_documents,
    load_agent_instructions
)


def test_initialize_creates_all_missing_learning_documents(
    tmp_path: Path,
) -> None:
    created_files = initialize_learning_documents(tmp_path)
    assert created_files == list(TEMPLATE_FILENAMES)

    for filename in TEMPLATE_FILENAMES:
        document_path = tmp_path / filename
        assert document_path.is_file()
        assert document_path.read_text(encoding="utf-8") != ""

def test_initialize_preserves_existing_learning_document(
    tmp_path: Path,
) -> None:
    existing_profile = tmp_path / "영어_학습프로필.md"
    existing_profile.write_text("기존 학습 기록", encoding="utf-8")
    created_files = initialize_learning_documents(tmp_path)
    # 기존 파일이 유지되는 지 확인
    assert existing_profile.read_text(encoding="utf-8") == "기존 학습 기록"
    assert "영어_학습프로필.md" not in created_files
    assert (tmp_path / "영어_학습이력.md").is_file()
    assert (tmp_path / "영어_복습단어.md").is_file()

def test_initialize_creates_workspace_directory_when_missing(
    tmp_path: Path,
) -> None:
    workspace_path = tmp_path / "new-workspace"
    initialize_learning_documents(workspace_path)
    assert workspace_path.is_dir()
    assert (workspace_path / "영어_학습프로필.md").is_file()

def test_load_agent_instructions_returns_file_content(
    tmp_path: Path,
) -> None:
    instructions_path = tmp_path / AGENT_INSTRUCTIONS_FILENAME
    instructions_path.write_text(
        "영어 학습을 시작합니다.",
        encoding="utf-8",
    )
    result = load_agent_instructions(tmp_path)
    assert result == "영어 학습을 시작합니다."

def test_load_agent_instructions_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        WorkspaceInitializationError,
        match="필수 지침 파일이 없습니다.",
    ):
        load_agent_instructions(tmp_path)

def test_load_agent_instructions_rejects_empty_file(
    tmp_path: Path,
) -> None:
    instructions_path = tmp_path / AGENT_INSTRUCTIONS_FILENAME
    instructions_path.write_text("   \n", encoding="utf-8")
    with pytest.raises(
        WorkspaceInitializationError,
        match="비어 있을 수 없습니다.",
    ):
        load_agent_instructions(tmp_path)
