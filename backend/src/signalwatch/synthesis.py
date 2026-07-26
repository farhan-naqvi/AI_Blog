from datetime import UTC, datetime, timedelta
import re

from .llm import LanguageModelProvider
from .coverage import development_category
from .models import ReportOutput
from .prompts import report_prompt
from .repository import SupabaseRepository

_ROUTINE_RELEASE = re.compile(
    r"\b(bug fixes?|documentation updates?|dependency updates?|maintenance|code refactor(?:ing)?|"
    r"code quality improvements?|housekeeping)\b",
    re.I,
)
_CONCRETE_CHANGE = re.compile(
    r"\b(introduces?|adds?|enables?|supports?|launches?|removes?|changes?|makes available|open-sources?)\b",
    re.I,
)
_REPOSITORY_RELEASE = re.compile(r"^([^/\s]+)/([^:]+):\s*(\S.+)$")
_PRERELEASE = re.compile(
    r"(?:alpha|beta|rc|preview|dev|nightly)|^\d+(?:\.\d+)+(?:a|b|rc)\d+$",
    re.I,
)

REPORT_PROMPT_VERSION = "report-v1"
DIGEST_TEMPLATE_VERSION = "daily-digest-v2"
ACTIVITY_TEMPLATE_VERSION = "daily-activity-v1"


def _public_rank(row: dict) -> tuple[int, float]:
    order = {
        ("Verified", "Major"): 0,
        ("Reported", "Major"): 1,
        ("Verified", "Notable"): 2,
        ("Reported", "Notable"): 3,
        ("Verified", "Incremental"): 4,
        ("Reported", "Incremental"): 5,
    }
    published = row.get("published_at")
    timestamp = datetime.fromisoformat(published.replace("Z", "+00:00")).timestamp() if published else 0
    return order.get((row.get("verification_status"), row.get("importance_label")), 6), -timestamp


def _reader_value_candidate(row: dict) -> bool:
    if row.get("importance_label") != "Incremental" or row.get("event_type") != "Release":
        return True
    release = _REPOSITORY_RELEASE.match(str(row.get("headline") or ""))
    if release and _PRERELEASE.search(release.group(3)):
        return False
    summary = str(row.get("summary") or "")
    return not (_ROUTINE_RELEASE.search(summary) and not _CONCRETE_CHANGE.search(summary))


def _development_subject(row: dict) -> str:
    if row.get("product"):
        return f"product:{str(row['product']).strip().casefold()}"
    release = _REPOSITORY_RELEASE.match(str(row.get("headline") or ""))
    if release:
        return f"repository:{release.group(1).casefold()}/{release.group(2).casefold()}"
    if row.get("organisation"):
        return f"organisation:{str(row['organisation']).strip().casefold()}"
    return f"development:{row.get('id')}"


def _limit_per_category(rows: list[dict], limit: int = 5) -> list[dict]:
    selected: list[dict] = []
    category_counts: dict[str, int] = {}
    category_subjects: dict[str, set[str]] = {}
    for row in sorted(rows, key=_public_rank):
        if not _reader_value_candidate(row):
            continue
        category = development_category(row)
        if category_counts.get(category, 0) >= limit:
            continue
        subject = _development_subject(row)
        seen = category_subjects.setdefault(category, set())
        if subject in seen:
            continue
        seen.add(subject)
        category_counts[category] = category_counts.get(category, 0) + 1
        selected.append(row)
    return selected


def _monitoring_digest(developments: list[dict], now: datetime) -> ReportOutput:
    groups = (
        ("Major verified developments", "Verified", "Major"),
        ("Reported announcements - Major", "Reported", "Major"),
        ("Notable verified developments", "Verified", "Notable"),
        ("Reported announcements - Notable", "Reported", "Notable"),
        ("Other verified updates", "Verified", "Incremental"),
        ("Reported announcements - Incremental", "Reported", "Incremental"),
    )
    selected_developments = _limit_per_category(developments)
    sections: list[str] = []
    for heading, status, importance in groups:
        rows = [
            row
            for row in selected_developments
            if row.get("verification_status") == status
            and (importance is None or row.get("importance_label") == importance)
        ]
        if rows:
            entries = "\n".join(f"- {row['headline']}: {row['summary']}" for row in rows)
            sections.append(f"{heading}\n{entries}")
    return ReportOutput(
        title=f"Daily Monitoring Digest — {now.date().isoformat()}",
        summary=(
            f"{len(selected_developments)} reliably sourced public developments were recorded. "
            "Verified updates and source-reported announcements are presented separately."
        ),
        body="\n\n".join(sections),
        development_ids=[row["id"] for row in selected_developments],
    )


def _activity_summary(developments: list[dict], now: datetime) -> ReportOutput:
    entries = "\n".join(
        f"- [{row['verification_status']}] {row['headline']}: {row['summary']}"
        for row in developments
    )
    return ReportOutput(
        title=f"Daily Activity Summary — {now.date().isoformat()}",
        summary=(
            f"{len(developments)} reliably sourced public development"
            f"{' was' if len(developments) == 1 else 's were'} recorded; this is not a full daily report."
        ),
        body=f"Public activity\n{entries}",
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
    if not developments:
        return {"created": False, "reason": "insufficient_activity", "count": len(developments)}
    report_level = "Briefing"
    model_identifier = provider.model_identifier if provider else "deterministic"
    prompt_version = REPORT_PROMPT_VERSION
    if report_type == "Daily":
        briefing_items = [
            row
            for row in developments
            if row.get("verification_status") == "Verified"
            and row.get("importance_label") in {"Major", "Notable"}
        ]
        if len(developments) < 3:
            report_level = "Activity summary"
            output = _activity_summary(developments, now)
            prompt_version = ACTIVITY_TEMPLATE_VERSION
        elif len(briefing_items) < 3:
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
        if len(developments) < 5:
            return {"created": False, "reason": "insufficient_activity", "count": len(developments)}
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
