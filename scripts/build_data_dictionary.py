
import csv
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse_monitor.db"
OUTPUT_DIR = ROOT / "docs" / "phase10"

EXCLUDED_TABLES = {
    "sqlite_sequence"
}


def get_table_names(connection):
    rows = connection.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

    return rows


def get_foreign_keys(connection, table):
    return connection.execute(
        f'PRAGMA foreign_key_list("{table}")'
    ).fetchall()


def get_indexes(connection, table):
    indexes = connection.execute(
        f'PRAGMA index_list("{table}")'
    ).fetchall()

    result = []

    for index in indexes:
        name = index[1]
        unique = bool(index[2])

        columns = connection.execute(
            f'PRAGMA index_info("{name}")'
        ).fetchall()

        result.append({
            "name": name,
            "unique": unique,
            "columns": [column[2] for column in columns]
        })

    return result


def get_columns(connection, table):
    rows = connection.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()

    foreign_keys = get_foreign_keys(connection, table)

    fk_map = {
        fk[3]: {
            "referenced_table": fk[2],
            "referenced_column": fk[4]
        }
        for fk in foreign_keys
    }

    columns = []

    for row in rows:
        column_name = row[1]

        columns.append({
            "name": column_name,
            "data_type": row[2],
            "not_null": bool(row[3]),
            "default_value": row[4],
            "primary_key_position": row[5],
            "foreign_key": fk_map.get(column_name)
        })

    return columns


def build_dictionary():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)

    try:
        tables = get_table_names(connection)

        dictionary = {
            "project": "Warehouse Risk Monitoring System",
            "database": "warehouse_monitor.db",
            "generated_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "tables": []
        }

        csv_rows = []

        for table_name, create_sql in tables:
            if table_name in EXCLUDED_TABLES:
                continue

            columns = get_columns(connection, table_name)
            foreign_keys = get_foreign_keys(
                connection, table_name
            )
            indexes = get_indexes(connection, table_name)

            table_info = {
                "table_name": table_name,
                "description": (
                    "Description requires business confirmation."
                ),
                "columns": columns,
                "foreign_keys": [
                    {
                        "column": fk[3],
                        "referenced_table": fk[2],
                        "referenced_column": fk[4],
                        "on_update": fk[5],
                        "on_delete": fk[6]
                    }
                    for fk in foreign_keys
                ],
                "indexes": indexes,
                "table_constraints_sql": create_sql
            }

            dictionary["tables"].append(table_info)

            for column in columns:
                csv_rows.append({
                    "table_name": table_name,
                    "column_name": column["name"],
                    "data_type": column["data_type"],
                    "required": column["not_null"],
                    "default_value": column["default_value"],
                    "primary_key_position":
                        column["primary_key_position"],
                    "foreign_key_table":
                        (column["foreign_key"] or {}).get(
                            "referenced_table", ""
                        ),
                    "foreign_key_column":
                        (column["foreign_key"] or {}).get(
                            "referenced_column", ""
                        )
                })

        json_path = OUTPUT_DIR / "data_dictionary.json"

        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(dictionary, file, indent=2)

        csv_path = OUTPUT_DIR / "data_dictionary.csv"

        with open(
            csv_path, "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=csv_rows[0].keys()
            )
            writer.writeheader()
            writer.writerows(csv_rows)

        markdown_path = OUTPUT_DIR / "data_dictionary.md"

        with open(
            markdown_path, "w", encoding="utf-8"
        ) as file:
            file.write(
                "# Warehouse Risk Monitoring System\n"
                "# Data Dictionary\n\n"
            )

            file.write(
                "This document is generated from the actual "
                "SQLite database schema.\n\n"
            )

            file.write(
                f"Tables documented: {len(dictionary['tables'])}\n\n"
            )

            for table in dictionary["tables"]:
                file.write(f"## {table['table_name']}\n\n")
                file.write(
                    "| Column | Type | Required | Primary Key | "
                    "Foreign Key |\n"
                )
                file.write(
                    "|---|---|---|---|---|\n"
                )

                for column in table["columns"]:
                    fk = column["foreign_key"]

                    fk_text = (
                        f"{fk['referenced_table']}."
                        f"{fk['referenced_column']}"
                        if fk else "-"
                    )

                    file.write(
                        f"| {column['name']} "
                        f"| {column['data_type']} "
                        f"| {'Yes' if column['not_null'] else 'No'} "
                        f"| {column['primary_key_position'] or '-'} "
                        f"| {fk_text} |\n"
                    )

                file.write("\n### Indexes\n\n")

                if table["indexes"]:
                    for index in table["indexes"]:
                        file.write(
                            f"- `{index['name']}`: "
                            f"{', '.join(index['columns'])}; "
                            f"unique={index['unique']}\n"
                        )
                else:
                    file.write("No explicit indexes.\n")

                file.write("\n### Validation constraints\n\n")
                sql = table["table_constraints_sql"] or ""

                checks = re.findall(
                    r"CHECK\s*\(.*?\)",
                    sql,
                    flags=re.IGNORECASE | re.DOTALL
                )

                if checks:
                    for check in checks:
                        file.write(f"- `{check}`\n")
                else:
                    file.write(
                        "No CHECK constraints detected.\n"
                    )

                file.write("\n")

        print("DATA DICTIONARY GENERATION COMPLETE")
        print("Tables documented:", len(dictionary["tables"]))
        print("Columns documented:", len(csv_rows))
        print("JSON:", json_path.relative_to(ROOT))
        print("CSV:", csv_path.relative_to(ROOT))
        print("Markdown:", markdown_path.relative_to(ROOT))

    finally:
        connection.close()


if __name__ == "__main__":
    build_dictionary()
