import re
from collections import Counter
from datetime import UTC, datetime, timedelta

import httpx

from ..models import CollectedItem, SourceRecord
from ..normalization import canonicalize_url, content_fingerprint, normalize_title, parse_date, stable_hash
from .base import (
    JSON_CONTENT_TYPES,
    CollectionResult,
    conditional_headers,
    fetch_bounded_response,
)

DEFAULT_TASK_TAGS = {
    "automatic-speech-recognition",
    "conversational",
    "feature-extraction",
    "image-classification",
    "image-text-to-text",
    "object-detection",
    "question-answering",
    "reinforcement-learning",
    "sentence-similarity",
    "text-generation",
    "text-to-image",
    "text2text-generation",
    "token-classification",
}
VARIANT_PATTERN = re.compile(
    r"(?:^|[-_.])(awq|gptq|gguf|4bit|8bit|fp16|fp8|int4|int8|quant(?:ized)?|copy|mirror)(?:$|[-_.])",
    re.IGNORECASE,
)


class HuggingFaceCollector:
    key = "huggingface"

    def __init__(self, token: str | None = None, max_items: int = 40) -> None:
        self.token = token
        self.max_items = max(1, min(max_items, 100))

    async def collect(self, source: SourceRecord, client: httpx.AsyncClient) -> CollectionResult:
        author = source.connector_config.get("author")
        max_age_days = max(1, min(int(source.connector_config.get("max_model_age_days", 90)), 365))
        new_model_days = max(
            1, min(int(source.connector_config.get("new_model_window_days", 30)), max_age_days)
        )
        task_tags = {
            str(tag).casefold()
            for tag in source.connector_config.get("task_tags", DEFAULT_TASK_TAGS)
        }
        reject_variants = bool(source.connector_config.get("reject_variants", True))
        require_model_card = bool(source.connector_config.get("require_model_card", True))
        watchlist = {
            str(name).casefold() for name in source.connector_config.get("watchlist", [])
        }
        headers = conditional_headers(source)
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
        params: dict[str, str | int] = {
            "sort": "createdAt",
            "direction": -1,
            "limit": self.max_items,
            "full": "true",
        }
        if author:
            params["author"] = author
        response = await fetch_bounded_response(
            client,
            "https://huggingface.co/api/models",
            connector=self.key,
            params=params,
            headers=headers,
            allowed_content_types=JSON_CONTENT_TYPES,
            expected_kind="json",
        )
        if response.status_code == 304:
            return CollectionResult(not_modified=True)
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("invalid Hugging Face models response")
        items: list[CollectedItem] = []
        filtered: Counter[str] = Counter()
        now = datetime.now(UTC)
        for model in payload[: self.max_items]:
            model_id = model.get("modelId") or model.get("id")
            if not model_id:
                filtered["insufficient_metadata"] += 1
                continue
            tags = [str(tag) for tag in model.get("tags", [])[:12]]
            created = parse_date(model.get("createdAt"))
            if created is None:
                filtered["insufficient_metadata"] += 1
                continue
            if created < now - timedelta(days=max_age_days):
                filtered["stale_update"] += 1
                continue
            model_name = str(model_id).rsplit("/", 1)[-1]
            if reject_variants and VARIANT_PATTERN.search(model_name):
                filtered["likely_duplicate_variant"] += 1
                continue
            if created < now - timedelta(days=new_model_days):
                filtered["routine_model_update"] += 1
                continue
            publisher = str(model.get("author") or str(model_id).split("/", 1)[0]).casefold()
            if watchlist and publisher not in watchlist:
                filtered["weak_development_signal"] += 1
                continue
            pipeline_tag = str(model.get("pipeline_tag") or "").casefold()
            recognized_task = pipeline_tag in task_tags or bool(
                task_tags.intersection(tag.casefold() for tag in tags)
            )
            siblings = model.get("siblings") or []
            has_readme = any(
                str(sibling.get("rfilename") or "").casefold() == "readme.md"
                for sibling in siblings
                if isinstance(sibling, dict)
            )
            card_data = model.get("cardData") if isinstance(model.get("cardData"), dict) else {}
            description = str(model.get("description") or card_data.get("description") or "").strip()
            explicit_link = any(
                tag.casefold().startswith(("arxiv:", "doi:", "repo:")) for tag in tags
            ) or any(key in card_data for key in ("arxiv", "paper", "repository", "repo"))
            if require_model_card and not (has_readme or len(description) >= 40 or explicit_link):
                filtered["insufficient_metadata"] += 1
                continue
            if not recognized_task and not explicit_link:
                filtered["weak_development_signal"] += 1
                continue
            signals = [f"Task: {pipeline_tag}" if pipeline_tag else "Recognized task metadata"]
            if has_readme:
                signals.append("Model card available")
            if explicit_link:
                signals.append("Paper or repository metadata available")
            downloads = model.get("downloads")
            likes = model.get("likes")
            if isinstance(downloads, int):
                signals.append(f"Downloads: {downloads}")
            if isinstance(likes, int):
                signals.append(f"Likes: {likes}")
            excerpt = ". ".join(signals)[:1200]
            raw_url = f"https://huggingface.co/{model_id}"
            canonical = canonicalize_url(raw_url)
            title = normalize_title(f"{model_id} model release")
            if created > now:
                filtered["weak_development_signal"] += 1
                continue
            items.append(
                CollectedItem(
                    source_id=source.id,
                    source_identifier=model_id[:500],
                    url=canonical,
                    canonical_url=canonical,
                    title=title,
                    published_at=created,
                    excerpt=excerpt,
                    event_type_hint="release",
                    content_hash=content_fingerprint(title, excerpt),
                    title_hash=stable_hash(title.casefold()),
                )
            )
        return CollectionResult(
            items=items,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
            discovered_count=min(len(payload), self.max_items),
            filtered_reasons=dict(filtered),
        )
