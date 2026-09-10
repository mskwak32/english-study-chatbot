import pytest
from app.config import PROJECT_ROOT, Settings
from pydantic import ValidationError


def test_settings_use_defaults() -> None:
    settings = Settings()

    assert settings.model == "gemma3:4b"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.instructions_path == PROJECT_ROOT / "instructions"
    assert settings.tz == "Asia/Seoul"


def test_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("MODEL", "test-model")
    monkeypatch.setenv("TZ", "UTC")

    settings = Settings()

    assert settings.model == "test-model"
    assert settings.tz == "UTC"


def test_settings_reject_empty_model(monkeypatch) -> None:
    monkeypatch.setenv("MODEL", "  ")

    with pytest.raises(ValidationError, match="MODEL must not be empty"):
        Settings()


def test_settings_reject_invalid_ollama_base_url(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "localhost:11434")

    with pytest.raises(
        ValidationError, match="OLLAMA_BASE_URL must be a valid HTTP URL"
    ):
        Settings()


def test_settings_reject_invalid_timezone(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "Seoul")

    with pytest.raises(ValidationError, match="TZ must be a valid IANA time zone"):
        Settings()


def test_settings_reject_relative_instructions_path(monkeypatch) -> None:
    monkeypatch.setenv("INSTRUCTIONS_PATH", "instructions")

    with pytest.raises(
        ValidationError, match="INSTRUCTIONS_PATH must be an absolute path"
    ):
        Settings()


def test_settings_reject_non_sqlite_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/english_study")

    with pytest.raises(
        ValidationError, match="DATABASE_URL must be an absolute SQLite URL"
    ):
        Settings()


def test_settings_read_dotenv_file(tmp_path, monkeypatch) -> None:
    # 터미널 환경 변수가 .env보다 우선하는 영향 제거
    monkeypatch.delenv("MODEL", raising=False)
    monkeypatch.delenv("TZ", raising=False)

    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("MODEL=dotenv-model\nTZ=UTC\n", encoding="utf-8")

    settings = Settings(_env_file=dotenv_file)

    assert settings.model == "dotenv-model"
    assert settings.tz == "UTC"
