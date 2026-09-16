#!/usr/bin/env bash
# 개발 PC에서 Pi의 직전 성공 Agent image로 롤백 실행.

set -euo pipefail

fail() {
    printf '실패: %s\n' "$*" >&2
    exit 1
}

[[ $# -eq 2 ]] || {
    printf '%s\n' '사용법: ./scripts/rollback_agent_on_pi.sh <Pi-SSH-대상> <Pi-프로젝트-절대경로>'
    exit 1
}

readonly PI_TARGET="$1"
readonly PI_PROJECT_DIRECTORY="$2"

[[ "$PI_TARGET" =~ ^[A-Za-z0-9][A-Za-z0-9._@-]*$ ]] || fail \
    'Pi SSH 대상은 SSH config 별칭 또는 user@host 형식이어야 함'
[[ "$PI_PROJECT_DIRECTORY" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail \
    'Pi 프로젝트 경로는 공백 없는 절대 경로여야 함'

command -v ssh > /dev/null || fail 'ssh 명령을 찾을 수 없음'
ssh "$PI_TARGET" "cd '$PI_PROJECT_DIRECTORY' && ./scripts/rollback_agent.sh"
