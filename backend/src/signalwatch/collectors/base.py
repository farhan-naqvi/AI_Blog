from dataclasses import dataclass, field
from typing import Protocol

import httpx

from ..models import CollectedItem, SourceRecord


@dataclass
class CollectionResult:
    items: list[CollectedItem] = field(default_factory=list)
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False


class Collector(Protocol):
    key: str

    async def collect(self, source: SourceRecord, client: httpx.AsyncClient) -> CollectionResult:
        ...


def conditional_headers(source: SourceRecord) -> dict[str, str]:
    headers = {"user-agent": "SignalWatch/0.1 (+owner-operated AI monitoring)"}
    if source.etag:
        headers["if-none-match"] = source.etag
    if source.last_modified:
        headers["if-modified-since"] = source.last_modified
    return headers
