#!/usr/bin/env bash
# 개발 PC에서 Pi의 직전 release로 current 링크를 되돌리고 Agent만 재시작합니다.
# Pi의 .env, data, backups와 Ollama 모델은 변경하지 않습니다.

set -euo pipefail

fail() {
    printf '실패: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf '%s\n' '사용법: ./scripts/rollback_on_pi.sh <Pi-SSH-대상> <Pi-프로젝트-절대경로>'
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

command -v ssh > /dev/null || fail 'ssh 명령을 찾을 수 없음'

# current release의 Pi 스크립트를 실행하므로 sudo 비밀번호가 필요하면 현재 터미널에서 입력할 수 있습니다.
ssh -tt "$PI_TARGET" \
    "$PI_PROJECT_DIRECTORY/current/scripts/rollback_pi_release.sh" \
    "$PI_PROJECT_DIRECTORY"
