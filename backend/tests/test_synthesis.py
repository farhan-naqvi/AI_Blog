from datetime import UTC

import pytest

from signalwatch.models import ReportOutput
from signalwatch.synthesis import generate_report


def rows(*importance: str, status: str = "Verified") -> list[dict]:
    return [
        {
            "id": str(index),
            "headline": f"Public development {index}",
            "summary": "A reliable primary source recorded an identifiable AI development.",
            "category": "Developer tools",
            "importance_label": label,
            "verification_status": status,
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
        assert "reported" in prompt.lower()
        return ReportOutput(
            title="Daily Intelligence Briefing",
            summary="Three notable verified developments form a supported daily pattern.",
            body="This briefing contains grounded public developments and clearly separates any reported announcements.",
            development_ids=self.development_ids or ["0", "1", "2"],
        )


@pytest.mark.asyncio
async def test_zero_public_developments_create_no_report() -> None:
    repository = Repository([])
    provider = Provider()
    result = await generate_report(repository, provider, "Daily")
    assert result == {"created": False, "reason": "insufficient_activity", "count": 0}
    assert repository.created is None
    assert provider.called is False


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 2])
async def test_one_or_two_public_items_create_activity_summary(count: int) -> None:
    repository = Repository(rows(*(["Incremental"] * count), status="Reported"))
    result = await generate_report(repository, None, "Daily")
    assert result["created"] is True
    assert result["report_level"] == "Activity summary"
    assert repository.created[-1] == "Activity summary"
    assert "not a full daily report" in repository.created[1].summary


@pytest.mark.asyncio
async def test_daily_digest_separates_verified_and_reported_items() -> None:
    developments = rows("Incremental", "Incremental")
    developments.extend(rows("Incremental", status="Reported"))
    developments[-1]["id"] = "reported"
    repository = Repository(developments)
    result = await generate_report(repository, None, "Daily")
    assert result["created"] is True
    assert result["report_level"] == "Monitoring digest"
    output = repository.created[1]
    assert "Other verified updates" in output.body
    assert "Reported announcements" in output.body
    assert repository.created[-1] == "Monitoring digest"


@pytest.mark.asyncio
async def test_reported_major_does_not_satisfy_briefing_threshold() -> None:
    developments = rows("Major", "Notable")
    developments.extend(rows("Major", status="Reported"))
    developments[-1]["id"] = "reported"
    repository = Repository(developments)
    provider = Provider()
    result = await generate_report(repository, provider, "Daily")
    assert result["report_level"] == "Monitoring digest"
    assert provider.called is False


@pytest.mark.asyncio
async def test_daily_briefing_requires_three_verified_major_or_notable_items() -> None:
    developments = rows("Major", "Notable", "Notable", "Incremental")
    repository = Repository(developments)
    provider = Provider([row["id"] for row in developments])
    result = await generate_report(repository, provider, "Daily")
    assert result["report_level"] == "Briefing"
    assert provider.called is True
    assert repository.created[-1] == "Briefing"


@pytest.mark.asyncio
async def test_weekly_report_still_requires_five_public_items() -> None:
    repository = Repository(rows("Incremental", "Incremental", "Incremental", "Incremental"))
    provider = Provider()
    result = await generate_report(repository, provider, "Weekly")
    assert result == {"created": False, "reason": "insufficient_activity", "count": 4}
    assert provider.called is False
