# Raspberry Pi 영어 학습 챗봇 구현 계획

## 1. 최종 목표

Raspberry Pi 5에서 Docker Compose로 실행되며, PC와 휴대폰 브라우저에서 이용할 수 있는 개인용 로컬 영어 학습 챗봇을 만든다.

- 로컬 LLM은 Ollama를 통해 실행한다.
- Python Agent가 프롬프트 구성, 학습 데이터 도구, 채팅 저장을 담당한다.
- 채팅과 메시지는 SQLite에 저장한다.
- 학습 프로필, 복습 단어, 학습 이력은 채팅과 함께 SQLite에 저장한다.
- 영어 튜터 지침과 학습 가이드라인은 `instructions/`에 보존한다.
- 애플리케이션은 `instructions/`의 고정 런타임 문서만 읽는다.

## 2. 목표 디렉터리 구조

```text
english_study_ai/
├── AGENTS.md                 # Codex 개발 지침
├── plan.ai.md                # 단계별 구현 계획과 진행 상태
├── README.md                 # 설치, 실행, 운영 방법
├── TODO.md                   # 현재 단계의 세부 작업 목록
├── Dockerfile                # 프로젝트 루트 컨텍스트를 사용하는 이미지 빌드
├── .env.example              # 환경 변수 예시
├── .gitignore
├── docker-compose.yml
├── backend/                 # Python 백엔드 서비스
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py           # API 및 애플리케이션 진입점
│   │   ├── config.py
│   │   ├── instructions.py   # 고정 런타임 지침 로딩
│   │   ├── study_time.py     # UTC 시각 변환과 사용자 기준 학습 날짜 계산
│   │   ├── agent/            # 구조화 응답 검증과 도구 호출 반복
│   │   │   ├── __init__.py
│   │   │   ├── protocol.py   # LLM 구조화 JSON 응답 검증
│   │   │   └── runner.py     # LLM 요청과 도구 호출 반복 조정
│   │   ├── llm/              # 교체 가능한 LLM 인터페이스와 구현체
│   │   │   ├── __init__.py
│   │   │   ├── client.py     # 공통 LLM 인터페이스와 오류
│   │   │   └── ollama.py     # Ollama HTTP 어댑터
│   │   ├── database/          # SQLite 저장 계층
│   │   │   ├── __init__.py
│   │   │   ├── connection.py # URL 검증 및 DB 연결 생성
│   │   │   ├── schema.py     # 스키마 초기화와 마이그레이션
│   │   │   ├── chats.py      # 채팅 조회·생성·삭제
│   │   │   ├── messages.py   # 메시지 저장·조회
│   │   │   ├── learning_profiles.py
│   │   │   ├── review_words.py
│   │   │   └── study_records.py
│   │   ├── services/         # API 요청용 채팅 생성과 프롬프트 준비 흐름
│   │   └── llm_tools/        # LLM이 요청할 수 있는 학습 데이터 도구
│   └── tests/
├── web/                      # 자체 Web UI
├── data/                     # SQLite 등 런타임 데이터
├── docs/
│   ├── ARCHITECTURE.md
│   └── SECURITY.md
└── instructions/
    ├── AGENT.md              # 영어 교사 LLM의 런타임 지침
    └── 영어_가이드라인.md    # 영어 학습 방식과 진행 기준
```

Docker 빌드 컨텍스트는 프로젝트 루트를 사용한다.

아직 사용하지 않는 디렉터리와 파일은 해당 구현 단계에서 생성한다.

## 3. 단계별 계획

### 0단계 — 환경과 제품 정책 결정

**상태:** 완료 (2026-09-03)

실행 환경:

- Raspberry Pi 5, ARM64, Debian GNU/Linux 13.6
- RAM 7.9 GiB, swap 2.0 GiB
- Samsung SSD 970 EVO NVMe 465.8 GiB

확정 정책:

- 자체 Web UI, 단일 사용자
- 날짜별 기본 채팅 1개와 추가 학습 채팅
- LAN 우선, 로그인과 보안 구현 후 DDNS·포트 포워딩 검토
- FastAPI, Python 3.13, pytest, SQLite, `Asia/Seoul`
- Ollama 기반 로컬 LLM

초기 모델 및 성능 기준:

- 우선 후보: Ollama의 `gemma3:4b` (Pi 성능 기준 통과 전까지 미확정)
- 대체 후보: 1B급 Gemma 모델(4B가 느리거나 메모리 부족일 때)
- 초기 벤치마크: 첫 응답 시작 시간, 전체 응답 시간, 메모리 최고 사용량 기록
- 제안 합격 기준: 첫 응답 시작 5초 이내, 약 80단어 답변 완료 30초 이내, swap 과다 사용 없음

---

### 1단계 — 프로젝트 골격과 설정

**상태:** 완료 (2026-09-04)

구현 및 검증 결과:

- FastAPI 앱, `GET /health`, 설정 기본값·환경 변수·형식 검증, 기본 로깅 구현
- `.env` 지원, `.env.example`, `requirements.lock`, Dockerfile, `.dockerignore` 작성
- Python 3.13 로컬 테스트: `9 passed` (외부 의존성의 향후 변경 경고 2개)
- ARM64 Docker 이미지 빌드, 컨테이너 실행, `GET /health`의 HTTP 200 응답 확인

---

### 2단계 — 고정 런타임 지침 로딩

**상태:** 완료 (2026-09-07)

확정 정책:

- `instructions/AGENT.md` 누락 또는 읽기 실패 시 애플리케이션 시작 실패
- 학습 가이드라인도 고정 런타임 문서로 읽는다.
- 구조화된 학습 자료는 4단계부터 SQLite에 저장한다.

구현 및 검증 결과:

- `instructions/AGENT.md`와 `영어_가이드라인.md`의 고정 경로 로딩
- 누락·빈 파일·UTF-8 오류·심볼릭 링크를 시작 오류로 처리
- 4단계 DB 전환에서 범용 파일 도구와 학습 자료 템플릿 제거

---

### 3단계 — SQLite 채팅 저장

**상태:** 완료 (2026-09-08)

확정한 정책:

- `Asia/Seoul` 날짜마다 기본 학습 채팅을 정확히 하나만 둔다.
- 추가 학습은 같은 날짜에 생성하며 제목은
  `{기본 제목} - 추가 학습 (N)` 형식으로 자동 생성한다. `N`은 1부터 시작한다.
- 추가 학습을 삭제한 뒤에는 비어 있는 번호를 다시 사용할 수 있다.
- 사용자가 채팅 제목을 직접 변경하는 기능은 포함하지 않는다.

구현 및 검증 결과:

- 절대 경로 SQLite URL 검증과 연결별 외래 키 제약 활성화
- `schema_migrations`를 사용한 버전 1 스키마 마이그레이션 적용
- 날짜별 기본 채팅과 추가 학습 채팅의 생성·조회·목록·삭제 구현
- 삭제한 추가 학습 번호 재사용과 사용자 제목 변경 제외 정책 반영
- 사용자 및 assistant 메시지의 순서 보장 저장과 조회 구현
- `Asia/Seoul` 학습일 계산과 오늘의 기본 채팅 서비스 구현
- 앱 시작 시 데이터베이스 스키마 초기화
- 동시 기본 채팅·추가 채팅·메시지 요청의 중복 방지 검증
- 채팅 삭제 시 연결된 메시지만 cascade 삭제됨을 검증
- Ruff 포맷·린트 검사 통과
- 전체 테스트: `55 passed` (사용자 확인)

---

### 4단계 — Ollama와 Python Agent 연동

**상태:** 완료 (2026-09-10)

모델을 교체할 수 있는 추상화와 영어 학습용 대화 흐름을 구현한다.

확정 정책:

- MVP의 기본 조합은 `gemma3:4b`와 구조화 JSON 프로토콜로 한다.
- `gemma3:4b`가 네이티브 도구 호출을 지원하지 않으므로 JSON Schema로 행동과 인자를 제한하고 Python에서 다시 검증한다.
- 같은 채팅의 전체 메시지를 매 요청에 전달하고 다른 채팅은 포함하지 않는다.
- 튜터 지침과 학습 가이드라인은 `instructions/`에서 읽는다.
- 학습 프로필, 복습 단어, 최근 학습 이력 5개는 SQLite에서 읽는다.
- 기존 Markdown 학습 기록은 가져오지 않고 빈 DB에서 새 학습자로 시작한다.
- 임의의 메시지 개수 제한 대신 Ollama의 입력 토큰 수와 Pi 성능을 측정한 뒤 요약이나 제한 필요성을 판단한다.
- Ollama 요청의 `keep_alive` 기본값은 `30m`이며, `OLLAMA_KEEP_ALIVE` 환경 변수로 바꿀 수 있다. 짧은 학습 세션 사이의 모델 재로딩을 줄이는 용도이다.
- 전체 Agent 요청에는 별도 시간 제한을 두지 않는다. Ollama HTTP 요청 하나의 제한 시간은 60초이며, 도구 호출 뒤의 다음 모델 요청은 별도로 제한 시간을 적용한다.

구현 항목:

- Ollama 상태 및 모델 가용성 확인
- 교체 가능한 LLM 어댑터 인터페이스
- 학습 프로필, 실력 테스트, 레벨 변경, 복습 단어, 학습 이력의 SQLite 저장 계층
- 런타임 지침, 최근 채팅, 필요한 학습 자료를 조합하는 프롬프트
- 구조화 JSON 응답을 검증하는 학습 데이터 도구 실행 루프
- 모델 연결 및 도구 오류의 안전한 처리
- 요청과 응답의 DB 저장

구현 및 검증 결과:

- Ollama HTTP 어댑터, 모델 가용성 확인, 구조화 JSON 응답 검증, 학습 데이터 도구 호출 반복을 구현했다.
- 현재 채팅 전체, 고정 런타임 지침, SQLite 학습 자료를 조합해 모델에 전달하고, 사용자 메시지와 응답을 저장하는 채팅 API를 구현했다.
- 설정값 `OLLAMA_KEEP_ALIVE`를 `/api/chat` 요청의 `keep_alive`로 전달한다.
- Raspberry Pi 5에서 `gemma3:4b`를 측정했다. cold 요청은 첫 응답 12.09초·전체 36.69초(모델 로드 9.77초)였고, warm 요청 3회는 첫 응답 0.52~0.53초·전체 21.19~24.32초였다.
- warm 요청의 최대 RSS는 4.20 GiB, swap 사용량은 최대 24.2 MiB였다. warm 성능을 기준으로 `gemma3:4b`를 MVP 기본 모델로 채택하고 `keep_alive=30m`으로 cold 시작을 줄인다.

완료 기준:

- 모델명을 환경 변수로 바꿀 수 있음
- 영어 대화와 교정 응답이 저장됨
- 허용된 도구만 호출됨
- Ollama 장애 시 사용자가 이해할 수 있는 오류를 반환함

---

### 5단계 — 반응형 Web UI

**상태:** 진행 중 (2026-09-10)

PC와 휴대폰에서 사용할 채팅 화면을 만든다.

확정 정책:

- Chrome, Edge, Firefox, Safari의 최근 2개 주요 버전을 지원한다.
- 최소 화면 크기는 360×640이며, 360px·768px·1280px 너비에서 반응형 레이아웃을 검증한다.
- MVP에는 응답 스트리밍을 포함하지 않는다.
- 모델 응답을 기다리는 동안 로딩 상태를 표시하고, 검증이 끝난 응답만 화면에 출력한다.

구현 항목:

- 오늘 학습 자동 열기
- 메시지 입력과 응답 표시
- 날짜별 채팅 목록과 과거 채팅 열기
- 새 채팅 생성
- 확인 절차가 포함된 채팅 삭제
- 로딩, 오류, 빈 화면 상태
- 모바일 반응형 레이아웃

완료 기준:

- PC와 휴대폰에서 핵심 흐름이 작동함
- 새로고침 후 기존 채팅이 복원됨
- UI가 서버 파일이나 Ollama에 직접 접근하지 않음

---

### 6단계 — Docker Compose와 Raspberry Pi 배포

**상태:** 대기

Agent와 Ollama를 분리하고 데이터를 영속화한다.

필요한 것:

- Raspberry Pi SSH 또는 직접 실행 환경
- Docker Engine과 Compose 플러그인
- 모델 및 DB를 보관할 저장공간
- LAN 접속 환경

구현 항목:

- ARM64 호환 Agent 이미지
- `agent`, `ollama` 서비스 구성
- 브라우저 접속용 호스트 포트 `8100`을 Agent 컨테이너의 FastAPI 포트 `8000`에 연결
- 모델, SQLite, 런타임 지침 영속 볼륨
- 비루트 컨테이너와 최소 권한
- health check 및 재시작 정책
- LAN 접속과 운영 문서

완료 기준:

- Pi에서 `docker compose up -d --build`로 실행됨
- 컨테이너 재생성 후 DB, 런타임 지침, 모델이 유지됨
- 휴대폰에서 접속 가능함
- Docker 소켓이나 불필요한 호스트 경로가 노출되지 않음

---

### 7단계 — 통합 검증과 운영 준비

**상태:** 대기

MVP 전체 흐름을 검증하고 백업 및 장애 대응 방법을 문서화한다.

필요한 것:

- SQLite와 런타임 지침 백업 위치 및 주기
- 로그 보존 기간

구현 항목:

- 전체 사용자 흐름 통합 테스트
- 백업 및 복구 절차
- 데이터 손상 및 Ollama 장애 대응
- `README.md`를 포함한 설치·업데이트·운영 문서 완성

완료 기준:

- 주요 MVP 시나리오가 모두 통과함
- 백업에서 DB와 런타임 지침을 복구할 수 있음
- 운영자가 설치, 시작, 중지, 업데이트, 문제 확인을 문서만 보고 수행할 수 있음

## 4. MVP 이후 후보

MVP 완료 전에는 기본 범위에 포함하지 않는다.

- 응답 스트리밍
- 오래된 대화 요약과 컨텍스트 예산 관리
- 음성 입력, STT, TTS
- 로그인과 사용자 계정 관리
- DDNS와 공유기 포트 포워딩을 통한 외부 브라우저 접속
- 리버스 프록시, HTTPS 인증서 발급·자동 갱신
- 외부 공개 접속의 접근 제어, 접속 기록, 보안 점검
- 다중 사용자 지원
- Gemma와 다른 모델의 자동 벤치마크
- Raspberry Pi 벤치마크 후 `qwen3.5:4b`와 네이티브 도구 호출로 선택적 전환
- 학습 통계 및 시각화

## 5. Ruff 명령어

```bash
# 포맷 검사 / 수정
.venv/bin/python -m ruff format --check backend
.venv/bin/python -m ruff format backend

# 린트 검사 / 자동 수정
.venv/bin/python -m ruff check backend
.venv/bin/python -m ruff check --fix backend
```
