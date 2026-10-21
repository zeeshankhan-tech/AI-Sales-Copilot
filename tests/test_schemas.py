from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.inventory import InventoryRecord, InventoryRepository
from app.schemas import (
    ANALYZE_RESPONSE_FIELDS,
    AnalyzeRequest,
    AnalyzeResponse,
    Evidence,
    EvidenceSource,
    EvidenceStatus,
    IssueCategory,
    Urgency,
)


def test_foundation_imports() -> None:
    from app import config, schemas
    from app.inventory.repository import InventoryRepository as Repo

    assert config.settings.llm_provider == "mock"
    assert schemas.AnalyzeRequest is AnalyzeRequest
    assert Repo is InventoryRepository


def _valid_response(**overrides: object) -> dict:
    payload: dict = {
        "issue_category": "stockout",
        "urgency": "high",
        "evidence": [
            {
                "source": "field_update",
                "claim": "Metro Fresh reports Cola 500ml is out of stock.",
                "status": "reported",
                "record_id": None,
            },
            {
                "source": "verified_table",
                "claim": "System inventory records 48 units of Cola 500ml at Metro Fresh.",
                "status": "conflicting",
                "record_id": "inv_metro_fresh_cola_500ml",
            },
        ],
        "recommended_next_action": "Verify the physical shelf and the inventory record.",
        "missing_information": ["When the shelf was last physically checked"],
        "needs_human_review": True,
        "review_reason": "Reported stockout conflicts with the 48-unit system record.",
    }
    payload.update(overrides)
    return payload


def test_analyze_request_accepts_only_field_update() -> None:
    request = AnalyzeRequest(field_update="Metro Fresh is out of Cola 500ml.")
    assert request.field_update.startswith("Metro Fresh")


def test_analyze_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AnalyzeRequest.model_validate(
            {"field_update": "ok", "unexpected": True}
        )


def test_analyze_request_rejects_empty_or_too_long() -> None:
    with pytest.raises(ValidationError):
        AnalyzeRequest(field_update="")
    with pytest.raises(ValidationError):
        AnalyzeRequest(field_update="x" * 5001)


def test_evidence_requires_record_id_only_for_verified_table() -> None:
    reported = Evidence(
        source=EvidenceSource.FIELD_UPDATE,
        claim="Rep reports a stockout.",
        status=EvidenceStatus.REPORTED,
        record_id=None,
    )
    assert reported.record_id is None
    with pytest.raises(ValidationError):
        Evidence(
            source=EvidenceSource.FIELD_UPDATE,
            claim="Rep reports a stockout.",
            status=EvidenceStatus.REPORTED,
            record_id="inv_metro_fresh_cola_500ml",
        )
    with pytest.raises(ValidationError):
        Evidence(
            source=EvidenceSource.VERIFIED_TABLE,
            claim="48 units recorded.",
            status=EvidenceStatus.CONFLICTING,
            record_id=None,
        )


def test_analyze_response_has_exactly_seven_top_level_fields() -> None:
    response = AnalyzeResponse.model_validate(_valid_response())
    assert tuple(AnalyzeResponse.model_fields.keys()) == ANALYZE_RESPONSE_FIELDS
    assert set(response.model_dump().keys()) == set(ANALYZE_RESPONSE_FIELDS)
    assert len(ANALYZE_RESPONSE_FIELDS) == 7


def test_analyze_response_rejects_extra_fields_and_invalid_enums() -> None:
    with pytest.raises(ValidationError):
        AnalyzeResponse.model_validate(_valid_response() | {"extra": 1})
    with pytest.raises(ValidationError):
        AnalyzeResponse.model_validate(_valid_response(issue_category="not-a-category"))
    with pytest.raises(ValidationError):
        AnalyzeResponse.model_validate(_valid_response(urgency="urgent"))


def test_review_reason_matches_needs_human_review() -> None:
    ok = AnalyzeResponse.model_validate(
        _valid_response(
            needs_human_review=False,
            review_reason=None,
            missing_information=[],
        )
    )
    assert ok.review_reason is None
    with pytest.raises(ValidationError):
        AnalyzeResponse.model_validate(_valid_response(review_reason=None))
    with pytest.raises(ValidationError):
        AnalyzeResponse.model_validate(
            _valid_response(needs_human_review=False, review_reason="should be null")
        )


def test_enums_match_brief() -> None:
    assert {item.value for item in IssueCategory} == {
        "stockout",
        "damaged_product",
        "pricing",
        "delivery",
        "customer_safety",
        "other",
        "none",
    }
    assert {item.value for item in Urgency} == {"low", "medium", "high", "critical"}
    assert {item.value for item in EvidenceSource} == {"field_update", "verified_table"}
    assert {item.value for item in EvidenceStatus} == {
        "reported",
        "verified",
        "conflicting",
        "unverified",
    }


def test_inventory_record_ids_are_stable() -> None:
    assert InventoryRecord is InventoryRecord
    from pathlib import Path

    repo = InventoryRepository(Path(__file__).resolve().parent.parent / "data" / "inventory.json")
    assert repo.get("inv_metro_fresh_cola_500ml") is not None
    assert repo.get("INV-002") is None
