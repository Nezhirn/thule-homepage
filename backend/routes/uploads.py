"""File upload API routes."""
import os
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from services import UPLOADS_DIR, validate_file, read_file_with_limit, save_image_bytes

router = APIRouter(prefix="/api", tags=["uploads"])


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    validate_file(file)
    content = await read_file_with_limit(file)
    filename = save_image_bytes(content, file.filename)
    return {
        "filename": filename,
        "url": f"/api/uploads/{filename}"
    }


@router.get("/uploads/{filename}")
async def serve_uploaded_file(filename: str):
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)


@router.delete("/upload/{filename}")
async def delete_uploaded_file(filename: str):
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    os.remove(filepath)
    return {"message": "File deleted successfully"}
