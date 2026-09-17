"""시스템 설정 상태 HTTP API를 제공합니다."""

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.services.system_status import collect_settings_status

router = APIRouter(prefix="/settings", tags=["settings"])


class ModelStatusResponse(BaseModel):
    """현재 AI 모델의 상태입니다."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    ollama_name: str = Field(serialization_alias="ollamaName")
    size: str | None
    loaded: bool | None


class OllamaStatusResponse(BaseModel):
    """Ollama API에서 확인 가능한 상태입니다."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    api_connected: bool = Field(serialization_alias="apiConnected")
    version: str | None


class SystemStatusResponse(BaseModel):
    """Raspberry Pi 또는 Linux 시스템의 자원 상태입니다."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    cpu_usage: int | None = Field(serialization_alias="cpuUsage")
    memory_used: str | None = Field(serialization_alias="memoryUsed")
    memory_total: str | None = Field(serialization_alias="memoryTotal")
    disk_used: str | None = Field(serialization_alias="diskUsed")
    disk_total: str | None = Field(serialization_alias="diskTotal")


class LearningDataStatusResponse(BaseModel):
    """저장된 채팅과 SQLite 학습 데이터의 상태입니다."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    chat_count: int | None = Field(serialization_alias="chatCount")
    size: str | None


class SettingsStatusResponse(BaseModel):
    """설정 페이지가 사용하는 전체 상태 응답입니다."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    model: ModelStatusResponse
    ollama: OllamaStatusResponse
    system: SystemStatusResponse
    learning_data: LearningDataStatusResponse = Field(serialization_alias="learningData")


@router.get(
    "/status",
    response_model=SettingsStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def read_settings_status() -> SettingsStatusResponse:
    """설정 변경 없이 현재 모델, 시스템, 학습 데이터 상태를 반환합니다."""
    current_status = await collect_settings_status(
        model=settings.model,
        ollama_base_url=settings.ollama_base_url,
        database_url=settings.database_url,
    )
    return SettingsStatusResponse.model_validate(current_status)
