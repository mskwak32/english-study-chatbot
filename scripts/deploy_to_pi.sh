#!/usr/bin/env bash
# PC 테스트 후 소스를 Pi로 전송하고 Pi에서 Agent image를 빌드·교체
# Pi의 .env, data, backups, Ollama 모델은 전송하거나 변경하지 않음

# 명령 실패·미정의 변수·파이프라인 실패를 즉시 중단해 불완전한 배포를 막음
set -euo pipefail

# 스크립트 위치를 기준으로 프로젝트와 로컬 테스트 Python을 찾음
readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "$SCRIPT_DIRECTORY/.." && pwd)"
readonly PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"

fail() {
    # 동일한 형식으로 오류를 출력하고 성공처럼 다음 단계가 계속되지 않게 종료
    printf '실패: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf '%s\n' '사용법: ./scripts/deploy_to_pi.sh <Pi-SSH-대상> <Pi-프로젝트-절대경로>'
}

require_command() {
    # 실제 명령을 실행하기 전에 개발 PC에 필요한 도구가 있는지 확인
    command -v "$1" > /dev/null || fail "$1 명령을 찾을 수 없음"
}

# 첫 인수는 SSH 로그인 대상, 둘째 인수는 Pi의 프로젝트 절대 경로
[[ $# -eq 2 ]] || {
    usage
    exit 1
}

readonly PI_TARGET="$1"
readonly PI_PROJECT_DIRECTORY="$2"

# 경로와 SSH 대상에 셸 제어 문자가 들어가지 않게 제한함
[[ "$PI_TARGET" =~ ^[A-Za-z0-9][A-Za-z0-9._@-]*$ ]] || fail \
    'Pi SSH 대상은 SSH config 별칭 또는 user@host 형식이어야 함'
[[ "$PI_PROJECT_DIRECTORY" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail \
    'Pi 프로젝트 경로는 공백 없는 절대 경로여야 함'

# git은 커밋 태그, npm·Python은 테스트, rsync·ssh는 전송에 사용
require_command git
require_command npm
require_command rsync
require_command ssh

cd "$PROJECT_ROOT"

[[ -x "$PYTHON_BIN" ]] || fail "Python 실행 파일을 찾을 수 없음: $PYTHON_BIN"
# 전송하는 소스와 이미지 태그가 같은 Git 커밋을 가리키게 함
[[ -z "$(git status --porcelain)" ]] || fail '미커밋 또는 untracked 변경이 있음'

# 12자리 커밋 SHA를 Pi에서 빌드할 이미지 태그로 사용
readonly AGENT_TAG="$(git rev-parse --short=12 HEAD)"
[[ "$AGENT_TAG" =~ ^[0-9a-f]{12}$ ]] || fail 'Git commit 태그 형식이 올바르지 않음'

# 테스트가 실패하면 set -e 때문에 rsync와 Pi 변경을 전혀 실행하지 않음
printf '%s\n' 'Python 테스트 실행'
(cd backend && "$PYTHON_BIN" -m pytest)

printf '%s\n' 'Web 테스트 실행'
npm --prefix web test

# rsync 대상 디렉터리를 먼저 만든다. <<'이름'부터 이름까지의 본문은
# 로컬이 아닌 Pi의 bash에서 실행되고, $변수도 로컬에서 미리 바뀌지 않음
ssh "$PI_TARGET" bash -s -- "$PI_PROJECT_DIRECTORY" <<'REMOTE_PREPARE'
set -euo pipefail

project_directory="$1"
[[ "$project_directory" =~ ^/[A-Za-z0-9._/-]+$ ]] || {
    printf '%s\n' '실패: Pi 프로젝트 경로 형식이 올바르지 않음' >&2
    exit 1
}
mkdir -p -- "$project_directory"
REMOTE_PREPARE

printf '%s\n' 'Pi 프로젝트 파일 rsync 전송'
# -a는 파일 권한·수정 시각 등을 보존하는 archive 모드.
# --delete는 로컬에서 제거된 소스 파일을 Pi에서도 제거해 코드가 섞이지 않게 함.
# 다만 아래 exclude 대상은 --delete의 대상도 아니므로 Pi의 운영 데이터가 보존됨.
# .env는 Pi 비밀값·환경별 설정이고, data/는 실제 SQLite DB임.
# backups/는 사용자가 만든 DB 백업이며 .deployment/은 현재·직전 이미지 태그 기록임.
# 개발용 문서·지침·테스트·캐시·로컬 전용 스크립트는 Docker build와 실행에 필요하지 않음.
rsync -a --delete \
    --exclude '.env' \
    --exclude '.git/' \
    --exclude '.venv/' \
    --exclude 'data/' \
    --exclude 'backups/' \
    --exclude '.deployment/' \
    --exclude '.runtime-test/' \
    --exclude 'artifacts/' \
    --exclude 'AGENTS.md' \
    --exclude 'TODO.md' \
    --exclude 'plan.ai.md' \
    --exclude 'docs/' \
    --exclude 'scripts/' \
    --exclude '.gitignore' \
    --exclude 'backend/scripts/' \
    --exclude 'backend/tests/' \
    --exclude 'web/tests/' \
    --exclude 'web/package.json' \
    --exclude 'node_modules/' \
    --exclude '**/node_modules/' \
    --exclude '.pytest_cache/' \
    --exclude '**/.pytest_cache/' \
    --exclude '.ruff_cache/' \
    --exclude '**/.ruff_cache/' \
    --exclude '**/__pycache__/' \
    --exclude '**/*.egg-info/' \
    --exclude '**/*.pyc' \
    --exclude '.DS_Store' \
    "$PROJECT_ROOT/" "$PI_TARGET:$PI_PROJECT_DIRECTORY/"

# 큰따옴표 문자열 대신 heredoc 인수로 전달해 원격 셸 확장을 피함
ssh "$PI_TARGET" bash -s -- "$PI_PROJECT_DIRECTORY" "$AGENT_TAG" <<'REMOTE_DEPLOY'
set -euo pipefail

project_directory="$1"
agent_tag="$2"
state_directory="$project_directory/.deployment"
state_path="$state_directory/agent-tags"

fail() {
    # 원격 단계도 오류를 즉시 종료해 태그 기록을 잘못 쓰지 않음
    printf '실패: %s\n' "$*" >&2
    exit 1
}

wait_for_agent_healthy() {
    local container_id health_status

    # healthcheck가 healthy가 될 때까지 최대 60초 기다림
    for _ in {1..30}; do
        # -q는 컨테이너 ID만 출력한다. 그 ID로 Docker healthcheck 상태를 읽음
        container_id="$(AGENT_TAG="$agent_tag" docker compose ps -q agent < /dev/null)"
        [[ -n "$container_id" ]] || return 1
        health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id" < /dev/null)"
        [[ "$health_status" == 'healthy' ]] && return 0
        sleep 2 # healthcheck interval보다 짧게 반복 확인
    done

    return 1
}

wait_for_ollama_healthy() {
    local health_status

    # Agent를 빌드하기 전에 Ollama 서버가 요청을 받을 준비를 확인.
    # 모델 파일이 없더라도 컨테이너 자체가 healthy일 수 있어 뒤에서 show를 추가로 실행함.
    for _ in {1..30}; do
        health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$ollama_container_id" < /dev/null)"
        [[ "$health_status" == 'healthy' ]] && return 0
        sleep 2
    done

    return 1
}

# ssh로 받은 값도 다시 검증한다. 로컬 검증만 믿지 않아 원격 명령의 대상 범위를 고정함
[[ "$project_directory" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail 'Pi 프로젝트 경로 형식이 올바르지 않음'
[[ "$agent_tag" =~ ^[0-9a-f]{12}$ ]] || fail 'Agent 태그 형식이 올바르지 않음'
command -v docker > /dev/null || fail 'docker 명령을 찾을 수 없음'
command -v awk > /dev/null || fail 'awk 명령을 찾을 수 없음'
command -v stat > /dev/null || fail 'stat 명령을 찾을 수 없음'

cd -- "$project_directory"
if [[ ! -f .env ]]; then
    # 최초 한 번만 예시 파일을 Pi 전용 설정 파일로 복사.
    # 이후 rsync는 .env를 제외하므로 이 블록은 기존 Pi 설정을 덮어쓰지 않음.
    [[ -f .env.example ]] || fail 'Pi .env와 .env.example 파일을 찾을 수 없음'
    cp -- .env.example .env
    chmod 600 .env
    printf '%s\n' 'Pi .env를 .env.example 기본값으로 생성함. 필요한 값은 Pi에서 수정해야 함'
fi
# 이미지 안의 app 사용자(UID/GID 10001)가 SQLite 파일을 쓸 수 있어야 함.
# 호스트 data/가 다른 사용자 소유면 컨테이너는 시작해도 DB 생성·기록에서 실패함.
[[ -d data ]] || fail 'Pi data 디렉터리를 찾을 수 없음. 최초 설정의 소유권 명령을 먼저 실행해야 함'
[[ "$(stat -c '%u:%g' data)" == '10001:10001' ]] || fail \
    'Pi data 디렉터리 소유자는 10001:10001이어야 함. 최초 설정의 chown 명령을 확인해야 함'

# Agent 이미지가 아직 없어도 Ollama만 먼저 시작할 수 있도록 임시 태그 사용.
# compose.yaml의 agent image 변수 해석만 위한 값이며 bootstrap 이미지를 빌드하거나 실행하지 않음.
# 원격 Bash가 SSH 표준입력에서 읽는 나머지 스크립트를 Docker가 소비하지 못하게 함.
AGENT_TAG=bootstrap docker compose up -d ollama < /dev/null
ollama_container_id="$(AGENT_TAG=bootstrap docker compose ps -q ollama < /dev/null)"
[[ -n "$ollama_container_id" ]] || fail '실행 중인 Ollama 컨테이너를 찾을 수 없음'
wait_for_ollama_healthy || fail 'Ollama health 확인 실패'

# .env의 MODEL 값이 없으면 기본 모델을 사용하고, 모델 다운로드 여부만 읽기 전용 확인.
# 모델이 없을 때 자동 pull하지 않아 큰 다운로드가 배포 중 예고 없이 시작되지 않게 함.
model="$(awk -F= '$1 == "MODEL" { value = substr($0, length($1) + 2); sub(/\r$/, "", value); print value; exit }' .env)"
model="${model:-gemma3:4b}"
[[ "$model" =~ ^[A-Za-z0-9._:/@-]+$ ]] || fail 'MODEL 값 형식이 올바르지 않음'
docker compose exec -T ollama ollama show "$model" < /dev/null > /dev/null || fail \
    "Ollama 모델이 없음: $model. Pi에서 docker compose exec ollama ollama pull $model 실행 후 배포를 다시 실행해야 함"

current_tag='none'
previous_tag='none'
if [[ -f "$state_path" ]]; then
    # 태그 두 개만 보관해 한 단계 롤백에 사용.
    # 이미지 자체를 지우지 않으므로 오래된 태그가 Docker에 남을 수 있음.
    current_tag="$(awk -F= '$1 == "current_tag" { print $2 }' "$state_path")"
    previous_tag="$(awk -F= '$1 == "previous_tag" { print $2 }' "$state_path")"
fi
[[ "$current_tag" == 'none' || "$current_tag" =~ ^[0-9a-f]{12}$ ]] || fail '현재 Agent 태그 기록 형식이 올바르지 않음'
[[ "$previous_tag" == 'none' || "$previous_tag" =~ ^[0-9a-f]{12}$ ]] || fail '직전 Agent 태그 기록 형식이 올바르지 않음'

running_agent_id="$(AGENT_TAG=bootstrap docker compose ps -q agent < /dev/null)"
if [[ -n "$running_agent_id" ]]; then
    # 상태 파일보다 실제 실행 중인 컨테이너의 태그를 우선함.
    # Git SHA가 아닌 태그도 새 배포를 막지 않되, 롤백 대상으로는 기록하지 않음.
    running_image="$(docker inspect --format '{{.Config.Image}}' "$running_agent_id" < /dev/null)"
    if [[ "$running_image" =~ ^english-study-agent:([0-9a-f]{12})$ ]]; then
        current_tag="${BASH_REMATCH[1]}"
    else
        current_tag='none'
        previous_tag='none'
        printf '%s\n' "Git SHA가 아닌 실행 중 Agent image는 롤백 기록에 포함하지 않음: $running_image"
    fi
fi

printf '%s\n' "Pi에서 Agent image 빌드: $agent_tag"
# Dockerfile이 현재 rsync된 코드와 instructions를 이미지에 복사.
# 이 명령은 Pi CPU에서 실행되며, 같은 의존성 layer는 Docker cache를 재사용할 수 있음.
AGENT_TAG="$agent_tag" docker compose build agent < /dev/null
# --no-deps는 Ollama를 다시 만들지 않고 Agent만 교체.
# SQLite bind mount와 Ollama named volume도 Compose 정의를 변경하지 않아 그대로 유지됨.
AGENT_TAG="$agent_tag" docker compose up -d --no-deps agent < /dev/null
wait_for_agent_healthy || fail '새 Agent health 확인 실패. 롤백은 rollback_to_pi.sh를 명시적으로 실행해야 함'

[[ "$(AGENT_TAG="$agent_tag" docker compose ps -q ollama < /dev/null)" == "$ollama_container_id" ]] || fail \
    'Agent 업데이트 중 Ollama 컨테이너가 변경됨'

if [[ "$current_tag" != "$agent_tag" ]]; then
    previous_tag="$current_tag"
fi
mkdir -p -- "$state_directory"
# 임시 파일을 이동해 기록 도중 전원 장애가 나도 기존 태그 기록을 보존.
# mv는 같은 디렉터리 안에서 이름만 바꾸므로 완성된 두 줄만 상태 파일로 보임.
temporary_path="$(mktemp "$state_directory/agent-tags.XXXXXX")"
printf 'current_tag=%s\nprevious_tag=%s\n' "$agent_tag" "$previous_tag" > "$temporary_path"
mv -- "$temporary_path" "$state_path"

printf '%s\n' "Agent 배포 완료: english-study-agent:$agent_tag"
REMOTE_DEPLOY

printf '%s\n' "PC 테스트·Pi Agent 배포 완료: $AGENT_TAG"
