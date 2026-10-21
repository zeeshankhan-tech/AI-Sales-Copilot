from __future__ import annotations

import logging
import uuid
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.rate_limit import InMemoryRateLimiter
from app.config import settings
from app.inventory.repository import InventoryRepository
from app.llm import get_llm
from app.llm.base import LLMError, LLMProviderError, LLMTimeoutError
from app.schemas import ANALYZE_RESPONSE_FIELDS, AnalyzeRequest, AnalyzeResponse
from app.services.analysis import AnalysisParseError, AnalysisService
from app.services.evidence import EvidenceService, EvidenceVerificationError

logger = logging.getLogger("sales_copilot")
router = APIRouter()
_limiter = InMemoryRateLimiter(max_requests=settings.rate_limit_per_minute)


@lru_cache
def get_repository() -> InventoryRepository:
    return InventoryRepository(settings.inventory_path)


@lru_cache
def get_analysis_service() -> AnalysisService:
    repo = get_repository()
    return AnalysisService(repo=repo, llm=get_llm(), evidence=EvidenceService(repo))


def get_limiter() -> InMemoryRateLimiter:
    return _limiter


def enforce_rate_limit(
    request: Request,
    limiter: InMemoryRateLimiter = Depends(get_limiter),
) -> None:
    key = request.client.host if request.client else "unknown"
    limiter.hit(key)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    payload: AnalyzeRequest,
    request: Request,
    _: None = Depends(enforce_rate_limit),
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalyzeResponse:
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    text = payload.field_update.strip()
    if len(text) > settings.field_update_max_length:
        logger.info(
            "analyze_rejected request_id=%s outcome=invalid_length length=%s",
            request_id,
            len(text),
        )
        raise HTTPException(status_code=422, detail="Invalid request")

    try:
        result = service.analyze(text)
    except LLMTimeoutError:
        logger.info("analyze_failed request_id=%s outcome=timeout length=%s", request_id, len(text))
        raise HTTPException(status_code=504, detail="Analysis provider timed out") from None
    except LLMProviderError:
        logger.info("analyze_failed request_id=%s outcome=unavailable length=%s", request_id, len(text))
        raise HTTPException(status_code=503, detail="Analysis provider unavailable") from None
    except (LLMError, AnalysisParseError, EvidenceVerificationError):
        logger.info("analyze_failed request_id=%s outcome=bad_output length=%s", request_id, len(text))
        raise HTTPException(status_code=502, detail="Analysis failed") from None

    logger.info(
        "analyze_ok request_id=%s outcome=ok length=%s fields=%s",
        request_id,
        len(text),
        len(ANALYZE_RESPONSE_FIELDS),
    )
    return result
