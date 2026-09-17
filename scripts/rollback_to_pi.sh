#!/usr/bin/env bash
# Pi의 직전 Agent tag로만 컨테이너를 교체
# Pi의 .env, data, backups, Ollama 모델은 변경하지 않음

# 명령 실패·미정의 변수·파이프라인 실패를 즉시 중단
set -euo pipefail

fail() {
    # 오류 원인을 표준 오류로 보여 주고 이후 원격 명령을 실행하지 않음
    printf '실패: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf '%s\n' '사용법: ./scripts/rollback_to_pi.sh <Pi-SSH-대상> <Pi-프로젝트-절대경로>'
}

# 배포 때와 같은 SSH 대상·Pi 프로젝트 경로만 받음. 태그는 상태 파일에서 읽음.
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
command -v ssh > /dev/null || fail 'ssh 명령을 찾을 수 없음'

# Pi에서 태그 기록을 읽고 Agent 컨테이너만 교체.
# heredoc 본문은 Pi에서 실행되므로 Docker image와 상태 파일을 직접 읽을 수 있음.
ssh "$PI_TARGET" bash -s -- "$PI_PROJECT_DIRECTORY" <<'REMOTE_ROLLBACK'
set -euo pipefail

project_directory="$1"
state_path="$project_directory/.deployment/agent-tags"

fail() {
    # 상태 파일을 바꾸기 전에 오류를 종료해 기존 롤백 정보를 유지
    printf '실패: %s\n' "$*" >&2
    exit 1
}

wait_for_agent_healthy() {
    local container_id health_status

    # 롤백한 컨테이너가 healthy가 될 때까지 최대 60초 기다림
    for _ in {1..30}; do
        # 이전 태그로 생성된 Agent 컨테이너의 healthcheck 상태를 읽음
        container_id="$(AGENT_TAG="$previous_tag" docker compose ps -q agent)"
        [[ -n "$container_id" ]] || return 1
        health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")"
        [[ "$health_status" == 'healthy' ]] && return 0
        sleep 2
    done

    return 1
}

[[ "$project_directory" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail 'Pi 프로젝트 경로 형식이 올바르지 않음'
command -v docker > /dev/null || fail 'docker 명령을 찾을 수 없음'
[[ -f "$state_path" ]] || fail '배포 태그 기록을 찾을 수 없음'

cd -- "$project_directory"
current_tag="$(awk -F= '$1 == "current_tag" { print $2 }' "$state_path")"
previous_tag="$(awk -F= '$1 == "previous_tag" { print $2 }' "$state_path")"
# 태그만 바꾸고 재빌드하지 않으므로 이전 코드·instructions 이미지가 그대로 실행됨.
# 여기서 읽는 파일은 'current_tag=...'와 'previous_tag=...' 두 줄만 가진 간단한 기록 파일.
[[ "$current_tag" =~ ^[0-9a-f]{12}$ ]] || fail '현재 Agent 태그 형식이 올바르지 않음'
[[ "$previous_tag" =~ ^[0-9a-f]{12}$ ]] || fail '롤백할 직전 Agent image가 없음'
# 실제 이미지가 남아 있는지 먼저 확인해, Agent를 중단시킨 뒤에 실패하지 않게 함
docker image inspect "english-study-agent:$previous_tag" > /dev/null || \
    fail "직전 Agent image를 찾을 수 없음: $previous_tag"

ollama_container_id="$(AGENT_TAG=bootstrap docker compose ps -q ollama)"
[[ -n "$ollama_container_id" ]] || fail '실행 중인 Ollama 컨테이너를 찾을 수 없음'

# --no-deps로 Ollama와 모델 volume을 건드리지 않음.
# 이미지 태그만 달라지므로 SQLite data mount와 .env도 같은 위치를 계속 사용함.
AGENT_TAG="$previous_tag" docker compose up -d --no-deps agent
wait_for_agent_healthy || fail '롤백한 Agent health 확인 실패'

[[ "$(AGENT_TAG="$previous_tag" docker compose ps -q ollama)" == "$ollama_container_id" ]] || fail \
    'Agent 롤백 중 Ollama 컨테이너가 변경됨'

temporary_path="$(mktemp "$project_directory/.deployment/agent-tags.XXXXXX")"
# 성공한 뒤에만 현재·직전 태그를 서로 교체해 다음 롤백도 가능하게 함.
# 예: A에서 B로 롤백되면 기록은 current=B, previous=A가 됨.
printf 'current_tag=%s\nprevious_tag=%s\n' "$previous_tag" "$current_tag" > "$temporary_path"
mv -- "$temporary_path" "$state_path"

printf '%s\n' "Agent 롤백 완료: english-study-agent:$previous_tag"
REMOTE_ROLLBACK
