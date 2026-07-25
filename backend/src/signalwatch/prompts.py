import json
from typing import Any

from .models import FactualExtraction

PROMPT_VERSION = "development-v2"


def factual_extraction_prompt(source_items: list[dict[str, Any]], readable_text: str) -> str:
    item = source_items[0]
    metadata = {
        "title": item["title"],
        "published_at": item.get("published_at"),
        "excerpt": item.get("excerpt", ""),
    }
    return (
        "Extract factual information using only the supplied source. Return null for unknown "
        "organisation, product, or date. Return empty arrays when no supported claims or "
        "limitations exist. Do not invent dates, entities, limitations, claims, or metrics. "
        "Output only the schema-conforming object.\n\nSOURCE METADATA:\n"
        + json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
        + "\n\nTEMPORARY SOURCE TEXT:\n"
        + readable_text[:24_000]
    )


def development_analysis_prompt(factual: FactualExtraction) -> str:
    return (
        "Analyze only the validated factual extraction below. Do not repeat or change factual "
        "claims. Explain why it matters conservatively. No previous-version evidence was supplied, "
        "so return null for what_changed. Return empty arrays when affected groups or watch items "
        "are unsupported. Classify importance conservatively and do not invent facts. Output only "
        "the schema-conforming object.\n\nFACTUAL EXTRACTION:\n"
        + json.dumps(factual.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
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
