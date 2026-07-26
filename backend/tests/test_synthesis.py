from datetime import UTC

import pytest

from signalwatch.models import ReportOutput
from signalwatch.synthesis import generate_report


def rows(*importance: str) -> list[dict]:
    return [
        {
            "id": str(index),
            "headline": f"Verified development {index}",
            "summary": "A verified source recorded a factual AI development with sufficient public evidence.",
            "category": "Developer tools",
            "importance_label": label,
            "published_at": "2026-07-26T00:00:00Z",
        }
        for index, label in enumerate(importance)
    ]


class Repository:
    def __init__(self, developments):
        self.rows = developments
        self.created = None

    async def published_developments(self, since, limit=20):
        assert since.tzinfo is UTC
        assert limit == 20
        return self.rows

    async def create_report(self, *args):
        self.created = args
        return {"created": True}


class Provider:
    model_identifier = "local-test-model"

    def __init__(self, development_ids: list[str] | None = None):
        self.development_ids = development_ids
        self.called = False

    async def generate_structured(self, prompt, schema):
        self.called = True
        assert "daily intelligence briefing" in prompt.lower()
        return ReportOutput(
            title="Daily Intelligence Briefing",
            summary="Three notable developments form a supported daily intelligence pattern.",
            body="This briefing contains only verified public developments and a sufficiently detailed supported synthesis.",
            development_ids=self.development_ids or ["0", "1", "2"],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(("report_type", "count"), [("Daily", 2), ("Weekly", 4)])
async def test_insufficient_published_developments_create_no_report(report_type, count) -> None:
    repository = Repository(rows(*(["Incremental"] * count)))
    provider = Provider()
    result = await generate_report(repository, provider, report_type)
    assert result == {"created": False, "reason": "insufficient_activity", "count": count}
    assert repository.created is None
    assert provider.called is False


@pytest.mark.asyncio
async def test_daily_digest_requires_three_verified_public_items() -> None:
    repository = Repository(rows("Incremental", "Incremental", "Incremental"))
    result = await generate_report(repository, None, "Daily")
    assert result["created"] is True
    assert result["report_level"] == "Monitoring digest"
    output = repository.created[1]
    assert "Verified incremental updates" in output.body
    assert repository.created[-1] == "Monitoring digest"


@pytest.mark.asyncio
async def test_daily_briefing_requires_three_major_or_notable_items() -> None:
    developments = rows("Major", "Notable", "Notable", "Incremental")
    repository = Repository(developments)
    provider = Provider([row["id"] for row in developments])
    result = await generate_report(repository, provider, "Daily")
    assert result["report_level"] == "Briefing"
    assert provider.called is True
    assert repository.created[-1] == "Briefing"
