FROM python:3.13

WORKDIR /app/agent

COPY pyproject.toml requirements.lock ./
COPY app ./app

RUN python -m pip install --no-cache-dir --constraint requirements.lock .

EXPOSE 8000

CMD [ "python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]