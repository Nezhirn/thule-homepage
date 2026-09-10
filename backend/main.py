"""FastAPI Homepage Application.

A Gnome 42-inspired customizable homepage with cards. All data is stored on
the server side.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import auth
import config
from database import init_db
from routes.cards import router as cards_router
from routes.data import router as data_router
from routes.favicon import router as favicon_router
from routes.settings import router as settings_router
from routes.uploads import router as uploads_router

logger = logging.getLogger(__name__)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: http: https:; "
        "connect-src 'self' https://en.wikipedia.org; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    os.makedirs(config.database_dir(), exist_ok=True)
    os.makedirs(config.UPLOADS_DIR, exist_ok=True)
    init_db()
    if auth.enabled():
        logger.info("API authentication is enabled (AUTH_TOKEN is set)")
    else:
        logger.warning(
            "API authentication is DISABLED. Only expose this app on a trusted, "
            "local network or set the AUTH_TOKEN environment variable."
        )
    yield


app = FastAPI(title="Homepage API", version=config.APP_VERSION, lifespan=lifespan)

# Route modules.
app.include_router(settings_router)
app.include_router(cards_router)
app.include_router(uploads_router)
app.include_router(favicon_router)
app.include_router(data_router)


# Middleware registration order matters: the middleware added last runs first
# (outermost). Auth is registered before the response decorators so that even
# early 401 responses pass through the security-header middleware.
app.middleware("http")(auth.middleware)


@app.middleware("http")
async def cache_control_middleware(request, call_next):
    """Set sensible Cache-Control headers for static frontend assets.

    - /css, /js: no-cache (the browser revalidates with ETag every time, so a
      new frontend version is picked up immediately without re-downloading
      unchanged files). Filenames are not content-hashed, so a long max-age
      would serve stale JS/CSS after an update.
    - / (index.html): never cache, so new frontend versions are picked up.
    Routes that set their own Cache-Control (e.g. /api/uploads) are left untouched.
    """
    response = await call_next(request)
    path = request.url.path
    is_frontend_asset = path.startswith("/css/") or path.startswith("/js/") or path == "/"
    if 200 <= response.status_code < 300 and "cache-control" not in response.headers and is_frontend_asset:
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.middleware("http")
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


# ==================== Frontend Serving ====================

@app.get("/")
def serve_frontend():
    index_path = os.path.join(config.FRONTEND_DIR, "index.html")
    if not os.path.isfile(index_path):
        raise HTTPException(status_code=404, detail="Frontend not found")
    with open(index_path, encoding="utf-8") as handle:
        html = handle.read()
    # Asset URLs are versioned so a new release always busts the browser cache
    # even if a stale response was cached with a long max-age previously.
    return HTMLResponse(html.replace("__VERSION__", config.APP_VERSION))


if os.path.isdir(config.FRONTEND_DIR):
    app.mount("/css", StaticFiles(directory=os.path.join(config.FRONTEND_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(config.FRONTEND_DIR, "js")), name="js")


# ==================== Health ====================

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": config.APP_VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
