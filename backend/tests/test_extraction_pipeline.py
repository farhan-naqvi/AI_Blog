from datetime import date

import pytest
from pydantic import ValidationError

from signalwatch.extraction import compose_development
from signalwatch.models import Category, DevelopmentAnalysis, EventType, FactualExtraction
from signalwatch.prompts import factual_extraction_prompt
from signalwatch.release_metadata import apply_release_importance, ground_release_facts


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


def test_factual_prompt_separates_source_facts_from_reported_performance_claims() -> None:
    prompt = factual_extraction_prompt(
        [{"title": "Release", "published_at": None, "excerpt": ""}], "Short source"
    )
    assert "directly observable source facts" in prompt
    assert "not independently verified" in prompt
    assert "performance, benchmark, capability, compatibility, or outcome assertions" in prompt
    assert "repository, release tag" in prompt
    assert "promotional language" in prompt


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


def github_release_item(tag: str = "v2.0.0", *, prerelease: bool = False):
    return [{
        "id": "11111111-1111-1111-1111-111111111111",
        "url": f"https://github.com/pytorch/pytorch/releases/tag/{tag}",
        "canonical_url": f"https://github.com/pytorch/pytorch/releases/tag/{tag}",
        "title": "pytorch/pytorch: PyTorch 2.0",
        "published_at": "2023-03-15T00:00:00Z",
        "is_primary_source": True,
        "connector_key": "github",
        "release_metadata": {
            "repository": "pytorch/pytorch",
            "organisation": "pytorch",
            "release_tag": tag,
            "release_title": "PyTorch 2.0",
            "published_date": "2023-03-15",
            "prerelease": prerelease,
            "official_repository_release": True,
        },
    }]


def test_official_github_metadata_guarantees_observable_release_facts() -> None:
    factual = minimal_factual(
        event_type="Other",
        category="Other",
        organisation=None,
        product=None,
        release_date=None,
        confirmed_claims=[],
        reported_claims=["The project reports performance improvements."],
    )
    grounded, signals = ground_release_facts(factual, github_release_item())
    assert len(grounded.confirmed_claims) == 3
    assert any("official pytorch/pytorch repository" in claim for claim in grounded.confirmed_claims)
    assert grounded.reported_claims == ["The project reports performance improvements."]
    assert grounded.category is Category.DEVELOPER_TOOLS
    assert grounded.organisation == "pytorch"
    assert grounded.product == "pytorch"
    assert grounded.release_date == date(2023, 3, 15)
    assert signals["official_repository_release"] is True


def test_release_url_must_match_connector_metadata() -> None:
    item = github_release_item()[0]
    item["canonical_url"] = "https://github.com/unrelated/project/releases/tag/v2.0.0"
    grounded, signals = ground_release_facts(minimal_factual(category="Other"), [item])
    assert signals["official_repository_release"] is False
    assert grounded.confirmed_claims == []


def test_complete_non_prerelease_major_version_has_notable_floor() -> None:
    factual, signals = ground_release_facts(minimal_factual(category="Other"), github_release_item())
    analysis = DevelopmentAnalysis.model_validate({
        "why_it_matters": "The release affects a widely monitored open-source developer platform.",
        "importance_label": "Incremental",
        "importance_reasons": [],
    })
    bounded = apply_release_importance(analysis, signals)
    assert factual.confirmed_claims
    assert bounded.importance_label == "Notable"
    assert "never Major" in bounded.importance_reasons[0]


@pytest.mark.parametrize(
    "items",
    [github_release_item("v1.0.0"), github_release_item("v2.0.0-rc1", prerelease=True)],
)
def test_major_release_signal_does_not_overpromote_weak_or_prerelease_metadata(items) -> None:
    _, signals = ground_release_facts(minimal_factual(category="Other"), items)
    analysis = DevelopmentAnalysis.model_validate({
        "why_it_matters": "The release may affect developers using the monitored repository.",
        "importance_label": "Incremental",
    })
    assert apply_release_importance(analysis, signals).importance_label == "Incremental"
