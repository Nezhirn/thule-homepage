"""Settings API routes."""
import os
from fastapi import APIRouter, HTTPException

from database import get_db_connection
from schemas import SettingsUpdate, SettingsResponse
from services import UPLOADS_DIR, ensure_default_settings, sanitise_background_image

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM settings LIMIT 1")
        row = cursor.fetchone()

        if not row:
            ensure_default_settings(conn)
            cursor.execute("SELECT * FROM settings LIMIT 1")
            row = cursor.fetchone()

        # Sanitise: if background_image references a missing file, clear it
        row = sanitise_background_image(conn, row)

        return SettingsResponse(
            id=row["id"],
            background_image=row["background_image"],
            blur_radius=row["blur_radius"],
            dark_mode=bool(row["dark_mode"])
        )
    finally:
        conn.close()


@router.put("", response_model=SettingsResponse)
async def update_settings(settings_update: SettingsUpdate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM settings LIMIT 1")
        row = cursor.fetchone()

        if not row:
            ensure_default_settings(conn)
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

        return SettingsResponse(
            id=updated["id"],
            background_image=updated["background_image"],
            blur_radius=updated["blur_radius"],
            dark_mode=bool(updated["dark_mode"])
        )
    finally:
        conn.close()
