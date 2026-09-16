# Raspberry Pi 운영 및 rsync 배포

이 문서는 Raspberry Pi 5에서 네이티브 Ollama와 Python Agent를 운영하고, 개발 PC에서 검증한 소스를 `rsync`로 배포하는 절차를 설명합니다.

## 구성과 보존 경계

Pi 프로젝트 루트는 다음처럼 구성합니다.

```text
/home/<Pi 사용자명>/english_study_ai/
├── .env                    # Pi별 환경 변수
├── data/                   # SQLite 데이터
├── backups/                # SQLite 백업
├── releases/<Git 커밋>/    # 배포 가능한 Agent 소스
└── current -> releases/<Git 커밋>
```

| 대상 | 위치 | 배포·롤백 중 동작 |
| --- | --- | --- |
| Agent 소스와 런타임 지침 | `releases/<Git 커밋>/` | 새 release로 교체 |
| SQLite 데이터 | `data/` | 전송·변경·삭제하지 않음 |
| 환경 변수 | `.env` | 전송·변경·삭제하지 않음 |
| SQLite 백업 | `backups/` | 전송·변경·삭제하지 않음 |
| Ollama 모델 | Ollama의 로컬 모델 저장소 | 전송·변경·삭제하지 않음 |

`current`는 실행할 release만 가리키는 심볼릭 링크입니다. 롤백은 이 링크를 직전 release로 바꾸고 Agent 서비스만 재시작합니다. 런타임 지침은 release에 포함되므로 코드와 같은 버전으로 함께 전환됩니다.

Ollama는 Pi의 `127.0.0.1:11434`에서 실행합니다. Agent는 `8100` 포트에서 LAN 요청을 받고, `.env`의 Ollama URL로 로컬 Ollama에 연결합니다.

## Pi 최초 설정

Pi 운영 사용자에게 SSH 공개 키 로그인을 설정합니다. 아래 명령은 Python 가상환경, `rsync`, 상태 확인에 필요한 도구를 설치합니다. 프로젝트는 Python 3.13 이상이 필요하므로 설치된 버전을 먼저 확인합니다.

```bash
sudo apt update
sudo apt install -y python3 python3-venv rsync curl
python3 --version
```

`python3 --version`이 3.13보다 낮으면 Pi 운영체제에 맞는 Python 3.13 이상을 설치한 뒤, 아래 명령의 `python3`을 그 실행 파일 이름으로 바꿉니다.

Ollama는 Pi에 네이티브로 설치하고 서비스가 실행 중인지 확인합니다. 설치 방법은 Ollama 공식 안내를 따릅니다.

```bash
ollama --version
sudo systemctl enable --now ollama
curl -fsS http://127.0.0.1:11434/api/tags
```

필요한 모델을 한 번만 내려받고 확인합니다. 모델 이름은 Pi `.env`의 `MODEL`과 같아야 합니다.

```bash
ollama pull gemma3:4b
ollama show gemma3:4b
```

영속 경로를 Pi에서 한 번 만듭니다.

```bash
PI_PROJECT=/home/<Pi 사용자명>/english_study_ai
mkdir -p "$PI_PROJECT"/{data,backups,releases}
```

첫 배포 도구는 Pi 루트의 `.env`가 없을 때만 release의 예시 설정을 바탕으로 `.env`를 만들고 권한을 `0600`으로 설정합니다. 기존 `.env`는 절대 덮어쓰지 않습니다. 자동 생성된 값에는 Pi의 영속 `data/` 경로와 `current` release의 지침 경로가 포함됩니다.

최초 배포 후 `.env`를 검토해 Pi별 값을 조정합니다. `OLLAMA_BASE_URL`은 로컬 Ollama 주소여야 합니다.

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
DATABASE_URL=sqlite:////home/<Pi 사용자명>/english_study_ai/data/chat.db
INSTRUCTIONS_PATH=/home/<Pi 사용자명>/english_study_ai/current/instructions
```

응답이 느린 환경에서는 `OLLAMA_TIMEOUT_SECONDS=180`처럼 HTTP 요청 하나의 대기 시간만 늘릴 수 있습니다. 기본값은 60초이며, `OLLAMA_KEEP_ALIVE`는 모델 상주 시간이라 응답 대기 시간과 다릅니다.

## 최초 배포와 서비스 등록

개발 PC에는 프로젝트 루트 `.venv`, Node.js/npm, `rsync`, Pi SSH 공개 키 인증이 필요합니다. 최초 배포도 일반 배포와 같은 명령으로 release를 전송합니다.

```bash
PI_PYTHON_BIN=python3.13 \
  ./scripts/deploy_to_pi.sh <Pi-SSH-대상> /home/<Pi 사용자명>/english_study_ai
```

이 명령은 Python·Web 테스트를 통과한 현재 Git 커밋을 `releases/<Git 커밋>/`으로 전송하고, Pi 프로젝트 루트의 가상환경과 의존성을 준비합니다. `PI_PYTHON_BIN`은 Pi의 Python 3.13 이상 실행 파일을 지정합니다. 첫 실행에서는 `scripts/systemd/english-study-agent.service.template`을 사용해 `english-study-agent` 서비스를 설치·활성화하므로 Pi의 `sudo` 비밀번호 입력을 요청할 수 있습니다. 이후 Pi에서 서비스 상태를 확인합니다.

```bash
sudo systemctl status english-study-agent
curl -fsS http://127.0.0.1:8100/health
ollama show gemma3:4b
```

`/health`는 Agent의 HTTP 응답만 확인합니다. 브라우저에서 실제 학습 요청을 한 번 실행해 Agent와 Ollama의 전체 동작도 별도로 확인합니다.

## 일반 배포

개발 PC의 프로젝트 루트에서 같은 명령을 실행합니다. Agent 서비스가 이미 설치되어 있어야 합니다.

```bash
PI_PYTHON_BIN=python3.13 \
  ./scripts/deploy_to_pi.sh <Pi-SSH-대상> /home/<Pi 사용자명>/english_study_ai
```

배포 도구는 다음 순서로 동작합니다.

1. Python과 Web 테스트를 실행합니다.
2. 현재 Git 커밋으로 release 이름을 정하고, 소스와 런타임 지침을 `rsync`로 전송합니다.
3. Pi 프로젝트 루트의 가상환경과 의존성을 준비합니다.
4. `current` 링크를 새 release로 바꾸고 Agent 서비스만 재시작합니다.
5. `/health` 검사에 실패하면 `current`를 직전 release로 되돌립니다.

`rsync` 대상에는 `.env`, `data/`, `backups/`, 가상환경, 테스트 소스가 포함되지 않습니다. 배포 전 커밋되지 않은 변경이 있으면 중단하므로, 배포할 변경은 먼저 Git 커밋으로 확정해야 합니다.

## 롤백

개발 PC에서 직전 성공 release로 되돌립니다.

```bash
./scripts/rollback_on_pi.sh <Pi-SSH-대상> /home/<Pi 사용자명>/english_study_ai
```

롤백은 `current` 링크와 Agent 서비스만 변경합니다. SQLite DB, 백업, `.env`, Ollama 서비스와 모델은 그대로 유지됩니다. 롤백 후 `/health`와 실제 학습 요청을 확인합니다.

## 보안과 주의사항

- `.env`는 `0600` 권한으로 유지하고 Git·`rsync` 대상·로그에 포함하지 않습니다.
- Agent 서비스는 전용 운영 사용자로 실행하고, systemd unit의 `NoNewPrivileges`와 파일시스템 보호 설정을 유지합니다.
- Ollama는 `127.0.0.1:11434`에만 바인딩합니다. 외부에서 Ollama 포트에 직접 접근할 필요가 없습니다.
- `data/`, `backups/`, `.env`, Ollama 모델 저장소를 재귀 삭제하는 명령은 배포·롤백 절차에 포함하지 않습니다.
- release를 수동으로 삭제하기 전에는 `current`와 직전 롤백 대상이 무엇인지 확인합니다.
