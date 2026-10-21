from __future__ import annotations

from fastapi.testclient import TestClient

from pathlib import Path

from app.api.rate_limit import InMemoryRateLimiter
from app.api.routes import get_analysis_service, get_limiter
from app.inventory.repository import InventoryRepository
from app.llm.base import LLMProviderError, LLMTimeoutError
from app.main import app
from app.schemas import ANALYZE_RESPONSE_FIELDS
from app.services.analysis import AnalysisService
from app.services.evidence import EvidenceService
from tests.test_analysis import ScriptedLLM


def test_health_is_liveness_only(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    body = response.json()
    assert "llm" not in str(body).lower()
    assert "provider" not in str(body).lower()
    assert "key" not in str(body).lower()


def test_analyze_rejects_extra_fields(client: TestClient) -> None:
    response = client.post(
        "/analyze",
        json={"field_update": "Metro Fresh is out of Cola 500ml.", "skip_review": True},
    )
    assert response.status_code == 422


def test_analyze_rejects_empty_update(client: TestClient) -> None:
    response = client.post("/analyze", json={"field_update": ""})
    assert response.status_code == 422


def test_analyze_rejects_over_configured_length(client: TestClient) -> None:
    response = client.post("/analyze", json={"field_update": "x" * 4001})
    assert response.status_code == 422


def test_analyze_success_has_exactly_seven_fields(client: TestClient) -> None:
    response = client.post(
        "/analyze",
        json={"field_update": "Visited City Corner. Juice 1L looked fine on the shelf."},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == set(ANALYZE_RESPONSE_FIELDS)
    assert len(body.keys()) == 7


def test_analyze_attaches_inventory_record_when_store_and_product_match(
    client: TestClient,
) -> None:
    response = client.post(
        "/analyze",
        json={"field_update": "Metro Fresh reports Cola 500ml is out of stock."},
    )
    assert response.status_code == 200
    body = response.json()
    table = [item for item in body["evidence"] if item["source"] == "verified_table"]
    assert table
    assert table[0]["record_id"] == "inv_metro_fresh_cola_500ml"
    assert "48" in table[0]["claim"]


def test_rate_limit_returns_429() -> None:
    tight = InMemoryRateLimiter(max_requests=2, window_seconds=60)
    app.dependency_overrides[get_limiter] = lambda: tight
    with TestClient(app) as client:
        payload = {"field_update": "Checking stock at Indiranagar Mart for Cola 500ml."}
        assert client.post("/analyze", json=payload).status_code == 200
        assert client.post("/analyze", json=payload).status_code == 200
        limited = client.post("/analyze", json=payload)
        assert limited.status_code == 429
        assert limited.json() == {"detail": "Rate limit exceeded"}
    app.dependency_overrides.clear()


def _scripted_client(script: str | Exception, client: TestClient) -> None:
    repo = InventoryRepository(Path(__file__).resolve().parent.parent / "data" / "inventory.json")
    service = AnalysisService(repo, ScriptedLLM(script), EvidenceService(repo))
    app.dependency_overrides[get_analysis_service] = lambda: service


def test_malformed_llm_output_returns_502(client: TestClient) -> None:
    _scripted_client("{not-json", client)
    response = client.post(
        "/analyze",
        json={"field_update": "Metro Fresh reports Cola 500ml is out of stock."},
    )
    assert response.status_code == 502
    assert response.json() == {"detail": "Analysis failed"}


def test_llm_timeout_returns_504(client: TestClient) -> None:
    _scripted_client(LLMTimeoutError("timed out"), client)
    response = client.post(
        "/analyze",
        json={"field_update": "Metro Fresh reports Cola 500ml is out of stock."},
    )
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_unavailable_provider_returns_503(client: TestClient) -> None:
    _scripted_client(LLMProviderError("down"), client)
    response = client.post(
        "/analyze",
        json={"field_update": "Metro Fresh reports Cola 500ml is out of stock."},
    )
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()
