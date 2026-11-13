import sqlite3
import pytest
from app.database.database import SCHEMA_PATH


@pytest.fixture
def test_db(tmp_path):
    """Create an isolated SQLite database using the project's real schema."""
    db_path = tmp_path / "test_warehouse.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield conn
    conn.close()
