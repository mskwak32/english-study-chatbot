# Raspberry Pi 운영 가이드

이 문서는 Raspberry Pi 5에서 Docker Compose로 영어 학습 챗봇을 설치하고 운영하는 방법을 설명합니다. 현재 배포는 Pi의 프로젝트 소스와 `compose.yaml`로 Agent 이미지를 빌드하는 방식입니다. 레지스트리 이미지와 CI/CD 자동 배포는 7단계에서 다룹니다.

## 구성과 데이터 보관 위치

| 대상 | 위치 | 컨테이너 재생성 후 유지 여부 |
| --- | --- | --- |
| Agent | `agent` 서비스, 내부 포트 `8000` | 이미지 재빌드·컨테이너 재생성 필요 |
| Ollama | `ollama` 서비스, 내부 포트 `11434` | 컨테이너 재생성 가능 |
| SQLite 데이터 | 호스트 `./data`, Agent `/data` bind mount | 유지 |
| 런타임 지침 | 호스트 `./instructions`, Agent `/instructions` 읽기 전용 bind mount | 유지 |
| Ollama 모델 | `ollama-models` Docker named volume | 유지. volume 삭제 시 소실 |

Agent만 호스트의 TCP `8100` 포트로 공개합니다. Ollama에는 `ports:` 설정이 없으므로 같은 Compose 네트워크의 Agent만 `http://ollama:11434`로 호출합니다.

## Docker 설치

Raspberry Pi OS가 Debian 기반이고 ARM64인지 확인합니다.

```bash
uname -m
```

`aarch64` 또는 `arm64`가 출력되어야 합니다. Docker Engine은 ARM64를 지원합니다. Docker 설치와 업데이트는 [Docker의 Debian 설치 문서](https://docs.docker.com/engine/install/debian/)에서 현재 Raspberry Pi OS 버전에 맞는 공식 `apt` 저장소 절차를 사용합니다.

설치가 끝나면 다음을 확인합니다.

```bash
docker --version
docker compose version
sudo docker run hello-world
```

현재 로그인 사용자가 `sudo` 없이 Docker를 사용하려면 해당 사용자를 `docker` 그룹에 추가한 뒤 새 로그인 세션을 시작합니다. Docker daemon 제어 권한은 사실상 높은 권한이므로, 신뢰하는 사용자에게만 부여합니다.

```bash
sudo usermod -aG docker "$USER"
```

## 최초 준비

프로젝트 디렉터리에서 실행합니다. 아래의 `<Pi 사용자명>`과 프로젝트 경로는 실제 환경에 맞게 바꿉니다.

```bash
cd /home/<Pi 사용자명>/english_study_ai
```

`data/`는 컨테이너의 비루트 Agent 사용자(UID/GID `10001`)가 SQLite DB를 만들 수 있어야 합니다. 다른 사용자가 데이터를 읽지 못하도록 권한을 제한합니다.

```bash
mkdir -p data
sudo chown 10001:10001 data
sudo chmod 0750 data
sudo ls -ldn data
```

마지막 명령에서 소유자와 그룹이 모두 `10001`, 권한이 `750`인지 확인합니다. 이 설정 때문에 일반 로그인 사용자는 `data/`를 직접 열 수 없으며, 검사나 백업에는 `sudo`가 필요합니다.

환경 변수 파일은 저장소에 넣지 않습니다. 프로젝트의 `.env.example`을 참고해 Pi에만 `.env`를 만듭니다.

```bash
cp .env.example .env
```

현재 기본값은 다음과 같습니다.

```dotenv
MODEL=gemma3:4b
OLLAMA_KEEP_ALIVE=30m
TIMEZONE=Asia/Seoul
```

`OLLAMA_BASE_URL`, `DATABASE_URL`, `INSTRUCTIONS_PATH`는 Compose 내부 연결과 mount 경로를 보장하기 위해 `compose.yaml`에 고정되어 있습니다.

## 최초 시작과 모델 설치

Agent 이미지를 빌드하고 두 서비스를 시작합니다.

```bash
docker compose up -d --build
docker compose ps
```

두 서비스가 `running`이고 health check가 `healthy`가 될 때까지 기다립니다. Agent는 Ollama health check가 통과한 뒤 시작합니다.

모델은 Ollama 컨테이너에 명시적으로 내려받습니다.

```bash
docker compose exec ollama ollama pull gemma3:4b
docker compose exec ollama ollama list
```

`gemma3:4b`가 목록에 나타나야 합니다. 모델은 `ollama-models` named volume에 저장되므로 Ollama 컨테이너를 재생성해도 유지됩니다.

## 상태와 로그 확인

```bash
# 서비스, 포트, health check 상태
docker compose ps

# Pi 자체에서 Agent liveness 확인
curl -fsS http://127.0.0.1:8100/health

# Agent 또는 Ollama의 최근 로그 확인
docker compose logs --tail=100 agent
docker compose logs --tail=100 ollama

# 로그를 계속 표시
docker compose logs -f agent
```

`GET /health`는 FastAPI Agent가 HTTP 요청에 응답하는지만 확인합니다. 모델이 실제 요청을 처리할 수 있는지는 아래 명령으로 별도로 확인합니다.

```bash
docker compose exec ollama ollama show gemma3:4b
```

## LAN 접속

Pi의 LAN IP를 확인합니다.

```bash
hostname -I
```

같은 네트워크의 PC 또는 휴대폰 브라우저에서 다음 주소로 접속합니다.

```text
http://<Pi-IP>:8100
```

이 서비스에는 로그인 기능이 없으므로 신뢰하는 사설 LAN에서만 사용합니다. 공유기 포트 포워딩, 공인 IP 공개, 외부 터널 연결은 현재 범위에 포함하지 않습니다.

Docker가 공개한 포트는 일반 방화벽 규칙과 다르게 동작할 수 있습니다. 방화벽을 구성한다면 Docker의 [방화벽 제한 사항](https://docs.docker.com/engine/install/debian/#firewall-limitations)을 먼저 확인하고, Agent의 `8100/tcp`만 필요한 LAN 대역에 허용합니다.

## 중지와 다시 시작

```bash
# 컨테이너를 중지하고 Compose가 만든 컨테이너·네트워크를 제거
docker compose down

# 기존 이미지를 사용해 다시 시작
docker compose up -d
```

`docker compose down`은 `./data` bind mount와 `ollama-models` named volume을 유지합니다. `docker compose stop`은 컨테이너를 제거하지 않고 중지만 합니다.

## 코드 업데이트와 재배포

현재 방식에서는 Pi에 최신 프로젝트 파일이 있어야 Agent 이미지를 다시 빌드할 수 있습니다. Git을 사용하는 경우 다음과 같이 업데이트합니다.

```bash
cd /home/<Pi 사용자명>/english_study_ai
git pull --ff-only
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8100/health
```

개발 PC에서 `rsync`로 프로젝트를 전송하는 경우에도 전송 뒤 마지막 세 명령을 실행합니다. `docker compose down`을 먼저 실행할 필요는 없습니다. `up -d --build`는 변경된 Agent 이미지를 빌드하고 필요한 컨테이너만 재생성합니다.

업데이트 후에는 학습 기능을 한 번 사용해 Agent와 Ollama의 종단간 요청도 확인합니다. Compose 단일 서버 배포에서 서비스 코드 변경은 이미지를 다시 빌드하고 해당 서비스를 재생성해야 한다는 [Docker Compose 운영 지침](https://docs.docker.com/compose/how-tos/production/#deploying-changes)을 따릅니다.

## SQLite 백업

SQLite 파일을 단순 복사하는 대신 SQLite의 일관된 백업 기능을 사용합니다. Pi에 `sqlite3` 명령이 없으면 먼저 설치합니다.

```bash
sudo apt update
sudo apt install sqlite3
mkdir -p backups
sudo sqlite3 data/chat.db \
  ".backup 'backups/chat-$(date +%F-%H%M%S).db'"
sudo chown "$USER":"$USER" backups/*.db
```

백업 파일을 다른 신뢰할 수 있는 저장소에도 복사합니다. 복구 절차는 기존 DB를 덮어쓸 수 있으므로 7단계의 백업·복구 검증에서 다룹니다.

## 삭제 주의사항

다음 명령은 `ollama-models` named volume을 삭제하므로 Ollama 모델을 다시 내려받아야 합니다.

```bash
# 평소 운영에서 실행하지 않음
docker compose down --volumes
```

다음 명령도 사용하지 않습니다. Docker의 다른 프로젝트 volume까지 삭제할 수 있습니다.

```bash
# 평소 운영에서 실행하지 않음
docker system prune --volumes
```

`./data`와 `./instructions`는 호스트 bind mount이므로 위 명령의 직접적인 삭제 대상은 아니지만, 프로젝트 디렉터리를 삭제하면 함께 소실됩니다. 삭제·복구 작업 전에는 SQLite 백업을 먼저 만듭니다.

## 문제 확인 순서

1. `docker compose ps`에서 `ollama`와 `agent`의 상태와 health check를 확인합니다.
2. `docker compose logs --tail=100 agent`와 `docker compose logs --tail=100 ollama`로 오류를 확인합니다.
3. `curl -fsS http://127.0.0.1:8100/health`로 Agent liveness를 확인합니다.
4. `docker compose exec ollama ollama show gemma3:4b`로 모델 존재를 확인합니다.
5. 데이터베이스 오류라면 `sudo ls -ldn data`로 소유자·그룹 `10001:10001`과 권한 `750`을 확인합니다.
6. Compose 설정을 변경했다면 `docker compose config --quiet`로 설정 파일을 확인한 뒤 서비스를 다시 시작합니다.
