from .models import EventType, ExtractedDevelopment, VerificationDecision

STRONG_PRIMARY_ROLES = {"Primary announcement", "Documentation", "Repository", "Research paper"}
SENSITIVE_TERMS = {
    "security vulnerability",
    "medical",
    "political",
    "legal accusation",
    "misconduct",
    "job loss",
    "financial claim",
}


def verify_development(
    extracted: ExtractedDevelopment,
    *,
    primary_source_item_ids: set[str],
    contradictory: bool = False,
    unresolved_duplicate: bool = False,
) -> VerificationDecision:
    reasons: list[str] = []
    strong_primary = any(
        ref.source_item_id in primary_source_item_ids and ref.role in STRONG_PRIMARY_ROLES
        for ref in extracted.evidence
    )
    sensitive_text = " ".join(
        [extracted.event_type, extracted.category, extracted.headline, *extracted.confirmed_claims]
    ).casefold()
    sensitive = extracted.event_type is EventType.SECURITY or any(
        term in sensitive_text for term in SENSITIVE_TERMS
    )
    if sensitive:
        reasons.append("sensitive category requires owner review")
    if not strong_primary:
        reasons.append("no strong primary source")
    if not extracted.confirmed_claims:
        reasons.append("no confirmed factual claims")
    if contradictory:
        reasons.append("evidence contains a major contradiction")
    if unresolved_duplicate:
        reasons.append("possible semantic duplicate is unresolved")
    if sensitive or contradictory or unresolved_duplicate:
        return VerificationDecision(
            verification_status="Held",
            confidence_label="Low" if contradictory else "Medium",
            publication_status="Held",
            reasons=reasons,
            exception_type="Sensitive" if sensitive else "Evidence conflict",
        )
    if not strong_primary or not extracted.confirmed_claims:
        return VerificationDecision(
            verification_status="Developing",
            confidence_label="Low",
            publication_status="Held",
            reasons=reasons,
            exception_type="Insufficient evidence",
        )
    return VerificationDecision(
        verification_status="Verified",
        confidence_label="High",
        publication_status="Published",
        reasons=["strong primary evidence, confirmed claims, and complete processing"],
    )
