"""Cards API routes."""
import os
from fastapi import APIRouter, HTTPException

from database import get_db_connection
from schemas import CardCreate, CardUpdate, CardResponse, CardsReorderRequest
from services import (
    UPLOADS_DIR,
    validate_url_field,
    validate_icon_path,
    row_to_card,
)

router = APIRouter(prefix="/api/cards", tags=["cards"])

# Number of columns used for auto-placement and position computation.
# Kept in sync with the frontend's default desktop column count.
COLS_PER_ROW = 7


@router.get("", response_model=list[CardResponse])
async def get_cards():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards ORDER BY grid_row, grid_col")
        rows = cursor.fetchall()
        return [row_to_card(row) for row in rows]
    finally:
        conn.close()


def _auto_place_cursor(cursor, col_want: int, row_want: int) -> tuple[int, int]:
    """Find an unoccupied cell starting at (col_want, row_want), scanning forward."""
    cursor.execute("SELECT grid_col, grid_row FROM cards")
    occupied = {(row["grid_col"], row["grid_row"]) for row in cursor.fetchall()}

    col, row = col_want, row_want
    for _ in range(5000):  # safety cap
        if (col, row) not in occupied:
            return col, row
        col += 1
        if col > COLS_PER_ROW:
            col = 1
            row += 1
    return 1, 1


@router.post("", response_model=CardResponse, status_code=201)
async def create_card(card_create: CardCreate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        safe_url = validate_url_field(card_create.url)
        safe_icon = validate_icon_path(card_create.icon_path) if card_create.icon_path else None

        # Auto-place: if requested position is occupied, find nearest free cell
        col, row = card_create.grid_col, card_create.grid_row
        col, row = _auto_place_cursor(cursor, col, row)

        # Compute linear position from grid coordinates
        new_position = (row - 1) * COLS_PER_ROW + (col - 1)

        cursor.execute(
            "INSERT INTO cards (title, url, icon_path, size, position, grid_col, grid_row) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (card_create.title, safe_url, safe_icon, card_create.size, new_position, col, row)
        )
        conn.commit()
        card_id = cursor.lastrowid

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
    finally:
        conn.close()


@router.put("/{card_id}", response_model=CardResponse)
async def update_card(card_id: int, card_update: CardUpdate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        card = cursor.fetchone()

        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        updates = []
        values = []

        if card_update.title is not None:
            updates.append("title = ?")
            values.append(card_update.title)

        if card_update.url is not None:
            safe_url = validate_url_field(card_update.url)
            updates.append("url = ?")
            values.append(safe_url)

        if card_update.icon_path is not None:
            safe_icon = validate_icon_path(card_update.icon_path)
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
        return row_to_card(updated)
    finally:
        conn.close()


@router.delete("/{card_id}")
async def delete_card(card_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT icon_path FROM cards WHERE id = ?", (card_id,))
        card = cursor.fetchone()
        if not card:
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

        return {"message": "Card deleted successfully"}
    finally:
        conn.close()


@router.post("/reorder")
async def reorder_cards(request: CardsReorderRequest):
    if not request.card_ids:
        raise HTTPException(status_code=400, detail="No card IDs provided")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Validate all card IDs exist first
        placeholders = ",".join(["?"] * len(request.card_ids))
        cursor.execute(f"SELECT id FROM cards WHERE id IN ({placeholders})", request.card_ids)
        existing = {row["id"] for row in cursor.fetchall()}
        missing = set(request.card_ids) - existing
        if missing:
            raise HTTPException(status_code=400, detail=f"Cards not found: {missing}")

        # Update positions and reset grid coordinates to match new order
        for position, card_id in enumerate(request.card_ids):
            col = (position % COLS_PER_ROW) + 1
            row = (position // COLS_PER_ROW) + 1
            cursor.execute("UPDATE cards SET position = ?, grid_col = ?, grid_row = ? WHERE id = ?", (position, col, row, card_id))

        conn.commit()
        return {"message": "Cards reordered successfully"}
    finally:
        conn.close()
