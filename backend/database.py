"""Database configuration and schema migrations using sqlite3."""
import logging
import os
import sqlite3

import config

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

def _cards_table_sql(table: str = "cards") -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT,
            icon_path TEXT,
            size TEXT DEFAULT '1x1',
            position INTEGER DEFAULT 0,
            grid_col INTEGER DEFAULT 1,
            grid_row INTEGER DEFAULT 1,
            open_in_new_tab INTEGER DEFAULT 1
        )
    """

SETTINGS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        background_image TEXT,
        blur_radius INTEGER DEFAULT 0,
        dark_mode INTEGER DEFAULT 0
    )
"""


def get_db_connection() -> sqlite3.Connection:
    """Open a connection configured for concurrent reads and safe writes.

    WAL + a generous busy timeout keep the app correct when several requests
    (or worker processes) touch the database at the same time.
    """
    os.makedirs(config.database_dir(), exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables and apply migrations atomically.

    All DDL runs inside an explicit transaction (SQLite DDL is transactional),
    so an interrupted migration is rolled back on the next open instead of
    leaving a half-migrated schema behind.
    """
    os.makedirs(config.database_dir(), exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("BEGIN IMMEDIATE")
        try:
            _migrate(conn)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    finally:
        conn.close()


def _table_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,))
    return cursor.fetchone() is not None


def _recover_interrupted_rebuild(cursor: sqlite3.Cursor) -> None:
    """Recover a database left behind by the old non-transactional cards rebuild.

    The previous implementation ran ``CREATE TABLE cards_new`` ... ``DROP TABLE
    cards`` ... ``RENAME`` in autocommit. A crash after DROP could leave the
    migrated rows only in ``cards_new`` — restore them instead of discarding.
    """
    if not _table_exists(cursor, "cards_new"):
        return
    if _table_exists(cursor, "cards"):
        logger.warning("Dropping leftover cards_new table from an interrupted migration")
        cursor.execute("DROP TABLE cards_new")
    else:
        logger.warning("Recovering cards table from interrupted migration (cards_new)")
        cursor.execute("ALTER TABLE cards_new RENAME TO cards")


def _migrate(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    _recover_interrupted_rebuild(cursor)

    # --- settings ---
    settings_columns = _table_columns(cursor, "settings")
    if "background_data" in settings_columns and "background_image" not in settings_columns:
        cursor.execute("ALTER TABLE settings ADD COLUMN background_image TEXT")
        cursor.execute("UPDATE settings SET background_image = NULL")
    cursor.execute(SETTINGS_TABLE_SQL)

    # Enforce the singleton invariant: exactly one settings row, id = 1.
    settings_ids = [row[0] for row in cursor.execute("SELECT id FROM settings ORDER BY id")]
    if not settings_ids:
        cursor.execute("INSERT INTO settings (id, blur_radius, dark_mode) VALUES (1, 0, 0)")
    else:
        keep = settings_ids[0]
        cursor.execute("DELETE FROM settings WHERE id != ?", (keep,))
        if keep != 1:
            cursor.execute("UPDATE settings SET id = 1 WHERE id = ?", (keep,))

    # --- cards ---
    cards_columns = _table_columns(cursor, "cards")
    if not cards_columns:
        cursor.execute(_cards_table_sql())
    else:
        if "icon_data" in cards_columns and "icon_path" not in cards_columns:
            cursor.execute("ALTER TABLE cards ADD COLUMN icon_path TEXT")
            cursor.execute("UPDATE cards SET icon_path = NULL")

        if "tab_id" in cards_columns:
            _recover_interrupted_rebuild(cursor)
            cursor.execute(_cards_table_sql("cards_new"))
            cursor.execute(
                "INSERT INTO cards_new (id, title, url, icon_path, size, position)"
                " SELECT id, title, url, icon_path, size, position FROM cards"
            )
            cursor.execute("DROP TABLE cards")
            cursor.execute("ALTER TABLE cards_new RENAME TO cards")
        else:
            if "grid_col" not in cards_columns:
                cursor.execute("ALTER TABLE cards ADD COLUMN grid_col INTEGER DEFAULT 1")
            if "grid_row" not in cards_columns:
                cursor.execute("ALTER TABLE cards ADD COLUMN grid_row INTEGER DEFAULT 1")

        cards_columns = _table_columns(cursor, "cards")
        if "open_in_new_tab" not in cards_columns:
            cursor.execute("ALTER TABLE cards ADD COLUMN open_in_new_tab INTEGER DEFAULT 1")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_grid ON cards (grid_row, grid_col)")
