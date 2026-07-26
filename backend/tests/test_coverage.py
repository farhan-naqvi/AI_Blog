from datetime import UTC, datetime

from signalwatch.collectors.base import CollectionResult
from signalwatch.collection import CollectionService
from signalwatch.coverage import (
    AGENTS, BUSINESS, INFRASTRUCTURE, MODELS, POLICY, RESEARCH,
    category_rejection_reason, deterministic_cluster_key, development_category,
    select_balanced, source_category,
)
from signalwatch.models import CollectedItem, ReleaseMetadata, SourceRecord
from signalwatch.normalization import content_fingerprint, stable_hash
from signalwatch.repository import SupabaseRepository


def source(category: str, key: str = "github") -> SourceRecord:
    return SourceRecord(
        id="00000000-0000-0000-0000-000000000001", name="Acme source",
        base_url="https://example.com", source_type="Open source", retrieval_method="API",
        connector_key=key, connector_config={"public_category": category},
        is_primary_source=True, reliability_level="High", poll_interval_minutes=120,
        rate_limit_per_hour=30,
    )


def item(title: str, excerpt: str, hint: str = "release") -> CollectedItem:
    fingerprint = stable_hash(title)
    return CollectedItem(
        source_id="00000000-0000-0000-0000-000000000001", source_identifier=title,
        url=f"https://example.com/{fingerprint[:10]}",
        canonical_url=f"https://example.com/{fingerprint[:10]}", title=title,
        published_at=datetime(2026, 7, 20, tzinfo=UTC), excerpt=excerpt,
        event_type_hint=hint, content_hash=content_fingerprint(title, excerpt),
        title_hash=stable_hash(title.casefold()),
    )


def test_source_category_uses_explicit_public_mapping() -> None:
    for category, key in ((MODELS, "github"), (AGENTS, "github"), (RESEARCH, "arxiv"),
                          (INFRASTRUCTURE, "github"), (BUSINESS, "rss"), (POLICY, "rss")):
        assert source_category(source(category, key)) == category
    assert development_category({"public_category": POLICY, "category": "Research"}) == POLICY


def test_category_filters_are_specific_and_grounded() -> None:
    assert category_rejection_reason(item("Acme model 2.0", "Named model release with weights."), MODELS) is None
    assert category_rejection_reason(item("Acme social post", "A generic company update."), MODELS) == "weak_models_signal"
    assert category_rejection_reason(item("A new agent planning method", "short", "research"), RESEARCH) == "insufficient_research_abstract"
    assert category_rejection_reason(item("Runtime 1.2.3", "Dependency housekeeping release."), AGENTS) == "routine_maintenance"


def test_versioned_cross_source_items_share_a_cluster_without_version_only_matching() -> None:
    release = item("acme/runtime: Runtime 2.0", "Runtime release notes.")
    release.release_metadata = ReleaseMetadata(
        repository="acme/runtime", organisation="acme", release_tag="v2.0",
        release_title="Runtime 2.0", published_date=release.published_at.date(),
        official_repository_release=True,
    )
    announcement = item("Runtime 2.0 launches", "Official launch announcement.", "article")
    unrelated = item("Runtime 3.0 launches", "A later official launch.", "article")
    assert deterministic_cluster_key(release, source(AGENTS)) == deterministic_cluster_key(announcement, source(AGENTS, "rss"))
    assert deterministic_cluster_key(release, source(AGENTS)) != deterministic_cluster_key(unrelated, source(AGENTS, "rss"))


def test_balanced_selection_respects_category_quotas() -> None:
    rows = ([{"public_category": MODELS, "n": value} for value in range(5)]
            + [{"public_category": POLICY, "n": value} for value in range(4)])
    selected = select_balanced(rows, 20, {MODELS: 4, POLICY: 2})
    assert [row["public_category"] for row in selected].count(MODELS) == 4
    assert [row["public_category"] for row in selected].count(POLICY) == 2


async def test_collection_enforces_per_category_candidate_limit() -> None:
    candidates = [
        item("Agent runtime 2.0", "A meaningful agent framework release."),
        item("Agent runtime 2.1", "Another meaningful agent framework release."),
    ]

    class Collector:
        key = "github"
        async def collect(self, configured_source, client):
            return CollectionResult(items=candidates, discovered_count=2)

    class Repository:
        def __init__(self): self.rejections = []
        async def ingest_item(self, candidate, rejection):
            self.rejections.append(rejection)
            return {"inserted": True, "queued": rejection is None}
        async def record_source_result(self, *args, **kwargs): return None

    repository = Repository()
    service = CollectionService(repository, {"github": Collector()}, concurrency=1,
                                candidate_limits={AGENTS: 1})
    result = await service.run_sources([source(AGENTS)])
    assert repository.rejections == [None, "category_candidate_limit"]
    assert result["jobs_created"] == 1
    assert result["items_filtered"] == 1


async def test_cluster_source_metadata_never_overwrites_source_item_identity() -> None:
    class Client:
        async def aclose(self): return None

    repository = object.__new__(SupabaseRepository)
    repository.client = Client()
    calls = 0

    async def request(method, path, *, params=None, json=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return [{"id": "item-id", "source_id": "source-id", "cluster_key": "a" * 64}]
        if calls == 2:
            return [{"id": "item-id", "source_id": "source-id", "cluster_key": "a" * 64}]
        return [{"id": "source-id", "name": "Acme", "base_url": "https://example.com",
                 "is_primary_source": True, "source_type": "Open source",
                 "retrieval_method": "API", "connector_key": "github",
                 "connector_config": {"public_category": AGENTS}}]

    repository._request = request
    rows = await repository.source_items_for_job({"source_item_id": "item-id"})
    assert rows[0]["id"] == "item-id"
    assert rows[0]["name"] == "Acme"
