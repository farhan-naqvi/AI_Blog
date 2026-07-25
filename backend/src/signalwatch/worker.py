import logging
from time import perf_counter
from typing import Any

import httpx

from .llm import LanguageModelProvider, ModelUnavailableError, StructuredGenerationError
from .extraction import compose_development
from .models import DevelopmentAnalysis, ExtractedDevelopment, FactualExtraction, LinkedinDraftOutput
from .prompts import (
    PROMPT_VERSION,
    development_analysis_prompt,
    factual_extraction_prompt,
    linkedin_prompt,
)
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
                    await self.repository.fail_job(
                        job["id"], self.worker_id, str(exc), retryable=True
                    )
                    unavailable += 1
                    break
                except (StructuredGenerationError, ValueError, RuntimeError) as exc:
                    await self.repository.fail_job(
                        job["id"], self.worker_id, str(exc), retryable=True
                    )
                    logger.exception(
                        "job_failed", extra={"subsystem": "worker", "category": "processing"}
                    )
                    failed += 1
        return {"claimed": len(jobs), "completed": completed, "failed": failed, "unavailable": unavailable}

    async def _process(
        self,
        job: dict[str, Any],
        client: httpx.AsyncClient,
        transitions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        source_items = await self.repository.source_items_for_job(job)
        if not source_items:
            raise ValueError("job source item does not exist")
        if transitions is not None:
            transitions.append({"state": "source_metadata_loaded", "created": False})
        item = source_items[0]
        readable_text = ""
        try:
            readable_text = await fetch_readable_text(client, item["canonical_url"] or item["url"])
            if transitions is not None:
                transitions.append({"state": "source_fetched_and_extracted_locally", "created": False})
            extracted, _ = await self._extract(source_items, readable_text, transitions)
        finally:
            readable_text = ""
        allowed_ids = {row["id"] for row in source_items}
        allowed_urls = {row["canonical_url"] or row["url"] for row in source_items}
        if any(str(ref.url) not in allowed_urls or ref.source_item_id not in allowed_ids for ref in extracted.evidence):
            raise ValueError("model returned an invented evidence reference")
        if transitions is not None:
            transitions.append({"state": "structured_output_validated", "created": False})
        primary_ids = {row["id"] for row in source_items if row.get("is_primary_source", True)}
        decision = verify_development(extracted, primary_source_item_ids=primary_ids)
        outcome = await self.repository.complete_job(
            job["id"], self.worker_id, extracted, decision, self.provider.model_identifier, PROMPT_VERSION
        )
        if transitions is not None:
            transitions.append({"state": "development_stored", "created": True})
        draft_created = False
        if outcome and outcome.get("linkedin_allowed"):
            try:
                draft = await self.provider.generate_structured(
                    linkedin_prompt(extracted.model_dump(mode="json")), LinkedinDraftOutput
                )
                draft_result = await self.repository.create_linkedin_draft(
                    outcome["development_id"], draft
                )
                draft_created = bool(draft_result and draft_result.get("created"))
            except (ModelUnavailableError, StructuredGenerationError, ValueError, RuntimeError):
                logger.exception(
                    "linkedin_draft_failed_after_job_completion",
                    extra={"subsystem": "worker", "category": "draft"},
                )
        logger.info("job_completed", extra={"subsystem": "worker", "category": "success"})
        return {
            "verification_status": decision.verification_status,
            "publication_status": decision.publication_status,
            "linkedin_draft_created": draft_created,
        }

    async def _extract(
        self,
        source_items: list[dict[str, Any]],
        readable_text: str,
        transitions: list[dict[str, Any]] | None = None,
    ) -> tuple[ExtractedDevelopment, dict[str, Any]]:
        stage_a_started = perf_counter()
        factual = await self.provider.generate_structured(
            factual_extraction_prompt(source_items, readable_text), FactualExtraction
        )
        stage_a_seconds = perf_counter() - stage_a_started
        stage_a_repair_used = bool(getattr(self.provider, "last_repair_used", False))
        if transitions is not None:
            transitions.append({"state": "factual_extraction_validated", "created": False})
        stage_b_started = perf_counter()
        analysis = await self.provider.generate_structured(
            development_analysis_prompt(factual), DevelopmentAnalysis
        )
        stage_b_seconds = perf_counter() - stage_b_started
        stage_b_repair_used = bool(getattr(self.provider, "last_repair_used", False))
        if transitions is not None:
            transitions.append({"state": "bounded_analysis_validated", "created": False})
        extracted = compose_development(factual, analysis, source_items)
        return extracted, {
            "stage_a_seconds": round(stage_a_seconds, 2),
            "stage_b_seconds": round(stage_b_seconds, 2),
            "stage_a_repair_used": stage_a_repair_used,
            "stage_b_repair_used": stage_b_repair_used,
        }

    async def replay_extraction_once(self) -> dict[str, Any]:
        job = await self.repository.replay_job()
        if not job:
            return {"ok": False, "reason": "no_replayable_job"}
        source_items = await self.repository.source_items_for_job(job)
        if not source_items:
            return {"ok": False, "reason": "job_source_item_missing"}
        readable_text = ""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                readable_text = await fetch_readable_text(
                    client, source_items[0]["canonical_url"] or source_items[0]["url"]
                )
                extracted, timings = await self._extract(source_items, readable_text)
            return {
                "ok": True,
                "stage_a_valid": True,
                "stage_b_valid": True,
                "final_valid": isinstance(extracted, ExtractedDevelopment),
                "database_writes": 0,
                **timings,
            }
        except StructuredGenerationError as exc:
            return {
                "ok": False,
                "reason": exc.reason,
                "errors": exc.errors,
                "json_valid": exc.json_valid,
                "additional_prose": exc.additional_prose,
                "database_writes": 0,
            }
        finally:
            readable_text = ""

    async def retry_replayed_job_once(self) -> dict[str, Any]:
        replay_job = await self.repository.replay_job()
        if not replay_job:
            return {"ok": False, "reason": "no_replayable_job", "transitions": []}
        jobs = await self.repository.claim_replay_job(self.worker_id, replay_job["id"])
        if len(jobs) != 1:
            return {"ok": False, "reason": "specific_job_claim_failed", "transitions": []}
        return await self._run_claimed_diagnostic(jobs[0])

    async def run_diagnostic_once(self) -> dict[str, Any]:
        jobs = await self.repository.claim_jobs(self.worker_id, 1)
        if not jobs:
            return {"ok": False, "reason": "no_pending_job", "transitions": []}
        return await self._run_claimed_diagnostic(jobs[0])

    async def _run_claimed_diagnostic(self, job: dict[str, Any]) -> dict[str, Any]:
        transitions: list[dict[str, Any]] = []
        transitions.append({"state": "job_claimed", "created": False})
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            try:
                result = await self._process(job, client, transitions)
                transitions.extend(
                    [
                        {
                            "state": "deterministic_verification_applied",
                            "created": False,
                            "verification_status": result["verification_status"],
                            "publication_status": result["publication_status"],
                        },
                        {
                            "state": "linkedin_draft",
                            "created": result["linkedin_draft_created"],
                        },
                    ]
                )
                return {"ok": True, "transitions": transitions}
            except (ModelUnavailableError, StructuredGenerationError, ValueError, RuntimeError) as exc:
                await self.repository.fail_job(
                    job["id"], self.worker_id, str(exc), retryable=True
                )
                transitions.append(
                    {"state": "job_requeued", "created": False, "error_type": type(exc).__name__}
                )
                return {"ok": False, "reason": type(exc).__name__, "transitions": transitions}
