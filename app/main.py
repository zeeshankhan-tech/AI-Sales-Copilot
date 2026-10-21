from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.rate_limit import RateLimitExceeded
from app.api.routes import router

app = FastAPI(title="AI Sales Copilot", version="0.1.0")
app.include_router(router)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_request: Request, _exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
