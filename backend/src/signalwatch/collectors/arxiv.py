from urllib.parse import urlencode

import feedparser
import httpx

from ..models import CollectedItem, SourceRecord
from ..normalization import canonicalize_url, content_fingerprint, normalize_title, parse_date, stable_hash
from .base import CollectionResult


class ArxivCollector:
    key = "arxiv"

    async def collect(self, source: SourceRecord, client: httpx.AsyncClient) -> CollectionResult:
        categories = source.connector_config.get("categories", ["cs.AI", "cs.LG"])
        query = " OR ".join(f"cat:{category}" for category in categories)
        url = "https://export.arxiv.org/api/query?" + urlencode(
            {
                "search_query": query,
                "start": 0,
                "max_results": 50,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
        )
        response = await client.get(url, headers={"user-agent": "SignalWatch/0.1"})
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise ValueError("invalid arXiv Atom response")
        items: list[CollectedItem] = []
        for entry in parsed.entries:
            title = normalize_title(entry.get("title", ""))
            raw_url = entry.get("id")
            if not raw_url or len(title) < 3:
                continue
            canonical = canonicalize_url(raw_url.replace("http://", "https://"))
            excerpt = normalize_title(entry.get("summary", ""))[:1200]
            items.append(
                CollectedItem(
                    source_id=source.id,
                    source_identifier=canonical.rsplit("/", 1)[-1][:500],
                    url=canonical,
                    canonical_url=canonical,
                    title=title,
                    published_at=parse_date(entry.get("published")),
                    excerpt=excerpt,
                    event_type_hint="research",
                    content_hash=content_fingerprint(title, excerpt),
                    title_hash=stable_hash(title.casefold()),
                )
            )
        return CollectionResult(items=items)
