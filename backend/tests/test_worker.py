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
        self.claim_calls = 0

    async def claim_jobs(self, worker_id, limit):
        self.claim_calls += 1
        if self.claim_calls > 1:
            return []
        return [{"id": "job-1", "source_item_id": "item-1"}]

    async def source_items_for_job(self, job):
        return [{
            "id": "item-1",
            "url": "https://example.com",
            "canonical_url": "https://example.com",
            "title": "Documented release",
            "excerpt": "",
            "is_primary_source": True,
        }]

    async def fail_job(self, job_id, worker_id, error, retryable=True):
        self.failures.append((job_id, worker_id, retryable))


@pytest.mark.asyncio
async def test_worker_requeues_when_ollama_is_unavailable(monkeypatch) -> None:
    async def fake_fetch(client, url):
        return "Official release content"

    monkeypatch.setattr("signalwatch.worker.fetch_readable_text", fake_fetch)
    repository = FakeRepository()
    result = await LocalWorker(repository, OfflineProvider(), "worker-1").run_once()
    assert result["unavailable"] == 1
    assert repository.failures == [("job-1", "worker-1", True)]
    assert repository.claim_calls == 1


class DraftFailureProvider:
    model_identifier = "local-test"

    def __init__(self, factual, analysis):
        self.factual = factual
        self.analysis = analysis
        self.calls = 0

    async def generate_structured(self, prompt, schema):
        self.calls += 1
        if self.calls == 1:
            return self.factual
        if self.calls == 2:
            return self.analysis
        raise ModelUnavailableError("Ollama stopped after development persistence")


class CompletingRepository(FakeRepository):
    async def source_items_for_job(self, job):
        return [{
            "id": "11111111-1111-1111-1111-111111111111",
            "url": "https://example.com/releases/v2",
            "canonical_url": "https://example.com/releases/v2",
            "title": "Documented release",
            "excerpt": "",
            "is_primary_source": True,
        }]

    async def complete_job(self, job_id, worker_id, extracted, decision, model, prompt_version):
        return {"development_id": "dev-1", "linkedin_allowed": True}


@pytest.mark.asyncio
async def test_draft_failure_does_not_requeue_completed_development(
    monkeypatch, factual, analysis
) -> None:
    async def fake_fetch(client, url):
        return "Official release content"

    monkeypatch.setattr("signalwatch.worker.fetch_readable_text", fake_fetch)
    repository = CompletingRepository()
    result = await LocalWorker(
        repository, DraftFailureProvider(factual, analysis), "worker-1"
    ).run_once()
    assert result == {"claimed": 1, "completed": 1, "failed": 0, "unavailable": 0}
    assert repository.failures == []


class EmptyRepository(FakeRepository):
    async def claim_jobs(self, worker_id, limit):
        return []


@pytest.mark.asyncio
async def test_bounded_worker_exits_when_queue_is_empty() -> None:
    result = await LocalWorker(EmptyRepository(), OfflineProvider(), "worker-1").run_once(5)
    assert result == {"claimed": 0, "completed": 0, "failed": 0, "unavailable": 0}
