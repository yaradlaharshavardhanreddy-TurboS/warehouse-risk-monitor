
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse_monitor.db"
DICTIONARY_PATH = ROOT / "docs" / "phase10" / "data_dictionary.json"


def main():
    print("========== PHASE 10 SCHEMA VALIDATION ==========")

    connection = sqlite3.connect(DB_PATH)

    try:
        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        foreign_keys = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        with open(DICTIONARY_PATH, encoding="utf-8") as file:
            dictionary = json.load(file)

        actual_tables = {
            row[0]
            for row in connection.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
            """)
        }

        documented_tables = {
            table["table_name"]
            for table in dictionary["tables"]
        }

        actual_columns = {
            table: {
                row[1]
                for row in connection.execute(
                    f'PRAGMA table_info("{table}")'
                )
            }
            for table in actual_tables
        }

        documented_columns = {
            table["table_name"]: {
                column["name"]
                for column in table["columns"]
            }
            for table in dictionary["tables"]
        }

        missing_tables = actual_tables - documented_tables
        extra_tables = documented_tables - actual_tables

        missing_columns = []
        extra_columns = []

        for table in actual_tables & documented_tables:
            missing_columns.extend(
                (table, col)
                for col in actual_columns[table]
                - documented_columns[table]
            )
            extra_columns.extend(
                (table, col)
                for col in documented_columns[table]
                - actual_columns[table]
            )

        checks = {
            "Database integrity": integrity == "ok",
            "Foreign key integrity": len(foreign_keys) == 0,
            "All tables documented": len(missing_tables) == 0,
            "No unknown tables": len(extra_tables) == 0,
            "All columns documented": len(missing_columns) == 0,
            "No unknown columns": len(extra_columns) == 0
        }

        for name, passed in checks.items():
            print(f"{'PASS' if passed else 'FAIL'}: {name}")

        print("\nActual tables:", len(actual_tables))
        print("Documented tables:", len(documented_tables))
        print("Documented columns:", sum(
            len(columns) for columns in documented_columns.values()
        ))

        if missing_tables:
            print("Missing tables:", sorted(missing_tables))

        if missing_columns:
            print("Missing columns:", missing_columns)

        if not all(checks.values()):
            raise SystemExit("PHASE 10 VALIDATION FAILED")

        print("\nPHASE 10 SCHEMA VALIDATION PASSED")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
