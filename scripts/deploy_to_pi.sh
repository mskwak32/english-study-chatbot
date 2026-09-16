#!/usr/bin/env bash
# 개발 PC에서 검증한 release를 Pi에 rsync로 전송하고 Agent만 재시작합니다.
# Pi의 .env, data, backups와 Ollama 모델은 rsync 대상에서 제외합니다.

set -euo pipefail

readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "$SCRIPT_DIRECTORY/.." && pwd)"
readonly PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"

fail() {
    printf '실패: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf '%s\n' '사용법: ./scripts/deploy_to_pi.sh <Pi-SSH-대상> <Pi-프로젝트-절대경로>'
}

require_command() {
    command -v "$1" > /dev/null || fail "$1 명령을 찾을 수 없음"
}

[[ $# -eq 2 ]] || {
    usage
    exit 1
}

readonly PI_TARGET="$1"
readonly PI_PROJECT_DIRECTORY="$2"

[[ "$PI_TARGET" =~ ^[A-Za-z0-9][A-Za-z0-9._@-]*$ ]] || fail \
    'Pi SSH 대상은 SSH config 별칭 또는 user@host 형식이어야 함'
[[ "$PI_PROJECT_DIRECTORY" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail \
    'Pi 프로젝트 경로는 공백 없는 절대 경로여야 함'

require_command git
require_command npm
require_command rsync
require_command ssh

cd "$PROJECT_ROOT"

[[ -x "$PYTHON_BIN" ]] || fail "Python 실행 파일을 찾을 수 없음: $PYTHON_BIN"
[[ -z "$(git status --porcelain)" ]] || fail '미커밋 또는 untracked 변경이 있음'

readonly GIT_COMMIT="$(git rev-parse --verify HEAD)"
readonly RELEASE_NAME="$(git rev-parse --short=12 HEAD)"
readonly PI_PYTHON_BIN="${PI_PYTHON_BIN:-python3}"

[[ "$PI_PYTHON_BIN" =~ ^[A-Za-z0-9._/-]+$ ]] || fail \
    'PI_PYTHON_BIN은 공백 없는 Python 실행 파일 경로여야 함'

printf '%s\n' 'Python 테스트 실행'
(cd backend && "$PYTHON_BIN" -m pytest)

printf '%s\n' 'Web 테스트 실행'
npm --prefix web test

# release 이름은 Git commit의 12자리 SHA로 제한하여 원격 경로를 고정합니다.
ssh "$PI_TARGET" bash -s -- "$PI_PROJECT_DIRECTORY" "$RELEASE_NAME" <<'REMOTE_PREPARE'
set -euo pipefail

project_root="$1"
release_name="$2"
releases_directory="$project_root/releases"
staging_directory="$releases_directory/.incoming-$release_name"
release_directory="$releases_directory/$release_name"

test -d "$project_root" || {
    printf '실패: Pi 프로젝트 디렉터리가 없음: %s\n' "$project_root" >&2
    exit 1
}
test ! -e "$release_directory" || {
    printf '실패: 같은 commit release가 이미 있음: %s\n' "$release_directory" >&2
    exit 1
}

mkdir -p "$releases_directory"
mkdir "$staging_directory"
REMOTE_PREPARE

readonly PI_STAGING_DIRECTORY="$PI_PROJECT_DIRECTORY/releases/.incoming-$RELEASE_NAME"

printf '%s\n' 'release 파일 rsync 전송'
rsync -a --delete \
    --exclude '.git/' \
    --exclude '.venv/' \
    --exclude 'data/' \
    --exclude 'backups/' \
    --exclude 'releases/' \
    --exclude 'current' \
    --exclude '.env' \
    --exclude '.deployment/' \
    --exclude 'artifacts/' \
    --exclude 'node_modules/' \
    --exclude 'backend/tests/' \
    --exclude 'web/tests/' \
    --exclude '.pytest_cache/' \
    --exclude '.ruff_cache/' \
    --exclude '__pycache__/' \
    --exclude '*.egg-info/' \
    --exclude '.DS_Store' \
    "$PROJECT_ROOT/" "$PI_TARGET:$PI_STAGING_DIRECTORY/"

# release 안의 Pi 스크립트를 실행하므로 sudo 비밀번호가 필요하면 현재 터미널에서 입력할 수 있습니다.
ssh -tt "$PI_TARGET" \
    "$PI_STAGING_DIRECTORY/scripts/activate_pi_release.sh" \
    "$PI_PROJECT_DIRECTORY" "$RELEASE_NAME" "$GIT_COMMIT" "$PI_PYTHON_BIN"

printf '%s\n' "PC 검증·Pi rsync 배포 완료: $RELEASE_NAME"
