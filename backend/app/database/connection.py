"""SQLite 연결과 데이터베이스 경로 검증을 처리합니다."""

import sqlite3
from pathlib import Path

SQLITE_URL_PREFIX = "sqlite:///"


class DatabaseError(ValueError):
    """데이터베이스 설정이 올바르지 않을 때 발생합니다."""


def database_path_from_url(database_url: str) -> Path:
    """SQLite URL에서 DB 파일의 절대 경로를 반환합니다."""
    if not database_url.startswith(SQLITE_URL_PREFIX):
        raise DatabaseError("SQLite URL이어야 합니다.")

    database_path = Path(database_url.removeprefix(SQLITE_URL_PREFIX))

    if not database_path.is_absolute():
        raise DatabaseError("데이터베이스 파일은 절대 경로여야 합니다.")

    return database_path


def connect_database(database_url: str) -> sqlite3.Connection:
    """DB 상위 디렉터리를 필요하면 만든 뒤 SQLite에 연결하고 외래 키를 활성화합니다."""
    database_path = database_path_from_url(database_url)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")

    return connection
