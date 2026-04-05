"""
FastAPI Homepage Application
A Gnome 42-inspired customizable homepage with cards.
All data is stored on the server side.
"""
import os
import uuid
import re
import json
from contextlib import asynccontextmanager
from typing import Optional, List
from urllib.parse import urlparse, urljoin, unquote

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import get_db_connection, init_db

# ==================== Config ====================

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}

# ==================== Pydantic Schemas ====================

class SettingsUpdate(BaseModel):
    background_image: Optional[str] = None
    blur_radius: Optional[int] = None
    dark_mode: Optional[bool] = None


class SettingsResponse(BaseModel):
    id: int
    background_image: Optional[str] = None
    blur_radius: int
    dark_mode: bool




class CardCreate(BaseModel):
    title: str
    url: Optional[str] = None
    icon_path: Optional[str] = None
    size: str = "1x1"
    grid_col: int = 1
    grid_row: int = 1


class CardUpdate(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    icon_path: Optional[str] = None
    size: Optional[str] = None
    position: Optional[int] = None
    grid_col: Optional[int] = None
    grid_row: Optional[int] = None


class CardResponse(BaseModel):
    id: int
    title: str
    url: Optional[str] = None
    icon_path: Optional[str] = None
    size: str
    position: int
    grid_col: int
    grid_row: int


class CardsReorderRequest(BaseModel):
    card_ids: List[int]


class FetchIconRequest(BaseModel):
    url: str


class FetchIconResponse(BaseModel):
    icon_path: Optional[str] = None


class FullDataResponse(BaseModel):
    settings: SettingsResponse
    cards: List[CardResponse]


# ==================== Lifespan ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    yield


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


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend not found")
    with open(index_path, "r") as f:
        return f.read()


# Serve static files (CSS, JS)
if os.path.exists(FRONTEND_DIR):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


# ==================== Helpers ====================

def _validate_url_field(url: Optional[str]) -> Optional[str]:
    """Validate URL to prevent javascript: and other dangerous schemes."""
    if url is None:
        return None
    url = url.strip()
    if not url:
        return None
    dangerous_schemes = ("javascript:", "data:", "vbscript:")
    if url.lower().startswith(tuple(dangerous_schemes)):
        raise HTTPException(status_code=400, detail="Invalid URL scheme")
    return url


def _validate_icon_path(icon_path: str) -> str:
    """Validate icon_path. Accepts either a full URL (http/https) or a safe local filename.
    Rejects path traversal in local filenames. Returns the original value if valid."""
    if not icon_path:
        return icon_path
    # If it's a URL, allow it (frontend validates the scheme via _validate_url_field on card.url,
    # but icon_path itself can be a URL like https://example.com/icon.svg)
    parsed = urlparse(icon_path)
    if parsed.scheme in ("http", "https"):
        return icon_path
    # Local filename — reject path traversal
    if ".." in icon_path or "/" in icon_path or "\\" in icon_path:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return icon_path


def _validate_file(file: UploadFile):
    """Validate uploaded file type and size."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file.content_type}' not allowed. Allowed: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )


async def _read_file_with_limit(file: UploadFile, max_size: int = MAX_FILE_SIZE) -> bytes:
    """Read file content with size limit."""
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {max_size // (1024 * 1024)} MB"
        )
    return content


def _save_image_bytes(data: bytes, original_filename: Optional[str] = None) -> str:
    """Save image bytes to uploads directory, return filename."""
    ext = ".png"
    if original_filename:
        ext = os.path.splitext(original_filename)[1]
        if not ext or ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"):
            ext = ".png"
        if ext.lower() == ".jpg":
            ext = ".jpeg"

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(data)
    return filename


# ==================== Settings ====================

@app.get("/api/settings", response_model=SettingsResponse)
def get_settings():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM settings LIMIT 1")
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO settings (blur_radius, dark_mode) VALUES (0, 0)")
        conn.commit()
        cursor.execute("SELECT * FROM settings LIMIT 1")
        row = cursor.fetchone()

    # Sanitise: if background_image references a missing file, clear it
    bg = row["background_image"]
    if bg and not os.path.exists(os.path.join(UPLOADS_DIR, bg)):
        cursor.execute("UPDATE settings SET background_image = NULL WHERE id = ?", (row["id"],))
        conn.commit()
        cursor.execute("SELECT * FROM settings WHERE id = ?", (row["id"],))
        row = cursor.fetchone()

    conn.close()

    return SettingsResponse(
        id=row["id"],
        background_image=row["background_image"],
        blur_radius=row["blur_radius"],
        dark_mode=bool(row["dark_mode"])
    )


@app.put("/api/settings", response_model=SettingsResponse)
def update_settings(settings_update: SettingsUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM settings LIMIT 1")
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO settings (blur_radius, dark_mode) VALUES (0, 0)")
        conn.commit()
        cursor.execute("SELECT * FROM settings LIMIT 1")
        row = cursor.fetchone()

    updates = []
    values = []

    if settings_update.background_image is not None:
        # Delete old background file if replacing
        old_bg = row["background_image"]
        if old_bg and old_bg != settings_update.background_image:
            old_path = os.path.join(UPLOADS_DIR, old_bg)
            if os.path.exists(old_path):
                os.remove(old_path)
        updates.append("background_image = ?")
        values.append(settings_update.background_image)
    elif settings_update.background_image is None and row["background_image"]:
        # Explicitly setting background_image to null — delete old file
        old_bg = row["background_image"]
        old_path = os.path.join(UPLOADS_DIR, old_bg)
        if os.path.exists(old_path):
            os.remove(old_path)
        updates.append("background_image = ?")
        values.append(None)

    if settings_update.blur_radius is not None:
        updates.append("blur_radius = ?")
        values.append(settings_update.blur_radius)

    if settings_update.dark_mode is not None:
        updates.append("dark_mode = ?")
        values.append(int(settings_update.dark_mode))

    if updates:
        values.append(row["id"])
        cursor.execute(f"UPDATE settings SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()

    cursor.execute("SELECT * FROM settings WHERE id = ?", (row["id"],))
    updated = cursor.fetchone()
    conn.close()

    return SettingsResponse(
        id=updated["id"],
        background_image=updated["background_image"],
        blur_radius=updated["blur_radius"],
        dark_mode=bool(updated["dark_mode"])
    )


# ==================== File Upload ====================

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    _validate_file(file)
    content = await _read_file_with_limit(file)
    filename = _save_image_bytes(content, file.filename)
    return {
        "filename": filename,
        "url": f"/api/uploads/{filename}"
    }


@app.get("/api/uploads/{filename}")
def serve_uploaded_file(filename: str):
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)


@app.delete("/api/upload/{filename}")
def delete_uploaded_file(filename: str):
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    os.remove(filepath)
    return {"message": "File deleted successfully"}


# ==================== Favicon Fetch ====================

def _is_private_ip(hostname: str) -> bool:
    """Check if hostname resolves to a private/internal IP (SSRF protection)."""
    import socket, ipaddress
    try:
        ips = set(ip for _, _, _, _, (ip, _) in socket.getaddrinfo(hostname, None))
        for ip in ips:
            try:
                addr = ipaddress.ip_address(ip)
                if addr.is_private or addr.is_loopback or addr.is_reserved:
                    return True
            except ValueError:
                return False  # can't parse — be safe and reject
        return False
    except socket.gaierror:
        return False  # can't resolve — be safe and reject


async def _fetch_favicon(page_url: str) -> Optional[str]:
    """Fetch favicon from a URL and save it to uploads. Returns icon_path or None.

    Security: Rejects private/internal URLs (SSRF), skips SVG (XSS via <script>).
    """
    import socket
    try:
        parsed = urlparse(page_url)
        if not parsed.scheme:
            page_url = "https://" + page_url
            parsed = urlparse(page_url)

        # SSRF protection: reject private/internal URLs
        if not _is_private_ip(parsed.hostname or ""):
            pass  # hostname is safe (public)
        else:
            return None

        if not parsed.hostname:
            return None

        base_url = f"{parsed.scheme}://{parsed.hostname}"

        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            icon_url = None

            # Try to fetch the page and parse link rel="icon"
            try:
                resp = await client.get(page_url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
                if resp.status_code == 200:
                    patterns = [
                        r'<link[^>]+rel=["\'](?:shortcut icon|icon|apple-touch-icon)["\'][^>]+href=["\']([^"\']+)["\']',
                        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\'](?:shortcut icon|icon|apple-touch-icon)["\']',
                    ]
                    for pat in patterns:
                        match = re.search(pat, resp.text, re.IGNORECASE)
                        if match:
                            icon_url = urljoin(page_url, match.group(1))
                            break

                    if not icon_url:
                        match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
                        if not match:
                            match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', resp.text, re.IGNORECASE)
                        if match:
                            icon_url = urljoin(page_url, match.group(1))
            except Exception:
                pass

            if not icon_url:
                icon_url = f"{base_url}/favicon.ico"

            # If icon URL has no extension, try variants (skip SVG to avoid XSS)
            if icon_url and not re.search(r'\.(png|jpg|jpeg|gif|ico|webp)(\?.*)?$', icon_url):
                ext_urls = [f"{icon_url}.png", icon_url]
            else:
                ext_urls = [icon_url]

            # Download the icon — try each variant
            for try_url in ext_urls:
                try:
                    icon_resp = await client.get(try_url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
                    if icon_resp.status_code != 200 or len(icon_resp.content) == 0:
                        continue
                    content_type = icon_resp.headers.get("content-type", "")
                    if "html" in content_type.lower():
                        continue
                    if "xml" in content_type.lower() or "svg" in content_type.lower():
                        continue  # skip SVG entirely — can contain <script> tags

                    ext_map = {"image/png": ".png", "image/jpeg": ".jpeg", "image/gif": ".gif", "image/webp": ".webp", "image/x-icon": ".ico"}
                    ext = ext_map.get(content_type.split(";")[0].strip(), ".png")

                    filename = _save_image_bytes(icon_resp.content, f"favicon{ext}")
                    return filename
                except Exception:
                    continue
    except Exception:
        pass
    return None


@app.post("/api/fetch-icon", response_model=FetchIconResponse)
async def fetch_icon(request: FetchIconRequest):
    if not request.url or not request.url.strip():
        return FetchIconResponse(icon_path=None)

    icon_path = await _fetch_favicon(request.url)
    return FetchIconResponse(icon_path=icon_path)


# ==================== Cards ====================

def _row_to_card(row) -> CardResponse:
    return CardResponse(
        id=row["id"],
        title=row["title"],
        url=row["url"],
        icon_path=row["icon_path"],
        size=row["size"],
        position=row["position"],
        grid_col=row["grid_col"] if row["grid_col"] is not None else 1,
        grid_row=row["grid_row"] if row["grid_row"] is not None else 1,
    )


@app.get("/api/cards", response_model=List[CardResponse])
def get_cards():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cards ORDER BY grid_row, grid_col")
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_card(row) for row in rows]


def _auto_place_cursor(cursor, col_want: int, row_want: int, cols_per_row: int = 10) -> tuple[int, int]:
    """Find an unoccupied cell starting at (col_want, row_want), scanning forward.

    Fetches all occupied cells in a single query, then scans in memory.
    """
    cursor.execute("SELECT grid_col, grid_row FROM cards")
    occupied = {(row["grid_col"], row["grid_row"]) for row in cursor.fetchall()}

    col, row = col_want, row_want
    for _ in range(5000):  # safety cap
        if (col, row) not in occupied:
            return col, row
        col += 1
        if col > cols_per_row:
            col = 1
            row += 1
    return 1, 1


@app.post("/api/cards", response_model=CardResponse, status_code=201)
def create_card(card_create: CardCreate):
    conn = get_db_connection()
    cursor = conn.cursor()

    safe_url = _validate_url_field(card_create.url)
    safe_icon = _validate_icon_path(card_create.icon_path) if card_create.icon_path else None

    # Auto-place: if requested position is occupied, find nearest free cell
    col, row = card_create.grid_col, card_create.grid_row
    col, row = _auto_place_cursor(cursor, col, row)

    # Compute linear position from grid coordinates
    new_position = (row - 1) * 10 + (col - 1)

    cursor.execute(
        "INSERT INTO cards (title, url, icon_path, size, position, grid_col, grid_row) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (card_create.title, safe_url, safe_icon, card_create.size, new_position, col, row)
    )
    conn.commit()
    card_id = cursor.lastrowid
    conn.close()

    return CardResponse(
        id=card_id,
        title=card_create.title,
        url=safe_url,
        icon_path=safe_icon,
        size=card_create.size,
        position=new_position,
        grid_col=col,
        grid_row=row,
    )


@app.put("/api/cards/{card_id}", response_model=CardResponse)
def update_card(card_id: int, card_update: CardUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
    card = cursor.fetchone()

    if not card:
        conn.close()
        raise HTTPException(status_code=404, detail="Card not found")

    updates = []
    values = []

    if card_update.title is not None:
        updates.append("title = ?")
        values.append(card_update.title)

    if card_update.url is not None:
        safe_url = _validate_url_field(card_update.url)
        updates.append("url = ?")
        values.append(safe_url)

    if card_update.icon_path is not None:
        safe_icon = _validate_icon_path(card_update.icon_path)
        # Delete old icon file if replacing
        old_icon = card["icon_path"]
        if old_icon and old_icon != safe_icon:
            old_path = os.path.join(UPLOADS_DIR, old_icon)
            if os.path.exists(old_path):
                os.remove(old_path)
        updates.append("icon_path = ?")
        values.append(safe_icon)

    if card_update.size is not None:
        updates.append("size = ?")
        values.append(card_update.size)

    if card_update.position is not None:
        updates.append("position = ?")
        values.append(card_update.position)

    if card_update.grid_col is not None:
        updates.append("grid_col = ?")
        values.append(card_update.grid_col)

    if card_update.grid_row is not None:
        updates.append("grid_row = ?")
        values.append(card_update.grid_row)

    if updates:
        values.append(card_id)
        cursor.execute(f"UPDATE cards SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()

    cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
    updated = cursor.fetchone()
    conn.close()

    return _row_to_card(updated)


@app.delete("/api/cards/{card_id}")
def delete_card(card_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT icon_path FROM cards WHERE id = ?", (card_id,))
    card = cursor.fetchone()
    if not card:
        conn.close()
        raise HTTPException(status_code=404, detail="Card not found")

    # Delete icon file only if no other card references it
    if card["icon_path"]:
        cursor.execute("SELECT COUNT(*) as cnt FROM cards WHERE icon_path = ? AND id != ?", (card["icon_path"], card_id))
        if cursor.fetchone()["cnt"] == 0:
            icon_path = os.path.join(UPLOADS_DIR, card["icon_path"])
            if os.path.exists(icon_path):
                os.remove(icon_path)

    cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    conn.commit()
    conn.close()

    return {"message": "Card deleted successfully"}


@app.post("/api/cards/reorder")
def reorder_cards(request: CardsReorderRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Validate all card IDs exist first
    cursor.execute("SELECT id FROM cards WHERE id IN ({})".format(",".join("?" * len(request.card_ids))), request.card_ids)
    existing = {row["id"] for row in cursor.fetchall()}
    missing = set(request.card_ids) - existing
    if missing:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Cards not found: {missing}")

    # Update positions and reset grid coordinates to match new order
    for position, card_id in enumerate(request.card_ids):
        col = (position % 10) + 1
        row = (position // 10) + 1
        cursor.execute("UPDATE cards SET position = ?, grid_col = ?, grid_row = ? WHERE id = ?", (position, col, row, card_id))

    conn.commit()
    conn.close()
    return {"message": "Cards reordered successfully"}


# ==================== Full Data ====================

@app.get("/api/full-data", response_model=FullDataResponse)
def get_full_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM settings LIMIT 1")
    settings_row = cursor.fetchone()

    if not settings_row:
        cursor.execute("INSERT INTO settings (blur_radius, dark_mode) VALUES (0, 0)")
        conn.commit()
        cursor.execute("SELECT * FROM settings LIMIT 1")
        settings_row = cursor.fetchone()

    # Sanitise: if background_image references a missing file, clear it
    bg = settings_row["background_image"]
    if bg and not os.path.exists(os.path.join(UPLOADS_DIR, bg)):
        cursor.execute("UPDATE settings SET background_image = NULL WHERE id = ?", (settings_row["id"],))
        conn.commit()
        cursor.execute("SELECT * FROM settings WHERE id = ?", (settings_row["id"],))
        settings_row = cursor.fetchone()

    settings = SettingsResponse(
        id=settings_row["id"],
        background_image=settings_row["background_image"],
        blur_radius=settings_row["blur_radius"],
        dark_mode=bool(settings_row["dark_mode"])
    )

    cursor.execute("SELECT * FROM cards ORDER BY grid_row, grid_col")
    card_rows = cursor.fetchall()
    conn.close()

    cards = [_row_to_card(row) for row in card_rows]

    return FullDataResponse(settings=settings, cards=cards)


# ==================== Health ====================

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
