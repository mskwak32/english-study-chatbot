import asyncio
import json

import httpx
import pytest

from app.llm import (
    LLMConnectionError,
    LLMMessage,
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


def test_chat_structured_sends_schema_and_returns_json_object() -> None:
    """메시지와 스키마를 전송하고 구조화 응답을 반환합니다."""
    response_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["reply", "save_review_word"],
            },
            "message": {
                "type": "string",
                "maxLength": 8_000,
            },
            "arguments": {
                "type": "object",
                "properties": {
                    "assessment": {
                        "type": "string",
                        "maxLength": 2_000,
                    }
                },
            },
        },
        "required": ["action", "message", "arguments"],
    }
    expected_content = {
        "action": "save_review_word",
        "message": "",
        "arguments": {
            "term": "hesitate",
            "explanation": "망설이다",
        },
    }
    expected_format = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["reply", "save_review_word"],
            },
            "message": {
                "type": "string",
            },
            "arguments": {
                "type": "object",
                "properties": {
                    "assessment": {
                        "type": "string",
                    }
                },
            },
        },
        "required": ["action", "message", "arguments"],
    }

    def handle_request(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/chat"
        assert json.loads(request.content) == {
            "model": "gemma3:4b",
            "messages": [
                {
                    "role": "system",
                    "content": "영어 튜터로 행동하세요.",
                },
                {
                    "role": "user",
                    "content": "hesitate를 복습 단어로 저장해 주세요.",
                },
            ],
            "stream": False,
            "format": expected_format,
            "keep_alive": "45m",
        }

        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    # Ollama는 모델이 만든 JSON을 문자열 content로 반환합니다.
                    "content": json.dumps(expected_content, ensure_ascii=False),
                },
                "done": True,
            },
        )

    async def run_test():
        transport = httpx.MockTransport(handle_request)

        async with OllamaClient(
            base_url="http://ollama.test",
            model="gemma3:4b",
            keep_alive="45m",
            transport=transport,
        ) as client:
            return await client.chat_structured(
                messages=[
                    LLMMessage(
                        role="system",
                        content="영어 튜터로 행동하세요.",
                    ),
                    LLMMessage(
                        role="user",
                        content="hesitate를 복습 단어로 저장해 주세요.",
                    ),
                ],
                response_schema=response_schema,
            )

    response = asyncio.run(run_test())

    assert response.content == expected_content
    assert response_schema["properties"]["message"]["maxLength"] == 8_000
    assert (
        response_schema["properties"]["arguments"]["properties"]["assessment"][
            "maxLength"
        ]
        == 2_000
    )


def test_chat_structured_rejects_invalid_json_content() -> None:
    """message.content가 JSON이 아니면 안전한 오류를 발생시킵니다."""

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "JSON이 아닌 응답",
                },
                "done": True,
            },
        )

    async def run_test() -> None:
        transport = httpx.MockTransport(handle_request)

        async with OllamaClient(
            base_url="http://ollama.test",
            model="gemma3:4b",
            transport=transport,
        ) as client:
            await client.chat_structured(
                messages=[LLMMessage(role="user", content="안녕하세요.")],
                response_schema={"type": "object"},
            )

    with pytest.raises(
        LLMResponseError,
        match="올바른 구조화 JSON",
    ):
        asyncio.run(run_test())


def test_chat_structured_rejects_json_array() -> None:
    """구조화 응답이 JSON 객체가 아니면 거부합니다."""

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": '["reply", "hello"]',
                },
                "done": True,
            },
        )

    async def run_test() -> None:
        transport = httpx.MockTransport(handle_request)

        async with OllamaClient(
            base_url="http://ollama.test",
            model="gemma3:4b",
            transport=transport,
        ) as client:
            await client.chat_structured(
                messages=[LLMMessage(role="user", content="안녕하세요.")],
                response_schema={"type": "object"},
            )

    with pytest.raises(
        LLMResponseError,
        match="JSON 객체여야 합니다",
    ):
        asyncio.run(run_test())


def test_chat_structured_rejects_missing_message() -> None:
    """Ollama 응답에 message 객체가 없으면 거부합니다."""

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"done": True},
        )

    async def run_test() -> None:
        transport = httpx.MockTransport(handle_request)

        async with OllamaClient(
            base_url="http://ollama.test",
            model="gemma3:4b",
            transport=transport,
        ) as client:
            await client.chat_structured(
                messages=[LLMMessage(role="user", content="안녕하세요.")],
                response_schema={"type": "object"},
            )

    with pytest.raises(
        LLMResponseError,
        match="유효한 message 객체",
    ):
        asyncio.run(run_test())


def test_chat_structured_rejects_empty_messages() -> None:
    """LLM에 전달할 메시지가 없으면 요청 전에 거부합니다."""

    async def run_test() -> None:
        async with OllamaClient(
            base_url="http://ollama.test",
            model="gemma3:4b",
        ) as client:
            await client.chat_structured(
                messages=[],
                response_schema={"type": "object"},
            )

    with pytest.raises(
        ValueError,
        match="메시지는 하나 이상이어야 합니다",
    ):
        asyncio.run(run_test())
