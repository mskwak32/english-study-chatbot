# Raspberry Pi 영어 학습 챗봇 구현 계획

## 목표

Raspberry Pi 5에서 Docker Compose로 Ollama와 Python Agent를 실행하고 PC·휴대폰 브라우저에서 사용하는 개인용 영어 학습 챗봇을 만든다.

- Ollama와 Python Agent, SQLite, 자체 Web UI를 사용한다.
- 채팅, 학습 프로필, 실력 테스트, 복습 단어, 학습 이력은 SQLite에 저장한다.
- 튜터 지침과 학습 가이드라인은 `instructions/`의 고정 런타임 문서만 사용한다.

## 확정 정책

- 단일 사용자, `Asia/Seoul` 기준 날짜별 기본 채팅 1개와 추가 학습 채팅을 사용한다.
- 기본 모델은 `gemma3:4b`이며 `OLLAMA_KEEP_ALIVE=30m`을 사용한다.
- 모델과 Ollama URL은 환경 변수로 설정한다.
- JSON Schema로 LLM 행동을 제한하고 Python에서 다시 검증한다. Ollama 전송용 스키마에서는 `maxLength`를 제거하고 Pydantic 검증에는 유지한다.
- 초기 실력 테스트는 14문항이다. 초기 테스트 세션의 사용자 답변이 14개 쌓이기 전에는 완료 도구를 선택하거나 저장할 수 없다.
- Web UI는 Chrome, Edge, Firefox, Safari의 최근 2개 주요 버전과 최소 360×640 화면을 지원한다. MVP에는 응답 스트리밍을 포함하지 않는다.
- Agent는 LAN의 `8100` 포트를 사용하고, Ollama는 Compose 내부 네트워크에서만 연결한다.
- Pi의 `.env`, `data/`, `backups/`, Ollama 모델 volume은 계속 보관하는 데이터이며 배포·롤백에서 전송·삭제·변경하지 않는다.

## 단계 현황

| 단계 | 상태 | 결과 |
|---|---|---|
| 0. 환경과 제품 정책 | 완료 | Raspberry Pi 5, ARM64, LAN 우선 정책 확정 |
| 1. 프로젝트 골격과 설정 | 완료 | FastAPI, 설정 검증, `GET /health` 구현 |
| 2. 런타임 지침 로딩 | 완료 | 고정 지침 파일의 안전한 로딩 구현 |
| 3. SQLite 채팅 저장 | 완료 | 날짜별 채팅, 메시지, 동시 생성 방지 구현 |
| 4. Ollama와 Python Agent | 완료 | 구조화 JSON Agent, 학습 데이터 저장, `keep_alive` 구현 |
| 5. 반응형 Web UI | 완료 | 채팅, 정보 화면, 초기 프로필 생성, 키보드 전송 구현 |
| 6. Docker Compose Pi 운영 기반 | 진행 중 | Agent·Ollama 분리, SQLite와 모델 volume 계속 보관 |
| 7. rsync 기반 Pi 이미지 빌드·배포 | 진행 중 | PC 검증 후 소스 전송, Pi Agent 이미지 빌드·태그·롤백 |

4단계의 Raspberry Pi 측정에서 `gemma3:4b` warm 요청은 첫 응답 0.52~0.53초, 전체 21.19~24.32초였고 최대 RSS는 4.20 GiB였다.

5단계 검증 결과:

- 동일 출처 Web UI와 API, 시작·삭제·새로고침 상태 전환, 반응형 화면을 확인했다.
- 초기 테스트 완료 도구의 점수·레벨·답변 수를 서버에서 검증한다.
- Python 테스트 93개와 Web 테스트 10개를 통과했다. Python 테스트에는 외부 의존성의 폐기 경고 2개가 있다.

### 6·7단계 완료 조건

- Pi에는 Docker Engine과 Compose Plugin이 설치되고, Compose가 Ollama와 Agent를 실행한다.
- Ollama 모델은 named volume에 보관하며, Agent만 다시 빌드·재생성해도 모델 volume은 유지된다.
- 개발 PC의 한 배포 명령은 Python·Web 테스트와 clean Git 확인 후 소스를 `rsync`로 전송하고, Pi에서 현재 Git 커밋의 12자리 SHA 태그로 Agent 이미지를 빌드·실행한다.
- Agent 이미지는 코드와 `instructions/`를 포함하고, Pi 호스트의 `instructions/`를 mount하지 않는다.
- 개발 PC의 한 롤백 명령은 `.deployment/agent-tags`에 기록한 직전 태그로 Agent만 다시 만든다.
- 최신 배포·직전 태그 롤백·최신 태그 재배포 동안 SQLite DB·백업·`.env`·Ollama 모델 volume이 유지되는 것을 검증한다.
- `OLLAMA_TIMEOUT_SECONDS` 기본값은 60초이며 Pi `.env`로 환경별 값을 설정할 수 있다. SSH 키와 Pi 접속 정보는 개발 PC에만 보관한다.

## MVP 이후 후보

- 응답 스트리밍과 오래된 대화 요약
- 음성 입력·출력
- 로그인과 다중 사용자 지원
- 외부 공개 접속 보안
- 모델 자동 벤치마크와 학습 통계
- GitHub Actions를 이용한 테스트 자동화와 컨테이너 레지스트리 이미지 배포
