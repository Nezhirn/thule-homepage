"""Cards API routes."""
from fastapi import APIRouter, HTTPException, Response

import config
from database import get_db_connection
from schemas import (
    CardCreate,
    CardResponse,
    CardsReorderRequest,
    CardUpdate,
    MessageResponse,
)
from services import (
    delete_upload_file,
    position_for,
    row_to_card,
    size_to_wh,
    upload_file_is_referenced,
    validate_icon_path,
    validate_url_field,
)

router = APIRouter(prefix="/api/cards", tags=["cards"])


def _occupied_cells(cursor, exclude_id: int | None = None) -> set[tuple[int, int]]:
    """All grid cells covered by existing cards, honouring card sizes."""
    occupied: set[tuple[int, int]] = set()
    cursor.execute("SELECT id, grid_col, grid_row, size FROM cards")
    for row in cursor.fetchall():
        if exclude_id is not None and row["id"] == exclude_id:
            continue
        width, height = size_to_wh(row["size"])
        col = row["grid_col"] or 1
        grid_row = row["grid_row"] or 1
        for cell_col in range(col, col + width):
            for cell_row in range(grid_row, grid_row + height):
                occupied.add((cell_col, cell_row))
    return occupied


def _auto_place_cursor(cursor, col_want: int, row_want: int, width: int = 1, height: int = 1) -> tuple[int, int]:
    """Find a free area for a width x height card, scanning forward row-major."""
    occupied = _occupied_cells(cursor)
    col, row = col_want, row_want
    for _ in range(5000):  # safety cap
        cells = [
            (cell_col, cell_row)
            for cell_col in range(col, col + width)
            for cell_row in range(row, row + height)
        ]
        fits = col + width - 1 <= config.COLS_PER_ROW and not any(cell in occupied for cell in cells)
        if fits:
            return col, row
        col += 1
        if col + width - 1 > config.COLS_PER_ROW:
            col = 1
            row += 1
    return 1, 1


@router.get("", response_model=list[CardResponse])
def get_cards():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards ORDER BY grid_row, grid_col")
        return [row_to_card(row) for row in cursor.fetchall()]
    finally:
        conn.close()


@router.post("", response_model=CardResponse, status_code=201)
def create_card(card_create: CardCreate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        safe_url = validate_url_field(card_create.url)
        safe_icon = validate_icon_path(card_create.icon_path)

        width, height = size_to_wh(card_create.size)
        col, row = _auto_place_cursor(cursor, card_create.grid_col, card_create.grid_row, width, height)
        new_position = position_for(col, row)

        with conn:
            cursor.execute(
                "INSERT INTO cards (title, url, icon_path, size, position, grid_col, grid_row, open_in_new_tab)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    card_create.title,
                    safe_url,
                    safe_icon,
                    card_create.size,
                    new_position,
                    col,
                    row,
                    int(card_create.open_in_new_tab),
                ),
            )
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
            open_in_new_tab=card_create.open_in_new_tab,
        )
    finally:
        conn.close()


@router.put("/{card_id}", response_model=CardResponse)
def update_card(card_id: int, card_update: CardUpdate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        card = cursor.fetchone()
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        provided = card_update.model_fields_set
        updates: list[str] = []
        values: list = []
        old_icon_to_maybe_delete: str | None = None

        if "title" in provided:
            updates.append("title = ?")
            values.append(card_update.title)

        if "url" in provided:
            updates.append("url = ?")
            values.append(validate_url_field(card_update.url))

        if "icon_path" in provided:
            safe_icon = validate_icon_path(card_update.icon_path)
            old_icon = card["icon_path"]
            if old_icon and old_icon != safe_icon:
                old_icon_to_maybe_delete = old_icon
            updates.append("icon_path = ?")
            values.append(safe_icon)

        if "size" in provided:
            updates.append("size = ?")
            values.append(card_update.size)

        provided_col = card_update.grid_col if "grid_col" in provided else card["grid_col"]
        provided_row = card_update.grid_row if "grid_row" in provided else card["grid_row"]

        if "position" in provided:
            updates.append("position = ?")
            values.append(card_update.position)
        elif "grid_col" in provided or "grid_row" in provided:
            updates.append("position = ?")
            values.append(position_for(provided_col or 1, provided_row or 1))

        if "grid_col" in provided:
            updates.append("grid_col = ?")
            values.append(provided_col)

        if "grid_row" in provided:
            updates.append("grid_row = ?")
            values.append(provided_row)

        if "open_in_new_tab" in provided:
            updates.append("open_in_new_tab = ?")
            values.append(int(card_update.open_in_new_tab))

        if updates:
            values.append(card_id)
            # Fragments are fixed column assignments built above, values are bound.
            with conn:
                cursor.execute(f"UPDATE cards SET {', '.join(updates)} WHERE id = ?", values)  # noqa: S608

        if old_icon_to_maybe_delete and not upload_file_is_referenced(cursor, old_icon_to_maybe_delete):
            delete_upload_file(old_icon_to_maybe_delete)

        cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        updated = cursor.fetchone()
        if updated is None:
            raise HTTPException(status_code=404, detail="Card not found")
        return row_to_card(updated)
    finally:
        conn.close()


@router.delete("/{card_id}", status_code=204)
def delete_card(card_id: int):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT icon_path FROM cards WHERE id = ?", (card_id,))
        card = cursor.fetchone()
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        with conn:
            cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))

        icon = card["icon_path"]
        if icon and not upload_file_is_referenced(cursor, icon):
            delete_upload_file(icon)
        return Response(status_code=204)
    finally:
        conn.close()


@router.post("/reorder", response_model=MessageResponse)
def reorder_cards(request: CardsReorderRequest):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        if len(set(request.card_ids)) != len(request.card_ids):
            raise HTTPException(status_code=400, detail="Duplicate card IDs are not allowed")

        cursor.execute("SELECT id FROM cards", ())
        all_ids = {row["id"] for row in cursor.fetchall()}
        requested = set(request.card_ids)

        missing = requested - all_ids
        if missing:
            raise HTTPException(status_code=400, detail=f"Cards not found: {sorted(missing)}")
        unlisted = all_ids - requested
        if unlisted:
            raise HTTPException(status_code=400, detail=f"Card IDs missing from reorder request: {sorted(unlisted)}")

        with conn:
            for position, card_id in enumerate(request.card_ids):
                col = (position % config.COLS_PER_ROW) + 1
                row = (position // config.COLS_PER_ROW) + 1
                cursor.execute(
                    "UPDATE cards SET position = ?, grid_col = ?, grid_row = ? WHERE id = ?",
                    (position, col, row, card_id),
                )

        return MessageResponse(message="Cards reordered successfully")
    finally:
        conn.close()
