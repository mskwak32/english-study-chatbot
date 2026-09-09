"""LLM 클라이언트가 따라야 할 공통 인터페이스를 정의합니다."""

from dataclasses import dataclass
from typing import Protocol, Literal


@dataclass(frozen=True)
class LLMMessage:
    """LLM에 전달하는 역할과 메시지 내용을 표현합니다."""

    role: Literal["system","user","assistant"]
    content: str

@dataclass(frozen=True)
class LLMStatus:
    """LLM 서버와 설정된 모델의 준비 상태를 표현합니다."""

    server_version: str
    model: str
    capabilities: tuple[str, ...]


class LLMError(RuntimeError):
    """LLM을 정상적으로 사용할 수 없을 때 발생하는 기본 오류입니다."""


class LLMConnectionError(LLMError):
    """LLM 서버에 연결할 수 없을 때 발생합니다."""


class LLMResponseError(LLMError):
    """LLM 서버가 예상하지 못한 응답을 반환했을 때 발생합니다."""


class ModelUnavailableError(LLMError):
    """설정된 모델을 LLM 서버에서 찾을 수 없을 때 발생합니다."""


class LLMClient(Protocol):
    """Python Agent가 사용할 LLM 클라이언트의 공통 인터페이스입니다."""

    async def check_ready(self) -> LLMStatus:
        """LLM 서버와 모델이 사용할 준비가 되었는지 확인합니다."""
        ...

    async def aclose(self) -> None:
        """클라이언트가 사용하는 네트워크 자원을 정리합니다."""
        ...
