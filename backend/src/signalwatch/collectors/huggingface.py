from datetime import UTC, datetime

import httpx

from ..models import CollectedItem, SourceRecord
from ..normalization import canonicalize_url, content_fingerprint, normalize_title, parse_date, stable_hash
from .base import CollectionResult, conditional_headers


class HuggingFaceCollector:
    key = "huggingface"

    def __init__(self, token: str | None = None) -> None:
        self.token = token

    async def collect(self, source: SourceRecord, client: httpx.AsyncClient) -> CollectionResult:
        author = source.connector_config.get("author")
        headers = conditional_headers(source)
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
        params: dict[str, str | int] = {
            "sort": "lastModified",
            "direction": -1,
            "limit": 40,
            "full": "false",
        }
        if author:
            params["author"] = author
        response = await client.get("https://huggingface.co/api/models", params=params, headers=headers)
        if response.status_code == 304:
            return CollectionResult(not_modified=True)
        response.raise_for_status()
        items: list[CollectedItem] = []
        for model in response.json():
            model_id = model.get("modelId") or model.get("id")
            if not model_id:
                continue
            tags = [str(tag) for tag in model.get("tags", [])[:12]]
            excerpt = f"Updated model. Tags: {', '.join(tags)}"[:1200]
            raw_url = f"https://huggingface.co/{model_id}"
            canonical = canonicalize_url(raw_url)
            title = normalize_title(f"{model_id} model update")
            updated = parse_date(model.get("lastModified"))
            if updated and updated > datetime.now(UTC):
                updated = None
            items.append(
                CollectedItem(
                    source_id=source.id,
                    source_identifier=model_id[:500],
                    url=canonical,
                    canonical_url=canonical,
                    title=title,
                    published_at=updated,
                    excerpt=excerpt,
                    event_type_hint="model_update",
                    content_hash=content_fingerprint(title, excerpt),
                    title_hash=stable_hash(title.casefold()),
                )
            )
        return CollectionResult(
            items=items,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )
