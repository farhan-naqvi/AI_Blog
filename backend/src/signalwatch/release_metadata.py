import re
from typing import Any
from urllib.parse import unquote, urlsplit

from .models import Category, DevelopmentAnalysis, EventType, FactualExtraction, ReleaseMetadata

PRERELEASE_MARKERS = re.compile(r"(?:^|[.\-_])(alpha|beta|rc|preview|dev|nightly)(?:[.\-_\d]|$)", re.I)
SEMVER_MAJOR = re.compile(r"^v?(?P<major>0|[1-9]\d*)\.\d+(?:\.\d+)?(?:[.\-_+].*)?$", re.I)


def _release_metadata(item: dict[str, Any]) -> ReleaseMetadata | None:
    raw = item.get("release_metadata")
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        return ReleaseMetadata.model_validate(raw)
    except ValueError:
        return None


def grounded_release_signals(source_items: list[dict[str, Any]]) -> dict[str, Any]:
    if not source_items:
        return {}
    item = source_items[0]
    metadata = _release_metadata(item)
    if metadata is None or str(item.get("connector_key", "")).casefold() != "github":
        return {}
    url = urlsplit(str(item.get("canonical_url") or item.get("url") or ""))
    path = [unquote(part) for part in url.path.split("/") if part]
    url_repository = "/".join(path[:2]) if len(path) >= 5 else ""
    url_tag = path[4] if len(path) >= 5 and path[2:4] == ["releases", "tag"] else ""
    official = bool(
        item.get("is_primary_source")
        and metadata.official_repository_release
        and url.hostname == "github.com"
        and url_repository.casefold() == metadata.repository.casefold()
        and url_tag == metadata.release_tag
    )
    semver = SEMVER_MAJOR.fullmatch(metadata.release_tag.strip())
    prerelease = metadata.prerelease or bool(PRERELEASE_MARKERS.search(metadata.release_tag))
    complete = all(
        [metadata.repository, metadata.organisation, metadata.release_tag, metadata.release_title]
    ) and metadata.published_date is not None
    return {
        "official_repository_release": official,
        "repository": metadata.repository,
        "organisation": metadata.organisation,
        "release_tag": metadata.release_tag,
        "release_title": metadata.release_title,
        "published_date": metadata.published_date,
        "prerelease": prerelease,
        "semantic_major_version": int(semver.group("major")) if semver else None,
        "complete_release_metadata": complete,
    }


def ground_release_facts(
    factual: FactualExtraction, source_items: list[dict[str, Any]]
) -> tuple[FactualExtraction, dict[str, Any]]:
    signals = grounded_release_signals(source_items)
    if not signals.get("official_repository_release"):
        return factual, signals
    facts = list(factual.confirmed_claims)
    candidates = [
        f"The official {signals['repository']} repository published release {signals['release_tag']}.",
        f"The official release title is {signals['release_title']}.",
    ]
    if signals.get("published_date"):
        candidates.append(
            f"Official release metadata dates the release to {signals['published_date'].isoformat()}."
        )
    seen = {claim.casefold() for claim in facts}
    for claim in candidates:
        if claim.casefold() not in seen and len(facts) < 8:
            facts.append(claim)
            seen.add(claim.casefold())
    return factual.model_copy(
        update={
            "event_type": EventType.RELEASE,
            "organisation": factual.organisation or signals["organisation"],
            "product": factual.product or signals["repository"].split("/", 1)[1],
            "release_date": factual.release_date or signals.get("published_date"),
            "category": (
                Category.DEVELOPER_TOOLS if factual.category is Category.OTHER else factual.category
            ),
            "confirmed_claims": facts,
        }
    ), signals


def apply_release_importance(
    analysis: DevelopmentAnalysis, signals: dict[str, Any]
) -> DevelopmentAnalysis:
    qualifies_for_notable_floor = bool(
        signals.get("official_repository_release")
        and not signals.get("prerelease")
        and signals.get("complete_release_metadata")
        and isinstance(signals.get("semantic_major_version"), int)
        and signals["semantic_major_version"] >= 2
    )
    if not qualifies_for_notable_floor or analysis.importance_label != "Incremental":
        return analysis
    reason = (
        "Official watched repository published a non-prerelease major-version release with "
        "complete release metadata; deterministic policy sets a Notable floor, never Major."
    )
    reasons = list(analysis.importance_reasons)
    if reason not in reasons and len(reasons) < 6:
        reasons.append(reason)
    return analysis.model_copy(update={"importance_label": "Notable", "importance_reasons": reasons})
