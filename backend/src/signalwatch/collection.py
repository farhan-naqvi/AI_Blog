import asyncio
import logging
from time import perf_counter

import httpx

from .collectors.base import Collector, CollectorResponseError
from .coverage import CANDIDATE_LIMITS, category_rejection_reason, deterministic_cluster_key, source_category
from .filtering import rejection_reason
from .repository import SupabaseRepository

logger = logging.getLogger(__name__)


class CollectionService:
    def __init__(
        self,
        repository: SupabaseRepository,
        collectors: dict[str, Collector],
        *,
        concurrency: int = 4,
        candidate_limits: dict[str, int] | None = None,
    ) -> None:
        self.repository = repository
        self.collectors = collectors
        self.semaphore = asyncio.Semaphore(concurrency)
        self.candidate_limits = candidate_limits or CANDIDATE_LIMITS
        self._category_counts: dict[str, int] = {}
        self._candidate_lock = asyncio.Lock()

    async def run(
        self, connector_key: str | None = None, source_limit: int | None = None
    ) -> dict[str, int]:
        sources = await self.repository.due_sources(connector_key, source_limit)
        return await self.run_sources(sources)

    async def run_sources(self, sources) -> dict:
        self._category_counts = {}
        results = await asyncio.gather(*(self._collect_source(source) for source in sources))
        totals = {
            "sources_checked": len(sources),
            "items_detected": sum(result[0] for result in results),
            "items_new": sum(result[1] for result in results),
            "jobs_created": sum(result[2] for result in results),
            "errors": sum(result[3] for result in results),
            "items_filtered": sum(result[4] for result in results),
            "duplicates": sum(result[5] for result in results),
            "items_clustered": sum(result[6] for result in results),
        }
        by_category: dict[str, dict[str, int]] = {}
        keys = tuple(totals)
        for source, result in zip(sources, results, strict=True):
            category = source_category(source)
            metrics = by_category.setdefault(category, {key: 0 for key in keys})
            for index, key in enumerate(keys):
                metrics[key] += 1 if key == "sources_checked" else result[index - 1]
        return {**totals, "by_category": by_category}

    async def _collect_source(self, source) -> tuple[int, int, int, int, int, int, int]:
        collector = self.collectors.get(source.connector_key)
        if collector is None:
            await self.repository.record_source_result(
                source.id, success=False, error=f"unsupported connector: {source.connector_key}"
            )
            return 0, 0, 0, 1, 0, 0, 0
        started = perf_counter()
        try:
            async with self.semaphore:
                async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
                    for attempt in range(3):
                        try:
                            result = await collector.collect(source, client)
                            break
                        except (
                            httpx.TimeoutException,
                            httpx.NetworkError,
                            CollectorResponseError,
                        ) as exc:
                            if isinstance(exc, CollectorResponseError) and (
                                exc.status_code is None or exc.status_code < 500
                            ):
                                raise
                            if attempt == 2:
                                raise
                            logger.warning(
                                "source_retry",
                                extra={
                                    "subsystem": f"collector:{source.connector_key}",
                                    "retry_count": attempt + 1,
                                    "category": "network",
                                },
                            )
                            await asyncio.sleep(2**attempt)
            new_count = 0
            queued_count = 0
            duplicate_count = 0
            clustered_count = 0
            filtered_count = sum(result.filtered_reasons.values())
            for item in result.items:
                category = source_category(source)
                rejection = rejection_reason(item) or category_rejection_reason(
                    item, category, source.connector_config
                )
                item.cluster_key = deterministic_cluster_key(item, source)
                if rejection is None:
                    async with self._candidate_lock:
                        count = self._category_counts.get(category, 0)
                        if count >= self.candidate_limits[category]:
                            rejection = "category_candidate_limit"
                        else:
                            self._category_counts[category] = count + 1
                outcome = await self.repository.ingest_item(item, rejection)
                if outcome and outcome.get("inserted"):
                    new_count += 1
                if outcome and outcome.get("queued"):
                    queued_count += 1
                elif outcome and outcome.get("inserted"):
                    filtered_count += 1
                elif outcome and outcome.get("reason") == "duplicate":
                    duplicate_count += 1
                if outcome and outcome.get("clustered"):
                    clustered_count += 1
            await self.repository.record_source_result(
                source.id,
                success=True,
                etag=result.etag,
                last_modified=result.last_modified,
            )
            logger.info(
                "source_checked",
                extra={
                    "subsystem": f"collector:{source.connector_key}",
                    "duration_ms": round((perf_counter() - started) * 1000),
                    "result_count": result.discovered_count
                    if result.discovered_count is not None
                    else len(result.items),
                    "new_count": new_count,
                    "filtered_count": filtered_count,
                    "duplicate_count": duplicate_count,
                    "filter_reasons": result.filtered_reasons or None,
                    "category": "success",
                },
            )
            detected = (
                result.discovered_count
                if result.discovered_count is not None
                else len(result.items)
            )
            return detected, new_count, queued_count, 0, filtered_count, duplicate_count, clustered_count
        except (httpx.HTTPError, ValueError, RuntimeError) as exc:
            await self.repository.record_source_result(source.id, success=False, error=str(exc))
            logger.exception(
                "source_failed",
                extra={"subsystem": f"collector:{source.connector_key}", "category": "failure"},
            )
            return 0, 0, 0, 1, 0, 0, 0
