from pathlib import Path

TEMPLATE_FILENAMES = (
    "영어_학습프로필.md",
    "영어_학습이력.md",
    "영어_복습단어.md",
)

AGENT_INSTRUCTIONS_FILENAME = "AGENT.md"


class WorkspaceInitializationError(RuntimeError):
    """workspace 초기화에 실패했을 때 사용합니다."""


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
        raise WorkspaceInitializationError(
            "AGENT.md는 심볼릭 링크일 수 없습니다."
        )

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
        raise WorkspaceInitializationError(
            "AGENTS.md는 비어 있을 수 없습니다."
        )

    return instructions
