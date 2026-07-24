import json

import httpx
import pytest

from signalwatch.llm import ModelUnavailableError, OllamaProvider, StructuredGenerationError
from signalwatch.models import ExtractedDevelopment


@pytest.mark.asyncio
async def test_ollama_retries_invalid_structured_output(extracted_payload: dict) -> None:
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = "not json" if calls == 1 else json.dumps(extracted_payload)
        return httpx.Response(200, json={"message": {"content": content}})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider("http://localhost:11434", "test-model", client=client)
    result = await provider.generate_structured("prompt", ExtractedDevelopment)
    assert result.headline == extracted_payload["headline"]
    assert calls == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_ollama_stops_after_fixed_invalid_attempts() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"message": {"content": "{}"}})))
    provider = OllamaProvider("http://localhost:11434", "test-model", client=client, max_attempts=2)
    with pytest.raises(StructuredGenerationError):
        await provider.generate_structured("prompt", ExtractedDevelopment)
    await client.aclose()


@pytest.mark.asyncio
async def test_ollama_unavailable_is_explicit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider("http://localhost:11434", "test-model", client=client)
    with pytest.raises(ModelUnavailableError):
        await provider.generate_structured("prompt", ExtractedDevelopment)
    await client.aclose()
