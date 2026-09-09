import asyncio
import json

import httpx
import pytest
from app.llm import (
    LLMConnectionError,
    LLMResponseError,
    ModelUnavailableError,
    OllamaClient,
)


def test_check_ready_returns_server_and_model_information() -> None:
    """서버 버전과 설정된 모델의 기능을 반환합니다."""

    def handle_request(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            assert request.method == "GET"
            return httpx.Response(
                200,
                json={"version": "0.12.6"},
            )

        if request.url.path == "/api/show":
            assert request.method == "POST"
            assert json.loads(request.content) == {"model": "gemma3:4b"}

            return httpx.Response(
                200,
                json={"capabilities": ["completion", "tools"]},
            )

        return httpx.Response(404)

    async def run_test():
        transport = httpx.MockTransport(handle_request)

        async with OllamaClient(
            base_url="http://ollama.test",
            model="gemma3:4b",
            transport=transport,
        ) as client:
            return await client.check_ready()

    status = asyncio.run(run_test())

    assert status.server_version == "0.12.6"
    assert status.model == "gemma3:4b"
    assert status.capabilities == ("completion", "tools")


def test_check_ready_reports_missing_model() -> None:
    """Ollama에 설정된 모델이 없으면 명확한 오류를 발생시킵니다."""

    def handle_request(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(
                200,
                json={"version": "0.12.6"},
            )

        return httpx.Response(
            404,
            json={"error": "model not found"},
        )

    async def run_test() -> None:
        transport = httpx.MockTransport(handle_request)

        async with OllamaClient(
            base_url="http://ollama.test",
            model="missing-model",
            transport=transport,
        ) as client:
            await client.check_ready()

    with pytest.raises(
        ModelUnavailableError,
        match="설정된 모델이 없습니다",
    ):
        asyncio.run(run_test())


def test_check_ready_converts_connection_error() -> None:
    """저수준 HTTP 연결 오류를 애플리케이션 오류로 변환합니다."""

    def handle_request(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection refused",
            request=request,
        )

    async def run_test() -> None:
        transport = httpx.MockTransport(handle_request)

        async with OllamaClient(
            base_url="http://ollama.test",
            model="gemma3:4b",
            transport=transport,
        ) as client:
            await client.check_ready()

    with pytest.raises(
        LLMConnectionError,
        match="Ollama 서버에 연결할 수 없습니다",
    ):
        asyncio.run(run_test())


def test_check_ready_rejects_invalid_model_response() -> None:
    """모델 정보 응답 형식이 잘못되면 안전한 오류를 발생시킵니다."""

    def handle_request(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(
                200,
                json={"version": "0.12.6"},
            )

        return httpx.Response(
            200,
            json={"capabilities": "completion"},
        )

    async def run_test() -> None:
        transport = httpx.MockTransport(handle_request)

        async with OllamaClient(
            base_url="http://ollama.test",
            model="gemma3:4b",
            transport=transport,
        ) as client:
            await client.check_ready()

    with pytest.raises(
        LLMResponseError,
        match="capabilities 형식이 올바르지 않습니다",
    ):
        asyncio.run(run_test())
