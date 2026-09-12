FROM python:3.13

WORKDIR /app

COPY backend/pyproject.toml backend/requirements.lock ./
COPY backend/app ./app
COPY instructions /instructions
COPY web /web

RUN python -m pip install --no-cache-dir --constraint requirements.lock .

EXPOSE 8000

CMD [ "python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
