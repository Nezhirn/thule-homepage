"""Favicon fetch API route."""
from fastapi import APIRouter, Request

from ratelimit import RateLimiter, client_key
from schemas import FetchIconRequest, FetchIconResponse
from services import fetch_favicon

router = APIRouter(prefix="/api", tags=["favicon"])

_fetch_limiter = RateLimiter(max_requests=20, window_seconds=60)


@router.post("/fetch-icon", response_model=FetchIconResponse)
async def fetch_icon(request: FetchIconRequest, http_request: Request):
    _fetch_limiter.check(client_key(http_request))
    icon_path = await fetch_favicon(request.url)
    return FetchIconResponse(icon_path=icon_path)
