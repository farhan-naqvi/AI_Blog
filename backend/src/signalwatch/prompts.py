import json
from typing import Any

from .models import FactualExtraction

PROMPT_VERSION = "development-v5"


def factual_extraction_prompt(source_items: list[dict[str, Any]], readable_text: str) -> str:
    item = source_items[0]
    metadata = {
        "title": item["title"],
        "published_at": item.get("published_at"),
        "excerpt": item.get("excerpt", ""),
        "release_metadata": item.get("release_metadata"),
    }
    return (
        "Extract factual information using only the supplied source. Return null for unknown "
        "organisation, product, or date. Return empty arrays when no supported claims or "
        "limitations exist. Put directly observable source facts in confirmed_claims (for "
        "example, a release exists, a repository added a documented feature, or a paper "
        "introduces a stated method). Confirmed here means supported by this source, not "
        "independently verified. For an official repository release, its repository, release tag, "
        "release title, published date, and named entries visibly present in release notes are "
        "observable facts. Put performance, benchmark, capability, compatibility, or outcome assertions "
        "made by the source in reported_claims unless independent evidence is supplied. Exclude "
        "opinions, promotional language, and unsupported inference from both lists. Do not invent "
        "independent confirmation, dates, entities, limitations, claims, or metrics. "
        "Output only the schema-conforming object.\n\nSOURCE METADATA:\n"
        + json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
        + "\n\nTEMPORARY SOURCE TEXT:\n"
        + readable_text[:24_000]
    )


def development_analysis_prompt(
    factual: FactualExtraction, release_signals: dict[str, Any] | None = None
) -> str:
    return (
        "Analyze only the validated factual extraction below. Do not repeat or change factual "
        "claims. Explain why it matters conservatively. Create reader_headline only when the facts "
        "identify a concrete change: name the product and the change in plain language, stay under "
        "110 characters, and avoid tag-only titles, clickbait, hype, or unsupported adjectives. "
        "Return null for reader_headline when the source supports only routine maintenance or does "
        "not identify a concrete reader-relevant change. Do not call an update critical, major, "
        "significant, or transformative unless the validated facts directly support that impact. "
        "No previous-version evidence was supplied, "
        "so return null for what_changed. Return empty arrays when affected groups or watch items "
        "are unsupported. Classify importance conservatively using the bounded release signals when "
        "provided; a major-version signal alone must not imply Major. Do not invent facts. Output only "
        "the schema-conforming object.\n\nFACTUAL EXTRACTION:\n"
        + json.dumps(factual.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
        + "\n\nBOUNDED RELEASE SIGNALS:\n"
        + json.dumps(release_signals or {}, ensure_ascii=False, separators=(",", ":"), default=str)
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
        {
            key: row.get(key)
            for key in (
                "id",
                "headline",
                "summary",
                "category",
                "importance_label",
                "verification_status",
                "published_at",
            )
        }
        for row in developments
    ]
    report_name = report_type if "Briefing" in report_type else f"{report_type} intelligence report"
    return (
        f"Create a {report_name} using only these public developments. Verified items may form the "
        "main analysis. If Reported items are included, place them in a clearly labelled secondary "
        "section and never describe their claims as independently verified. Include patterns, what "
        "changed, and what to watch next. Every development_id must come from the supplied IDs. Do "
        "not add unsupported facts.\n"
        + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    )
