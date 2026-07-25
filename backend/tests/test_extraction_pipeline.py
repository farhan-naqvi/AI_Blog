from datetime import date

import pytest
from pydantic import ValidationError

from signalwatch.extraction import compose_development
from signalwatch.models import Category, DevelopmentAnalysis, EventType, FactualExtraction


def minimal_factual(**overrides):
    payload = {
        "event_type": "Release",
        "category": "Infrastructure",
        "factual_summary": "A documented source announced a bounded software update.",
    }
    payload.update(overrides)
    return FactualExtraction.model_validate(payload)


def test_unknown_entities_date_and_empty_lists_are_valid() -> None:
    factual = minimal_factual(organisation=None, product=None, release_date=None)
    assert factual.organisation is None
    assert factual.product is None
    assert factual.release_date is None
    assert factual.confirmed_claims == factual.reported_claims == factual.limitations == []


def test_known_enum_aliases_are_normalized() -> None:
    factual = minimal_factual(event_type="model_release", category="ai_infrastructure")
    assert factual.event_type is EventType.RELEASE
    assert factual.category is Category.INFRASTRUCTURE


def test_empty_optional_strings_become_null_and_iso_datetime_becomes_date() -> None:
    factual = minimal_factual(
        organisation="  ", product="", release_date="2026-01-02T10:30:00Z"
    )
    assert factual.organisation is None and factual.product is None
    assert factual.release_date == date(2026, 1, 2)


def test_lists_drop_blanks_duplicates_and_enforce_limits() -> None:
    factual = minimal_factual(
        confirmed_claims=[" Claim ", "", "claim", *[f"Claim {i}" for i in range(20)]]
    )
    assert factual.confirmed_claims[0] == "Claim"
    assert len(factual.confirmed_claims) == 8


def test_required_facts_are_not_invented_by_defaults() -> None:
    with pytest.raises(ValidationError):
        FactualExtraction.model_validate({})


def test_what_changed_is_null_without_comparison_evidence() -> None:
    analysis = DevelopmentAnalysis.model_validate({
        "why_it_matters": "The source may matter to developers evaluating local infrastructure.",
        "what_changed": "",
    })
    assert analysis.what_changed is None


def test_composition_adds_only_deterministic_evidence(factual, analysis) -> None:
    source_items = [{
        "id": "11111111-1111-1111-1111-111111111111",
        "url": "https://example.com/release",
        "canonical_url": "https://example.com/release",
        "title": "Example Runtime publishes a documented release",
        "is_primary_source": True,
        "connector_key": "github",
    }]
    result = compose_development(factual, analysis, source_items)
    assert result.what_changed is None
    assert result.evidence[0].role == "Repository"
    assert result.evidence[0].claim_indexes == [0]
