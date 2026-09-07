import os
import tempfile
from pathlib import Path

TEMPLATE_FILENAMES = (
    "영어_학습프로필.md",
    "영어_학습이력.md",
    "영어_복습단어.md",
)

AGENT_INSTRUCTIONS_FILENAME = "AGENT.md"
ALLOWED_FILE_EXTENSIONS = {".md", ".txt"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MiB


class WorkspaceInitializationError(RuntimeError):
    """workspace 초기화에 실패했을 때 사용합니다."""


class WorkspaceFileError(RuntimeError):
    """workspace 파일 도구 실행에 실패했을 때 사용합니다."""


def initialize_learning_documents(workspace_path: Path) -> list[str]:
    """
    누락된 학습 문서만 템플릿으로 생성합니다.

    이미 존재하는 파일은 수정하지 않습니다.
    새로 생성한 파일 이름을 반환합니다.
    """
    # 실제 경로로 정리
    workspace_path = workspace_path.resolve()
    # 폴더가 없으면 만듦
    workspace_path.mkdir(parents=True, exist_ok=True)
    if not workspace_path.is_dir():
        raise WorkspaceInitializationError(
            f"workspace 경로가 폴더가 아닙니다: {workspace_path}"
        )

    # 템플릿 디렉토리
    template_directory = Path(__file__).parent / "templates" / "workspace"
    created_files: list[str] = []

    for filename in TEMPLATE_FILENAMES:
        template_path = template_directory / filename
        destination_path = workspace_path / filename
        # 템플릿 자체가 없을 경우 오류
        if not template_path.is_file():
            raise WorkspaceInitializationError(
                f"템플릿 파일이 없습니다: {template_path}"
            )

        # 심볼릭 링크는 workspace 밖의 파일을 가리킬 수 있으므로 거부
        if destination_path.is_symlink():
            raise WorkspaceInitializationError(
                f"심볼릭 링크는 사용할 수 없습니다: {destination_path}"
            )

        # 기존 기록은 보존
        if destination_path.exists():
            continue
        # 템플릿 읽기
        template_content = template_path.read_text(encoding="utf-8")
        try:
            # "x" 모드는 새 파일일 때만 생성
            # "x": 새파일 생성. 기존 파일이 있으면 FileExistsError 발생
            # "r": 읽기
            # "w": 쓰기. 기존 내용을 모두 지움
            # "a": 이어쓰기. 파일 끝에 추가
            with destination_path.open(
                mode="x",
                encoding="utf-8",
                newline="\n",
            ) as file:
                file.write(template_content)
        except FileExistsError:
            # 동시에 생성된 경우 기존 파일을 덮어쓰지 않음
            continue
        created_files.append(filename)

    return created_files


def load_agent_instructions(workspace_path: Path) -> str:
    """
    workspace/AGENT.md를 읽어 영어 튜터의 런타임 지침을 반환합니다.
    """
    workspace_path = workspace_path.resolve()
    instructions_path = workspace_path / AGENT_INSTRUCTIONS_FILENAME
    if instructions_path.is_symlink():
        raise WorkspaceInitializationError("AGENT.md는 심볼릭 링크일 수 없습니다.")

    if not instructions_path.is_file():
        raise WorkspaceInitializationError(
            f"필수 지침 파일이 없습니다: {instructions_path}"
        )

    try:
        instructions = instructions_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise WorkspaceInitializationError(
            "AGENT.md는 UTF-8 텍스트여야 합니다."
        ) from error
    except OSError as error:
        raise WorkspaceInitializationError(
            f"AGENT.md를 읽을 수 없습니다: {instructions_path}"
        ) from error

    if not instructions.strip():
        raise WorkspaceInitializationError("AGENTS.md는 비어 있을 수 없습니다.")

    return instructions


def resolve_workspace_file(workspace_path: Path, relative_path: str) -> Path:
    """상대 경로를 안전한 workspace 내부 실제 경로로 변환합니다."""
    workspace_root = workspace_path.resolve()
    requested_path = Path(relative_path)

    if requested_path.is_absolute():
        raise WorkspaceFileError("절대 경로는 사용할 수 없습니다.")

    if ".." in requested_path.parts:
        raise WorkspaceFileError("상위 경로(..)는 사용할 수 없습니다.")

    resolved_path = (workspace_root / requested_path).resolve()

    # workspace 폴더의 하위에 있는 지 검사
    if not resolved_path.is_relative_to(workspace_root):
        raise WorkspaceFileError("workspace 밖의 파일에는 접근할 수 없습니다.")

    return resolved_path


def validate_file_extension(file_path: Path) -> None:
    """파일 확장자가 허용 목록에 있는 지 검사합니다."""

    if file_path.suffix.lower() not in ALLOWED_FILE_EXTENSIONS:
        raise WorkspaceFileError("허용되지 않은 파일 확장자입니다.")


def list_files(workspace_path: Path) -> list[str]:
    """workspace 안의 허용된 파일 목록을 상대 경로로 반환합니다."""

    workspace_root = workspace_path.resolve()

    if not workspace_root.is_dir():
        raise WorkspaceFileError(f"workspace 경로가 폴더가 아닙니다: {workspace_root}")

    files: list[str] = []

    # "*" 패턴으로 모든 파일 탐색(하위 폴더까지)
    for candidate_path in workspace_root.rglob("*"):
        if not candidate_path.is_file():
            continue

        relative_path = candidate_path.relative_to(workspace_root).as_posix()

        try:
            safe_path = resolve_workspace_file(workspace_root, relative_path)
            validate_file_extension(safe_path)
        except WorkspaceFileError:
            continue

        files.append(relative_path)

    return sorted(files)


def read_file(workspace_path: Path, relative_path: str) -> str:
    """workspace 안의 허용된 UTF-8 텍스트 파일을 읽습니다."""

    file_path = resolve_workspace_file(workspace_path, relative_path)
    validate_file_extension(file_path)

    if not file_path.is_file():
        raise WorkspaceFileError(f"파일이 없습니다: {relative_path}")

    if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
        raise WorkspaceFileError("파일 크기는 5 MiB를 초과할 수 없습니다.")

    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise WorkspaceFileError("파일은 UTF-8 텍스트여야 합니다.") from error
    except OSError as error:
        raise WorkspaceFileError(f"파일을 읽을 수 없습니다: {relative_path}") from error


def validate_content_size(content: str) -> None:
    """UTF-8로 인코딩한 텍스트가 최대 크기를 넘지 않는지 검사합니다."""

    content_size = len(content.encode("utf-8"))

    if content_size > MAX_FILE_SIZE_BYTES:
        raise WorkspaceFileError("파일 내용은 5 MiB를 초과할 수 없습니다.")


def write_text_atomically(file_path: Path, content: str) -> None:
    """임시 파일을 만든 뒤 대상 파일과 원자적으로 교체합니다."""
    temporary_path: Path | None = None

    try:
        # 대상 파일과 같은 폴더에 임시 파일을 만든다.
        # 같은 파일시스템이어야 os.replace()가 원자적으로 동작.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=file_path.parent,
            prefix=".workspace-",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)

        # 기존 파일이 있으면 교체하고, 없으면 새 파일로 만든다.
        os.replace(temporary_path, file_path)

    except OSError as error:
        raise WorkspaceFileError(f"파일을 쓸 수 없습니다: {file_path.name}") from error

    finally:
        # os.replace()가 성공하면 임시 파일은 이미 없어짐.
        # 실패했을 때 남은 임시 파일만 정리.
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def write_file(workspace_path: Path, relative_path: str, content: str) -> None:
    """workspace 안의 허용된 파일에 UTF-8 텍스트를 원자적으로 씁니다."""
    file_path = resolve_workspace_file(workspace_path, relative_path)
    validate_file_extension(file_path)
    validate_content_size(content)

    # 부모 폴더가 없으면 생성
    file_path.parent.mkdir(parents=True, exist_ok=True)

    write_text_atomically(file_path, content)


def append_file(workspace_path: Path, relative_path: str, content: str) -> None:
    """파일 끝에 UTF-8 텍스트를 추가합니다. 파일이 없으면 새로 만듭니다."""
    file_path = resolve_workspace_file(workspace_path, relative_path)
    validate_file_extension(file_path)

    if file_path.exists():
        existing_content = read_file(workspace_path, relative_path)
    else:
        existing_content = ""

    combined_content = existing_content + content
    write_file(workspace_path, relative_path, combined_content)
