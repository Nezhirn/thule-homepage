"""Full data and import API routes."""
import logging
import sqlite3

from fastapi import APIRouter, HTTPException

from database import get_db_connection
from schemas import (
    FullDataResponse,
    ImportData,
    MessageResponse,
    SettingsResponse,
)
from services import (
    apply_settings_patch,
    delete_upload_file,
    fetch_settings_row,
    position_for,
    row_to_card,
    sanitise_background_image,
    upload_file_is_referenced,
    validate_icon_path,
    validate_url_field,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data"])


@router.get("/api/full-data", response_model=FullDataResponse)
def get_full_data():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        row = fetch_settings_row(cursor)
        row, changed = sanitise_background_image(conn, row)
        if changed:
            conn.commit()

        settings = SettingsResponse(
            id=row["id"],
            background_image=row["background_image"],
            blur_radius=row["blur_radius"] if row["blur_radius"] is not None else 0,
            dark_mode=bool(row["dark_mode"]),
        )

        cursor.execute("SELECT * FROM cards ORDER BY grid_row, grid_col")
        cards = [row_to_card(card_row) for card_row in cursor.fetchall()]
        return FullDataResponse(settings=settings, cards=cards)
    finally:
        conn.close()


# ==================== Transactional Import ====================

@router.post("/api/import", response_model=MessageResponse)
def import_data(data: ImportData):
    """Replace settings and cards from an exported backup.

    All validation and database writes happen before any file is touched: the
    database transaction is committed first, then only genuinely orphaned
    upload files are removed. A failure at any point leaves both stores
    consistent with the previous state.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Validate everything up front so invalid input never mutates state.
        prepared = []
        new_icons: set[str] = set()
        for card in data.cards:
            safe_url = validate_url_field(card.url)
            safe_icon = validate_icon_path(card.icon_path)
            if safe_icon:
                new_icons.add(safe_icon)
            prepared.append((card, safe_url, safe_icon))

        stale_files: set[str] = set()
        try:
            cursor.execute("SELECT icon_path FROM cards")
            old_icons = {row["icon_path"] for row in cursor.fetchall() if row["icon_path"]}

            if data.settings is not None:
                settings_row = fetch_settings_row(cursor)
                stale_files.update(apply_settings_patch(cursor, settings_row, data.settings))

            cursor.execute("DELETE FROM cards")
            for card, safe_url, safe_icon in prepared:
                cursor.execute(
                    "INSERT INTO cards (title, url, icon_path, size, position, grid_col, grid_row, open_in_new_tab)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        card.title,
                        safe_url,
                        safe_icon,
                        card.size,
                        position_for(card.grid_col, card.grid_row),
                        card.grid_col,
                        card.grid_row,
                        int(card.open_in_new_tab),
                    ),
                )
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except sqlite3.Error:
            conn.rollback()
            logger.exception("Import failed; transaction rolled back")
            raise HTTPException(status_code=500, detail="Import failed, transaction rolled back") from None

        # Point of no return passed — remove files that nothing references
        # anymore (a replaced background may still be a card icon, etc.).
        candidates = (old_icons - new_icons) | stale_files
        for filename in candidates:
            if not upload_file_is_referenced(cursor, filename):
                delete_upload_file(filename)

        return MessageResponse(message="Import successful")
    finally:
        conn.close()
