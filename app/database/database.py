"""Database initialization and Vercel-aware database loading."""

import gzip
import os
import shutil
import sqlite3
import tempfile

from pathlib import Path
from contextlib import closing, contextmanager

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / "data"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _valid_database(path):
    """Check database integrity and always close the SQLite connection."""

    if not path.is_file():
        return False

    try:
        connection = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro",
            uri=True,
            timeout=30
        )

        try:
            result = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()

            return result is not None and result[0] == "ok"
        finally:
            connection.close()

    except (sqlite3.Error, OSError):
        return False


def _prepare_vercel_database():
    """Extract the packaged database into the writable runtime directory."""

    archive = DATABASE_DIR / "warehouse_monitor.db.gz"

    if not archive.is_file():
        raise FileNotFoundError(
            f"Deployment database archive is missing: {archive}"
        )

    runtime_dir = Path(tempfile.gettempdir()) / "warehouse-risk-monitor"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    destination = runtime_dir / "warehouse_monitor.db"

    if _valid_database(destination):
        return destination

    temporary_path = None

    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix="warehouse_",
            suffix=".tmp",
            dir=str(runtime_dir)
        )

        temporary_path = Path(temporary_name)
        os.close(file_descriptor)

        with gzip.open(archive, "rb") as source:
            with temporary_path.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)

        if not _valid_database(temporary_path):
            raise RuntimeError(
                "Extracted deployment database failed SQLite integrity check."
            )

        # Replace an invalid old copy only after the new copy is validated.
        if destination.exists():
            destination.unlink()

        os.replace(temporary_path, destination)
        temporary_path = None

        if not _valid_database(destination):
            raise RuntimeError(
                "Final runtime database failed SQLite integrity check."
            )

        return destination

    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass


def _resolve_database_path():
    """Resolve the local, configured, or Vercel database path."""

    override = os.getenv("WAREHOUSE_DATABASE_PATH")

    if override:
        return Path(override)

    if os.getenv("VERCEL"):
        return _prepare_vercel_database()

    return DATABASE_DIR / "warehouse_monitor.db"


DATABASE_PATH = _resolve_database_path()


def initialize_database():
    """Create the database and apply the SQL schema."""

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema not found: {SCHEMA_PATH}")

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            SCHEMA_PATH.read_text(encoding="utf-8")
        )
        connection.commit()

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
