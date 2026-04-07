"""Business logic services for the Homepage API."""
import os
import re
import uuid
import socket
import ipaddress
from typing import Optional
from urllib.parse import urlparse, urljoin

import httpx
from fastapi import HTTPException, UploadFile

from database import get_db_connection
from schemas import CardResponse

# Config
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", os.path.join(os.path.dirname(__file__), "uploads"))
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}


# ==================== Database helpers ====================

def ensure_default_settings(conn):
    """Ensure a default settings row exists. Called once from lifespan."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO settings (blur_radius, dark_mode) VALUES (0, 0)")
        conn.commit()


def sanitise_background_image(conn, settings_row):
    """If background_image references a missing file, clear it. Returns (possibly updated) row."""
    bg = settings_row["background_image"]
    if bg and not os.path.exists(os.path.join(UPLOADS_DIR, bg)):
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET background_image = NULL WHERE id = ?", (settings_row["id"],))
        conn.commit()
        cursor.execute("SELECT * FROM settings WHERE id = ?", (settings_row["id"],))
        return cursor.fetchone()
    return settings_row


# ==================== Validation ====================

def validate_url_field(url: Optional[str]) -> Optional[str]:
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


def validate_icon_path(icon_path: str) -> str:
    """Validate icon_path. Accepts either a full URL (http/https) or a safe local filename.
    Rejects path traversal in local filenames. Returns the original value if valid."""
    if not icon_path:
        return icon_path
    parsed = urlparse(icon_path)
    if parsed.scheme in ("http", "https"):
        return icon_path
    if ".." in icon_path or "/" in icon_path or "\\" in icon_path:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return icon_path


def validate_file(file: UploadFile):
    """Validate uploaded file type."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file.content_type}' not allowed. Allowed: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )


async def read_file_with_limit(file: UploadFile, max_size: int = MAX_FILE_SIZE) -> bytes:
    """Read file content with size limit."""
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {max_size // (1024 * 1024)} MB"
        )
    return content


def save_image_bytes(data: bytes, original_filename: Optional[str] = None) -> str:
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


# ==================== SSRF Protection ====================

def is_private_ip(hostname: str) -> bool:
    """Check if hostname resolves to a private/internal IP (SSRF protection)."""
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


# ==================== Favicon Fetch ====================

async def fetch_favicon(page_url: str) -> Optional[str]:
    """Fetch favicon from a URL and save it to uploads. Returns icon_path or None.

    Security: Rejects private/internal URLs (SSRF), skips SVG (XSS via <script>).
    """
    try:
        parsed = urlparse(page_url)
        if not parsed.scheme:
            page_url = "https://" + page_url
            parsed = urlparse(page_url)

        # SSRF protection: reject private/internal URLs
        if is_private_ip(parsed.hostname or ""):
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

                    filename = save_image_bytes(icon_resp.content, f"favicon{ext}")
                    return filename
                except Exception:
                    continue
    except Exception:
        pass
    return None


# ==================== Card helpers ====================

def row_to_card(row) -> CardResponse:
    """Convert a database row to a CardResponse."""
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
