from typing import Any

from .models import (
    DevelopmentAnalysis,
    EvidenceReference,
    ExtractedDevelopment,
    FactualExtraction,
)


def compose_development(
    factual: FactualExtraction,
    analysis: DevelopmentAnalysis,
    source_items: list[dict[str, Any]],
) -> ExtractedDevelopment:
    item = source_items[0]
    connector = str(item.get("connector_key") or "").casefold()
    if connector == "github":
        role = "Repository"
    elif connector == "arxiv":
        role = "Research paper"
    elif item.get("is_primary_source", False):
        role = "Primary announcement"
    else:
        role = "Discovery signal"
    url = item.get("canonical_url") or item["url"]
    evidence = EvidenceReference(
        source_item_id=item["id"],
        url=url,
        role=role,
        claim_indexes=list(range(len(factual.confirmed_claims))),
    )
    confidence_reasons = [
        "One primary source was supplied."
        if item.get("is_primary_source", False)
        else "Only a discovery source was supplied."
    ]
    return ExtractedDevelopment(
        event_type=factual.event_type,
        organisation=factual.organisation,
        product=factual.product,
        release_date=factual.release_date,
        category=factual.category,
        headline=" ".join(str(item["title"]).split())[:240].rstrip(),
        confirmed_claims=factual.confirmed_claims,
        reported_claims=factual.reported_claims,
        limitations=factual.limitations,
        summary=factual.factual_summary,
        why_it_matters=analysis.why_it_matters,
        what_changed=analysis.what_changed,
        who_affected="; ".join(analysis.affected_groups)[:800],
        watch_next="; ".join(analysis.watch_next)[:800],
        confidence_reasons=confidence_reasons,
        importance_reasons=analysis.importance_reasons,
        importance_label=analysis.importance_label,
        evidence=[evidence],
    )
