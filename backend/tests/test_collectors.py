import httpx
import pytest
from datetime import UTC, datetime, timedelta

from signalwatch.collectors.github import GitHubCollector
from signalwatch.collectors.huggingface import HuggingFaceCollector
from signalwatch.collection import CollectionService
from signalwatch.collectors.base import CollectionResult
from signalwatch.models import CollectedItem, SourceRecord
from signalwatch.normalization import content_fingerprint, stable_hash


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
    now = datetime.now(UTC).isoformat()
    payload = [{"modelId": "acme/model-v2", "author": "acme", "createdAt": now, "lastModified": now, "pipeline_tag": "text-generation", "tags": ["transformers", "text-generation"], "siblings": [{"rfilename": "README.md"}]}]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
        result = await HuggingFaceCollector().collect(source("huggingface", {"author": "acme"}), client)
    assert result.items[0].source_identifier == "acme/model-v2"
    assert "text-generation" in result.items[0].excerpt


def hf_model(name: str = "model-v2", *, created_days_ago: int = 0, **overrides):
    created = (datetime.now(UTC) - timedelta(days=created_days_ago)).isoformat()
    payload = {
        "modelId": f"acme/{name}",
        "author": "acme",
        "createdAt": created,
        "lastModified": datetime.now(UTC).isoformat(),
        "pipeline_tag": "text-generation",
        "tags": ["transformers", "text-generation"],
        "siblings": [{"rfilename": "README.md"}],
        "downloads": 0,
        "likes": 0,
    }
    payload.update(overrides)
    return payload


async def collect_hf(payload, config=None):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=[payload]))
    async with httpx.AsyncClient(transport=transport) as client:
        return await HuggingFaceCollector(max_items=1).collect(
            source("huggingface", {"author": "acme"} | (config or {})), client
        )


@pytest.mark.asyncio
async def test_huggingface_meaningful_new_release_is_candidate_without_popularity_floor() -> None:
    result = await collect_hf(hf_model())
    assert len(result.items) == 1
    assert result.items[0].event_type_hint == "release"
    assert result.filtered_reasons == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (hf_model(created_days_ago=45), "routine_model_update"),
        (hf_model(created_days_ago=120), "stale_update"),
        (hf_model(siblings=[]), "insufficient_metadata"),
        (hf_model(name="model-v2-AWQ"), "likely_duplicate_variant"),
        (hf_model(pipeline_tag=None, tags=["transformers"]), "weak_development_signal"),
    ],
)
async def test_huggingface_weak_signals_are_filtered(payload, reason) -> None:
    result = await collect_hf(payload)
    assert result.items == []
    assert result.filtered_reasons == {reason: 1}


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


@pytest.mark.asyncio
async def test_collection_is_idempotent_for_the_same_normalized_item() -> None:
    title = "Acme Runtime publishes version two"
    excerpt = "A sufficiently detailed release description for deterministic collection testing."
    item = CollectedItem(
        source_id="1",
        source_identifier="release-2",
        url="https://example.com/releases/v2",
        canonical_url="https://example.com/releases/v2",
        title=title,
        published_at=datetime.now(UTC),
        excerpt=excerpt,
        event_type_hint="release",
        content_hash=content_fingerprint(title, excerpt),
        title_hash=stable_hash(title.casefold()),
    )

    class StaticCollector:
        key = "github"

        async def collect(self, configured_source, client):
            return CollectionResult(items=[item], discovered_count=1)

    class Repository:
        def __init__(self):
            self.seen = set()

        async def ingest_item(self, candidate, rejection):
            if candidate.source_identifier in self.seen:
                return {"inserted": False, "reason": "duplicate"}
            self.seen.add(candidate.source_identifier)
            return {"inserted": True, "queued": True}

        async def record_source_result(self, *args, **kwargs):
            return None

    repository = Repository()
    service = CollectionService(repository, {"github": StaticCollector()}, concurrency=1)
    configured_source = source("github", {"repository": "acme/runtime"})
    first = await service.run_sources([configured_source])
    second = await service.run_sources([configured_source])
    assert first["items_new"] == first["jobs_created"] == 1
    assert second["items_new"] == second["jobs_created"] == 0
    assert second["duplicates"] == 1
