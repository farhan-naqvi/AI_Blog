import logging
from typing import Any

import httpx

from .llm import LanguageModelProvider, ModelUnavailableError, StructuredGenerationError
from .models import ExtractedDevelopment, LinkedinDraftOutput
from .prompts import PROMPT_VERSION, development_prompt, linkedin_prompt
from .repository import SupabaseRepository
from .security import fetch_readable_text
from .verification import verify_development

logger = logging.getLogger(__name__)


class LocalWorker:
    def __init__(
        self,
        repository: SupabaseRepository,
        provider: LanguageModelProvider,
        worker_id: str,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.worker_id = worker_id

    async def run_once(self, batch_size: int = 5) -> dict[str, int]:
        jobs = await self.repository.claim_jobs(self.worker_id, batch_size)
        completed = failed = unavailable = 0
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            for job in jobs:
                try:
                    await self._process(job, client)
                    completed += 1
                except ModelUnavailableError as exc:
                    await self.repository.fail_job(job["id"], str(exc), retryable=True)
                    unavailable += 1
                    break
                except (StructuredGenerationError, ValueError, RuntimeError) as exc:
                    await self.repository.fail_job(job["id"], str(exc), retryable=True)
                    logger.exception("job_failed", extra={"job_id": job["id"]})
                    failed += 1
        return {"claimed": len(jobs), "completed": completed, "failed": failed, "unavailable": unavailable}

    async def _process(self, job: dict[str, Any], client: httpx.AsyncClient) -> None:
        source_items = await self.repository.source_items_for_job(job)
        if not source_items:
            raise ValueError("job source item does not exist")
        item = source_items[0]
        readable_text = ""
        try:
            readable_text = await fetch_readable_text(client, item["canonical_url"] or item["url"])
            extracted = await self.provider.generate_structured(
                development_prompt(source_items, readable_text), ExtractedDevelopment
            )
        finally:
            readable_text = ""
        allowed_ids = {row["id"] for row in source_items}
        allowed_urls = {row["canonical_url"] or row["url"] for row in source_items}
        if any(str(ref.url) not in allowed_urls or ref.source_item_id not in allowed_ids for ref in extracted.evidence):
            raise ValueError("model returned an invented evidence reference")
        primary_ids = {row["id"] for row in source_items if row.get("is_primary_source", True)}
        decision = verify_development(extracted, primary_source_item_ids=primary_ids)
        outcome = await self.repository.complete_job(
            job["id"], extracted, decision, self.provider.model_identifier, PROMPT_VERSION
        )
        if outcome and outcome.get("linkedin_allowed"):
            draft = await self.provider.generate_structured(
                linkedin_prompt(extracted.model_dump(mode="json")), LinkedinDraftOutput
            )
            await self.repository.create_linkedin_draft(outcome["development_id"], draft)
        logger.info("job_completed", extra={"job_id": job["id"]})
