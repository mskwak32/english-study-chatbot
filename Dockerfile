FROM python:3.13

# 읽기 전용 컨테이너에서 Python 바이트코드 캐시 쓰기를 막음
ENV PYTHONDONTWRITEBYTECODE=1

# Agent 프로세스를 비루트 사용자로 실행
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home \
    --shell /usr/sbin/nologin app

WORKDIR /app

COPY backend/pyproject.toml backend/requirements.lock ./
COPY backend/app ./app
COPY instructions /instructions
COPY web /web

RUN python -m pip install --no-cache-dir --constraint requirements.lock .

USER app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
