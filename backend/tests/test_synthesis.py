from datetime import UTC

import pytest

from signalwatch.synthesis import generate_report


class Repository:
    def __init__(self, rows):
        self.rows = rows
        self.created = False

    async def published_developments(self, since, limit=20):
        assert since.tzinfo is UTC
        assert limit == 20
        return self.rows

    async def create_report(self, *args, **kwargs):
        self.created = True
        return {}


class Provider:
    model_identifier = "unused"

    async def generate_structured(self, prompt, schema):
        raise AssertionError("the model must not run when evidence is insufficient")


@pytest.mark.asyncio
@pytest.mark.parametrize(("report_type", "count"), [("Daily", 2), ("Weekly", 4)])
async def test_insufficient_published_developments_create_no_report(report_type, count) -> None:
    repository = Repository([{"id": str(index)} for index in range(count)])
    result = await generate_report(repository, Provider(), report_type)
    assert result == {"created": False, "reason": "insufficient_evidence", "count": count}
    assert repository.created is False
