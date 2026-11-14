import csv
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse_monitor.db"
OUTPUT_DIR = ROOT / "docs" / "phase10"

# These values are explicitly enforced by the current SQLite schema.
CHECK_VALUES = {
    ("alarm_history", "from_state"): [
        "OPEN", "ACKNOWLEDGED", "RESOLVED", "CLOSED"
    ],
    ("alarm_history", "to_state"): [
        "OPEN", "ACKNOWLEDGED", "RESOLVED", "CLOSED"
    ],
    ("remediations", "remediation_type"): [
        "ADJUST_TEMPERATURE",
        "ADJUST_HUMIDITY",
        "REPAIR_SENSOR",
        "CLOSE_DOOR",
        "REPAIR_DOOR",
        "RELOCATE_INVENTORY",
        "QUARANTINE_INVENTORY",
        "RECALIBRATE_SENSOR",
        "OTHER",
    ],
    ("remediations", "remediation_status"): [
        "PLANNED", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELLED"
    ],
}

# Units and explanatory rules not expressible as SQLite column types.
FIELD_NOTES = {
    ("alarm_history", "history_id"): {
        "units": "identifier (integer)",
        "validation_rule": "Generated INTEGER PRIMARY KEY AUTOINCREMENT; unique row identifier.",
    },
    ("alarm_history", "alarm_id"): {
        "validation_rule": "Required; foreign key to alarms.alarm_id.",
    },
    ("alarm_history", "from_state"): {
        "validation_rule": "Optional; when present must be one of the four CHECK-enforced alarm states.",
    },
    ("alarm_history", "to_state"): {
        "validation_rule": "Required; CHECK-enforced alarm lifecycle state.",
    },
    ("alarm_history", "changed_at"): {
        "units": "timestamp (TEXT)",
        "validation_rule": "Required timestamp text; SQLite does not enforce a timestamp format.",
    },
    ("alarm_history", "reason"): {
        "validation_rule": "Required explanatory text.",
    },
    ("alarm_history", "severity"): {
        "allowed_values_note": "Observed values only; no CHECK constraint on this column.",
        "validation_rule": "Required text; no column-level CHECK constraint in this table.",
    },
    ("alarm_history", "age_minutes"): {
        "units": "minutes",
        "validation_rule": "Required REAL value; no CHECK constraint in this table.",
    },
    ("alarm_history", "rule_version"): {
        "validation_rule": "Required rule/version identifier text.",
    },

    ("inspection_history", "inspection_history_id"): {
        "validation_rule": "Required TEXT PRIMARY KEY; unique identifier.",
    },
    ("inspection_history", "inspection_id"): {
        "validation_rule": "Required; foreign key to inspections.inspection_id.",
    },
    ("inspection_history", "from_status"): {
        "allowed_values_note": "Observed values only; no status CHECK constraint on this table.",
        "validation_rule": "Optional status text; no SQLite CHECK constraint.",
    },
    ("inspection_history", "to_status"): {
        "allowed_values_note": "Observed values only; no status CHECK constraint on this table.",
        "validation_rule": "Required status text; no SQLite CHECK constraint.",
    },
    ("inspection_history", "changed_at"): {
        "units": "timestamp (TEXT)",
        "validation_rule": "Required timestamp text; SQLite does not enforce a timestamp format.",
    },
    ("inspection_history", "reason"): {
        "validation_rule": "Required explanatory text.",
    },
    ("inspection_history", "rule_version"): {
        "validation_rule": "Required rule/version identifier text.",
    },

    ("remediation_history", "history_id"): {
        "validation_rule": "Required TEXT PRIMARY KEY; unique identifier.",
    },
    ("remediation_history", "remediation_id"): {
        "validation_rule": "Required; foreign key to remediations.remediation_id.",
    },
    ("remediation_history", "from_status"): {
        "allowed_values_note": "Observed values only; no status CHECK constraint on this table.",
        "validation_rule": "Optional status text; no SQLite CHECK constraint.",
    },
    ("remediation_history", "to_status"): {
        "allowed_values_note": "Observed values only; no status CHECK constraint on this table.",
        "validation_rule": "Required status text; no SQLite CHECK constraint.",
    },
    ("remediation_history", "changed_at"): {
        "units": "timestamp (TEXT)",
        "validation_rule": "Required timestamp text; SQLite does not enforce a timestamp format.",
    },
    ("remediation_history", "reason"): {
        "validation_rule": "Required explanatory text.",
    },
    ("remediation_history", "rule_version"): {
        "validation_rule": "Required rule/version identifier text.",
    },

    ("remediation_lots", "remediation_id"): {
        "validation_rule": "Required; first component of composite primary key and foreign key to remediations.remediation_id.",
    },
    ("remediation_lots", "lot_id"): {
        "validation_rule": "Required; second component of composite primary key and foreign key to inventory_lots.lot_id.",
    },
    ("remediation_lots", "linked_at"): {
        "units": "timestamp (TEXT)",
        "validation_rule": "Required timestamp text; SQLite does not enforce a timestamp format.",
    },
    ("remediations", "remediation_type"): {
        "validation_rule": "Required; value must match one of the nine values in the SQLite CHECK constraint.",
    },
}

OBSERVED_COLUMNS = {
    ("alarm_history", "severity"),
    ("inspection_history", "from_status"),
    ("inspection_history", "to_status"),
    ("remediation_history", "from_status"),
    ("remediation_history", "to_status"),
}

def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'

def get_table_names(connection):
    return connection.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

def get_foreign_keys(connection, table):
    return connection.execute(
        f"PRAGMA foreign_key_list({quote_identifier(table)})"
    ).fetchall()

def get_indexes(connection, table):
    rows = connection.execute(
        f"PRAGMA index_list({quote_identifier(table)})"
    ).fetchall()
    result = []
    for row in rows:
        name = row[1]
        cols = connection.execute(
            f"PRAGMA index_info({quote_identifier(name)})"
        ).fetchall()
        result.append({
            "name": name,
            "unique": bool(row[2]),
            "columns": [col[2] for col in cols],
        })
    return result

def get_observed_values(connection, table, column):
    sql = (
        f"SELECT DISTINCT {quote_identifier(column)} "
        f"FROM {quote_identifier(table)} "
        f"WHERE {quote_identifier(column)} IS NOT NULL "
        f"ORDER BY {quote_identifier(column)}"
    )
    return [row[0] for row in connection.execute(sql).fetchall()]

def get_columns(connection, table, create_sql, indexes):
    rows = connection.execute(
        f"PRAGMA table_info({quote_identifier(table)})"
    ).fetchall()
    foreign_keys = get_foreign_keys(connection, table)
    fk_map = {
        fk[3]: {
            "referenced_table": fk[2],
            "referenced_column": fk[4],
        }
        for fk in foreign_keys
    }

    unique_single = set()
    unique_composite = []
    for index in indexes:
        if index["unique"]:
            cols = index["columns"]
            if len(cols) == 1:
                unique_single.add(cols[0])
            elif cols:
                unique_composite.append(cols)

    columns = []
    for row in rows:
        name, declared_type, not_null, default, pk_position = (
            row[1], row[2], bool(row[3]), row[4], row[5]
        )
        required = bool(not_null or pk_position)
        unique = (
            "Yes (primary key)"
            if pk_position and len([
                r for r in rows if r[5]
            ]) == 1
            else "Yes (part of composite primary key)"
            if pk_position
            else "Yes"
            if name in unique_single
            else "Part of unique key"
            if any(name in group for group in unique_composite)
            else "No"
        )

        checks = CHECK_VALUES.get((table, name), [])
        observed = (
            get_observed_values(connection, table, name)
            if (table, name) in OBSERVED_COLUMNS else []
        )

        notes = FIELD_NOTES.get((table, name), {})
        fk = fk_map.get(name)
        rules = []
        if required:
            rules.append("Required (NOT NULL or PRIMARY KEY).")
        if pk_position:
            rules.append(f"Primary key position {pk_position}; unique.")
        if fk:
            rules.append(
                f"Foreign key references {fk['referenced_table']}."
                f"{fk['referenced_column']}."
            )
        if checks:
            rules.append("CHECK constraint restricts the value to the listed values.")
        if notes.get("validation_rule"):
            rules = [notes["validation_rule"]]
        elif not rules:
            rules.append("No additional column-level validation identified in the SQLite schema.")

        columns.append({
            "name": name,
            "data_type": declared_type or "",
            "not_null": required,
            "default_value": default,
            "primary_key_position": pk_position,
            "foreign_key": fk,
            "allowed_values": checks,
            "allowed_values_note": notes.get("allowed_values_note", ""),
            "observed_values": observed,
            "units": notes.get("units", "Not specified / not applicable"),
            "unique": unique,
            "validation_rule": " ".join(rules),
        })
    return columns

def markdown_cell(value):
    if value is None or value == "":
        return "-"
    if isinstance(value, list):
        return ", ".join(str(x) for x in value) if value else "-"
    return str(value).replace("|", "\\|").replace("\n", " ")

def build_dictionary():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # URI read-only connection; query_only is an additional write guard.
    connection = sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row

    try:
        connection.execute("PRAGMA query_only = ON")
        tables = get_table_names(connection)
        dictionary = {
            "project": "Warehouse Risk Monitoring System",
            "database": "warehouse_monitor.db",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_mode": "read-only",
            "tables": [],
        }
        csv_rows = []

        for table_name, create_sql in tables:
            indexes = get_indexes(connection, table_name)
            columns = get_columns(
                connection, table_name, create_sql or "", indexes
            )
            foreign_keys = get_foreign_keys(connection, table_name)

            table_info = {
                "table_name": table_name,
                "description": "Description requires business confirmation.",
                "columns": columns,
                "foreign_keys": [
                    {
                        "column": fk[3],
                        "referenced_table": fk[2],
                        "referenced_column": fk[4],
                        "on_update": fk[5],
                        "on_delete": fk[6],
                    }
                    for fk in foreign_keys
                ],
                "indexes": indexes,
                "table_constraints_sql": create_sql,
            }
            dictionary["tables"].append(table_info)

            for col in columns:
                fk = col["foreign_key"] or {}
                csv_rows.append({
                    "table_name": table_name,
                    "column_name": col["name"],
                    "data_type": col["data_type"],
                    "required": col["not_null"],
                    "default_value": col["default_value"],
                    "primary_key_position": col["primary_key_position"],
                    "foreign_key_table": fk.get("referenced_table", ""),
                    "foreign_key_column": fk.get("referenced_column", ""),
                    "allowed_values": "; ".join(col["allowed_values"]),
                    "allowed_values_note": col["allowed_values_note"],
                    "observed_values_not_constraints": "; ".join(
                        str(v) for v in col["observed_values"]
                    ),
                    "units": col["units"],
                    "unique": col["unique"],
                    "validation_rule": col["validation_rule"],
                })

        with open(OUTPUT_DIR / "data_dictionary.json", "w", encoding="utf-8") as f:
            json.dump(dictionary, f, indent=2, ensure_ascii=False)

        csv_path = OUTPUT_DIR / "data_dictionary.csv"
        fieldnames = list(csv_rows[0].keys()) if csv_rows else []
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

        md_path = OUTPUT_DIR / "data_dictionary.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(
                "# Warehouse Risk Monitoring System\n"
                "# Data Dictionary\n\n"
                "Generated from the actual SQLite schema using a read-only connection. "
                "Required includes declared NOT NULL columns and primary-key columns. "
                "“Allowed values” lists only values enforced by SQLite CHECK constraints. "
                "Observed values are shown separately and are not presented as constraints. "
                "Units are documented only where established; otherwise they are marked "
                "not specified / not applicable.\n\n"
            )
            f.write(f"Tables documented: {len(dictionary['tables'])}\n\n")

            for table in dictionary["tables"]:
                f.write(f"## {table['table_name']}\n\n")
                f.write(
                    "| Column | Type | Required | Allowed values (CHECK) | "
                    "Observed values (not constraints) | Units | Unique | "
                    "Validation rule | Foreign key |\n"
                )
                f.write("|---|---|---|---|---|---|---|---|---|\n")
                for col in table["columns"]:
                    fk = col["foreign_key"]
                    fk_text = (
                        f"{fk['referenced_table']}.{fk['referenced_column']}"
                        if fk else "-"
                    )
                    f.write(
                        "| " + " | ".join([
                            markdown_cell(col["name"]),
                            markdown_cell(col["data_type"]),
                            "Yes" if col["not_null"] else "No",
                            markdown_cell(col["allowed_values"]),
                            markdown_cell(col["observed_values"]),
                            markdown_cell(col["units"]),
                            markdown_cell(col["unique"]),
                            markdown_cell(col["validation_rule"]),
                            markdown_cell(fk_text),
                        ]) + " |\n"
                    )

                f.write("\n### Indexes and uniqueness\n\n")
                if table["indexes"]:
                    for index in table["indexes"]:
                        f.write(
                            f"- `{index['name']}`: "
                            f"{', '.join(index['columns'])}; "
                            f"unique={index['unique']}\n"
                        )
                else:
                    f.write("No indexes reported.\n")

                f.write("\n### Table validation constraints\n\n")
                sql = table["table_constraints_sql"] or ""
                checks = re.findall(
                    r"CHECK\s*\(.*?\)",
                    sql,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                if checks:
                    for check in checks:
                        f.write(f"- `{check}`\n")
                else:
                    f.write("No CHECK constraints detected.\n")

                if table["foreign_keys"]:
                    f.write("\n### Foreign keys\n\n")
                    for fk in table["foreign_keys"]:
                        f.write(
                            f"- `{fk['column']}` references "
                            f"`{fk['referenced_table']}.{fk['referenced_column']}` "
                            f"(ON UPDATE {fk['on_update']}; "
                            f"ON DELETE {fk['on_delete']}).\n"
                        )
                f.write("\n")

        print("DATA DICTIONARY GENERATION COMPLETE")
        print("Database opened read-only; PRAGMA query_only=ON.")
        print("Tables documented:", len(dictionary["tables"]))
        print("Columns documented:", len(csv_rows))
        print("Markdown:", md_path.relative_to(ROOT))
        print("CSV:", csv_path.relative_to(ROOT))
        print("JSON:", (OUTPUT_DIR / "data_dictionary.json").relative_to(ROOT))

        expected = {
            "alarm_history", "inspection_history",
            "remediation_history", "remediation_lots",
        }
        actual = {t["table_name"] for t in dictionary["tables"]}
        missing = sorted(expected - actual)
        if missing:
            raise RuntimeError(
                "Expected history/link tables missing from database: "
                + ", ".join(missing)
            )

        remediation = next(
            t for t in dictionary["tables"]
            if t["table_name"] == "remediations"
        )
        type_column = next(
            c for c in remediation["columns"]
            if c["name"] == "remediation_type"
        )
        required_types = {"REPAIR_DOOR", "REPAIR_SENSOR"}
        if not required_types.issubset(set(type_column["allowed_values"])):
            raise RuntimeError(
                "The live remediations schema does not show both "
                "REPAIR_DOOR and REPAIR_SENSOR in its CHECK constraint."
            )
        print("Required history tables present: PASS")
        print("REPAIR_DOOR and REPAIR_SENSOR schema values: PASS")

    finally:
        connection.close()

if __name__ == "__main__":
    build_dictionary()
