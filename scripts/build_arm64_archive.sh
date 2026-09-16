#!/usr/bin/env bash
# 검증된 현재 commit으로 linux/arm64 Agent image archive와 SHA-256 생성.
# archive와 checksum 파일만 Pi 전송 단계의 입력으로 사용.

set -euo pipefail

readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "$SCRIPT_DIRECTORY/.." && pwd)"
readonly PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
readonly OUTPUT_DIRECTORY="${OUTPUT_DIRECTORY:-$PROJECT_ROOT/artifacts}"

fail() {
    printf '실패: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" > /dev/null || fail "$1 명령을 찾을 수 없음"
}

cd "$PROJECT_ROOT"

require_command docker
require_command git
require_command npm
require_command shasum

[[ -x "$PYTHON_BIN" ]] || fail "Python 실행 파일을 찾을 수 없음: $PYTHON_BIN"
[[ -z "$(git status --porcelain)" ]] || fail "미커밋 또는 untracked 변경이 있음"

readonly GIT_COMMIT="$(git rev-parse --verify HEAD)"
readonly GIT_SHORT_COMMIT="$(git rev-parse --short=12 HEAD)"
readonly IMAGE_TAG="english-study-agent:$GIT_SHORT_COMMIT"
readonly ARCHIVE_PATH="$OUTPUT_DIRECTORY/english-study-agent-$GIT_SHORT_COMMIT.tar"
readonly CHECKSUM_PATH="$ARCHIVE_PATH.sha256"

[[ ! -e "$ARCHIVE_PATH" ]] || fail "기존 archive가 있어 덮어쓰지 않음: $ARCHIVE_PATH"
[[ ! -e "$CHECKSUM_PATH" ]] || fail "기존 checksum 파일이 있어 덮어쓰지 않음: $CHECKSUM_PATH"

printf '%s\n' 'Python 테스트 실행'
(cd backend && "$PYTHON_BIN" -m pytest)

printf '%s\n' 'Web 테스트 실행'
npm --prefix web test

printf '%s\n' 'linux/arm64 Agent image 빌드'
docker buildx build \
    --platform linux/arm64 \
    --load \
    --tag "$IMAGE_TAG" \
    .

readonly IMAGE_PLATFORM="$(docker image inspect "$IMAGE_TAG" --format '{{.Os}}/{{.Architecture}}')"
[[ "$IMAGE_PLATFORM" == 'linux/arm64' ]] || fail "image 플랫폼이 linux/arm64가 아님: $IMAGE_PLATFORM"

mkdir -p "$OUTPUT_DIRECTORY"
docker save --output "$ARCHIVE_PATH" "$IMAGE_TAG"
(
    cd "$OUTPUT_DIRECTORY"
    shasum -a 256 "$(basename -- "$ARCHIVE_PATH")" > "$(basename -- "$CHECKSUM_PATH")"
)

printf '%s\n' \
    'ARM64 Agent image archive 생성 완료' \
    "Git commit: $GIT_COMMIT" \
    "Image tag: $IMAGE_TAG" \
    "Archive: $ARCHIVE_PATH" \
    "SHA-256: $CHECKSUM_PATH"
