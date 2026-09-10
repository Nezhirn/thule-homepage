"""File upload API routes."""
import os

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from database import get_db_connection
from schemas import UploadResponse
from services import (
    ALLOWED_SERVE_EXTENSIONS,
    delete_upload_file,
    detect_image_ext,
    read_file_with_limit,
    safe_upload_path,
    save_image_bytes,
    upload_file_is_referenced,
)

router = APIRouter(prefix="/api", tags=["uploads"])

_MEDIA_TYPES = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
}


@router.post("/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    content = await read_file_with_limit(file)
    ext = detect_image_ext(content)
    if ext is None:
        raise HTTPException(status_code=400, detail="Unsupported image format")
    filename = save_image_bytes(content, ext)
    return UploadResponse(filename=filename, url=f"/api/uploads/{filename}")


@router.get("/uploads/{filename}")
def serve_uploaded_file(filename: str):
    extension = os.path.splitext(filename)[1].lower()
    if extension not in ALLOWED_SERVE_EXTENSIONS:
        raise HTTPException(status_code=404, detail="File not found")

    filepath = safe_upload_path(filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    # Uploaded files have unique UUID names and never change content,
    # so they can be cached aggressively (1 year, immutable).
    return FileResponse(
        filepath,
        media_type=_MEDIA_TYPES.get(extension),
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.delete("/upload/{filename}", status_code=204)
def delete_uploaded_file(filename: str):
    extension = os.path.splitext(filename)[1].lower()
    if extension not in ALLOWED_SERVE_EXTENSIONS:
        raise HTTPException(status_code=404, detail="File not found")

    filepath = safe_upload_path(filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if upload_file_is_referenced(cursor, filename):
            raise HTTPException(status_code=409, detail="File is still referenced")
    finally:
        conn.close()

    delete_upload_file(filename)
    return Response(status_code=204)
