from app.config import Settings
from pydantic import ValidationError
import pytest

def test_settings_use_defaults() -> None:
    settings = Settings()
    
    assert settings.model == "gemma3:4b"
    assert settings.ollama_base_url == "http://localhost:11434"
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
        ValidationError,
        match="OLLAMA_BASE_URL must be a valid HTTP URL"
    ):
        Settings()
        
def test_settings_reject_invalid_timezone(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "Seoul")
    
    with pytest.raises(
        ValidationError,
        match="TZ must be a valid IANA time zone"
    ):
        Settings()
        
def test_settings_reject_relative_workspace_path(monkeypatch) -> None:
    monkeypatch.setenv("WORKSPACE_PATH", "workspace")
    
    with pytest.raises(
        ValidationError,
        match="WORKSPACE_PATH must be an absolute path"
    ):
        Settings()
        
def test_settings_reject_non_sqlite_database_url(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://localhost/english_study"
    )
    
    with pytest.raises(
        ValidationError,
        match="DATABASE_URL must be an absolute SQLite URL"
    ):
        Settings()