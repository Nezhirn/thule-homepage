"""Full data and import API routes."""
import os
from typing import Optional
from fastapi import APIRouter, HTTPException

from database import get_db_connection
from schemas import (
    FullDataResponse, SettingsResponse, CardResponse,
    ImportData, SettingsUpdate, CardCreate,
)
from services import (
    UPLOADS_DIR, ensure_default_settings, sanitise_background_image,
    validate_url_field, validate_icon_path, row_to_card,
)

router = APIRouter(tags=["data"])


@router.get("/api/full-data", response_model=FullDataResponse)
async def get_full_data():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM settings LIMIT 1")
        settings_row = cursor.fetchone()

        if not settings_row:
            ensure_default_settings(conn)
            cursor.execute("SELECT * FROM settings LIMIT 1")
            settings_row = cursor.fetchone()

        # Sanitise: if background_image references a missing file, clear it
        settings_row = sanitise_background_image(conn, settings_row)

        settings = SettingsResponse(
            id=settings_row["id"],
            background_image=settings_row["background_image"],
            blur_radius=settings_row["blur_radius"],
            dark_mode=bool(settings_row["dark_mode"])
        )

        cursor.execute("SELECT * FROM cards ORDER BY grid_row, grid_col")
        card_rows = cursor.fetchall()
        cards = [row_to_card(row) for row in card_rows]

        return FullDataResponse(settings=settings, cards=cards)
    finally:
        conn.close()


# ==================== Transactional Import ====================

@router.post("/api/import")
async def import_data(data: ImportData):
    """Transactional import of settings and cards.

    All operations run in a single database transaction.
    If anything fails, the transaction is rolled back and no data is lost.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # 1. Update settings if provided
        if data.settings is not None:
            cursor.execute("SELECT * FROM settings LIMIT 1")
            row = cursor.fetchone()
            if not row:
                ensure_default_settings(conn)
                cursor.execute("SELECT * FROM settings LIMIT 1")
                row = cursor.fetchone()

            updates = []
            values = []

            if data.settings.background_image is not None:
                # Delete old background file
                old_bg = row["background_image"]
                if old_bg and old_bg != data.settings.background_image:
                    old_path = os.path.join(UPLOADS_DIR, old_bg)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                updates.append("background_image = ?")
                values.append(data.settings.background_image)
            elif data.settings.background_image is None and row["background_image"]:
                old_bg = row["background_image"]
                old_path = os.path.join(UPLOADS_DIR, old_bg)
                if os.path.exists(old_path):
                    os.remove(old_path)
                updates.append("background_image = ?")
                values.append(None)

            if data.settings.blur_radius is not None:
                updates.append("blur_radius = ?")
                values.append(data.settings.blur_radius)

            if data.settings.dark_mode is not None:
                updates.append("dark_mode = ?")
                values.append(int(data.settings.dark_mode))

            if updates:
                values.append(row["id"])
                cursor.execute(f"UPDATE settings SET {', '.join(updates)} WHERE id = ?", values)

        # 2. Delete all existing cards
        cursor.execute("SELECT icon_path FROM cards")
        for card_row in cursor.fetchall():
            # Delete orphaned icon files
            if card_row["icon_path"]:
                icon_path = os.path.join(UPLOADS_DIR, card_row["icon_path"])
                if os.path.exists(icon_path):
                    os.remove(icon_path)

        cursor.execute("DELETE FROM cards")

        # 3. Insert new cards
        for card in data.cards:
            safe_url = validate_url_field(card.url)
            safe_icon = validate_icon_path(card.icon_path) if card.icon_path else None
            col = card.grid_col
            row_num = card.grid_row
            position = (row_num - 1) * 7 + (col - 1)  # COLS_PER_ROW = 7

            cursor.execute(
                "INSERT INTO cards (title, url, icon_path, size, position, grid_col, grid_row) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (card.title, safe_url, safe_icon, card.size, position, col, row_num)
            )

        conn.commit()
        return {"message": "Import successful"}
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Import failed, transaction rolled back")
    finally:
        conn.close()
