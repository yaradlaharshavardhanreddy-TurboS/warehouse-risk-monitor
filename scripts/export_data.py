from __future__ import annotations

import csv
import hashlib
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "warehouse_monitor.db"
EXPORT_DIR = ROOT / "data" / "exports"
GROUND_TRUTH = ROOT / "docs" / "phase10" / "ground_truth.csv"


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_table(conn: sqlite3.Connection, table: str) -> tuple[int, int]:
    output = EXPORT_DIR / f"{table}.csv"
    temp_output = output.with_suffix(".csv.tmp")

    quoted_table = quote_identifier(table)

    cursor = conn.execute(f"SELECT * FROM {quoted_table}")
    headers = [column[0] for column in cursor.description]

    exported_rows = 0
    with temp_output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)

        while True:
            rows = cursor.fetchmany(5000)
            if not rows:
                break
            writer.writerows(rows)
            exported_rows += len(rows)

    temp_output.replace(output)

    database_rows = conn.execute(
        f"SELECT COUNT(*) FROM {quoted_table}"
    ).fetchone()[0]

    # Independently count CSV data records, excluding the header.
    with output.open("r", encoding="utf-8-sig", newline="") as file:
        csv_rows = sum(1 for _ in csv.reader(file)) - 1

    if exported_rows != database_rows or csv_rows != database_rows:
        raise RuntimeError(
            f"Count mismatch for {table}: "
            f"database={database_rows}, "
            f"written={exported_rows}, CSV={csv_rows}"
        )

    return database_rows, csv_rows


def main() -> None:
    if not DB.is_file():
        raise FileNotFoundError(f"Database not found: {DB}")

    if not GROUND_TRUTH.is_file():
        raise FileNotFoundError(f"Ground truth file not found: {GROUND_TRUTH}")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Open the database strictly read-only.
    db_uri = DB.as_uri() + "?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)

    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Database integrity check failed: {integrity}")

        tables = [
            row[0]
            for row in conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
        ]

        if not tables:
            raise RuntimeError("No database tables found.")

        print("========== CSV TABLE EXPORTS ==========")
        print(f"Database: {DB}")
        print(f"Export directory: {EXPORT_DIR}")
        print(f"Tables found: {len(tables)}")
        print()

        results = []
        for table in tables:
            database_rows, csv_rows = export_table(conn, table)
            results.append((table, database_rows, csv_rows))
            print(
                f"{table}: database={database_rows}, "
                f"CSV={csv_rows} "
                f"{'PASS' if database_rows == csv_rows else 'FAIL'}"
            )

        # Copy the source ground truth without parsing or rewriting it.
        ground_truth_output = EXPORT_DIR / GROUND_TRUTH.name
        source_hash = sha256(GROUND_TRUTH)
        shutil.copyfile(GROUND_TRUTH, ground_truth_output)

        copied_hash = sha256(ground_truth_output)
        if source_hash != copied_hash:
            raise RuntimeError("Ground truth copy does not match source bytes.")

        source_size = GROUND_TRUTH.stat().st_size
        copied_size = ground_truth_output.stat().st_size

        if source_size != copied_size:
            raise RuntimeError("Ground truth file size mismatch.")

        # Count records for reporting only; the copied file remains untouched.
        with ground_truth_output.open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:
            ground_truth_rows = sum(1 for _ in csv.reader(file)) - 1

        print()
        print("========== GROUND TRUTH COPY ==========")
        print(f"Source: {GROUND_TRUTH}")
        print(f"Copy: {ground_truth_output}")
        print(f"Data rows: {ground_truth_rows}")
        print(f"Bytes: {copied_size}")
        print(f"SHA-256 identical: {source_hash == copied_hash}")

        failures = [
            table for table, db_count, csv_count in results
            if db_count != csv_count
        ]

        print()
        print("========== EXPORT SUMMARY ==========")
        print(f"Tables exported: {len(results)}")
        print(f"Total database rows: {sum(r[1] for r in results)}")
        print(f"Total CSV data rows: {sum(r[2] for r in results)}")
        print(f"Count mismatches: {len(failures)}")
        print(f"Ground truth unchanged: {source_hash == copied_hash}")
        print("Database opened read-only; no database writes performed.")

        if failures:
            raise RuntimeError(f"Export count mismatches: {failures}")

        print("RESULT: ALL TABLE EXPORT COUNTS MATCH.")

    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"EXPORT FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
