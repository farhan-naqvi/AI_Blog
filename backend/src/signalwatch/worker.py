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
from .release_metadata import apply_release_importance, ground_release_facts
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

    async def run_once(self, max_jobs: int = 5) -> dict[str, int]:
        claimed = completed = failed = unavailable = 0
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            for _ in range(max(0, max_jobs)):
                jobs = await self.repository.claim_jobs(self.worker_id, 1)
                if not jobs:
                    break
                claimed += 1
                job = jobs[0]
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
        return {"claimed": claimed, "completed": completed, "failed": failed, "unavailable": unavailable}

    async def _process(
        self,
        job: dict[str, Any],
        client: httpx.AsyncClient,
        transitions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        job_started = perf_counter()
        source_items = await self.repository.source_items_for_job(job)
        if not source_items:
            raise ValueError("job source item does not exist")
        if transitions is not None:
            transitions.append({"state": "source_metadata_loaded", "created": False})
        item = source_items[0]
        readable_text = ""
        try:
            readable_text = await fetch_readable_text(client, item["canonical_url"] or item["url"])
            fetch_seconds = float(getattr(readable_text, "fetch_seconds", 0.0))
            extraction_seconds = float(getattr(readable_text, "extraction_seconds", 0.0))
            if transitions is not None:
                transitions.append({"state": "source_fetched_and_extracted_locally", "created": False})
            extracted, timings = await self._extract(source_items, readable_text, transitions)
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
        total_seconds = perf_counter() - job_started
        logger.info(
            "job_completed",
            extra={
                "subsystem": "worker",
                "category": "success",
                "fetch_duration_ms": round(fetch_seconds * 1000),
                "extraction_duration_ms": round(extraction_seconds * 1000),
                "stage_a_duration_ms": round(timings["stage_a_seconds"] * 1000),
                "stage_b_duration_ms": round(timings["stage_b_seconds"] * 1000),
                "total_duration_ms": round(total_seconds * 1000),
            },
        )
        return {
            "verification_status": decision.verification_status,
            "importance_label": extracted.importance_label,
            "publication_status": decision.publication_status,
            "deterministic_reasons": decision.reasons,
            "confirmed_claims": len(extracted.confirmed_claims),
            "reported_claims": len(extracted.reported_claims),
            "linkedin_draft_created": draft_created,
            "fetch_seconds": round(fetch_seconds, 2),
            "extraction_seconds": round(extraction_seconds, 2),
            "total_seconds": round(total_seconds, 2),
            **timings,
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
        factual, release_signals = ground_release_facts(factual, source_items)
        stage_b_started = perf_counter()
        analysis = await self.provider.generate_structured(
            development_analysis_prompt(factual, release_signals), DevelopmentAnalysis
        )
        analysis = apply_release_importance(analysis, release_signals)
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

    async def run_representative_batch(self, max_jobs: int = 4) -> dict[str, Any]:
        candidates = await self.repository.representative_pending_jobs(limit=max_jobs)
        results: list[dict[str, Any]] = []
        previous_failure: str | None = None
        consecutive_failures = 0
        for candidate in candidates:
            category = candidate["connector_key"]
            claimed = await self.repository.claim_replay_job(self.worker_id, candidate["id"])
            if len(claimed) != 1:
                result = {"ok": False, "reason": "specific_job_claim_failed", "transitions": []}
            else:
                claimed[0]["connector_key"] = category
                result = await self._run_claimed_diagnostic(claimed[0])
            transitions = result.get("transitions", [])
            details = result.get("result", {})
            safe_result = {
                "source_category": category,
                "stage_a": any(row.get("state") == "factual_extraction_validated" for row in transitions),
                "stage_b": any(row.get("state") == "bounded_analysis_validated" for row in transitions),
                "repair_used": bool(
                    details.get("stage_a_repair_used") or details.get("stage_b_repair_used")
                ),
                "job_state": "Completed" if result.get("ok") else "Pending",
                "development_state": details.get("verification_status"),
                "importance_label": details.get("importance_label"),
                "publication_state": details.get("publication_status"),
                "deterministic_reasons": details.get("deterministic_reasons", []),
                "confirmed_claims": details.get("confirmed_claims", 0),
                "reported_claims": details.get("reported_claims", 0),
                "fetch_seconds": details.get("fetch_seconds"),
                "extraction_seconds": details.get("extraction_seconds"),
                "stage_a_seconds": details.get("stage_a_seconds"),
                "stage_b_seconds": details.get("stage_b_seconds"),
                "duration_seconds": details.get("total_seconds", result.get("duration_seconds")),
                "failure": None if result.get("ok") else result.get("reason"),
            }
            results.append(safe_result)
            failure = safe_result["failure"]
            if failure:
                consecutive_failures = consecutive_failures + 1 if failure == previous_failure else 1
                previous_failure = failure
                if consecutive_failures >= 2:
                    break
            else:
                previous_failure = None
                consecutive_failures = 0
        return {
            "selected_categories": [row["connector_key"] for row in candidates],
            "processed": len(results),
            "results": results,
        }

    async def run_balanced_batch(self, max_jobs: int = 20) -> dict[str, Any]:
        candidates = await self.repository.balanced_pending_jobs(limit=max_jobs)
        results: list[dict[str, Any]] = []
        previous_failure: str | None = None
        consecutive_failures = 0
        for candidate in candidates:
            category = candidate["public_category"]
            claimed = await self.repository.claim_replay_job(self.worker_id, candidate["id"])
            result = (
                await self._run_claimed_diagnostic(claimed[0])
                if len(claimed) == 1
                else {"ok": False, "reason": "specific_job_claim_failed", "transitions": []}
            )
            transitions = result.get("transitions", [])
            details = result.get("result", {})
            failure = None if result.get("ok") else result.get("reason")
            results.append(
                {
                    "public_category": category,
                    "stage_a": any(row.get("state") == "factual_extraction_validated" for row in transitions),
                    "stage_b": any(row.get("state") == "bounded_analysis_validated" for row in transitions),
                    "repair_used": bool(details.get("stage_a_repair_used") or details.get("stage_b_repair_used")),
                    "verification_status": details.get("verification_status"),
                    "publication_status": details.get("publication_status"),
                    "importance_label": details.get("importance_label"),
                    "confirmed_claims": details.get("confirmed_claims", 0),
                    "reported_claims": details.get("reported_claims", 0),
                    "deterministic_reasons": details.get("deterministic_reasons", []),
                    "stage_a_seconds": details.get("stage_a_seconds"),
                    "stage_b_seconds": details.get("stage_b_seconds"),
                    "total_seconds": details.get("total_seconds", result.get("duration_seconds")),
                    "failure": failure,
                }
            )
            if failure:
                consecutive_failures = consecutive_failures + 1 if failure == previous_failure else 1
                previous_failure = failure
                if consecutive_failures >= 3:
                    break
            else:
                previous_failure = None
                consecutive_failures = 0
        return {"selected": len(candidates), "processed": len(results), "results": results}

    async def _run_claimed_diagnostic(self, job: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
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
                return {
                    "ok": True,
                    "transitions": transitions,
                    "result": result,
                    "duration_seconds": round(perf_counter() - started, 2),
                }
            except (ModelUnavailableError, StructuredGenerationError, ValueError, RuntimeError) as exc:
                await self.repository.fail_job(
                    job["id"], self.worker_id, str(exc), retryable=True
                )
                transitions.append(
                    {"state": "job_requeued", "created": False, "error_type": type(exc).__name__}
                )
                return {
                    "ok": False,
                    "reason": type(exc).__name__,
                    "transitions": transitions,
                    "duration_seconds": round(perf_counter() - started, 2),
                }
