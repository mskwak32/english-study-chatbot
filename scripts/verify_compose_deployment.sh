#!/usr/bin/env bash
# Docker Compose 배포의 영속성·보안 경계를 검증.
#
# 목적:
# - 테스트 전용 SQLite DB가 일회성 Agent 컨테이너 재생성 뒤에도 유지되는지 확인
# - 실제 data/chat.db에 테스트 데이터를 쓰지 않는지 확인
# - 런타임 지침 mount가 읽기 전용인지 확인
# - Agent health와 Ollama 모델 가용성을 확인
#
# 실행:
#   ./scripts/verify_compose_deployment.sh
#   ./scripts/verify_compose_deployment.sh --recreate-services
#
# --recreate-services:
# - Ollama와 Agent 컨테이너를 강제로 재생성
# - Ollama 모델 named volume과 Agent 재시작 복구를 추가 확인
# - 실행 중 짧은 서비스 중단이 발생할 수 있음
#
# 전제:
# - docker compose 서비스가 이미 시작된 상태
# - .runtime-test/data의 소유자와 그룹이 10001:10001인 상태

set -euo pipefail

readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "$SCRIPT_DIRECTORY/.." && pwd)"
readonly TEST_DIRECTORY="$PROJECT_ROOT/.runtime-test/data"
readonly TEST_DATABASE_URL="sqlite:////runtime-test/chat.db"

recreate_services=false

fail() {
    printf '실패: %s\n' "$*" >&2
    exit 1
}

prepare_test_directory_message() {
    local reason="$1"

    printf '실패: %s\n\n' "$reason" >&2
    cat >&2 <<'EOF'
테스트 SQLite 저장소 준비 필요

이 스크립트는 운영 데이터(data/chat.db)를 변경하지 않기 위해
.runtime-test/data에 별도의 테스트 데이터베이스를 만듭니다.

프로젝트 루트에서 다음 명령을 한 번 실행합니다.

  mkdir -p .runtime-test/data
  sudo chown 10001:10001 .runtime-test/data
  sudo chmod 0750 .runtime-test/data

준비 상태 확인:

  sudo ls -ldn .runtime-test .runtime-test/data

.runtime-test/data의 예상 소유자·그룹·권한:

  10001 10001 ... 750 ... .runtime-test/data

준비 후 스크립트를 다시 실행합니다.

  ./scripts/verify_compose_deployment.sh
EOF
    exit 1
}

usage() {
    printf '%s\n' \
        '사용법:' \
        '  ./scripts/verify_compose_deployment.sh' \
        '  ./scripts/verify_compose_deployment.sh --recreate-services'
}

wait_for_healthy() {
    local service="$1"
    local container_id
    local health_status

    for _ in {1..30}; do
        container_id="$(docker compose ps -q "$service")"

        [[ -n "$container_id" ]] || fail "$service 컨테이너를 찾을 수 없음"

        health_status="$(
            docker inspect \
            --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
            "$container_id"
        )"

        if [[ "$health_status" == "healthy" ]]; then
        return
        fi

        sleep 2
    done

    fail "$service health check가 제한 시간 안에 통과하지 않음"
}

model_name() {
    local configured_model=""

    if [[ -f .env ]]; then
        configured_model="$(
            sed -n 's/^MODEL=//p' .env | tail -n 1
        )"
    fi

    printf '%s\n' "${configured_model:-gemma3:4b}"
}

case "${1:-}" in
    "")
        ;;
    --recreate-services)
        recreate_services=true
        ;;
    --help|-h)
        usage
        exit 0
        ;;
    *)
        usage
        exit 1
        ;;
esac

cd "$PROJECT_ROOT"

command -v docker > /dev/null || fail "docker 명령을 찾을 수 없음"
command -v curl > /dev/null || fail "curl 명령을 찾을 수 없음"

docker compose config --quiet

if [[ ! -d "$TEST_DIRECTORY" ]]; then
    prepare_test_directory_message ".runtime-test/data 디렉터리가 없음"
fi

readonly TEST_DIRECTORY_OWNER="$(stat -c '%u:%g' "$TEST_DIRECTORY")"
readonly TEST_DIRECTORY_MODE="$(stat -c '%a' "$TEST_DIRECTORY")"

if [[ "$TEST_DIRECTORY_OWNER" != "10001:10001" ]]; then
    prepare_test_directory_message \
        ".runtime-test/data의 소유자·그룹이 ${TEST_DIRECTORY_OWNER}임"
fi

if [[ "$TEST_DIRECTORY_MODE" != "750" ]]; then
    prepare_test_directory_message \
        ".runtime-test/data의 권한이 ${TEST_DIRECTORY_MODE}임"
fi

wait_for_healthy ollama
wait_for_healthy agent

readonly AGENT_CONTAINER_ID="$(docker compose ps -q agent)"
readonly INSTRUCTIONS_READ_WRITE="$(
    docker inspect \
        --format '{{range .Mounts}}{{if eq .Destination "/instructions"}}{{.RW}}{{end}}{{end}}' \
        "$AGENT_CONTAINER_ID"
)"

[[ "$INSTRUCTIONS_READ_WRITE" == "false" ]] || fail \
    "/instructions mount가 읽기 전용이 아님"

docker compose exec -T agent \
    python -c '
from pathlib import Path

database_path = Path("/data/chat.db")
if not database_path.is_file():
    raise SystemExit("운영 SQLite DB 파일이 없습니다.")

print("운영 SQLite DB 읽기 확인")
'

docker compose run --rm --no-deps \
    --env "DATABASE_URL=$TEST_DATABASE_URL" \
    --volume "$TEST_DIRECTORY:/runtime-test" \
    agent \
    python -c '
from app.config import settings
from app.database import initialize_database

initialize_database(settings.database_url)
print("테스트 SQLite 스키마 초기화 확인")
'

readonly TEST_MARKER="compose-$(date +%s)-$$"

docker compose run --rm --no-deps \
    --env "DATABASE_URL=$TEST_DATABASE_URL" \
    --env "DEPLOYMENT_TEST_MARKER=$TEST_MARKER" \
    --volume "$TEST_DIRECTORY:/runtime-test" \
    agent \
    python -c '
import os
import sqlite3

connection = sqlite3.connect("/runtime-test/chat.db")
connection.execute(
    "CREATE TABLE IF NOT EXISTS deployment_check (marker TEXT NOT NULL)"
)
connection.execute(
    "INSERT INTO deployment_check (marker) VALUES (?)",
    (os.environ["DEPLOYMENT_TEST_MARKER"],),
)
connection.commit()
connection.close()

print("테스트 SQLite 식별값 저장 확인")
'

docker compose run --rm --no-deps \
    --env "DATABASE_URL=$TEST_DATABASE_URL" \
    --env "DEPLOYMENT_TEST_MARKER=$TEST_MARKER" \
    --volume "$TEST_DIRECTORY:/runtime-test" \
    agent \
    python -c '
import os
import sqlite3

connection = sqlite3.connect("/runtime-test/chat.db")
row = connection.execute(
    "SELECT marker FROM deployment_check WHERE marker = ?",
    (os.environ["DEPLOYMENT_TEST_MARKER"],),
).fetchone()
connection.close()

if row is None:
    raise SystemExit("테스트 SQLite 식별값이 유지되지 않았습니다.")

print("테스트 SQLite 영속성 확인")
'

if docker compose exec -T agent \
    python -c '
from pathlib import Path

Path("/instructions/.deployment-write-test").write_text("blocked")
' \
    > /dev/null 2>&1; then
    docker compose exec -T agent \
        python -c '
from pathlib import Path

Path("/instructions/.deployment-write-test").unlink(missing_ok=True)
' \
    > /dev/null 2>&1 || true

    fail "/instructions에 쓰기가 허용되었습니다."
fi

printf '%s\n' '런타임 지침 읽기 전용 확인'

readonly MODEL_NAME="$(model_name)"
docker compose exec -T ollama ollama show "$MODEL_NAME" > /dev/null
printf 'Ollama 모델 확인: %s\n' "$MODEL_NAME"

curl --fail --silent --show-error \
    http://127.0.0.1:8100/health \
    > /dev/null
printf '%s\n' 'Agent health 확인'

if [[ "$recreate_services" == true ]]; then
    docker compose up -d --force-recreate ollama
    wait_for_healthy ollama

    docker compose exec -T ollama ollama show "$MODEL_NAME" > /dev/null
    printf '%s\n' 'Ollama 컨테이너 재생성 뒤 모델 유지 확인'

    docker compose up -d --force-recreate agent
    wait_for_healthy agent

    curl --fail --silent --show-error \
        http://127.0.0.1:8100/health \
        > /dev/null
    printf '%s\n' 'Agent 컨테이너 재생성 뒤 health 확인'
fi

printf '%s\n' '배포 검증 완료'
