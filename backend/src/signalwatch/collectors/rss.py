from datetime import UTC, datetime

import feedparser
import httpx

from ..models import CollectedItem, SourceRecord
from ..normalization import (
    canonicalize_url,
    content_fingerprint,
    normalize_title,
    parse_date,
    stable_hash,
)
from .base import (
    XML_CONTENT_TYPES,
    CollectionResult,
    conditional_headers,
    fetch_bounded_response,
)


class RssCollector:
    key = "rss"

    def __init__(self, max_items: int = 100) -> None:
        self.max_items = max(1, min(max_items, 100))

    async def collect(self, source: SourceRecord, client: httpx.AsyncClient) -> CollectionResult:
        response = await fetch_bounded_response(
            client,
            str(source.base_url),
            connector=self.key,
            headers=conditional_headers(source),
            allowed_content_types=XML_CONTENT_TYPES,
            expected_kind="xml",
            validate_redirects=True,
            max_redirects=3,
        )
        if response.status_code == 304:
            return CollectionResult(not_modified=True)
        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise ValueError(f"invalid feed: {parsed.bozo_exception}")
        items: list[CollectedItem] = []
        for entry in parsed.entries[: self.max_items]:
            raw_url = entry.get("link") or entry.get("id")
            title = normalize_title(entry.get("title", ""))
            if not raw_url or len(title) < 3:
                continue
            canonical = canonicalize_url(raw_url)
            excerpt = normalize_title(entry.get("summary", ""))[:1200]
            published = parse_date(entry.get("published") or entry.get("updated"))
            if published and published > datetime.now(UTC):
                published = None
            items.append(
                CollectedItem(
                    source_id=source.id,
                    source_identifier=str(entry.get("id") or canonical)[:500],
                    url=canonical,
                    canonical_url=canonical,
                    title=title,
                    published_at=published,
                    excerpt=excerpt,
                    event_type_hint="article",
                    content_hash=content_fingerprint(title, excerpt),
                    title_hash=stable_hash(title.casefold()),
                )
            )
        return CollectionResult(
            items=items,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
            discovered_count=min(len(parsed.entries), self.max_items),
        )
