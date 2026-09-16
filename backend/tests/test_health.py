from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.database import connect_database


@pytest.fixture
def temporary_app_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    """수명 주기 테스트에 필요한 지침과 데이터베이스를 준비합니다."""
    database_path = tmp_path / "data" / "chat.db"
    database_url = f"sqlite:///{database_path}"
    instructions_path = tmp_path / "instructions"
    instructions_path.mkdir()
    (instructions_path / "AGENT.md").write_text(
        "테스트용 런타임 지침",
        encoding="utf-8",
    )
    (instructions_path / "영어_가이드라인.md").write_text(
        "테스트용 학습 가이드라인",
        encoding="utf-8",
    )
    (instructions_path / "초기_실력_테스트.md").write_text(
        "테스트용 초기 실력 테스트 지침",
        encoding="utf-8",
    )

    monkeypatch.setattr(main.settings, "database_url", database_url)
    monkeypatch.setattr(main.settings, "instructions_path", instructions_path)

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
        schema_table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'schema_migrations'
            """
        ).fetchone()
    finally:
        connection.close()

    assert schema_table == ("schema_migrations",)
