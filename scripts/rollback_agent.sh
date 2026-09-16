#!/usr/bin/env bash
# Pi의 직전 성공 Agent image로 Agent 서비스만 되돌림.
# SQLite, .env, Ollama 서비스와 model volume은 변경하지 않음.
# 런타임 지침은 직전 Agent image에 포함된 버전으로 함께 되돌림.

set -euo pipefail
umask 077

readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "$SCRIPT_DIRECTORY/.." && pwd)"
readonly STATE_PATH="$PROJECT_ROOT/.deployment/agent-state"

fail() {
    printf '실패: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" > /dev/null || fail "$1 명령을 찾을 수 없음"
}

state_value() {
    local key="$1"
    local value

    value="$(awk -F= -v key="$key" '$1 == key { print substr($0, length(key) + 2) }' "$STATE_PATH")"
    [[ -n "$value" ]] || fail "배포 기록에 $key 값이 없음"
    printf '%s\n' "$value"
}

wait_for_agent_healthy() {
    local container_id
    local health_status

    for _ in {1..30}; do
        container_id="$(docker compose ps -q agent)"
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
    local state_directory
    local temporary_path

    state_directory="$(dirname -- "$STATE_PATH")"
    mkdir -p "$state_directory"
    temporary_path="$(mktemp "$state_directory/agent-state.XXXXXX")"

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
        [[ "$image" == "$current_image" || "$image" == "$previous_image" ]] && continue

        docker image rm "$image" > /dev/null || \
            printf '경고: 사용하지 않는 Agent image를 정리하지 못함: %s\n' "$image" >&2
    done < <(docker image ls --format '{{.Repository}}:{{.Tag}}' english-study-agent)
}

[[ $# -eq 0 ]] || fail '인수를 받지 않음'
[[ -f "$STATE_PATH" ]] || fail "직전 Agent image 배포 기록이 없음: $STATE_PATH"

cd "$PROJECT_ROOT"

require_command docker
require_command awk

readonly TARGET_IMAGE="$(state_value previous_image)"
readonly TARGET_COMMIT="$(state_value previous_git_commit)"
readonly TARGET_CHECKSUM="$(state_value previous_archive_sha256)"
readonly AGENT_CONTAINER_ID="$(docker compose ps -q agent)"
readonly OLLAMA_CONTAINER_ID="$(docker compose ps -q ollama)"

[[ -n "$AGENT_CONTAINER_ID" ]] || fail '현재 Agent 컨테이너를 찾을 수 없음'
[[ -n "$OLLAMA_CONTAINER_ID" ]] || fail '현재 Ollama 컨테이너를 찾을 수 없음'

readonly CURRENT_IMAGE="$(docker inspect --format '{{.Config.Image}}' "$AGENT_CONTAINER_ID")"
readonly CURRENT_IMAGE_ID="$(docker image inspect "$CURRENT_IMAGE" --format '{{.Id}}')"
readonly RECORDED_CURRENT_IMAGE="$(state_value current_image)"
readonly CURRENT_COMMIT="$(state_value current_git_commit)"
readonly CURRENT_CHECKSUM="$(state_value current_archive_sha256)"

[[ "$RECORDED_CURRENT_IMAGE" == "$CURRENT_IMAGE" ]] || fail \
    '배포 기록의 현재 image와 실행 중인 Agent image가 다름'
docker image inspect "$TARGET_IMAGE" > /dev/null || fail "직전 Agent image를 찾을 수 없음: $TARGET_IMAGE"
readonly TARGET_IMAGE_ID="$(docker image inspect "$TARGET_IMAGE" --format '{{.Id}}')"

AGENT_IMAGE="$TARGET_IMAGE" docker compose config --quiet
if ! AGENT_IMAGE="$TARGET_IMAGE" docker compose up -d --no-deps agent; then
    AGENT_IMAGE="$CURRENT_IMAGE" docker compose up -d --no-deps agent || true
    fail '직전 Agent image 시작 실패. 기존 Agent image 복귀를 시도함'
fi

if ! wait_for_agent_healthy; then
    AGENT_IMAGE="$CURRENT_IMAGE" docker compose up -d --no-deps agent || true
    wait_for_agent_healthy || fail '롤백 health 실패 후 기존 Agent image 복귀에도 실패함'
    fail '롤백 Agent health 실패. 기존 Agent image로 복귀함'
fi

[[ "$(docker compose ps -q ollama)" == "$OLLAMA_CONTAINER_ID" ]] || fail \
    'Agent 롤백 중 Ollama 컨테이너가 변경됨'

write_state \
    "$TARGET_IMAGE" \
    "$TARGET_IMAGE_ID" \
    "$TARGET_COMMIT" \
    "$TARGET_CHECKSUM" \
    "$CURRENT_IMAGE" \
    "$CURRENT_IMAGE_ID" \
    "$CURRENT_COMMIT" \
    "$CURRENT_CHECKSUM"
prune_agent_images "$TARGET_IMAGE" "$CURRENT_IMAGE"

printf '%s\n' \
    'Agent 롤백 완료' \
    "현재 image: $TARGET_IMAGE ($TARGET_IMAGE_ID)" \
    "다음 롤백 image: $CURRENT_IMAGE ($CURRENT_IMAGE_ID)"
