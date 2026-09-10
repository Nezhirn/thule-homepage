"""Database migration invariants: idempotence, data preservation, recovery."""
import sqlite3

import database


def _connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_init_creates_schema_and_singleton(data_paths):
    database.init_db()

    conn = _connect(data_paths["db"])
    try:
        settings = conn.execute("SELECT * FROM settings").fetchall()
        assert len(settings) == 1
        assert settings[0]["id"] == 1
        assert settings[0]["blur_radius"] == 0

        card_columns = _table_columns(conn, "cards")
        assert {"title", "url", "icon_path", "size", "grid_col", "grid_row", "open_in_new_tab"} <= card_columns
        assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
        index_names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_cards_grid" in index_names
    finally:
        conn.close()


def test_init_is_idempotent(data_paths):
    database.init_db()
    conn = _connect(data_paths["db"])
    conn.execute("INSERT INTO cards (title) VALUES ('kept')")
    conn.commit()
    conn.close()

    database.init_db()

    conn = _connect(data_paths["db"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 1
    finally:
        conn.close()


def _create_legacy_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            background_data TEXT,
            blur_radius INTEGER DEFAULT 0,
            dark_mode INTEGER DEFAULT 0
        );
        INSERT INTO settings (background_data, blur_radius) VALUES ('legacy', 7);

        CREATE TABLE cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT,
            icon_data TEXT,
            size TEXT DEFAULT '1x1',
            position INTEGER DEFAULT 0,
            tab_id INTEGER
        );
        INSERT INTO cards (title, url, icon_data, tab_id) VALUES ('one', 'https://example.com', 'raw', 3);
        INSERT INTO cards (title, url, icon_data, tab_id) VALUES ('two', NULL, NULL, 3);
        """
    )
    conn.commit()
    conn.close()


def test_legacy_migration_preserves_rows(data_paths):
    _create_legacy_db(data_paths["db"])

    database.init_db()

    conn = _connect(data_paths["db"])
    try:
        settings_columns = _table_columns(conn, "settings")
        assert "background_image" in settings_columns

        cards = conn.execute("SELECT * FROM cards ORDER BY id").fetchall()
        assert [row["title"] for row in cards] == ["one", "two"]
        card_columns = _table_columns(conn, "cards")
        assert "tab_id" not in card_columns
        assert "icon_path" in card_columns
        assert "open_in_new_tab" in card_columns

        # Second run must not fail or lose data.
        conn.close()
        database.init_db()
        conn = _connect(data_paths["db"])
        assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 2
    finally:
        conn.close()


def test_recovers_interrupted_rebuild_when_cards_missing(data_paths):
    data_paths["db"].parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(data_paths["db"]))
    conn.executescript(
        """
        CREATE TABLE settings (id INTEGER PRIMARY KEY, blur_radius INTEGER DEFAULT 0, dark_mode INTEGER DEFAULT 0);
        INSERT INTO settings (id) VALUES (1);
        CREATE TABLE cards_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT,
            icon_path TEXT,
            size TEXT DEFAULT '1x1',
            position INTEGER DEFAULT 0,
            grid_col INTEGER DEFAULT 1,
            grid_row INTEGER DEFAULT 1,
            open_in_new_tab INTEGER DEFAULT 1
        );
        INSERT INTO cards_new (title) VALUES ('survivor');
        """
    )
    conn.commit()
    conn.close()

    database.init_db()

    conn = _connect(data_paths["db"])
    try:
        titles = [row["title"] for row in conn.execute("SELECT title FROM cards")]
        assert titles == ["survivor"]
    finally:
        conn.close()


def test_drops_leftover_cards_new_when_cards_exists(data_paths):
    database.init_db()
    conn = sqlite3.connect(str(data_paths["db"]))
    conn.execute("CREATE TABLE cards_new (id INTEGER PRIMARY KEY, title TEXT)")
    conn.execute("INSERT INTO cards_new (id, title) VALUES (1, 'stale')")
    conn.commit()
    conn.close()

    database.init_db()

    conn = _connect(data_paths["db"])
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "cards_new" not in tables
        assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 0
    finally:
        conn.close()


def test_settings_singleton_is_normalised(data_paths):
    data_paths["db"].parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(data_paths["db"]))
    conn.executescript(
        """
        CREATE TABLE settings (id INTEGER PRIMARY KEY AUTOINCREMENT, background_image TEXT,
                               blur_radius INTEGER DEFAULT 0, dark_mode INTEGER DEFAULT 0);
        INSERT INTO settings (id, blur_radius) VALUES (2, 5);
        INSERT INTO settings (id, blur_radius) VALUES (3, 9);
        """
    )
    conn.commit()
    conn.close()

    database.init_db()

    conn = _connect(data_paths["db"])
    try:
        rows = conn.execute("SELECT * FROM settings").fetchall()
        assert len(rows) == 1
        assert rows[0]["id"] == 1
        assert rows[0]["blur_radius"] == 5
    finally:
        conn.close()
