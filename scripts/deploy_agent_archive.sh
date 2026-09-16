#!/usr/bin/env bash
# Pi에서 검증된 Agent image archive를 load하고 Agent만 교체.
# SQLite, .env, Ollama 서비스와 model volume은 변경하지 않음.
# 런타임 지침은 Agent image에 포함되어 Agent 교체와 함께 버전 변경.

set -euo pipefail
umask 077

readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "$SCRIPT_DIRECTORY/.." && pwd)"
readonly STATE_DIRECTORY="$PROJECT_ROOT/.deployment"
readonly STATE_PATH="$STATE_DIRECTORY/agent-state"

fail() {
    printf '실패: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf '%s\n' '사용법: ./scripts/deploy_agent_archive.sh <image-archive.tar> <image-archive.tar.sha256>'
}

require_command() {
    command -v "$1" > /dev/null || fail "$1 명령을 찾을 수 없음"
}

wait_for_agent_healthy() {
    local agent_image="$1"
    local container_id
    local health_status

    for _ in {1..30}; do
        container_id="$(AGENT_IMAGE="$agent_image" docker compose ps -q agent)"
        [[ -n "$container_id" ]] || return 1

        health_status="$(
            docker inspect \
                --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
                "$container_id"
        )"

        [[ "$health_status" == 'healthy' ]] && return 0
        sleep 2
    done

    return 1
}

write_state() {
    local current_image="$1"
    local current_image_id="$2"
    local current_commit="$3"
    local current_checksum="$4"
    local previous_image="$5"
    local previous_image_id="$6"
    local previous_commit="$7"
    local previous_checksum="$8"
    local temporary_path

    mkdir -p "$STATE_DIRECTORY"
    temporary_path="$(mktemp "$STATE_DIRECTORY/agent-state.XXXXXX")"

    printf '%s\n' \
        "current_image=$current_image" \
        "current_image_id=$current_image_id" \
        "current_git_commit=$current_commit" \
        "current_archive_sha256=$current_checksum" \
        "previous_image=$previous_image" \
        "previous_image_id=$previous_image_id" \
        "previous_git_commit=$previous_commit" \
        "previous_archive_sha256=$previous_checksum" \
        "deployed_at=$(date --iso-8601=seconds)" \
        > "$temporary_path"
    mv "$temporary_path" "$STATE_PATH"
}

prune_agent_images() {
    local current_image="$1"
    local previous_image="$2"
    local image

    while IFS= read -r image; do
        [[ "$image" == "$current_image" ]] && continue
        [[ "$previous_image" != 'none' && "$image" == "$previous_image" ]] && continue

        docker image rm "$image" > /dev/null || \
            printf '경고: 사용하지 않는 Agent image를 정리하지 못함: %s\n' "$image" >&2
    done < <(docker image ls --format '{{.Repository}}:{{.Tag}}' english-study-agent)
}

[[ $# -eq 2 ]] || {
    usage
    exit 1
}

readonly ARCHIVE_PATH="$1"
readonly CHECKSUM_PATH="$2"
readonly ARCHIVE_DIRECTORY="$(cd -- "$(dirname -- "$ARCHIVE_PATH")" && pwd)"
readonly ARCHIVE_NAME="$(basename -- "$ARCHIVE_PATH")"
readonly CHECKSUM_NAME="$(basename -- "$CHECKSUM_PATH")"

[[ -f "$ARCHIVE_PATH" ]] || fail "image archive를 찾을 수 없음: $ARCHIVE_PATH"
[[ -f "$CHECKSUM_PATH" ]] || fail "SHA-256 파일을 찾을 수 없음: $CHECKSUM_PATH"
[[ "$CHECKSUM_NAME" == "$ARCHIVE_NAME.sha256" ]] || fail 'checksum 파일명은 archive 파일명 뒤에 .sha256이어야 함'

if [[ "$ARCHIVE_NAME" =~ ^english-study-agent-([0-9a-f]{12})\.tar$ ]]; then
    readonly GIT_SHORT_COMMIT="${BASH_REMATCH[1]}"
else
    fail "허용하지 않는 image archive 파일명: $ARCHIVE_NAME"
fi

readonly NEW_IMAGE="english-study-agent:$GIT_SHORT_COMMIT"
readonly CHECKSUM_ENTRY="$(awk 'NR == 1 { print $2 }' "$CHECKSUM_PATH")"
readonly CHECKSUM_LINES="$(wc -l < "$CHECKSUM_PATH" | tr -d ' ')"

[[ "$CHECKSUM_LINES" == '1' ]] || fail 'SHA-256 파일에는 archive 한 개만 있어야 함'
[[ "$CHECKSUM_ENTRY" == "$ARCHIVE_NAME" ]] || fail 'SHA-256 파일이 현재 archive 파일을 가리키지 않음'

cd "$PROJECT_ROOT"

require_command docker
require_command sha256sum
require_command awk

(
    cd "$ARCHIVE_DIRECTORY"
    sha256sum --check --status "$CHECKSUM_NAME"
) || fail 'image archive SHA-256 검증 실패'

readonly ARCHIVE_SHA256="$(awk 'NR == 1 { print $1 }' "$CHECKSUM_PATH")"
readonly AGENT_CONTAINER_ID="$(AGENT_IMAGE=english-study-agent:bootstrap docker compose ps -q agent)"
readonly OLLAMA_CONTAINER_ID="$(AGENT_IMAGE=english-study-agent:bootstrap docker compose ps -q ollama)"

[[ -n "$OLLAMA_CONTAINER_ID" ]] || fail '현재 Ollama 컨테이너를 찾을 수 없음'

has_previous_agent=false
previous_image='none'
previous_image_id='none'
previous_commit='unknown'
previous_checksum='unknown'

if [[ -n "$AGENT_CONTAINER_ID" ]]; then
    has_previous_agent=true
    previous_image="$(docker inspect --format '{{.Config.Image}}' "$AGENT_CONTAINER_ID")"
    previous_image_id="$(docker image inspect "$previous_image" --format '{{.Id}}')"

    if [[ -f "$STATE_PATH" ]]; then
        recorded_current_image="$(awk -F= '$1 == "current_image" { print substr($0, 15) }' "$STATE_PATH")"

        if [[ "$recorded_current_image" == "$previous_image" ]]; then
            previous_commit="$(awk -F= '$1 == "current_git_commit" { print substr($0, 20) }' "$STATE_PATH")"
            previous_checksum="$(awk -F= '$1 == "current_archive_sha256" { print substr($0, 24) }' "$STATE_PATH")"
        fi
    fi
fi

docker load --input "$ARCHIVE_PATH" > /dev/null
docker image inspect "$NEW_IMAGE" > /dev/null || fail "load한 image를 찾을 수 없음: $NEW_IMAGE"

readonly NEW_IMAGE_ID="$(docker image inspect "$NEW_IMAGE" --format '{{.Id}}')"
readonly NEW_IMAGE_PLATFORM="$(docker image inspect "$NEW_IMAGE" --format '{{.Os}}/{{.Architecture}}')"
[[ "$NEW_IMAGE_PLATFORM" == 'linux/arm64' ]] || fail \
    "load한 image 플랫폼이 linux/arm64가 아님: $NEW_IMAGE_PLATFORM"
AGENT_IMAGE="$NEW_IMAGE" docker compose config --quiet

if ! AGENT_IMAGE="$NEW_IMAGE" docker compose up -d --no-deps agent; then
    if [[ "$has_previous_agent" == true ]]; then
        AGENT_IMAGE="$previous_image" docker compose up -d --no-deps agent || true
        fail '새 Agent 컨테이너 시작 실패. 직전 Agent image 복귀를 시도함'
    fi

    AGENT_IMAGE="$NEW_IMAGE" docker compose rm --stop --force agent || true
    fail '첫 Agent 컨테이너 시작 실패. 생성된 Agent 컨테이너 제거를 시도함'
fi

if ! wait_for_agent_healthy "$NEW_IMAGE"; then
    if [[ "$has_previous_agent" == true ]]; then
        AGENT_IMAGE="$previous_image" docker compose up -d --no-deps agent || true
        wait_for_agent_healthy "$previous_image" || fail '새 Agent health 실패 후 직전 Agent image 복귀에도 실패함'
        fail '새 Agent health 실패. 직전 Agent image로 복귀함'
    fi

    AGENT_IMAGE="$NEW_IMAGE" docker compose rm --stop --force agent || true
    fail '첫 Agent health 실패. 생성된 Agent 컨테이너 제거를 시도함'
fi

[[ "$(AGENT_IMAGE="$NEW_IMAGE" docker compose ps -q ollama)" == "$OLLAMA_CONTAINER_ID" ]] || fail \
    'Agent 업데이트 중 Ollama 컨테이너가 변경됨'

write_state \
    "$NEW_IMAGE" \
    "$NEW_IMAGE_ID" \
    "$GIT_SHORT_COMMIT" \
    "$ARCHIVE_SHA256" \
    "$previous_image" \
    "$previous_image_id" \
    "$previous_commit" \
    "$previous_checksum"
prune_agent_images "$NEW_IMAGE" "$previous_image"

printf '%s\n' \
    'Agent 업데이트 완료' \
    "현재 image: $NEW_IMAGE ($NEW_IMAGE_ID)" \
    "직전 image: $previous_image ($previous_image_id)" \
    "배포 기록: $STATE_PATH"
