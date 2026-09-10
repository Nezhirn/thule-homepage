"""Optional shared-token authentication.

When ``AUTH_TOKEN`` is configured, every ``/api/*`` request except
``GET /api/health`` must authenticate with either:

* ``X-Auth-Token: <token>`` / ``Authorization: Bearer <token>`` header, or
* the HttpOnly session cookie issued after a successful header-authenticated
  request (used by the browser for ``<img>`` loads of uploaded files).

Only GET/HEAD requests may authenticate with the cookie. Mutating requests
additionally require the explicit header, which blocks cross-site request
forgery where the browser would silently attach the cookie.

The token is never embedded into served HTML, so exposing the port to a
network does not leak the secret to unauthenticated clients.
"""
import logging
import secrets

from starlette.requests import Request
from starlette.responses import JSONResponse

import config

logger = logging.getLogger(__name__)

COOKIE_NAME = "thule_session"
OPEN_PATHS = {"/api/health"}
SAFE_METHODS = {"GET", "HEAD"}


def enabled() -> bool:
    return bool(config.AUTH_TOKEN)


def _configured_token() -> str:
    return config.AUTH_TOKEN or ""


def _header_token(request: Request) -> str | None:
    token = request.headers.get("x-auth-token")
    if token:
        return token.strip()
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def token_matches(candidate: str | None) -> bool:
    if not candidate:
        return False
    return secrets.compare_digest(candidate, _configured_token())


def _cookie_matches(request: Request) -> bool:
    return token_matches(request.cookies.get(COOKIE_NAME))


def is_authorized(request: Request) -> bool:
    """True when the request carries valid credentials for a protected path."""
    if not enabled():
        return True
    path = request.url.path
    if path in OPEN_PATHS or not path.startswith("/api/"):
        return True  # health check, frontend and static assets
    if token_matches(_header_token(request)):
        return True
    return request.method in SAFE_METHODS and _cookie_matches(request)


def _use_secure_cookie(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    forwarded = request.headers.get("x-forwarded-proto", "")
    return forwarded.split(",")[0].strip().lower() == "https"


async def middleware(request: Request, call_next):
    if not is_authorized(request):
        return JSONResponse(
            {"detail": "Unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    response = await call_next(request)

    # Issue/refresh the session cookie after a successful header authentication
    # so that subsequent <img src="/api/uploads/..."> requests are authorized.
    if enabled() and token_matches(_header_token(request)):
        response.set_cookie(
            COOKIE_NAME,
            _configured_token(),
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="strict",
            secure=_use_secure_cookie(request),
            path="/",
        )
    return response
