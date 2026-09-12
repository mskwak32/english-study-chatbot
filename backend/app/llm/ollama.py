"""Ollama HTTP API를 사용하는 LLM 클라이언트를 제공합니다."""

import json
from collections.abc import Sequence
from types import TracebackType
from typing import Self

import httpx

from .client import (
    LLMConnectionError,
    LLMMessage,
    LLMResponseError,
    LLMStatus,
    LLMStructuredResponse,
    ModelUnavailableError,
)


class OllamaClient:
    """Ollama HTTP API를 비동기로 호출합니다."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        keep_alive: str = "30m",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._keep_alive = keep_alive

        # AsyncClient를 재사용하면 요청마다 연결을 새로 만드는 비용을 줄일 수 있음
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        """async with 블록이 시작될 때 현재 클라이언트를 반환합니다."""
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """async with 블록이 끝날 때 네트워크 자원을 정리합니다."""
        await self.aclose()

    async def aclose(self) -> None:
        """HTTP 연결 풀과 관련 네트워크 자원을 정리합니다."""
        await self._client.aclose()

    async def check_ready(self) -> LLMStatus:
        """Ollama 서버 연결과 설정된 모델의 가용성을 확인합니다."""
        version_response = await self._request("GET", "/api/version")
        self._raise_for_status(version_response, "Ollama 서버 상태 확인")

        model_response = await self._request(
            "POST",
            "/api/show",
            json_body={"model": self._model},
        )

        if model_response.status_code == 404:
            raise ModelUnavailableError(
                f"Ollama에 설정된 모델이 없습니다: {self._model}"
            )

        self._raise_for_status(model_response, "Ollama 모델 확인")

        version_data = self._read_json(version_response, "Ollama 버전 응답")
        model_data = self._read_json(model_response, "Ollama 모델 정보 응답")

        server_version = version_data.get("version")

        if not isinstance(server_version, str) or not server_version.strip():
            raise LLMResponseError("Ollama 버전 응답에 유효한 version이 없습니다.")

        capabilities = model_data.get("capabilities", [])

        if not isinstance(capabilities, list) or not all(
            isinstance(capability, str) for capability in capabilities
        ):
            raise LLMResponseError(
                "Ollama 모델 정보의 capabilities 형식이 올바르지 않습니다."
            )

        return LLMStatus(
            server_version=server_version,
            model=self._model,
            capabilities=tuple(capabilities),
        )

    async def chat_structured(
        self, messages: Sequence[LLMMessage], response_schema: dict[str, object]
    ) -> LLMStructuredResponse:
        """JSON Schema에 맞는 Ollama 대화 응답을 생성합니다."""
        if not messages:
            raise ValueError("LLM에 전달할 메시지는 하나 이상이어야 합니다.")

        request_body: dict[str, object] = {
            "model": self._model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ],
            # 스트리밍은 Web UI 단계 이후에 검토하므로 현재는 완성된 응답을 받음
            "stream": False,
            "format": response_schema,
            # 유휴 시간이 짧은 학습 세션에서 모델 재로딩을 줄입니다.
            "keep_alive": self._keep_alive,
        }

        response = await self._request("POST", "/api/chat", json_body=request_body)
        self._raise_for_status(response, "Ollama 대화 생성")

        response_data = self._read_json(response, "Ollama 대화 응답")
        message_data = response_data.get("message")

        if not isinstance(message_data, dict):
            raise LLMResponseError("Ollama 대화 응답에 유효한 message 객체가 없습니다.")

        content = message_data.get("content")

        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError("Ollama 대화 응답에 유효한 content가 없습니다.")

        try:
            structured_content = json.loads(content)
        except json.JSONDecodeError as error:
            raise LLMResponseError(
                "Ollama가 올바른 구조화 JSON을 반환하지 않았습니다."
            ) from error

        if not isinstance(structured_content, dict):
            raise LLMResponseError("Ollama의 구조화 응답은 JSON 객체여야 합니다.")

        return LLMStructuredResponse(content=structured_content)

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, object] | None = None,
    ) -> httpx.Response:
        """네트워크 요청을 합니다."""
        try:
            return await self._client.request(method, path, json=json_body)
        except httpx.RequestError as error:
            raise LLMConnectionError("Ollama 서버에 연결할 수 없습니다.") from error

    @staticmethod
    def _raise_for_status(
        response: httpx.Response,
        operation: str,
    ) -> None:
        """Ollama의 HTTP 오류 응답을 안전한 애플리케이션 오류로 바꿉니다."""
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise LLMResponseError(
                f"{operation}에 실패했습니다. HTTP 상태 코드: {response.status_code}"
            ) from error

    @staticmethod
    def _read_json(
        response: httpx.Response,
        response_name: str,
    ) -> dict[str, object]:
        """JSON 응답이 객체 형태인지 검사한 뒤 반환합니다."""
        try:
            data = response.json()
        except ValueError as error:
            raise LLMResponseError(
                f"{response_name}이 올바른 JSON이 아닙니다."
            ) from error

        if not isinstance(data, dict):
            raise LLMResponseError(f"{response_name}은 JSON 객체여야 합니다.")

        return data
