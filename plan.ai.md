# Raspberry Pi 영어 학습 챗봇 구현 계획

## 목표

Raspberry Pi 5에서 Docker Compose로 실행하고 PC·휴대폰 브라우저에서 사용하는 개인용 영어 학습 챗봇을 만든다.

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
- Docker의 FastAPI 내부 포트는 8000, 브라우저용 호스트 포트는 8100으로 사용한다.

## 단계 현황

| 단계 | 상태 | 결과 |
|---|---|---|
| 0. 환경과 제품 정책 | 완료 | Raspberry Pi 5, ARM64, LAN 우선 정책 확정 |
| 1. 프로젝트 골격과 설정 | 완료 | FastAPI, 설정 검증, Dockerfile, `GET /health` 구현 |
| 2. 런타임 지침 로딩 | 완료 | 고정 지침 파일의 안전한 로딩 구현 |
| 3. SQLite 채팅 저장 | 완료 | 날짜별 채팅, 메시지, 동시 생성 방지 구현 |
| 4. Ollama와 Python Agent | 완료 | 구조화 JSON Agent, 학습 데이터 저장, `keep_alive` 구현 |
| 5. 반응형 Web UI | 완료 | 채팅, 정보 화면, 초기 프로필 생성, 키보드 전송 구현 |
| 6. Docker Compose와 Raspberry Pi 배포 | 완료 | Agent·Ollama 분리, 영속 저장소, 최소 권한 Agent, 운영 문서화 |
| 7. PC 기반 ARM64 이미지 배포 | 진행 중 | 개발 PC 이미지 빌드·Pi 직접 전송, Agent 업데이트·롤백 절차 |

4단계의 Raspberry Pi 측정에서 `gemma3:4b` warm 요청은 첫 응답 0.52~0.53초, 전체 21.19~24.32초였고 최대 RSS는 4.20 GiB였다.

5단계 검증 결과:

- 동일 출처 Web UI와 API, 시작·삭제·새로고침 상태 전환, 반응형 화면을 확인했다.
- 초기 테스트 완료 도구의 점수·레벨·답변 수를 서버에서 검증한다.
- Python 테스트 93개와 Web 테스트 10개를 통과했다. Python 테스트에는 외부 의존성의 폐기 경고 2개가 있다.

### 6단계 검증 결과

- ARM64 Raspberry Pi 5에 Docker Engine과 Docker Compose Plugin을 설치하고 `hello-world` 실행을 확인했다.
- Agent와 Ollama를 Compose 서비스로 분리했다. Agent는 `8100:8000`으로 LAN에 공개하고, Ollama `11434`는 Compose 내부 네트워크에서만 사용한다.
- SQLite `./data` bind mount, 읽기 전용 `./instructions` bind mount, Ollama named volume에 데이터·지침·모델을 영속화했다.
- Agent는 비루트 사용자, 읽기 전용 루트 파일시스템, `/tmp` tmpfs, capability 제거, `no-new-privileges`로 실행한다.
- 테스트 전용 SQLite DB를 이용해 컨테이너 재생성 뒤 DB·모델 영속성, 운영 DB 분리, 지침 쓰기 차단을 확인했다.
- 설치·시작·중지·상태·업데이트·LAN 접속·백업·삭제 주의사항을 `docs/operations.md`에 정리했다.

## 다음 단계

### 7단계 — PC 기반 ARM64 이미지 배포

검증된 Agent 이미지를 개발 PC에서 ARM64로 빌드해 Pi에 직접 전송하고, Agent만 안전하게 교체·롤백하는 배포 절차를 구현한다.

- 개발 PC에서 Python·Web 테스트를 통과한 코드만 ARM64 Agent 이미지로 빌드한다.
- 이미지 archive를 SSH 기반 전송으로 Pi에 전달하고, Pi에서 `docker load`로 가져온다. Agent image에는 버전 고정 런타임 지침을 포함한다. SQLite DB·백업, 환경 파일, Ollama 모델은 전송하지 않는다.
- Pi의 배포용 Compose 설정은 `build:`가 아닌 전달받은 Agent 이미지를 참조한다. SQLite bind mount와 Ollama named volume은 유지한다.
- 배포 archive의 SHA-256, 이미지 태그, Git commit, Pi의 image ID를 기록하고, 실패 시 직전 Agent 이미지로 되돌릴 수 있어야 한다.
- SSH 키와 Pi 접속 정보는 개발 PC에만 보관하며 Git 저장소·이미지·로그에 포함하지 않는다.

## MVP 이후 후보

- 응답 스트리밍과 오래된 대화 요약
- 음성 입력·출력
- 로그인과 다중 사용자 지원
- 외부 공개 접속 보안
- 모델 자동 벤치마크와 학습 통계
- 학습 진도 기록, 레벨 상승/하향에 대한 도구가 없음. 도구를 만들어야 함
- GitHub Actions와 컨테이너 레지스트리를 이용한 이미지 게시·자동 배포
