# Raspberry Pi 운영 및 Agent 이미지 배포

이 문서는 Raspberry Pi 5에서 Docker Compose로 영어 학습 챗봇을 운영하고, 개발 PC에서 검증한 ARM64 Agent 이미지를 배포하는 절차를 설명합니다. 일반적인 배포에서는 Pi에서 소스를 빌드하거나 Git·rsync로 프로젝트를 갱신하지 않습니다.

## 구성과 보존 경계

| 대상 | 위치 | 일반 배포 중 동작 |
| --- | --- | --- |
| Agent와 런타임 지침 | `english-study-agent:<commit>` 이미지 | 새 이미지로 교체하며, 지침도 같은 버전으로 변경 |
| SQLite 데이터 | Pi `./data` 바인드 마운트 | 전송·변경·삭제하지 않음 |
| 환경 변수 | Pi `.env` | 전송·변경·삭제하지 않음 |
| SQLite 백업 | Pi `backups/` | 전송·변경·삭제하지 않음 |
| Ollama | `ollama` 서비스 | 재생성·업데이트하지 않음 |
| Ollama 모델 | `ollama-models` 명명 볼륨 | 전송·변경·삭제하지 않음 |

Agent만 호스트 TCP `8100` 포트를 공개합니다. Ollama에는 `ports:`가 없으므로 Compose 내부의 Agent만 `http://ollama:11434`로 접근합니다.

Agent 이미지의 루트 파일 시스템은 읽기 전용입니다. 런타임 지침은 이미지에 포함되며, 지침 변경은 새 Agent 이미지를 배포할 때만 반영됩니다. Pi의 기존 `instructions/` 디렉터리는 일반적인 배포에서 읽거나 수정하지 않습니다.

## Pi 최초 설정

Pi에는 Docker Engine, Docker Compose Plugin, `sha256sum`, SSH 공개 키 로그인이 필요합니다. Docker 데몬 제어 권한은 사실상 높은 권한이므로 신뢰하는 운영 사용자에게만 부여합니다.

```bash
docker --version
docker compose version
sha256sum --version
```

이 단계의 `compose.yaml`과 Pi용 스크립트는 Pi 프로젝트 경로에 한 번 준비되어 있어야 합니다. 프로젝트 디렉터리가 없다면 아래 명령이 `docs/`와 `scripts/` 디렉터리를 함께 만듭니다. 개발 PC에서 다음 지원 파일만 한 번 전송합니다.

```bash
tar --no-mac-metadata -cf - \
  compose.yaml \
  .env.example \
  docs/operations.md \
  scripts/deploy_agent_archive.sh \
  scripts/rollback_agent.sh \
  scripts/verify_compose_deployment.sh \
| ssh <Pi-SSH-대상> \
  'mkdir -p \
    /home/<Pi 사용자명>/english_study_ai/docs \
    /home/<Pi 사용자명>/english_study_ai/scripts \
  && tar -xvf - -C /home/<Pi 사용자명>/english_study_ai'
```

`--no-mac-metadata`는 macOS의 `._*` 메타데이터 파일과 확장 속성 경고를 막습니다. 이 최초 설정에서는 Compose·`.env` 예시 파일·스크립트·문서만 전송합니다. `.env`, `data/`, `backups/`, 기존 `instructions/`, Ollama volume은 전송하거나 변경하지 않습니다. 이후 일반적인 Agent 배포에서는 이미지 아카이브와 체크섬만 전송합니다.

`.env`가 없다면 Pi에서만 `.env.example`을 복사해 만듭니다. 기존 `.env`가 있다면 덮어쓰지 않습니다.

```bash
cd /home/<Pi 사용자명>/english_study_ai
test -f .env || cp .env.example .env
chmod 0600 .env
```

필요하면 `.env`에서 `MODEL`, `OLLAMA_KEEP_ALIVE`, `OLLAMA_TIMEOUT_SECONDS`, `TIMEZONE` 값을 조정합니다. 응답이 느린 환경에서는 `OLLAMA_TIMEOUT_SECONDS=180`처럼 HTTP 요청 하나의 대기 시간만 늘릴 수 있습니다. 기본값은 60초이며, `OLLAMA_KEEP_ALIVE`는 모델 상주 시간이라 응답 대기 시간과 다릅니다. `.env`에는 환경별 설정이 들어가므로 Git, 이미지 아카이브, SSH 전송 대상에 포함하지 않습니다.

SQLite 저장소 권한도 확인합니다.

```bash
cd /home/<Pi 사용자명>/english_study_ai
sudo chown 10001:10001 data
sudo chmod 0750 data
chmod 0755 scripts/*.sh
```

처음 Agent 이미지를 배포하기 전에는 Ollama와 모델이 이미 준비되어 있어야 합니다.

```bash
AGENT_IMAGE=english-study-agent:bootstrap docker compose up -d ollama
AGENT_IMAGE=english-study-agent:bootstrap docker compose ps
AGENT_IMAGE=english-study-agent:bootstrap \
  docker compose exec ollama ollama show gemma3:4b
```

`english-study-agent:bootstrap`은 Compose 설정 해석에만 사용하는 임시 이름입니다. 이 단계에서는 `ollama`만 시작하므로 해당 Agent 이미지가 존재할 필요가 없습니다. 첫 배포 명령이 실제 Agent 이미지를 load하고 처음 Agent 컨테이너를 만듭니다.

## 개발 PC 준비

개발 PC에는 Docker Desktop 또는 실행 중인 Docker 데몬, Docker Buildx, 프로젝트 루트 `.venv`, Node.js/npm, Pi SSH 공개 키 인증이 필요합니다. SSH host key는 처음 연결할 때 운영자가 확인하고 저장합니다. 비밀값·SSH 키·Pi 접속 정보는 Git, 이미지, 아카이브, 로그에 넣지 않습니다.

배포 도구는 깨끗한 Git 작업 트리만 허용합니다. 따라서 배포할 변경은 테스트 가능한 커밋으로 먼저 확정해야 합니다.

## 배포 실행

개발 PC의 프로젝트 루트에서 실행합니다.

```bash
./scripts/deploy_arm64_to_pi.sh <Pi-SSH-대상> /home/<Pi 사용자명>/english_study_ai
```

예를 들어 SSH config 별칭이 `english-pi`라면 다음과 같습니다.

```bash
./scripts/deploy_arm64_to_pi.sh english-pi /home/pi/english_study_ai
```

이 명령은 다음을 순서대로 수행합니다.

1. Python과 Web 테스트를 실행합니다.
2. 현재 Git 커밋 태그로 `linux/arm64` Agent 이미지를 빌드하고 플랫폼을 확인합니다.
3. `artifacts/`에 이미지 아카이브와 SHA-256 파일을 만듭니다.
4. 이미지 아카이브와 체크섬 파일만 Pi의 `.deployment/incoming/`으로 전송합니다.
5. Pi에서 체크섬 검증, `docker load`, Agent 교체, 상태 검사를 수행합니다.
6. 실패하면 Pi가 직전 Agent 이미지로 자동 복귀합니다.
7. 성공하면 PC와 Pi의 임시 아카이브·체크섬 파일을 삭제하고, Pi에는 현재·직전 Agent 이미지 태그만 보관합니다.

Pi의 `.deployment/agent-state`에는 현재·직전 이미지 태그와 이미지 ID, Git 커밋, 아카이브 SHA-256, 배포 시각만 저장됩니다. SQLite·환경 변수·모델 정보는 기록하지 않습니다.

## 롤백 실행

개발 PC에서 직전 성공 Agent 이미지로 되돌립니다.

```bash
./scripts/rollback_agent_on_pi.sh <Pi-SSH-대상> /home/<Pi 사용자명>/english_study_ai
```

롤백은 Agent만 다시 만들고, 지침도 직전 Agent 이미지에 포함된 버전으로 함께 되돌립니다. 상태 검사에 실패하면 롤백 전 Agent 이미지로 다시 복귀를 시도합니다.

## 운영 확인

배포 또는 롤백 후에는 다음 세 계층을 독립적으로 확인합니다.

```bash
ssh <Pi-SSH-대상> 'curl -fsS http://127.0.0.1:8100/health'
ssh <Pi-SSH-대상> 'cd /home/<Pi 사용자명>/english_study_ai && docker compose exec -T ollama ollama show gemma3:4b'
```

`/health`는 Agent가 HTTP 요청에 응답하는지만 확인합니다. 브라우저에서 실제 학습 요청을 한 번 실행해 Agent와 Ollama의 전체 동작도 별도로 확인합니다.

## 주의사항

- `docker compose up --build`, `git pull`, `rsync`는 일반 Agent 배포 절차에 사용하지 않습니다.
- `docker compose down --volumes`와 `docker system prune --volumes`는 Ollama 모델을 삭제할 수 있으므로 사용하지 않습니다.
- 배포 스크립트가 정리하는 대상은 `english-study-agent` 이름의 사용하지 않는 이미지 태그와 전송 직후의 아카이브·체크섬 파일뿐입니다. 데이터 디렉터리, 백업, `.env`, Ollama 볼륨에는 삭제 명령을 실행하지 않습니다.
