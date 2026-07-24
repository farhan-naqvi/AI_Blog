import pytest

from signalwatch.llm import ModelUnavailableError
from signalwatch.worker import LocalWorker


class OfflineProvider:
    model_identifier = "offline"

    async def generate_structured(self, prompt, schema):
        raise ModelUnavailableError("Ollama unavailable")


class FakeRepository:
    def __init__(self):
        self.failures = []

    async def claim_jobs(self, worker_id, limit):
        return [{"id": "job-1", "source_item_id": "item-1"}]

    async def source_items_for_job(self, job):
        return [{
            "id": "item-1",
            "url": "https://example.com",
            "canonical_url": "https://example.com",
            "title": "Release",
            "excerpt": "",
            "is_primary_source": True,
        }]

    async def fail_job(self, job_id, error, retryable=True):
        self.failures.append((job_id, retryable))


@pytest.mark.asyncio
async def test_worker_requeues_when_ollama_is_unavailable(monkeypatch) -> None:
    async def fake_fetch(client, url):
        return "Official release content"

    monkeypatch.setattr("signalwatch.worker.fetch_readable_text", fake_fetch)
    repository = FakeRepository()
    result = await LocalWorker(repository, OfflineProvider(), "worker-1").run_once()
    assert result["unavailable"] == 1
    assert repository.failures == [("job-1", True)]
