from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from .config import Settings
from .models import (
    CollectedItem,
    ExtractedDevelopment,
    LinkedinDraftOutput,
    ReportOutput,
    SourceRecord,
    VerificationDecision,
)


class RepositoryError(RuntimeError):
    pass


class SupabaseRepository:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = str(settings.supabase_url).rstrip("/")
        key = settings.supabase_service_role_key.get_secret_value()
        self.headers = {
            "apikey": key,
            "authorization": f"Bearer {key}",
            "content-type": "application/json",
        }
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(20.0))

    async def close(self) -> None:
        await self.client.aclose()

    async def _request(
        self, method: str, path: str, *, params: dict[str, str] | None = None, json: Any = None
    ) -> Any:
        response = await self.client.request(
            method, f"{self.base_url}/rest/v1/{path}", headers=self.headers, params=params, json=json
        )
        if response.is_error:
            raise RepositoryError(f"Supabase {response.status_code}: {response.text[:500]}")
        return response.json() if response.content else None

    async def due_sources(
        self, connector_key: str | None = None, limit: int | None = None
    ) -> list[SourceRecord]:
        params = {"select": "*", "active": "eq.true", "order": "last_checked_at.asc.nullsfirst"}
        if connector_key:
            params["connector_key"] = f"eq.{connector_key}"
        rows = await self._request("GET", "sources", params=params)
        now = datetime.now(UTC)
        due: list[SourceRecord] = []
        for row in rows:
            last = datetime.fromisoformat(row["last_checked_at"].replace("Z", "+00:00")) if row.get("last_checked_at") else None
            if last is None or last + timedelta(minutes=row["poll_interval_minutes"]) <= now:
                due.append(SourceRecord.model_validate(row))
        return due[:limit] if limit is not None else due

    async def smoke_source(self, connector_key: str) -> SourceRecord | None:
        rows = await self._request(
            "GET",
            "sources",
            params={
                "select": "*",
                "active": "eq.true",
                "connector_key": f"eq.{connector_key}",
                "order": "name.asc",
                "limit": "1",
            },
        )
        return SourceRecord.model_validate(rows[0]) if rows else None

    async def record_source_result(
        self,
        source_id: str,
        *,
        success: bool,
        error: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        payload: dict[str, Any] = {"last_checked_at": now, "last_error": error[:1000] if error else None}
        if success:
            payload["last_success_at"] = now
        if etag:
            payload["etag"] = etag[:500]
        if last_modified:
            payload["last_modified"] = last_modified[:500]
        await self._request("PATCH", "sources", params={"id": f"eq.{source_id}"}, json=payload)
        await self._request(
            "POST",
            "operational_logs",
            json={
                "event_type": "source_success" if success else "source_error",
                "severity": "INFO" if success else "ERROR",
                "source_id": source_id,
                "details": {"error_type": error[:200] if error else None},
            },
        )

    async def ingest_item(self, item: CollectedItem, rejection: str | None) -> dict[str, Any]:
        payload = item.model_dump(mode="json")
        payload["status"] = "Rejected" if rejection else "Candidate"
        payload["rejection_reason"] = rejection
        return await self._request("POST", "rpc/ingest_source_item", json={"item": payload})

    async def claim_jobs(self, worker_id: str, limit: int = 5) -> list[dict[str, Any]]:
        return await self._request(
            "POST", "rpc/claim_processing_jobs", json={"p_worker": worker_id, "p_batch_size": limit}
        )

    async def representative_pending_jobs(
        self,
        connector_order: tuple[str, ...] = ("rss", "github", "arxiv", "huggingface"),
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        rows = await self._request(
            "GET",
            "processing_jobs",
            params={
                "select": "id,source_item_id,status,priority,created_at",
                "status": "eq.Pending",
                "order": "priority.desc,created_at.asc,id.asc",
                "limit": "100",
            },
        )
        first_by_connector: dict[str, dict[str, Any]] = {}
        for row in rows:
            items = await self.source_items_for_job(row)
            if not items:
                continue
            connector = items[0].get("connector_key")
            if connector in connector_order and connector not in first_by_connector:
                first_by_connector[connector] = {**row, "connector_key": connector}
        return [first_by_connector[key] for key in connector_order if key in first_by_connector][
            : max(0, min(limit, len(connector_order)))
        ]

    async def replay_job(self) -> dict[str, Any] | None:
        rows = await self._request(
            "GET",
            "processing_jobs",
            params={
                "select": "id,source_item_id,status,attempt_count",
                "status": "eq.Pending",
                "attempt_count": "gt.0",
                "order": "attempt_count.desc,created_at.asc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def claim_replay_job(self, worker_id: str, job_id: str) -> list[dict[str, Any]]:
        return await self._request(
            "POST",
            "rpc/claim_processing_job_by_id",
            json={"p_worker": worker_id, "p_job_id": job_id},
        )

    async def complete_job(
        self,
        job_id: str,
        worker_id: str,
        extracted: ExtractedDevelopment,
        decision: VerificationDecision,
        model_identifier: str,
        prompt_version: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "rpc/finalize_processing_job",
            json={
                "p_job_id": job_id,
                "p_worker": worker_id,
                "p_result": extracted.model_dump(mode="json"),
                "p_decision": decision.model_dump(mode="json"),
                "p_model_identifier": model_identifier,
                "p_prompt_version": prompt_version,
            },
        )

    async def fail_job(
        self, job_id: str, worker_id: str, error: str, retryable: bool = True
    ) -> None:
        await self._request(
            "POST",
            "rpc/fail_processing_job",
            json={
                "p_job_id": job_id,
                "p_worker": worker_id,
                "p_error_message": error[:1000],
                "p_retryable": retryable,
            },
        )

    async def source_items_for_job(self, job: dict[str, Any]) -> list[dict[str, Any]]:
        rows = await self._request(
            "GET", "source_items", params={"select": "*", "id": f"eq.{job['source_item_id']}"}
        )
        if rows:
            sources = await self._request(
                "GET",
                "sources",
                params={
                    "select": "name,base_url,is_primary_source,source_type,retrieval_method,connector_key,connector_config",
                    "id": f"eq.{rows[0]['source_id']}",
                },
            )
            if sources:
                rows[0].update(sources[0])
            rows[0]["is_primary_source"] = bool(sources and sources[0]["is_primary_source"])
        return rows

    async def health_snapshot(self) -> dict[str, Any]:
        return await self._request("POST", "rpc/system_health_snapshot", json={})

    async def create_linkedin_draft(
        self, development_id: str, draft: LinkedinDraftOutput
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "rpc/create_linkedin_draft",
            json={"p_development_id": development_id, "p_draft": draft.model_dump(mode="json")},
        )

    async def published_developments(self, since: datetime, limit: int = 20) -> list[dict[str, Any]]:
        return await self._request(
            "GET",
            "developments",
            params={
                "select": "id,headline,summary,category,published_at,why_it_matters,what_changed,limitations",
                "publication_status": "eq.Published",
                "verification_status": "eq.Verified",
                "published_at": f"gte.{since.isoformat()}",
                "order": "published_at.desc",
                "limit": str(limit),
            },
        )

    async def create_report(
        self,
        report_type: str,
        output: ReportOutput,
        period_start: datetime,
        period_end: datetime,
        model_identifier: str,
        prompt_version: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "rpc/create_verified_report",
            json={
                "p_report_type": report_type,
                "p_report": output.model_dump(mode="json"),
                "p_period_start": period_start.isoformat(),
                "p_period_end": period_end.isoformat(),
                "p_model_identifier": model_identifier,
                "p_prompt_version": prompt_version,
            },
        )
