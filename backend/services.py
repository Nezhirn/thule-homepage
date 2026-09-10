"""Business logic services for the Homepage API."""
import asyncio
import ipaddress
import logging
import os
import re
import socket
import uuid
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException, UploadFile

import config
from schemas import CardResponse, SettingsUpdate

logger = logging.getLogger(__name__)

ALLOWED_LINK_SCHEMES = {"http", "https", "mailto"}
ALLOWED_ICON_SCHEMES = {"http", "https"}
ALLOWED_UPLOAD_EXTENSIONS = {".jpeg", ".png", ".gif", ".webp"}
ALLOWED_SERVE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".gif", ".webp", ".ico"}

# All C0 control characters plus DEL. Browsers strip tab/newline/CR when
# parsing URLs (e.g. "java\tscript:"), so strip them before validating.
_CONTROL_CHARS = dict.fromkeys([*range(0x21), 0x7F])
_LOCAL_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

_IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpeg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"\x00\x00\x01\x00", ".ico"),
)


# ==================== Database helpers ====================

def ensure_default_settings(conn) -> None:
    """Ensure the singleton settings row exists. Transaction managed by caller."""
    conn.execute("INSERT OR IGNORE INTO settings (id, blur_radius, dark_mode) VALUES (1, 0, 0)")


def fetch_settings_row(cursor):
    """Return the singleton settings row (id = 1), creating it when missing."""
    cursor.execute("SELECT * FROM settings WHERE id = 1")
    row = cursor.fetchone()
    if row is None:
        ensure_default_settings(cursor.connection)
        cursor.execute("SELECT * FROM settings WHERE id = 1")
        row = cursor.fetchone()
    return row


def apply_settings_patch(cursor, row, patch: SettingsUpdate) -> list[str]:
    """Apply a partial settings update. Returns filenames to delete after commit.

    Uses ``model_fields_set`` so that an omitted field is left untouched while
    an explicit ``null`` clears it — the distinction Pydantic preserves but
    ``field is None`` does not.
    """
    provided = patch.model_fields_set
    updates: list[str] = []
    values: list = []
    stale_files: list[str] = []

    if "background_image" in provided:
        new_bg = validate_background_image(patch.background_image)
        old_bg = row["background_image"]
        if old_bg and old_bg != new_bg:
            stale_files.append(old_bg)
        updates.append("background_image = ?")
        values.append(new_bg)

    if "blur_radius" in provided:
        updates.append("blur_radius = ?")
        values.append(patch.blur_radius if patch.blur_radius is not None else 0)

    if "dark_mode" in provided:
        updates.append("dark_mode = ?")
        values.append(int(bool(patch.dark_mode)))

    if updates:
        values.append(1)
        # Fragments are fixed column assignments built above, values are bound.
        cursor.execute(f"UPDATE settings SET {', '.join(updates)} WHERE id = ?", values)  # noqa: S608

    return stale_files


def sanitise_background_image(conn, settings_row):
    """Clear background_image when the referenced file is gone or unsafe.

    Returns ``(row, changed)``; the caller owns the transaction.
    """
    background = settings_row["background_image"]
    if not background:
        return settings_row, False
    try:
        path = safe_upload_path(background)
        exists = os.path.isfile(path)
    except HTTPException:
        exists = False
    if exists:
        return settings_row, False

    conn.execute("UPDATE settings SET background_image = NULL WHERE id = ?", (settings_row["id"],))
    values = dict(settings_row)
    values["background_image"] = None
    return values, True


# ==================== Validation ====================

def validate_url_field(url: Optional[str]) -> Optional[str]:
    """Allowlist URL schemes after removing characters browsers ignore."""
    if url is None:
        return None
    url = url.strip().translate(_CONTROL_CHARS)
    if not url:
        return None
    if len(url) > config.MAX_URL_LENGTH:
        raise HTTPException(status_code=400, detail="URL is too long")
    scheme = urlparse(url).scheme.lower()
    if scheme and scheme not in ALLOWED_LINK_SCHEMES:
        raise HTTPException(status_code=400, detail="Invalid URL scheme")
    return url


def validate_icon_path(icon_path: Optional[str]) -> Optional[str]:
    """Accept an http(s) URL or a safe local filename, reject everything else."""
    if icon_path is None:
        return None
    icon_path = icon_path.strip()
    if not icon_path:
        return None
    if len(icon_path) > config.MAX_URL_LENGTH:
        raise HTTPException(status_code=400, detail="Icon path is too long")
    parsed = urlparse(icon_path)
    if parsed.scheme:
        if parsed.scheme.lower() not in ALLOWED_ICON_SCHEMES:
            raise HTTPException(status_code=400, detail="Invalid icon URL scheme")
        return icon_path
    return _validate_local_filename(icon_path, "Invalid filename")


def validate_background_image(background: Optional[str]) -> Optional[str]:
    """Background images may only reference a local upload filename."""
    if background is None:
        return None
    background = background.strip()
    if not background:
        return None
    return _validate_local_filename(background, "Invalid background image")


def _validate_local_filename(name: str, message: str) -> str:
    if not name or "\x00" in name or ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail=message)
    if not _LOCAL_FILENAME_RE.match(name):
        raise HTTPException(status_code=400, detail=message)
    return name


# ==================== Path safety ====================

def safe_upload_path(name: str) -> str:
    """Resolve a stored filename into a path guaranteed to live in UPLOADS_DIR.

    Absolute paths, traversal segments and symlinks escaping the uploads
    directory are rejected. This is the single allowed way to build a path
    from a database value.
    """
    if not name or "\x00" in name or "\\" in name or ".." in name or os.path.isabs(name):
        raise HTTPException(status_code=400, detail="Invalid filename")
    base = os.path.realpath(config.UPLOADS_DIR)
    candidate = os.path.join(base, name)
    if os.path.islink(candidate):
        raise HTTPException(status_code=400, detail="Invalid filename")
    resolved = os.path.realpath(candidate)
    try:
        inside = os.path.commonpath([base, resolved]) == base
    except ValueError:
        inside = False
    if not inside:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return resolved


def delete_upload_file(filename: Optional[str]) -> None:
    """Delete a stored upload, ignoring a missing file and logging other errors."""
    if not filename:
        return
    try:
        path = safe_upload_path(filename)
    except HTTPException:
        logger.warning("refusing to delete unsafe upload path %r", filename)
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning("failed to delete upload %s", path, exc_info=True)


def upload_file_is_referenced(cursor, filename: str) -> bool:
    """True when any card icon or the background image still references filename."""
    cursor.execute("SELECT 1 FROM cards WHERE icon_path = ? LIMIT 1", (filename,))
    if cursor.fetchone() is not None:
        return True
    cursor.execute("SELECT 1 FROM settings WHERE background_image = ? LIMIT 1", (filename,))
    return cursor.fetchone() is not None


# ==================== Uploads ====================

def detect_image_ext(data: bytes, allow_ico: bool = False) -> Optional[str]:
    """Detect an image type from magic bytes. Returns extension or None."""
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    for signature, ext in _IMAGE_SIGNATURES:
        if ext == ".ico" and not allow_ico:
            continue
        if data.startswith(signature):
            return ext
    return None


async def read_file_with_limit(file: UploadFile, max_size: int = config.MAX_FILE_SIZE) -> bytes:
    """Read an upload in chunks, aborting as soon as the limit is exceeded."""
    buffer = bytearray()
    while chunk := await file.read(64 * 1024):
        buffer.extend(chunk)
        if len(buffer) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {max_size // (1024 * 1024)} MB",
            )
    return bytes(buffer)


def save_image_bytes(data: bytes, ext: str) -> str:
    """Atomically store image bytes under a UUID name. Returns the filename."""
    filename = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(config.UPLOADS_DIR, exist_ok=True)
    filepath = os.path.join(config.UPLOADS_DIR, filename)
    tmp_path = f"{filepath}.tmp"
    with open(tmp_path, "wb") as handle:
        handle.write(data)
    os.replace(tmp_path, filepath)
    return filename


# ==================== SSRF Protection ====================

def _is_public_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


def assert_public_http_url(url: str) -> None:
    """Fail-closed validation of an http(s) URL before any outbound request.

    Every address the host resolves to must be globally routable; DNS errors
    are treated as rejections.
    """
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_ICON_SCHEMES or not parsed.hostname:
        raise ValueError("unsupported scheme or missing host")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError) as exc:
        raise ValueError("cannot resolve host") from exc
    if not infos:
        raise ValueError("cannot resolve host")
    for info in infos:
        if not _is_public_ip(info[4][0]):
            raise ValueError("host resolves to a non-public address")


def is_private_ip(hostname: str) -> bool:
    """True when a host is unsafe to fetch (fail-closed on resolution errors)."""
    if not hostname:
        return True
    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError):
        return True
    if not infos:
        return True
    return not all(_is_public_ip(info[4][0]) for info in infos)


# ==================== Favicon Fetch ====================

_ICON_PATTERNS = (
    r'<link[^>]+rel=["\'](?:shortcut icon|icon|apple-touch-icon)["\'][^>]+href=["\']([^"\']+)["\']',
    r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\'](?:shortcut icon|icon|apple-touch-icon)["\']',
)
_OG_IMAGE_PATTERNS = (
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
)


def _extract_icon_url(html: str, page_url: str) -> Optional[str]:
    for pattern in _ICON_PATTERNS:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return urljoin(page_url, match.group(1))
    for pattern in _OG_IMAGE_PATTERNS:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return urljoin(page_url, match.group(1))
    return None


def _icon_variants(icon_url: str) -> list[str]:
    if re.search(r"\.(png|jpg|jpeg|gif|ico|webp)(\?.*)?$", icon_url, re.IGNORECASE):
        return [icon_url]
    return [f"{icon_url}.png", icon_url]


async def _fetch_limited(
    client: httpx.AsyncClient,
    url: str,
    max_bytes: int,
    headers: dict,
    max_redirects: int = config.FETCH_MAX_REDIRECTS,
) -> Optional[bytes]:
    """GET a URL, following redirects manually, validating every hop and
    enforcing a hard response-size limit."""
    current = url
    for _ in range(max_redirects + 1):
        await asyncio.to_thread(assert_public_http_url, current)
        async with client.stream("GET", current, headers=headers) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    return None
                current = urljoin(current, location)
                continue
            if response.status_code != 200:
                return None
            content_length = response.headers.get("content-length", "")
            if content_length.isdigit() and int(content_length) > max_bytes:
                return None
            buffer = bytearray()
            async for chunk in response.aiter_bytes():
                buffer.extend(chunk)
                if len(buffer) > max_bytes:
                    return None
            return bytes(buffer)
    return None


async def fetch_favicon(page_url: str, client: Optional[httpx.AsyncClient] = None) -> Optional[str]:
    """Fetch a favicon for a page and store it. Returns the stored filename.

    Redirects are validated hop-by-hop and oversized bodies are dropped.
    """
    page_url = (page_url or "").strip()
    if not page_url:
        return None
    if "://" not in page_url:
        page_url = "https://" + page_url
    try:
        assert_public_http_url(page_url)
    except ValueError as exc:
        logger.info("Rejected favicon fetch for %s: %s", page_url, exc)
        return None

    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(config.FETCH_TIMEOUT, connect=config.FETCH_CONNECT_TIMEOUT),
        )
    try:
        candidates: list[str] = []
        page = await _fetch_limited(client, page_url, config.MAX_PAGE_BYTES, headers)
        if page:
            icon_url = _extract_icon_url(page.decode("utf-8", errors="replace"), page_url)
            if icon_url:
                candidates.append(icon_url)
        candidates.append(urljoin(page_url, "/favicon.ico"))

        for candidate in candidates:
            for variant in _icon_variants(candidate):
                try:
                    data = await _fetch_limited(client, variant, config.MAX_ICON_BYTES, headers, max_redirects=1)
                except (httpx.HTTPError, OSError, ValueError) as exc:
                    logger.info("Icon candidate failed %s: %s", variant, exc)
                    continue
                if not data:
                    continue
                ext = detect_image_ext(data, allow_ico=True)
                if not ext:
                    logger.info("Skipping icon %s: unrecognised image format", variant)
                    continue
                return save_image_bytes(data, ext)
    except (httpx.HTTPError, OSError, ValueError) as exc:
        logger.warning("Favicon fetch failed for %s: %s", page_url, exc)
    finally:
        if owns_client:
            await client.aclose()
    return None


# ==================== Card helpers ====================

def size_to_wh(size: Optional[str]) -> tuple[int, int]:
    try:
        width, height = (size or "1x1").split("x")
        return max(1, int(width)), max(1, int(height))
    except (ValueError, AttributeError):
        return 1, 1


def position_for(col: int, row: int) -> int:
    """Linear position mirroring grid coordinates (row-major)."""
    return (row - 1) * config.COLS_PER_ROW + (col - 1)


def row_to_card(row) -> CardResponse:
    """Convert a database row to a CardResponse."""
    try:
        new_tab = row["open_in_new_tab"]
    except (IndexError, KeyError):
        new_tab = None
    return CardResponse(
        id=row["id"],
        title=row["title"],
        url=row["url"],
        icon_path=row["icon_path"],
        size=row["size"],
        position=row["position"] if row["position"] is not None else 0,
        grid_col=row["grid_col"] if row["grid_col"] is not None else 1,
        grid_row=row["grid_row"] if row["grid_row"] is not None else 1,
        open_in_new_tab=bool(new_tab) if new_tab is not None else True,
    )
