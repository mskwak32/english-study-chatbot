#!/usr/bin/env bash
# 개발 PC에서 검증·ARM64 build·archive 전송·Pi Agent 업데이트를 한 번에 실행.
# archive와 checksum 파일만 SSH로 전송하며, Pi의 SQLite·.env·Ollama model volume은 전송하지 않음.

set -euo pipefail

readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "$SCRIPT_DIRECTORY/.." && pwd)"

fail() {
    printf '실패: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf '%s\n' '사용법: ./scripts/deploy_arm64_to_pi.sh <Pi-SSH-대상> <Pi-프로젝트-절대경로>'
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
require_command scp
require_command ssh

cd "$PROJECT_ROOT"

./scripts/build_arm64_archive.sh

readonly GIT_SHORT_COMMIT="$(git rev-parse --short=12 HEAD)"
readonly ARCHIVE_NAME="english-study-agent-$GIT_SHORT_COMMIT.tar"
readonly CHECKSUM_NAME="$ARCHIVE_NAME.sha256"
readonly ARCHIVE_PATH="$PROJECT_ROOT/artifacts/$ARCHIVE_NAME"
readonly CHECKSUM_PATH="$PROJECT_ROOT/artifacts/$CHECKSUM_NAME"
readonly PI_INCOMING_DIRECTORY="$PI_PROJECT_DIRECTORY/.deployment/incoming"
readonly PI_ARCHIVE_PATH="$PI_INCOMING_DIRECTORY/$ARCHIVE_NAME"
readonly PI_CHECKSUM_PATH="$PI_INCOMING_DIRECTORY/$CHECKSUM_NAME"

ssh "$PI_TARGET" "install -d -m 700 -- '$PI_INCOMING_DIRECTORY'"
scp -- "$ARCHIVE_PATH" "$CHECKSUM_PATH" "$PI_TARGET:$PI_INCOMING_DIRECTORY/"
ssh "$PI_TARGET" \
    "cd '$PI_PROJECT_DIRECTORY' && ./scripts/deploy_agent_archive.sh '$PI_ARCHIVE_PATH' '$PI_CHECKSUM_PATH'"

# docker load가 성공한 archive를 image로 보관하므로 전송용 임시 파일만 삭제.
ssh "$PI_TARGET" "rm -f -- '$PI_ARCHIVE_PATH' '$PI_CHECKSUM_PATH'"
rm -f -- "$ARCHIVE_PATH" "$CHECKSUM_PATH"

printf '%s\n' 'PC build·Pi Agent 배포 완료'
