import asyncio
import logging
from time import perf_counter

import httpx

from .collectors.base import Collector
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
    ) -> None:
        self.repository = repository
        self.collectors = collectors
        self.semaphore = asyncio.Semaphore(concurrency)

    async def run(self, connector_key: str | None = None) -> dict[str, int]:
        sources = await self.repository.due_sources(connector_key)
        results = await asyncio.gather(*(self._collect_source(source) for source in sources))
        return {
            "sources_checked": len(sources),
            "items_detected": sum(result[0] for result in results),
            "items_new": sum(result[1] for result in results),
            "errors": sum(result[2] for result in results),
        }

    async def _collect_source(self, source) -> tuple[int, int, int]:
        collector = self.collectors.get(source.connector_key)
        if collector is None:
            await self.repository.record_source_result(
                source.id, success=False, error=f"unsupported connector: {source.connector_key}"
            )
            return 0, 0, 1
        started = perf_counter()
        try:
            async with self.semaphore:
                async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
                    for attempt in range(3):
                        try:
                            result = await collector.collect(source, client)
                            break
                        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
                            if attempt == 2:
                                raise
                            logger.warning("source_retry", extra={"source_id": source.id})
                            await asyncio.sleep(2**attempt)
            new_count = 0
            for item in result.items:
                outcome = await self.repository.ingest_item(item, rejection_reason(item))
                if outcome and outcome.get("inserted"):
                    new_count += 1
            await self.repository.record_source_result(
                source.id,
                success=True,
                etag=result.etag,
                last_modified=result.last_modified,
            )
            logger.info(
                "source_checked",
                extra={
                    "source_id": source.id,
                    "duration_ms": round((perf_counter() - started) * 1000),
                    "result_count": len(result.items),
                    "new_count": new_count,
                },
            )
            return len(result.items), new_count, 0
        except (httpx.HTTPError, ValueError, RuntimeError) as exc:
            await self.repository.record_source_result(source.id, success=False, error=str(exc))
            logger.exception("source_failed", extra={"source_id": source.id})
            return 0, 0, 1
