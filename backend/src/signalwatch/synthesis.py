from datetime import UTC, datetime, timedelta

from .llm import LanguageModelProvider
from .models import ReportOutput
from .prompts import report_prompt
from .repository import SupabaseRepository

REPORT_PROMPT_VERSION = "report-v1"


async def generate_report(
    repository: SupabaseRepository,
    provider: LanguageModelProvider,
    report_type: str,
) -> dict:
    now = datetime.now(UTC)
    period_start = now - (timedelta(days=1) if report_type == "Daily" else timedelta(days=7))
    developments = await repository.published_developments(period_start, limit=20)
    minimum = 3 if report_type == "Daily" else 5
    if len(developments) < minimum:
        return {"created": False, "reason": "insufficient_evidence", "count": len(developments)}
    output = await provider.generate_structured(report_prompt(report_type, developments), ReportOutput)
    allowed_ids = {row["id"] for row in developments}
    if not set(output.development_ids).issubset(allowed_ids):
        raise ValueError("report referenced an unknown development")
    result = await repository.create_report(
        report_type,
        output,
        period_start,
        now,
        provider.model_identifier,
        REPORT_PROMPT_VERSION,
    )
    return {"created": True, "result": result}
