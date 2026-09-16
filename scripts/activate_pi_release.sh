#!/usr/bin/env bash
# Pi에서 rsync로 전송된 staging release를 활성화하고 Agent 서비스를 재시작합니다.
# 최초 배포에서만 .env·data·backups·가상환경·systemd 서비스를 준비합니다.

set -euo pipefail

fail() {
    printf '실패: %s\n' "$*" >&2
    exit 1
}

[[ $# -eq 4 ]] || fail '사용법: activate_pi_release.sh <Pi-프로젝트-절대경로> <release-이름> <Git-commit> <Python-실행-파일>'

readonly PROJECT_ROOT="$1"
readonly RELEASE_NAME="$2"
readonly GIT_COMMIT="$3"
readonly PI_PYTHON_BIN="$4"
readonly RELEASES_DIRECTORY="$PROJECT_ROOT/releases"
readonly STAGING_DIRECTORY="$RELEASES_DIRECTORY/.incoming-$RELEASE_NAME"
readonly RELEASE_DIRECTORY="$RELEASES_DIRECTORY/$RELEASE_NAME"
readonly CURRENT_LINK="$PROJECT_ROOT/current"
readonly NEXT_LINK="$PROJECT_ROOT/.current-next-$RELEASE_NAME"
readonly STATE_DIRECTORY="$PROJECT_ROOT/.deployment"
readonly STATE_PATH="$STATE_DIRECTORY/release-state"
readonly VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
readonly SERVICE_NAME='english-study-agent.service'

[[ "$PROJECT_ROOT" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail \
    'Pi 프로젝트 경로는 공백 없는 절대 경로여야 함'
[[ "$RELEASE_NAME" =~ ^[0-9a-f]{12}$ ]] || fail 'release 이름은 12자리 Git SHA여야 함'
[[ "$GIT_COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail 'Git commit은 40자리 SHA여야 함'
[[ "$PI_PYTHON_BIN" =~ ^[A-Za-z0-9._/-]+$ ]] || fail \
    'Python 실행 파일은 공백 없는 경로 또는 명령 이름이어야 함'

write_state() {
    local current_release="$1"
    local previous_release="$2"
    local temporary_path

    mkdir -p "$STATE_DIRECTORY"
    temporary_path="$(mktemp "$STATE_DIRECTORY/release-state.XXXXXX")"
    printf '%s\n' \
        "current_release=$current_release" \
        "previous_release=$previous_release" \
        "git_commit=$GIT_COMMIT" \
        "deployed_at=$(date --iso-8601=seconds)" > "$temporary_path"
    mv "$temporary_path" "$STATE_PATH"
}

restore_previous_release() {
    local previous_target="$1"

    if [[ -n "$previous_target" ]]; then
        ln -s "$previous_target" "$NEXT_LINK"
        mv -Tf "$NEXT_LINK" "$CURRENT_LINK"
        sudo systemctl restart "$SERVICE_NAME" || true
    elif [[ -L "$CURRENT_LINK" ]]; then
        rm "$CURRENT_LINK"
        sudo systemctl stop "$SERVICE_NAME" || true
    fi
}

test -d "$PROJECT_ROOT" || fail "Pi 프로젝트 디렉터리가 없음: $PROJECT_ROOT"
test -d "$STAGING_DIRECTORY" || fail "전송 중인 release 디렉터리가 없음: $STAGING_DIRECTORY"
test ! -e "$RELEASE_DIRECTORY" || fail "같은 commit release가 이미 있음: $RELEASE_DIRECTORY"

# 첫 배포에서만 .env와 영속 디렉터리를 만듭니다. 기존 .env는 덮어쓰지 않습니다.
if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
    install -m 0600 "$STAGING_DIRECTORY/.env.example" "$PROJECT_ROOT/.env"
    printf '\nDATABASE_URL=sqlite:///%s/data/chat.db\n' "$PROJECT_ROOT" >> "$PROJECT_ROOT/.env"
    printf 'INSTRUCTIONS_PATH=%s/current/instructions\n' "$PROJECT_ROOT" >> "$PROJECT_ROOT/.env"
fi
grep -q '^DATABASE_URL=sqlite:////' "$PROJECT_ROOT/.env" || fail \
    'Pi .env에 DATABASE_URL이 없음. release 밖의 data/chat.db 절대 경로를 설정해야 함'
grep -q '^INSTRUCTIONS_PATH=/' "$PROJECT_ROOT/.env" || fail \
    'Pi .env에 INSTRUCTIONS_PATH가 없음. current/instructions 절대 경로를 설정해야 함'

model_name="$(sed -n 's/^MODEL=//p' "$PROJECT_ROOT/.env" | tail -n 1)"
model_name="${model_name:-gemma3:4b}"
command -v ollama > /dev/null || fail '네이티브 Ollama 명령을 찾을 수 없음'
ollama show "$model_name" > /dev/null || fail \
    "Ollama 모델을 확인할 수 없음: $model_name"
command -v curl > /dev/null || fail 'Pi curl 명령을 찾을 수 없음'

mkdir -p "$PROJECT_ROOT/data" "$PROJECT_ROOT/backups" "$STATE_DIRECTORY"
if [[ ! -x "$VENV_PYTHON" ]]; then
    command -v "$PI_PYTHON_BIN" > /dev/null || fail \
        "Pi Python 실행 파일을 찾을 수 없음: $PI_PYTHON_BIN"
    "$PI_PYTHON_BIN" -m venv "$PROJECT_ROOT/.venv" || fail \
        'Pi 가상환경 생성 실패. python3-venv 패키지를 설치해야 함'
fi
"$VENV_PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 13))' || fail \
    'Pi Python은 3.13 이상이어야 함'

# sudo 인증을 한 번만 받아 서비스 설치와 재시작에서 재사용합니다.
sudo -v || fail 'Agent 서비스 설치·재시작용 sudo 권한을 확인할 수 없음'
if ! systemctl cat "$SERVICE_NAME" > /dev/null 2>&1; then
    sudo "$STAGING_DIRECTORY/scripts/install_pi_service.sh" "$PROJECT_ROOT" "$(id -un)"
fi

# 의존성은 전환 전에 설치하여 실패해도 current release를 유지합니다.
"$VENV_PYTHON" -m pip install \
    --disable-pip-version-check \
    --upgrade \
    --force-reinstall \
    --constraint "$STAGING_DIRECTORY/backend/requirements.lock" \
    "$STAGING_DIRECTORY/backend"

mv "$STAGING_DIRECTORY" "$RELEASE_DIRECTORY"
previous_target=''
previous_release='none'
if [[ -L "$CURRENT_LINK" ]]; then
    previous_target="$(readlink "$CURRENT_LINK")"
    previous_release="${previous_target##*/}"
fi

ln -s "releases/$RELEASE_NAME" "$NEXT_LINK"
mv -Tf "$NEXT_LINK" "$CURRENT_LINK"

if ! sudo systemctl restart "$SERVICE_NAME"; then
    restore_previous_release "$previous_target"
    fail '새 release의 Agent 서비스 시작 실패. 직전 release 복귀를 시도함'
fi

for _ in {1..30}; do
    if curl --fail --silent --show-error --max-time 3 http://127.0.0.1:8100/health > /dev/null; then
        write_state "$RELEASE_NAME" "$previous_release"
        printf '%s\n' \
            'Pi Agent 배포 완료' \
            "현재 release: $RELEASE_NAME" \
            "직전 release: $previous_release"
        exit 0
    fi
    sleep 2
done

restore_previous_release "$previous_target"
fail '새 release health 확인 실패. 직전 release 복귀를 시도함'
