from datetime import UTC, datetime, timedelta

from .llm import LanguageModelProvider
from .models import ReportOutput
from .prompts import report_prompt
from .repository import SupabaseRepository

REPORT_PROMPT_VERSION = "report-v1"
DIGEST_TEMPLATE_VERSION = "daily-digest-v1"


def _monitoring_digest(developments: list[dict], now: datetime) -> ReportOutput:
    groups = (
        ("Major developments", "Major"),
        ("Notable developments", "Notable"),
        ("Verified incremental updates", "Incremental"),
    )
    sections: list[str] = []
    for heading, importance in groups:
        rows = [row for row in developments if row.get("importance_label") == importance]
        if rows:
            entries = "\n".join(f"- {row['headline']}: {row['summary']}" for row in rows)
            sections.append(f"{heading}\n{entries}")
    return ReportOutput(
        title=f"Daily Monitoring Digest — {now.date().isoformat()}",
        summary=(
            f"{len(developments)} verified public developments were recorded. "
            "They are grouped by importance without promoting incremental updates to a major briefing."
        ),
        body="\n\n".join(sections),
        development_ids=[row["id"] for row in developments],
    )


async def generate_report(
    repository: SupabaseRepository,
    provider: LanguageModelProvider | None,
    report_type: str,
) -> dict:
    now = datetime.now(UTC)
    period_start = now - (timedelta(days=1) if report_type == "Daily" else timedelta(days=7))
    developments = await repository.published_developments(period_start, limit=20)
    minimum = 3 if report_type == "Daily" else 5
    if len(developments) < minimum:
        return {"created": False, "reason": "insufficient_activity", "count": len(developments)}
    report_level = "Briefing"
    model_identifier = provider.model_identifier if provider else "deterministic"
    prompt_version = REPORT_PROMPT_VERSION
    if report_type == "Daily":
        briefing_items = [
            row for row in developments if row.get("importance_label") in {"Major", "Notable"}
        ]
        if len(briefing_items) < 3:
            report_level = "Monitoring digest"
            output = _monitoring_digest(developments, now)
            prompt_version = DIGEST_TEMPLATE_VERSION
        else:
            if provider is None:
                raise ValueError("a local model provider is required for an intelligence briefing")
            output = await provider.generate_structured(
                report_prompt("Daily Intelligence Briefing", developments), ReportOutput
            )
    else:
        if provider is None:
            raise ValueError("a local model provider is required for a weekly report")
        output = await provider.generate_structured(report_prompt(report_type, developments), ReportOutput)
    allowed_ids = {row["id"] for row in developments}
    if not set(output.development_ids).issubset(allowed_ids):
        raise ValueError("report referenced an unknown development")
    result = await repository.create_report(
        report_type,
        output,
        period_start,
        now,
        model_identifier,
        prompt_version,
        report_level,
    )
    return {"created": True, "report_level": report_level, "result": result}
