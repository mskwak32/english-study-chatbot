from pathlib import Path

import pytest
from app import main
from app.database import connect_database
from fastapi.testclient import TestClient


@pytest.fixture
def temporary_app_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    """수명 주기 테스트가 사용할 임시 workspace와 데이터베이스를 설정합니다."""
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    (workspace_path / "AGENT.md").write_text(
        "테스트용 런타임 지침",
        encoding="utf-8",
    )
    (workspace_path / "영어_가이드라인.md").write_text(
        "테스트용 학습 가이드라인",
        encoding="utf-8",
    )

    monkeypatch.setattr(main.settings, "database_url", database_url)
    monkeypatch.setattr(main.settings, "workspace_path", workspace_path)

    return database_url


def test_health_check(temporary_app_settings: str) -> None:
    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lifespan_initializes_database(
    temporary_app_settings: str,
) -> None:
    with TestClient(main.app):
        pass

    connection = connect_database(temporary_app_settings)

    try:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert {
        "chats",
        "messages",
        "learning_profiles",
        "proficiency_tests",
        "level_changes",
        "review_words",
        "study_records",
    } <= table_names
