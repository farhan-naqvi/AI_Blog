import json
from typing import Any

PROMPT_VERSION = "development-v1"


def development_prompt(source_items: list[dict[str, Any]], readable_text: str) -> str:
    evidence = [
        {
            "source_item_id": item["id"],
            "url": item["canonical_url"] or item["url"],
            "title": item["title"],
            "published_at": item.get("published_at"),
            "excerpt": item.get("excerpt", ""),
            "is_primary": item.get("is_primary_source", False),
            "evidence_role": item.get("evidence_role", "Primary announcement"),
        }
        for item in source_items
    ]
    return (
        "Extract one potential AI development from the evidence. Confirmed claims must each map "
        "to at least one zero-based claim index in evidence.claim_indexes. Report uncertainty and "
        "limitations explicitly. Headline must be factual, not promotional. If a field is unknown, "
        "use null where allowed and do not infer it.\n\nEVIDENCE METADATA:\n"
        + json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
        + "\n\nTEMPORARY SOURCE TEXT:\n"
        + readable_text[:40_000]
    )


def linkedin_prompt(development: dict[str, Any]) -> str:
    safe = {key: development.get(key) for key in (
        "headline", "summary", "why_it_matters", "what_changed", "limitations", "category"
    )}
    return (
        "Create one concise private LinkedIn draft. Prefer a technical or strategic angle, include "
        "one specific insight, avoid hype, and do not add facts or metrics. Do not claim personal "
        "experience. No more than 220 words. Evidence:\n"
        + json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
    )


def report_prompt(report_type: str, developments: list[dict[str, Any]]) -> str:
    compact = [
        {key: row.get(key) for key in ("id", "headline", "summary", "category", "published_at")}
        for row in developments
    ]
    return (
        f"Create a {report_type.lower()} intelligence report using only these published verified "
        "developments. Include patterns, what changed, and what to watch next. Every development_id "
        "must come from the supplied IDs. Do not add unsupported facts.\n"
        + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    )
