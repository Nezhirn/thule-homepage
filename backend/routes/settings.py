"""Settings API routes."""
from fastapi import APIRouter, HTTPException

from database import get_db_connection
from schemas import SettingsResponse, SettingsUpdate
from services import (
    apply_settings_patch,
    delete_upload_file,
    fetch_settings_row,
    sanitise_background_image,
    upload_file_is_referenced,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _to_response(row) -> SettingsResponse:
    return SettingsResponse(
        id=row["id"],
        background_image=row["background_image"],
        blur_radius=row["blur_radius"] if row["blur_radius"] is not None else 0,
        dark_mode=bool(row["dark_mode"]),
    )


@router.get("", response_model=SettingsResponse)
def get_settings():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        row = fetch_settings_row(cursor)
        row, _changed = sanitise_background_image(conn, row)
        conn.commit()
        return _to_response(row)
    finally:
        conn.close()


@router.put("", response_model=SettingsResponse)
def update_settings(settings_update: SettingsUpdate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        row = fetch_settings_row(cursor)

        stale_files = apply_settings_patch(cursor, row, settings_update)
        conn.commit()

        # Files are removed only after the database transaction is durable and
        # only when nothing else references them (e.g. the same file as a card icon).
        for filename in stale_files:
            if not upload_file_is_referenced(cursor, filename):
                delete_upload_file(filename)

        cursor.execute("SELECT * FROM settings WHERE id = 1")
        updated = cursor.fetchone()
        if updated is None:
            raise HTTPException(status_code=404, detail="Settings not found")
        return _to_response(updated)
    finally:
        conn.close()
