import httpx
import pytest

from signalwatch.collectors.github import GitHubCollector
from signalwatch.collectors.huggingface import HuggingFaceCollector
from signalwatch.collection import CollectionService
from signalwatch.models import SourceRecord


def source(key: str, config: dict) -> SourceRecord:
    return SourceRecord(id="1", name="Test", base_url="https://example.com", source_type="Open source", retrieval_method="API", connector_key=key, connector_config=config, is_primary_source=True, reliability_level="High", poll_interval_minutes=120, rate_limit_per_hour=30)


@pytest.mark.asyncio
async def test_github_release_normalization() -> None:
    payload = [{"id": 42, "name": "v2.0", "tag_name": "v2.0", "html_url": "https://github.com/acme/runtime/releases/tag/v2.0", "body": "Major runtime update", "published_at": "2026-01-20T10:00:00Z", "draft": False}]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
        result = await GitHubCollector().collect(source("github", {"repository": "acme/runtime"}), client)
    assert result.items[0].source_identifier == "42"
    assert result.items[0].event_type_hint == "release"


@pytest.mark.asyncio
async def test_huggingface_model_normalization() -> None:
    payload = [{"modelId": "acme/model-v2", "lastModified": "2026-01-20T10:00:00Z", "tags": ["transformers", "text-generation"]}]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
        result = await HuggingFaceCollector().collect(source("huggingface", {"author": "acme"}), client)
    assert result.items[0].source_identifier == "acme/model-v2"
    assert "text-generation" in result.items[0].excerpt


@pytest.mark.asyncio
async def test_smoke_limits_are_sent_to_apis() -> None:
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen[request.url.host] = dict(request.url.params)
        return httpx.Response(200, json=[])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await GitHubCollector(max_items=3).collect(source("github", {"repository": "acme/runtime"}), client)
        await HuggingFaceCollector(max_items=3).collect(source("huggingface", {"author": "acme"}), client)
    assert seen["api.github.com"]["per_page"] == "3"
    assert seen["huggingface.co"]["limit"] == "3"


@pytest.mark.asyncio
async def test_collection_passes_source_limit_to_repository() -> None:
    class Repository:
        called_with = None

        async def due_sources(self, connector_key, limit):
            self.called_with = (connector_key, limit)
            return []

    repository = Repository()
    result = await CollectionService(repository, {}).run("rss", source_limit=2)
    assert repository.called_with == ("rss", 2)
    assert result["sources_checked"] == 0
