from datetime import UTC, datetime

import pytest

from signalwatch.models import ExtractedDevelopment


@pytest.fixture
def extracted_payload() -> dict:
    return {
        "event_type": "release",
        "organisation": "Example Org",
        "product": "Example Runtime",
        "release_date": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        "category": "AI infrastructure",
        "headline": "Example Runtime publishes a documented release",
        "confirmed_claims": ["The project published version 2."],
        "reported_claims": [],
        "limitations": ["Performance was not independently benchmarked."],
        "summary": "Example Org published a documented update to its local inference runtime.",
        "why_it_matters": "The update changes how developers can run models on local hardware.",
        "what_changed": "The official repository now documents the second major release.",
        "who_affected": "Developers operating local inference workloads.",
        "watch_next": "Watch for independent compatibility testing.",
        "confidence_reasons": ["Official repository release."],
        "importance_reasons": ["Material runtime change."],
        "importance_label": "Notable",
        "evidence": [{
            "source_item_id": "11111111-1111-1111-1111-111111111111",
            "url": "https://example.com/releases/v2",
            "role": "Repository",
            "claim_indexes": [0],
        }],
    }


@pytest.fixture
def extracted(extracted_payload: dict) -> ExtractedDevelopment:
    return ExtractedDevelopment.model_validate(extracted_payload)
