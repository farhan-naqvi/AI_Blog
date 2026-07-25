from datetime import UTC, datetime

import httpx

from ..models import CollectedItem, SourceRecord
from ..normalization import canonicalize_url, content_fingerprint, normalize_title, parse_date, stable_hash
from .base import CollectionResult, conditional_headers


class GitHubCollector:
    key = "github"

    def __init__(self, token: str | None = None, max_items: int = 25) -> None:
        self.token = token
        self.max_items = max(1, min(max_items, 100))

    async def collect(self, source: SourceRecord, client: httpx.AsyncClient) -> CollectionResult:
        repository = source.connector_config.get("repository")
        if not repository or "/" not in repository:
            raise ValueError("GitHub source requires connector_config.repository")
        headers = conditional_headers(source) | {"accept": "application/vnd.github+json"}
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
        response = await client.get(
            f"https://api.github.com/repos/{repository}/releases",
            params={"per_page": self.max_items},
            headers=headers,
        )
        if response.status_code == 304:
            return CollectionResult(not_modified=True)
        response.raise_for_status()
        items: list[CollectedItem] = []
        for release in response.json()[: self.max_items]:
            if release.get("draft"):
                continue
            title = normalize_title(release.get("name") or release.get("tag_name") or "")
            raw_url = release.get("html_url")
            if not raw_url or len(title) < 3:
                continue
            canonical = canonicalize_url(raw_url)
            body = normalize_title(release.get("body") or "")[:1200]
            published = parse_date(release.get("published_at") or release.get("created_at"))
            if published and published > datetime.now(UTC):
                published = None
            items.append(
                CollectedItem(
                    source_id=source.id,
                    source_identifier=str(release.get("id")),
                    url=canonical,
                    canonical_url=canonical,
                    title=f"{repository}: {title}"[:500],
                    published_at=published,
                    excerpt=body,
                    event_type_hint="release",
                    content_hash=content_fingerprint(title, body),
                    title_hash=stable_hash(f"{repository}:{title}".casefold()),
                )
            )
        return CollectionResult(
            items=items,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )
