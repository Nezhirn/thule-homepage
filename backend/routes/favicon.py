"""Favicon fetch API route."""
from fastapi import APIRouter

from schemas import FetchIconRequest, FetchIconResponse
from services import fetch_favicon

router = APIRouter(prefix="/api", tags=["favicon"])


@router.post("/fetch-icon", response_model=FetchIconResponse)
async def fetch_icon(request: FetchIconRequest):
    if not request.url or not request.url.strip():
        return FetchIconResponse(icon_path=None)

    icon_path = await fetch_favicon(request.url)
    return FetchIconResponse(icon_path=icon_path)
