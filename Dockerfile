FROM python:3.13

# 읽기 전용 컨테이너 파일시스템에서 Python 바이트코드 캐시 쓰기를 막음
ENV PYTHONDONTWRITEBYTECODE=1

# 컨테이너 내부에서만 사용하는 비루트 Agent 사용자 생성.
# 고정 UID/GID는 bind mount의 호스트 파일 권한을 일관되게 설정할 수 있게 합니다.
# 호스트 파일의 권한을 동일하게 맞춰주어야 합니다.
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home \
    --shell /usr/sbin/nologin app

WORKDIR /app

COPY backend/pyproject.toml backend/requirements.lock ./
COPY backend/app ./app
COPY instructions /instructions
COPY web /web

RUN python -m pip install --no-cache-dir --constraint requirements.lock .

# 패키지 설치 이후 Agent 프로세스는 root가 아닌 app 사용자로 실행
USER app

# 컨테이너 내부 FastAPI 포트
EXPOSE 8000

# FastAPI 서버 실행
CMD [ "python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
