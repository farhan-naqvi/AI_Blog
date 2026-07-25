import pytest
from pydantic import ValidationError

from signalwatch.models import ExtractedDevelopment
from signalwatch.verification import verify_development


def test_model_rejects_claim_without_evidence(extracted_payload: dict) -> None:
    extracted_payload["evidence"][0]["claim_indexes"] = []
    with pytest.raises(ValidationError, match="without evidence"):
        ExtractedDevelopment.model_validate(extracted_payload)


def test_primary_notable_item_auto_publishes(extracted: ExtractedDevelopment) -> None:
    decision = verify_development(extracted, primary_source_item_ids={extracted.evidence[0].source_item_id})
    assert decision.publication_status == "Published"
    assert decision.verification_status == "Verified"


def test_sensitive_item_is_held(extracted_payload: dict) -> None:
    extracted_payload["event_type"] = "Security"
    extracted_payload["category"] = "Security vulnerability"
    extracted = ExtractedDevelopment.model_validate(extracted_payload)
    decision = verify_development(extracted, primary_source_item_ids={extracted.evidence[0].source_item_id})
    assert decision.publication_status == "Held"
    assert decision.exception_type == "Sensitive"


def test_secondary_only_item_is_developing(extracted: ExtractedDevelopment) -> None:
    decision = verify_development(extracted, primary_source_item_ids=set())
    assert decision.verification_status == "Developing"
    assert decision.publication_status == "Held"
