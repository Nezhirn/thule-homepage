"""
FastAPI Homepage Application
A Gnome 42-inspired customizable homepage with cards.
All data is stored on the server side.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from routes.settings import router as settings_router
from routes.cards import router as cards_router
from routes.uploads import router as uploads_router
from routes.favicon import router as favicon_router
from routes.data import router as data_router

# ==================== Config ====================

UPLOADS_DIR = os.environ.get("UPLOADS_DIR", os.path.join(os.path.dirname(__file__), "uploads"))
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


# ==================== Lifespan ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    yield
    # Graceful shutdown: cleanup is handled by SQLite automatically
    # on connection close per request.


# ==================== App Setup ====================

app = FastAPI(
    title="Homepage API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cache_control_middleware(request, call_next):
    """Set sensible Cache-Control headers for static frontend assets.

    - /css, /js: cache for an hour but revalidate (filenames are not hashed).
    - / (index.html): never cache, so new frontend versions are picked up.
    Routes that set their own Cache-Control (e.g. /api/uploads) are left untouched.
    """
    response = await call_next(request)
    path = request.url.path
    # Only cache successful responses, and never override a header the route
    # already set (e.g. /api/uploads sets its own immutable Cache-Control).
    if 200 <= response.status_code < 300 and "cache-control" not in response.headers:
        if path.startswith("/css/") or path.startswith("/js/"):
            response.headers["Cache-Control"] = "public, max-age=3600"
        elif path == "/":
            response.headers["Cache-Control"] = "no-cache"
    return response


# ==================== Frontend Serving ====================

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(index_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Frontend not found")
    with open(index_path, "r") as f:
        return f.read()


# Serve static files (CSS, JS)
if os.path.exists(FRONTEND_DIR):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


# ==================== Register Route Modules ====================

app.include_router(settings_router)
app.include_router(cards_router)
app.include_router(uploads_router)
app.include_router(favicon_router)
app.include_router(data_router)


# ==================== Health ====================

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
