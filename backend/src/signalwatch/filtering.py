import re
from datetime import UTC, datetime, timedelta

from .models import CollectedItem

NOISE_PATTERNS = (
    r"^chore(?:\(.+\))?:",
    r"^deps?:",
    r"bump .+ from \S+ to \S+",
    r"weekly digest",
    r"minor documentation",
)


def rejection_reason(item: CollectedItem, max_age_days: int = 14) -> str | None:
    title = item.title.strip()
    if len(title) < 8:
        return "title_too_short"
    if item.published_at:
        published = item.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        if published < datetime.now(UTC) - timedelta(days=max_age_days):
            return "outside_time_window"
    lowered = title.casefold()
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in NOISE_PATTERNS):
        return "obvious_noise"
    if not item.excerpt.strip() and item.event_type_hint not in {"release", "research"}:
        return "empty_item"
    return None
