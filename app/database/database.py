
"""Database initialization and connection utilities."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATABASE_DIR / "warehouse_monitor.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def initialize_database():
    """Create the database and apply the SQL schema."""

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema not found: {SCHEMA_PATH}")

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            SCHEMA_PATH.read_text(encoding="utf-8")
        )

    print(f"Database initialized: {DATABASE_PATH}")


@contextmanager
def get_connection():
    """Provide a database connection with foreign keys enabled."""

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_table_names():
    """Return all application tables."""

    with get_connection() as connection:
        rows = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

    return [row["name"] for row in rows]


if __name__ == "__main__":
    initialize_database()

    print("\nCreated database tables:")

    for table in get_table_names():
        print(f" - {table}")
