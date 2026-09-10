"""Central configuration for the Homepage backend.

Values are read from the environment once at import time. Tests override them
by monkeypatching the module attributes (all runtime code reads them through
this module instead of copying the values at import time).
"""
import os

APP_VERSION = os.environ.get("APP_VERSION", "1.2.1")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "homepage.db"))
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", os.path.join(BASE_DIR, "uploads"))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

# Optional shared secret. When set, every /api/* request except GET /api/health
# requires authentication (see auth.py). Empty/unset disables authentication.
AUTH_TOKEN = os.environ.get("AUTH_TOKEN") or None

# Grid layout
COLS_PER_ROW = 7

# Limits
MAX_FILE_SIZE = 10 * 1024 * 1024          # uploaded images, bytes
MAX_ICON_BYTES = 2 * 1024 * 1024          # fetched favicons, bytes
MAX_PAGE_BYTES = 1024 * 1024              # fetched HTML pages, bytes
MAX_URL_LENGTH = 2048
MAX_TITLE_LENGTH = 200
MAX_IMPORT_CARDS = 1000
MAX_REORDER_IDS = 1000
MAX_BLUR_RADIUS = 50
MAX_GRID_ROW = 500
FETCH_TIMEOUT = 5.0
FETCH_CONNECT_TIMEOUT = 3.0
FETCH_MAX_REDIRECTS = 3

UPLOADS_URL_PREFIX = "/api/uploads/"


def database_dir() -> str:
    """Directory that contains the SQLite database (created at startup)."""
    return os.path.dirname(DATABASE_PATH) or "."
