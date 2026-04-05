"""Database configuration using sqlite3."""
import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "homepage.db")


def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables and migrate if needed."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Check if old columns exist and migrate
    cursor.execute("PRAGMA table_info(settings)")
    settings_columns = {row[1] for row in cursor.fetchall()}

    if "background_data" in settings_columns and "background_image" not in settings_columns:
        cursor.execute("ALTER TABLE settings ADD COLUMN background_image TEXT")
        cursor.execute("UPDATE settings SET background_image = NULL")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            background_image TEXT,
            blur_radius INTEGER DEFAULT 0,
            dark_mode INTEGER DEFAULT 0
        )
    """)

    cursor.execute("PRAGMA table_info(cards)")
    cards_columns = {row[1] for row in cursor.fetchall()}

    if len(cards_columns) == 0:
        # Cards table doesn't exist yet
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT,
                icon_path TEXT,
                size TEXT DEFAULT '1x1',
                position INTEGER DEFAULT 0,
                grid_col INTEGER DEFAULT 1,
                grid_row INTEGER DEFAULT 1
            )
        """)
    else:
        # Migrate icon_data -> icon_path if needed
        if "icon_data" in cards_columns and "icon_path" not in cards_columns:
            cursor.execute("ALTER TABLE cards ADD COLUMN icon_path TEXT")
            cursor.execute("UPDATE cards SET icon_path = NULL")

        # Remove tab_id if present (add grid columns at the same time)
        if "tab_id" in cards_columns:
            cursor.execute("""
                CREATE TABLE cards_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT,
                    icon_path TEXT,
                    size TEXT DEFAULT '1x1',
                    position INTEGER DEFAULT 0,
                    grid_col INTEGER DEFAULT 1,
                    grid_row INTEGER DEFAULT 1
                )
            """)
            cursor.execute("INSERT INTO cards_new (id, title, url, icon_path, size, position) SELECT id, title, url, icon_path, size, position FROM cards")
            cursor.execute("DROP TABLE cards")
            cursor.execute("ALTER TABLE cards_new RENAME TO cards")
        elif "grid_col" not in cards_columns or "grid_row" not in cards_columns:
            # Add grid columns
            if "grid_col" not in cards_columns:
                cursor.execute("ALTER TABLE cards ADD COLUMN grid_col INTEGER DEFAULT 1")
            if "grid_row" not in cards_columns:
                cursor.execute("ALTER TABLE cards ADD COLUMN grid_row INTEGER DEFAULT 1")

    # Insert default settings if not exists
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO settings (blur_radius, dark_mode) VALUES (0, 0)")

    conn.commit()
    conn.close()
