"""설정 화면에 필요한 실행 상태를 안전하게 수집합니다."""

import asyncio
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.database import database_path_from_url

_OLLAMA_STATUS_TIMEOUT_SECONDS = 2.0
_BYTES_PER_GIB = 1024**3
_DATABASE_SIDECAR_SUFFIXES = ("", "-wal", "-shm", "-journal")


@dataclass(frozen=True)
class ModelStatus:
    """설정된 Ollama 모델의 표시용 상태입니다."""

    name: str
    ollama_name: str
    size: str | None
    loaded: bool | None


@dataclass(frozen=True)
class OllamaStatus:
    """Ollama API에서 확인 가능한 연결 상태입니다."""

    api_connected: bool
    version: str | None


@dataclass(frozen=True)
class SystemStatus:
    """Linux에서 수집한 CPU, 메모리, 디스크 상태입니다."""

    cpu_usage: int | None
    memory_used: str | None
    memory_total: str | None
    disk_used: str | None
    disk_total: str | None


@dataclass(frozen=True)
class LearningDataStatus:
    """SQLite에 저장된 채팅 수와 데이터베이스 사용량입니다."""

    chat_count: int | None
    size: str | None


@dataclass(frozen=True)
class SettingsStatus:
    """설정 화면이 표시하는 모든 상태입니다."""

    model: ModelStatus
    ollama: OllamaStatus
    system: SystemStatus
    learning_data: LearningDataStatus


async def collect_settings_status(
    *, model: str, ollama_base_url: str, database_url: str
) -> SettingsStatus:
    """각 상태 원본을 독립적으로 수집해 일부 실패도 응답에 포함합니다."""
    ollama_result, system_result, learning_data_result = await asyncio.gather(
        _read_ollama_status(model, ollama_base_url),
        asyncio.to_thread(_read_system_status, database_url),
        asyncio.to_thread(_read_learning_data_status, database_url),
    )

    model_status, ollama_status = ollama_result
    return SettingsStatus(
        model=model_status,
        ollama=ollama_status,
        system=system_result,
        learning_data=learning_data_result,
    )


async def _read_ollama_status(
    model: str, ollama_base_url: str
) -> tuple[ModelStatus, OllamaStatus]:
    """Ollama API의 독립 요청으로 모델, 로드, 버전을 확인합니다."""
    unavailable_model = ModelStatus(
        name=_display_model_name(model),
        ollama_name=model,
        size=None,
        loaded=None,
    )
    unavailable_ollama = OllamaStatus(
        api_connected=False,
        version=None,
    )

    try:
        async with httpx.AsyncClient(
            base_url=ollama_base_url,
            timeout=_OLLAMA_STATUS_TIMEOUT_SECONDS,
        ) as client:
            version_result, ps_result, tags_result = await asyncio.gather(
                _request_json(client, "GET", "/api/version"),
                _request_json(client, "GET", "/api/ps"),
                _request_json(client, "GET", "/api/tags"),
            )
    except httpx.HTTPError:
        return unavailable_model, unavailable_ollama

    version_data = version_result if isinstance(version_result, dict) else None
    ps_data = ps_result if isinstance(ps_result, dict) else None
    tags_data = tags_result if isinstance(tags_result, dict) else None
    api_connected = version_data is not None
    version = _non_empty_string(version_data.get("version")) if version_data else None

    loaded_model = _find_model(ps_data, model)
    tagged_model = _find_model(tags_data, model)
    loaded = None if ps_data is None else loaded_model is not None
    size_bytes = _model_size_bytes(tagged_model) or _model_size_bytes(loaded_model)

    return (
        ModelStatus(
            name=_display_model_name(model),
            ollama_name=model,
            size=_format_bytes(size_bytes) if size_bytes is not None else None,
            loaded=loaded,
        ),
        OllamaStatus(
            api_connected=api_connected,
            version=version,
        ),
    )


async def _request_json(
    client: httpx.AsyncClient, method: str, path: str
) -> dict[str, Any] | None:
    """HTTP 또는 JSON 형식 오류를 상태 미확인으로 바꿉니다."""
    try:
        response = await client.request(method, path)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    return data if isinstance(data, dict) else None


def _find_model(data: dict[str, Any] | None, model: str) -> dict[str, Any] | None:
    """Ollama 모델 목록에서 현재 설정과 정확히 일치하는 모델을 찾습니다."""
    if data is None:
        return None

    models = data.get("models")
    if not isinstance(models, list):
        return None

    for candidate in models:
        if isinstance(candidate, dict) and candidate.get("name") == model:
            return candidate

    return None


def _model_size_bytes(model: dict[str, Any] | None) -> int | None:
    """Ollama 모델 객체의 byte 단위 크기를 검증해 반환합니다."""
    if model is None:
        return None

    size = model.get("size")
    return size if isinstance(size, int) and size >= 0 else None


def _read_system_status(database_url: str) -> SystemStatus:
    """Linux 가상 파일 시스템과 데이터 볼륨에서 시스템 상태를 읽습니다."""
    memory_used, memory_total = _read_memory()
    disk_used, disk_total = _read_disk(database_url)
    return SystemStatus(
        cpu_usage=_read_cpu_usage(),
        memory_used=memory_used,
        memory_total=memory_total,
        disk_used=disk_used,
        disk_total=disk_total,
    )


def _read_cpu_usage() -> int | None:
    """짧은 두 표본의 /proc/stat 차이로 Linux CPU 사용률을 계산합니다."""
    first = _read_cpu_times()
    if first is None:
        return None

    time.sleep(0.1)
    second = _read_cpu_times()
    if second is None:
        return None

    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]
    if total_delta <= 0:
        return None

    return round((total_delta - idle_delta) / total_delta * 100)


def _read_cpu_times() -> tuple[int, int] | None:
    """/proc/stat의 누적 전체 시간과 idle 시간을 반환합니다."""
    try:
        fields = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0].split()
        values = [int(value) for value in fields[1:]]
    except (OSError, IndexError, ValueError):
        return None

    if len(values) < 5:
        return None

    return sum(values), values[3] + (values[4] if len(values) > 4 else 0)


def _read_memory() -> tuple[str | None, str | None]:
    """/proc/meminfo의 전체·사용 중 메모리를 사람이 읽을 단위로 변환합니다."""
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, value, *_ = line.replace(":", "").split()
            values[key] = int(value) * 1024
    except (OSError, ValueError):
        return None, None

    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if total is None or available is None:
        return None, None

    return _format_bytes(total - available), _format_bytes(total)


def _read_disk(database_url: str) -> tuple[str | None, str | None]:
    """데이터베이스가 놓인 데이터 볼륨의 디스크 사용량을 반환합니다."""
    try:
        database_path = database_path_from_url(database_url)
        usage = os.statvfs(database_path.parent)
    except (OSError, ValueError):
        return None, None

    total = usage.f_blocks * usage.f_frsize
    available = usage.f_bavail * usage.f_frsize
    return _format_bytes(total - available), _format_bytes(total)


def _read_learning_data_status(database_url: str) -> LearningDataStatus:
    """채팅 테이블의 건수와 SQLite 본문·부속 파일의 합계 크기를 읽습니다."""
    try:
        database_path = database_path_from_url(database_url)
    except ValueError:
        return LearningDataStatus(chat_count=None, size=None)

    chat_count = _read_chat_count(database_path)
    size = _database_size(database_path)
    return LearningDataStatus(
        chat_count=chat_count,
        size=_format_bytes(size) if size is not None else None,
    )


def _read_chat_count(database_path: Path) -> int | None:
    """읽기 전용 SQLite 연결로 저장된 채팅 수를 조회합니다."""
    if not database_path.is_file():
        return None

    try:
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
        try:
            row = connection.execute("SELECT COUNT(*) FROM chats").fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return None

    return row[0] if row is not None and isinstance(row[0], int) else None


def _database_size(database_path: Path) -> int | None:
    """SQLite 본문과 WAL·SHM·journal 파일의 현재 합계 크기를 반환합니다."""
    try:
        return sum(
            candidate.stat().st_size
            for suffix in _DATABASE_SIDECAR_SUFFIXES
            if (candidate := Path(f"{database_path}{suffix}")).is_file()
        )
    except OSError:
        return None


def _display_model_name(model: str) -> str:
    """Ollama 모델 식별자를 설정 화면의 읽기 쉬운 이름으로 바꿉니다."""
    separated_model = re.sub(
        r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", model
    )
    return separated_model.replace(":", " ").replace("-", " ").title()


def _non_empty_string(value: object) -> str | None:
    """비어 있지 않은 문자열만 상태값으로 반환합니다."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def _format_bytes(value: int) -> str:
    """byte 단위 크기를 설정 화면에서 사용하는 GiB 또는 MiB 문자열로 변환합니다."""
    if value >= _BYTES_PER_GIB:
        return f"{value / _BYTES_PER_GIB:.1f} GB"
    return f"{value / (1024**2):.1f} MB"
