# Raspberry Pi 운영 및 rsync 배포

이 문서는 Raspberry Pi 5에서 Docker Compose로 Ollama와 Agent를 실행하고, 개발 PC에서 검증한 소스를 `rsync`로 전송해 Pi에서 Agent 이미지를 빌드하는 절차를 설명합니다.

## 구성과 보존 경계

Pi 프로젝트 루트는 다음처럼 구성합니다.

```text
/home/<Pi 사용자명>/english_study_ai/
├── .env                    # Pi별 환경 변수
├── data/                   # SQLite 데이터
├── backups/                # SQLite 백업
├── .deployment/            # 현재·직전 Agent 이미지 태그 기록
├── compose.yaml            # Ollama와 Agent 실행 정의
└── instructions/           # 다음 Agent 이미지 빌드에 포함할 지침
```

| 대상 | 위치 | 배포·롤백 중 동작 |
| --- | --- | --- |
| Agent 코드와 런타임 지침 | Pi 프로젝트 루트 | `rsync` 후 Pi에서 새 이미지로 빌드 |
| Agent 이미지 | Pi Docker image 저장소 | Git 커밋 태그별로 보관·실행 |
| SQLite 데이터 | `data/` | 전송·변경·삭제하지 않음 |
| 환경 변수 | `.env` | 전송·변경·삭제하지 않음 |
| SQLite 백업 | `backups/` | 전송·변경·삭제하지 않음 |
| Ollama 모델 | Docker named volume | 전송·변경·삭제하지 않음 |

Agent 이미지는 코드와 `instructions/`를 함께 포함합니다. 따라서 이전 이미지 태그로 롤백하면 코드와 지침도 함께 이전 버전으로 돌아갑니다. 반대로 `.env`, SQLite, 백업, Ollama 모델은 이미지 밖에 계속 보관하므로 Agent를 다시 빌드하거나 롤백해도 유지됩니다.

## Pi 최초 설정

Pi 운영 사용자에게 SSH 공개 키 로그인을 설정합니다. Docker Engine과 Compose Plugin은 Raspberry Pi OS에 맞는 Docker 공식 설치 절차로 설치한 뒤, 다음 명령으로 확인합니다.

```bash
docker --version
docker compose version
```

Pi에서 프로젝트 루트와 계속 보관할 디렉터리를 한 번 만듭니다. Agent는 컨테이너의 고정 사용자 ID `10001`로 SQLite 파일을 쓰므로 `data/` 소유권도 맞춥니다.

```bash
PI_PROJECT=/home/<Pi 사용자명>/english_study_ai
mkdir -p "$PI_PROJECT"/{data,backups}
sudo chown 10001:10001 "$PI_PROJECT/data"
sudo chmod 0750 "$PI_PROJECT/data"
```

Pi의 `.env`는 첫 배포 도구가 `.env.example`을 바탕으로 한 번만 만들고 권한을 `0600`으로 설정합니다. 기존 `.env`는 절대 덮어쓰지 않습니다. 이 파일은 `rsync` 대상이 아니며, 이후에는 Pi에서만 관리합니다.

최초 배포 뒤 아래 항목을 검토합니다. 모델 이름은 Ollama에 내려받을 이름과 같아야 합니다.

```dotenv
MODEL=gemma3:4b
OLLAMA_KEEP_ALIVE=30m
OLLAMA_TIMEOUT_SECONDS=60
TIMEZONE=Asia/Seoul
```

응답이 느린 환경에서는 `OLLAMA_TIMEOUT_SECONDS=180`처럼 HTTP 요청 하나의 대기 시간만 늘릴 수 있습니다. 기본값은 60초이며, `OLLAMA_KEEP_ALIVE`는 모델 상주 시간이라 응답 대기 시간과 다릅니다.

## 최초 배포

개발 PC에는 프로젝트 루트 `.venv`, Node.js/npm, `rsync`, Pi SSH 공개 키 인증이 필요합니다. Docker는 Pi에서만 빌드·실행하므로 개발 PC에 Docker나 Buildx는 필요하지 않습니다. 배포할 변경은 먼저 Git 커밋으로 확정해야 합니다.

먼저 개발 PC에서 아래 명령을 한 번 실행합니다. 소스와 `compose.yaml`을 전송하고, Pi의 `.env`·계속 보관할 디렉터리를 준비한 뒤 Ollama 컨테이너만 시작합니다. 아직 모델이 없으면 Agent 배포는 중단됩니다.

```bash
./scripts/deploy_to_pi.sh <Pi-SSH-대상> /home/<Pi 사용자명>/english_study_ai
```

Pi에서 필요한 모델을 한 번만 내려받고 확인합니다.

```bash
ssh <Pi-SSH-대상> \
  'cd /home/<Pi 사용자명>/english_study_ai && \
   docker compose exec ollama ollama pull gemma3:4b && \
   docker compose exec ollama ollama show gemma3:4b'
```

그 다음 같은 배포 명령을 다시 실행하면 Pi가 Agent 이미지를 빌드하고 Agent 컨테이너를 시작합니다. Ollama 모델은 named volume에 저장되므로 이후 Agent 배포·롤백에서 다시 내려받지 않습니다.

## 일반 배포

개발 PC에서 다음 명령을 실행합니다.

```bash
./scripts/deploy_to_pi.sh <Pi-SSH-대상> /home/<Pi 사용자명>/english_study_ai
```

이 명령은 다음 순서로 동작합니다.

1. 개발 PC에서 Python·Web 테스트와 clean Git 상태를 확인합니다.
2. Docker build에 필요한 Agent·Web 실행 파일, `instructions/`, Dockerfile·Compose 설정만 Pi 루트로 `rsync`합니다. `.env`, `data/`, `backups/`, `.deployment/`, 문서, 개발 지침, 테스트, 캐시는 전송하지 않습니다.
3. Pi가 현재 Git 커밋의 12자리 SHA를 `english-study-agent:<태그>`로 사용해 Agent 이미지를 빌드합니다.
4. Compose가 새 태그로 Agent 컨테이너만 다시 만듭니다. Ollama 컨테이너와 모델 volume은 그대로 둡니다.
5. Pi의 `.deployment/agent-tags`에 현재·직전 Agent 태그를 기록하고 `/health`를 확인합니다.

이미지 태그는 배포한 Git 커밋을 식별하는 이름표입니다. 예를 들어 커밋이 `abc123def456`이면 Pi에서 실행할 이미지는 `english-study-agent:abc123def456`입니다. `latest`처럼 계속 바뀌는 태그 대신 커밋 태그를 사용해야 현재 실행 코드와 롤백 대상을 분명히 알 수 있습니다.

배포 후 상태를 확인합니다.

```bash
ssh <Pi-SSH-대상> 'cd /home/<Pi 사용자명>/english_study_ai && docker compose ps'
curl -fsS http://<Pi-IP>:8100/health
```

`/health`는 Agent의 HTTP 응답만 확인합니다. 브라우저에서 실제 학습 요청을 한 번 실행해 Agent와 Ollama의 전체 동작도 별도로 확인합니다.

## Pi에서 직접 빌드·기동

개발 PC의 배포 도구는 Git 커밋과 테스트를 확인한 뒤 Pi에 전송합니다. 반면 Pi에서 코드를 직접 수정했거나, 개발·점검 목적으로 현재 Pi의 소스만으로 새 Agent 이미지를 만들 때는 아래 명령을 사용할 수 있습니다. 이 절차는 Git 커밋이나 `rsync`를 요구하지 않습니다.

모델이 이미 내려받아진 상태에서 Pi에서 실행합니다. 시간으로 만든 태그는 이 수동 빌드를 구분하는 이름표입니다.

```bash
cd /home/<Pi 사용자명>/english_study_ai
export AGENT_TAG="manual-$(date +%Y%m%d-%H%M%S)"
AGENT_TAG="$AGENT_TAG" docker compose up -d --build
```

이 명령은 현재 Pi 프로젝트의 소스로 Agent 이미지를 빌드하고 Ollama와 Agent 컨테이너를 기동합니다. 수동 태그는 개발 PC의 배포 도구가 기록하는 Git 커밋 태그가 아니므로, 이 방법으로 실행한 이미지는 `rollback_to_pi.sh`의 롤백 대상으로 기록되지 않습니다.

이미 만들어 둔 컨테이너가 중단되었을 뿐이고 이미지를 새로 빌드할 필요가 없다면 Pi에서 다음 명령으로 같은 컨테이너를 다시 시작합니다.

```bash
cd /home/<Pi 사용자명>/english_study_ai
docker compose start ollama agent
docker compose ps
```

컨테이너가 삭제되어 다시 만들어야 한다면, 먼저 남아 있는 이미지 태그를 확인한 뒤 해당 태그를 지정해 기동합니다.

```bash
docker image ls 'english-study-agent'
AGENT_TAG=<확인한-태그> docker compose up -d
```

## 롤백

문제가 생기면 개발 PC에서 한 명령으로 직전 Agent 태그를 실행합니다.

```bash
./scripts/rollback_to_pi.sh <Pi-SSH-대상> /home/<Pi 사용자명>/english_study_ai
```

롤백은 `.deployment/agent-tags`의 직전 태그를 읽어 Agent 컨테이너만 다시 만듭니다. SQLite DB, 백업, `.env`, Ollama 컨테이너와 모델 volume은 그대로 유지됩니다. 롤백 후 `/health`와 실제 학습 요청을 확인합니다.

## 보안과 주의사항

- `.env`는 `0600` 권한으로 유지하고 Git·`rsync` 대상·로그에 포함하지 않습니다.
- Ollama 포트는 Compose에서 호스트에 공개하지 않습니다. Agent만 LAN의 `8100` 포트를 공개합니다.
- Agent는 비루트 사용자와 읽기 전용 파일시스템으로 실행하고 SQLite bind mount만 쓸 수 있게 합니다.
- `data/`, `backups/`, `.env`, Ollama 모델 volume을 재귀 삭제하는 명령은 배포·롤백 절차에 포함하지 않습니다.
- 레지스트리 기반 이미지 배포와 GitHub Actions는 MVP 이후 후보입니다. 현재는 PC에서 Pi로 소스를 전송하고 Pi에서 이미지를 빌드합니다.
