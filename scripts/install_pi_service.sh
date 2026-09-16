#!/usr/bin/env bash
# Pi에서 systemd Agent 서비스를 설치하고 영속 디렉터리의 권한을 준비합니다.
# root 권한으로 실행하며 .env 내용과 data의 파일은 수정하지 않습니다.

set -euo pipefail

readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly TEMPLATE_PATH="$SCRIPT_DIRECTORY/systemd/english-study-agent.service.template"
readonly UNIT_PATH='/etc/systemd/system/english-study-agent.service'

fail() {
    printf '실패: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf '%s\n' '사용법: sudo ./scripts/install_pi_service.sh <Pi-프로젝트-절대경로> [실행-사용자]'
}

[[ $# -ge 1 && $# -le 2 ]] || {
    usage
    exit 1
}

readonly PROJECT_ROOT="$1"
readonly RUN_AS_USER="${2:-${SUDO_USER:-}}"

[[ "$EUID" -eq 0 ]] || fail 'root 권한으로 실행해야 함'
[[ "$PROJECT_ROOT" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail \
    'Pi 프로젝트 경로는 공백 없는 절대 경로여야 함'
[[ -n "$RUN_AS_USER" ]] || fail '실행 사용자를 지정해야 함'
[[ "$RUN_AS_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail '실행 사용자가 올바르지 않음'
[[ -d "$PROJECT_ROOT" ]] || fail "프로젝트 디렉터리가 없음: $PROJECT_ROOT"
[[ -f "$TEMPLATE_PATH" ]] || fail "systemd 템플릿을 찾을 수 없음: $TEMPLATE_PATH"

command -v systemctl > /dev/null || fail 'systemctl 명령을 찾을 수 없음'
id "$RUN_AS_USER" > /dev/null || fail "실행 사용자를 찾을 수 없음: $RUN_AS_USER"

readonly RUN_AS_GROUP="$(id -gn "$RUN_AS_USER")"
readonly RENDERED_UNIT="$(mktemp)"
trap 'rm -f -- "$RENDERED_UNIT"' EXIT

sed \
    -e "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" \
    -e "s|__RUN_AS_USER__|$RUN_AS_USER|g" \
    -e "s|__RUN_AS_GROUP__|$RUN_AS_GROUP|g" \
    "$TEMPLATE_PATH" > "$RENDERED_UNIT"

install -d -o "$RUN_AS_USER" -g "$RUN_AS_GROUP" -m 0700 \
    "$PROJECT_ROOT/data" \
    "$PROJECT_ROOT/backups" \
    "$PROJECT_ROOT/releases" \
    "$PROJECT_ROOT/.deployment"
install -m 0644 "$RENDERED_UNIT" "$UNIT_PATH"
systemctl daemon-reload
systemctl enable english-study-agent.service

printf '%s\n' \
    'systemd Agent 서비스 설치 완료' \
    "서비스: english-study-agent.service" \
    "실행 사용자: $RUN_AS_USER" \
    '첫 release 배포 후 서비스가 시작됩니다.'
