"""읽기 전용 설정 상태 API의 응답 계약을 검증합니다."""

from collections.abc import Iterator
import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from app import main
from app.api import settings as settings_api
from app.database import create_additional_chat
from app.services.system_status import (
    LearningDataStatus,
    ModelStatus,
    OllamaStatus,
    SettingsStatus,
    SystemStatus,
    _read_learning_data_status,
)
from app.services import system_status
from fastapi.testclient import TestClient


@pytest.fixture
def configured_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, str]]:
    """상태 API가 별도의 SQLite 데이터베이스를 사용하도록 준비합니다."""
    database_url = f"sqlite:///{tmp_path / 'data' / 'chat.db'}"
    instructions_path = tmp_path / "instructions"
    instructions_path.mkdir()

    for filename in ("AGENT.md", "영어_가이드라인.md", "초기_실력_테스트.md"):
        (instructions_path / filename).write_text("테스트 지침", encoding="utf-8")

    monkeypatch.setattr(main.settings, "database_url", database_url)
    monkeypatch.setattr(main.settings, "instructions_path", instructions_path)

    with TestClient(main.app) as client:
        yield client, database_url


def test_settings_status_returns_camel_case_read_only_contract(
    configured_client: tuple[TestClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """상태 API는 프론트엔드용 camelCase 계약과 null 미확인값을 반환합니다."""
    client, _ = configured_client

    async def collect_stub(**_: str) -> SettingsStatus:
        return SettingsStatus(
            model=ModelStatus(
                name="Gemma 3 4B",
                ollama_name="gemma3:4b",
                size="3.3 GB",
                loaded=True,
            ),
            ollama=OllamaStatus(
                api_connected=False,
                version=None,
            ),
            system=SystemStatus(
                cpu_usage=37,
                memory_used="3.2 GB",
                memory_total="8.0 GB",
                disk_used="42.0 GB",
                disk_total="128.0 GB",
            ),
            learning_data=LearningDataStatus(chat_count=1, size="128.0 MB"),
        )

    monkeypatch.setattr(settings_api, "collect_settings_status", collect_stub)

    response = client.get("/settings/status")

    assert response.status_code == 200
    assert response.json() == {
        "model": {
            "name": "Gemma 3 4B",
            "ollamaName": "gemma3:4b",
            "size": "3.3 GB",
            "loaded": True,
        },
        "ollama": {
            "apiConnected": False,
            "version": None,
        },
        "system": {
            "cpuUsage": 37,
            "memoryUsed": "3.2 GB",
            "memoryTotal": "8.0 GB",
            "diskUsed": "42.0 GB",
            "diskTotal": "128.0 GB",
        },
        "learningData": {"chatCount": 1, "size": "128.0 MB"},
    }


def test_learning_data_status_counts_chats_and_database_size(
    configured_client: tuple[TestClient, str],
) -> None:
    """학습 데이터 상태는 chats 테이블과 SQLite 파일 크기를 기준으로 계산합니다."""
    _, database_url = configured_client
    create_additional_chat(
        database_url,
        study_date=date(2026, 9, 17),
        created_at=datetime(2026, 9, 17, tzinfo=UTC),
    )

    learning_data = _read_learning_data_status(database_url)

    assert learning_data.chat_count == 1
    assert learning_data.size is not None


def test_ollama_status_keeps_available_values_when_one_api_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """모델 목록 조회가 실패해도 버전과 로드 상태는 독립적으로 반환합니다."""

    async def request_json_stub(_client: object, _method: str, path: str) -> object:
        responses = {
            "/api/version": {"version": "0.12.0"},
            "/api/ps": {"models": [{"name": "gemma3:4b", "size": 1024**3}]},
            "/api/tags": None,
        }
        return responses[path]

    monkeypatch.setattr(system_status, "_request_json", request_json_stub)

    model, ollama = asyncio.run(
        system_status._read_ollama_status("gemma3:4b", "http://ollama:11434")
    )

    assert model.loaded is True
    assert model.size == "1.0 GB"
    assert ollama.api_connected is True
    assert ollama.version == "0.12.0"
