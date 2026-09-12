"""애플리케이션 환경 설정을 읽고 검증합니다."""

from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """환경 변수와 프로젝트 루트의 .env에서 실행 설정을 읽고 검증합니다."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    model: str = "gemma3:4b"
    ollama_base_url: str = "http://localhost:11434"
    ollama_keep_alive: str = "30m"
    instructions_path: Path = PROJECT_ROOT / "instructions"
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'chat.db'}"
    timezone: str = "Asia/Seoul"

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """모델 이름이 비어 있지 않도록 검증합니다."""
        value = value.strip()

        if not value:
            raise ValueError("MODEL must not be empty")

        return value

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_base_url(cls, value: str) -> str:
        """Ollama 주소가 유효한 HTTP URL인지 검증합니다."""
        parsed = urlparse(value)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("OLLAMA_BASE_URL must be a valid HTTP URL")

        return value.rstrip("/")

    @field_validator("ollama_keep_alive")
    @classmethod
    def validate_ollama_keep_alive(cls, value: str) -> str:
        """모델 유지 시간이 비어 있지 않도록 검증합니다."""
        value = value.strip()

        if not value:
            raise ValueError("OLLAMA_KEEP_ALIVE must not be empty")

        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """시간대가 유효한 IANA 식별자인지 검증합니다."""
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("TIMEZONE must be a valid IANA time zone") from error

        return value

    @field_validator("instructions_path")
    @classmethod
    def validate_instructions_path(cls, value: Path) -> Path:
        """지침 경로가 절대 경로인지 검증합니다."""
        if not value.is_absolute():
            raise ValueError("INSTRUCTIONS_PATH must be an absolute path")

        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """데이터베이스 주소가 절대 SQLite URL인지 검증합니다."""
        if not value.startswith("sqlite:////"):
            raise ValueError("DATABASE_URL must be an absolute SQLite URL")

        return value


settings = Settings()
