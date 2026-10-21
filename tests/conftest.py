from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.rate_limit import InMemoryRateLimiter
from app.api.routes import get_limiter
from app.main import app


@pytest.fixture
def limiter() -> InMemoryRateLimiter:
    return InMemoryRateLimiter(max_requests=10, window_seconds=60)


@pytest.fixture
def client(limiter: InMemoryRateLimiter) -> TestClient:
    app.dependency_overrides[get_limiter] = lambda: limiter
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
