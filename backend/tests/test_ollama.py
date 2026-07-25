import json

import httpx
import pytest

from signalwatch.llm import ModelUnavailableError, OllamaProvider, StructuredGenerationError
from signalwatch.models import DevelopmentAnalysis, ExtractedDevelopment, FactualExtraction


@pytest.mark.asyncio
async def test_valid_json_schema_error_is_repaired_once(factual: FactualExtraction) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        content = json.dumps({"event_type": "Release"}) if len(requests) == 1 else factual.model_dump_json()
        return httpx.Response(200, json={"message": {"content": content}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider("http://localhost:11434", "test-model", client=client)
    result = await provider.generate_structured("UNIQUE SOURCE TEXT", FactualExtraction)
    assert result == factual
    assert len(requests) == 2
    assert requests[0]["think"] is False and requests[1]["think"] is False
    assert "UNIQUE SOURCE TEXT" not in requests[1]["messages"][1]["content"]
    assert "FIELD_ERRORS" in requests[1]["messages"][1]["content"]
    assert provider.last_repair_used is True
    await client.aclose()


@pytest.mark.asyncio
async def test_invalid_non_json_output_is_not_repaired() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"message": {"content": "not json"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider("http://localhost:11434", "test-model", client=client, max_attempts=2)
    with pytest.raises(StructuredGenerationError) as raised:
        await provider.generate_structured("prompt", FactualExtraction)
    assert raised.value.reason == "invalid_json"
    assert raised.value.json_valid is False
    assert calls == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_repair_failure_is_typed_and_bounded() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"message": {"content": "{}"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider("http://localhost:11434", "test-model", client=client, max_attempts=2)
    with pytest.raises(StructuredGenerationError) as raised:
        await provider.generate_structured("prompt", FactualExtraction)
    assert raised.value.reason == "repair_failed"
    assert raised.value.json_valid is True
    assert calls == 2
    assert {error["field"] for error in raised.value.errors} >= {
        "event_type", "category", "factual_summary"
    }
    await client.aclose()


@pytest.mark.asyncio
async def test_reasoning_disabled_in_both_extraction_stages(
    factual: FactualExtraction, analysis: DevelopmentAnalysis
) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        content = factual.model_dump_json() if len(requests) == 1 else analysis.model_dump_json()
        return httpx.Response(200, json={"message": {"content": content}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider("http://localhost:11434", "test-model", client=client)
    await provider.generate_structured("facts", FactualExtraction)
    await provider.generate_structured("analysis", DevelopmentAnalysis)
    assert [request["think"] for request in requests] == [False, False]
    assert [request["options"]["num_predict"] for request in requests] == [700, 500]
    assert all(request["options"]["temperature"] == 0.0 for request in requests)
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


def test_ollama_rejects_non_local_base_url() -> None:
    with pytest.raises(ValueError, match="loopback"):
        OllamaProvider("https://inference.example.com", "test-model")


@pytest.mark.asyncio
async def test_ollama_checks_installed_model_names() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})))
    provider = OllamaProvider("http://localhost:11434", "qwen2.5:7b", client=client)
    assert await provider.has_model("qwen2.5:7b")
    assert not await provider.has_model("missing:latest")
    await client.aclose()
