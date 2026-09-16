#!/usr/bin/env bash
# Pi에서 current 링크를 직전 성공 release로 바꾸고 Agent 서비스만 재시작합니다.
# .env, data, backups와 네이티브 Ollama 모델은 변경하지 않습니다.

set -euo pipefail

fail() {
    printf '실패: %s\n' "$*" >&2
    exit 1
}

[[ $# -eq 1 ]] || fail '사용법: rollback_pi_release.sh <Pi-프로젝트-절대경로>'

readonly PROJECT_ROOT="$1"
readonly CURRENT_LINK="$PROJECT_ROOT/current"
readonly NEXT_LINK="$PROJECT_ROOT/.current-rollback-next"
readonly STATE_PATH="$PROJECT_ROOT/.deployment/release-state"
readonly SERVICE_NAME='english-study-agent.service'

[[ "$PROJECT_ROOT" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail \
    'Pi 프로젝트 경로는 공백 없는 절대 경로여야 함'

state_value() {
    local key="$1"
    local value

    value="$(awk -F= -v key="$key" '$1 == key { print substr($0, length(key) + 2) }' "$STATE_PATH")"
    [[ -n "$value" ]] || fail "배포 기록에 $key 값이 없음"
    printf '%s\n' "$value"
}

write_state() {
    local current_release="$1"
    local previous_release="$2"
    local temporary_path

    temporary_path="$(mktemp "$PROJECT_ROOT/.deployment/release-state.XXXXXX")"
    printf '%s\n' \
        "current_release=$current_release" \
        "previous_release=$previous_release" \
        "deployed_at=$(date --iso-8601=seconds)" > "$temporary_path"
    mv "$temporary_path" "$STATE_PATH"
}

test -L "$CURRENT_LINK" || fail "현재 release 링크가 없음: $CURRENT_LINK"
test -f "$STATE_PATH" || fail "배포 기록이 없음: $STATE_PATH"
sudo -v || fail 'Agent 재시작용 sudo 권한을 확인할 수 없음'
systemctl cat "$SERVICE_NAME" > /dev/null || fail "systemd 서비스가 없음: $SERVICE_NAME"

current_release="$(state_value current_release)"
target_release="$(state_value previous_release)"
[[ "$target_release" != 'none' ]] || fail '첫 배포 뒤에는 직전 release가 없어 롤백할 수 없음'
[[ "$current_release" =~ ^[0-9a-f]{12}$ ]] || fail "현재 release 이름이 올바르지 않음: $current_release"
[[ "$target_release" =~ ^[0-9a-f]{12}$ ]] || fail "직전 release 이름이 올바르지 않음: $target_release"
[[ "$(readlink "$CURRENT_LINK")" == "releases/$current_release" ]] || fail \
    '배포 기록의 현재 release와 current 링크가 다름'
test -d "$PROJECT_ROOT/releases/$target_release" || fail "직전 release 디렉터리가 없음: $target_release"

ln -s "releases/$target_release" "$NEXT_LINK"
mv -Tf "$NEXT_LINK" "$CURRENT_LINK"

if ! sudo systemctl restart "$SERVICE_NAME"; then
    ln -s "releases/$current_release" "$NEXT_LINK"
    mv -Tf "$NEXT_LINK" "$CURRENT_LINK"
    sudo systemctl restart "$SERVICE_NAME" || true
    fail '직전 release의 Agent 시작 실패. 기존 release 복귀를 시도함'
fi

for _ in {1..30}; do
    if curl --fail --silent --show-error --max-time 3 http://127.0.0.1:8100/health > /dev/null; then
        write_state "$target_release" "$current_release"
        printf '%s\n' \
            'Pi Agent 롤백 완료' \
            "현재 release: $target_release" \
            "다음 롤백 release: $current_release"
        exit 0
    fi
    sleep 2
done

ln -s "releases/$current_release" "$NEXT_LINK"
mv -Tf "$NEXT_LINK" "$CURRENT_LINK"
sudo systemctl restart "$SERVICE_NAME" || true
fail '롤백 release health 확인 실패. 기존 release 복귀를 시도함'
