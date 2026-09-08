from pathlib import Path

import pytest
from app.workspace import (
    AGENT_INSTRUCTIONS_FILENAME,
    MAX_FILE_SIZE_BYTES,
    TEMPLATE_FILENAMES,
    WorkspaceFileError,
    WorkspaceInitializationError,
    append_file,
    initialize_learning_documents,
    list_files,
    load_agent_instructions,
    read_file,
    write_file,
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


def test_list_files_returns_allowed_workspace_files(tmp_path: Path) -> None:
    (tmp_path / "학습.md").write_text("학습 내용", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "memo.txt").write_text("메모", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"image")

    result = list_files(tmp_path)

    assert result == ["notes/memo.txt", "학습.md"]


def test_read_file_returns_utf8_text(tmp_path: Path) -> None:
    (tmp_path / "학습.md").write_text("영어 학습 내용", encoding="utf-8")

    result = read_file(tmp_path, "학습.md")

    assert result == "영어 학습 내용"


def test_write_file_creates_and_overwrites_file(tmp_path: Path) -> None:
    write_file(tmp_path, "notes/today.md", "첫 번째 내용")

    assert (tmp_path / "notes" / "today.md").read_text(
        encoding="utf-8"
    ) == "첫 번째 내용"

    write_file(tmp_path, "notes/today.md", "교체된 내용")

    assert (tmp_path / "notes" / "today.md").read_text(
        encoding="utf-8"
    ) == "교체된 내용"


def test_append_file_adds_content_to_existing_file(tmp_path: Path) -> None:
    write_file(tmp_path, "학습.md", "첫 문장\n")

    append_file(tmp_path, "학습.md", "둘째 문장\n")

    assert read_file(tmp_path, "학습.md") == "첫 문장\n둘째 문장\n"


def test_append_file_creates_missing_file(tmp_path: Path) -> None:
    append_file(tmp_path, "새_기록.txt", "새 내용")

    assert read_file(tmp_path, "새_기록.txt") == "새 내용"


def test_read_file_rejects_parent_path(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceFileError, match="상위 경로"):
        read_file(tmp_path, "../secret.md")


def test_write_file_rejects_absolute_path(tmp_path: Path) -> None:
    outside_file = tmp_path.parent / "outside.md"

    with pytest.raises(WorkspaceFileError, match="절대 경로"):
        write_file(tmp_path, str(outside_file), "허용되면 안 되는 내용")

    assert not outside_file.exists()


def test_read_file_rejects_symlink_outside_workspace(tmp_path: Path) -> None:
    outside_file = tmp_path.parent / "secret.md"
    outside_file.write_text("외부의 비밀 내용", encoding="utf-8")

    shortcut_path = tmp_path / "shortcut.md"
    shortcut_path.symlink_to(outside_file)

    with pytest.raises(WorkspaceFileError, match="workspace 밖"):
        read_file(tmp_path, "shortcut.md")

    # workspace 밖을 가리키는 링크는 파일 목록에도 포함하지 않음.
    assert list_files(tmp_path) == []


def test_write_file_rejects_symlink_outside_workspace(tmp_path: Path) -> None:
    outside_file = tmp_path.parent / "secret.md"
    outside_file.write_text("변경되면 안 되는 기존 내용", encoding="utf-8")

    shortcut_path = tmp_path / "shortcut.md"
    shortcut_path.symlink_to(outside_file)

    with pytest.raises(WorkspaceFileError, match="workspace 밖"):
        write_file(tmp_path, "shortcut.md", "외부 파일을 덮어쓰려는 내용")

    assert outside_file.read_text(encoding="utf-8") == "변경되면 안 되는 기존 내용"


def test_read_file_rejects_disallowed_extension(tmp_path: Path) -> None:
    (tmp_path / "script.py").write_text("print('hello')", encoding="utf-8")

    with pytest.raises(WorkspaceFileError, match="허용되지 않은 파일 확장자"):
        read_file(tmp_path, "script.py")


def test_write_file_rejects_disallowed_extension(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceFileError, match="허용되지 않은 파일 확장자"):
        write_file(tmp_path, "script.py", "print('hello')")

    assert not (tmp_path / "script.py").exists()


def test_read_file_rejects_oversized_file(tmp_path: Path) -> None:
    oversized_path = tmp_path / "large.md"
    oversized_path.write_bytes(b"a" * (MAX_FILE_SIZE_BYTES + 1))

    with pytest.raises(WorkspaceFileError, match="5 MiB"):
        read_file(tmp_path, "large.md")


def test_write_file_rejects_oversized_content(tmp_path: Path) -> None:
    oversized_content = "a" * (MAX_FILE_SIZE_BYTES + 1)

    with pytest.raises(WorkspaceFileError, match="5 MiB"):
        write_file(tmp_path, "large.md", oversized_content)

    assert not (tmp_path / "large.md").exists()


def test_read_file_rejects_non_utf8_file(tmp_path: Path) -> None:
    (tmp_path / "invalid.txt").write_bytes(b"\xff\xfe\x00")

    with pytest.raises(WorkspaceFileError, match="UTF-8"):
        read_file(tmp_path, "invalid.txt")
