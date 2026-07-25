from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from signalwatch.diagnostics import SMOKE_CONNECTORS, SMOKE_MAX_ITEMS, smoke_test_collectors


class SmokeRepository:
    def __init__(self) -> None:
        self.requested: list[str] = []

    async def smoke_source(self, connector: str):
        self.requested.append(connector)
        return SimpleNamespace(connector_key=connector)


@pytest.mark.asyncio
async def test_smoke_uses_one_source_per_supported_connector(monkeypatch) -> None:
    seen: list[list[str]] = []

    async def fake_run_sources(self, sources):
        seen.append([source.connector_key for source in sources])
        return {
            "sources_checked": 1,
            "items_detected": SMOKE_MAX_ITEMS,
            "items_new": 1,
            "jobs_created": 1,
            "errors": 0,
        }

    monkeypatch.setattr("signalwatch.diagnostics.CollectionService.run_sources", fake_run_sources)
    repository = SmokeRepository()
    settings = SimpleNamespace(
        github_token=SecretStr("token"), huggingface_token=SecretStr("token")
    )

    result = await smoke_test_collectors(repository, settings)

    assert tuple(repository.requested) == SMOKE_CONNECTORS
    assert seen == [[connector] for connector in SMOKE_CONNECTORS]
    assert result["max_items_per_connector"] == 3
    assert result["totals"]["sources_checked"] == 4
    assert result["totals"]["jobs_created"] == 4
