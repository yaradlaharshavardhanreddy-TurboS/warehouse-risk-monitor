
import sqlite3

from app.database.database import DATABASE_PATH


TABLES = [
    "alarms",
    "alarm_lots",
    "inspections",
    "remediations",
    "sensor_outages",
]


def table_exists(conn, table):
    return conn.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table,)
    ).fetchone() is not None


def get_primary_key(conn, table):
    rows = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return [
        row[1]
        for row in sorted(rows, key=lambda item: item[5])
        if row[5] > 0
    ]


def main():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    try:
        print("\n===== PHASE 5 VALIDATION =====")

        print("\n--- TABLE COUNTS ---")

        for table in TABLES:
            if not table_exists(conn, table):
                print(f"{table}: TABLE NOT FOUND")
                continue

            count = cur.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"{table}: {count:,}")

        print("\n--- PRIMARY KEY DUPLICATE CHECK ---")

        for table in TABLES:
            if not table_exists(conn, table):
                continue

            primary_keys = get_primary_key(conn, table)

            if not primary_keys:
                print(f"{table}: No primary key defined")
                continue

            columns = ", ".join(primary_keys)

            duplicates = cur.execute(
                f"""
                SELECT COUNT(*)
                FROM (
                    SELECT {columns}
                    FROM {table}
                    GROUP BY {columns}
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]

            print(f"{table}: {duplicates} duplicate primary keys")

        print("\n--- FOREIGN KEY CHECK ---")

        foreign_key_errors = cur.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        print("Foreign key violations:", len(foreign_key_errors))

        for error in foreign_key_errors[:20]:
            print(" ", error)

        print("\n--- ORPHAN CHECKS ---")

        orphan_checks = [
            (
                "alarm_lots without alarms",
                """
                SELECT COUNT(*)
                FROM alarm_lots al
                LEFT JOIN alarms a ON a.alarm_id = al.alarm_id
                WHERE a.alarm_id IS NULL
                """
            ),
            (
                "inspections without alarms",
                """
                SELECT COUNT(*)
                FROM inspections i
                LEFT JOIN alarms a ON a.alarm_id = i.alarm_id
                WHERE a.alarm_id IS NULL
                """
            ),
            (
                "remediations without inspections",
                """
                SELECT COUNT(*)
                FROM remediations r
                LEFT JOIN inspections i
                    ON i.inspection_id = r.inspection_id
                WHERE i.inspection_id IS NULL
                """
            ),
            (
                "remediations without inventory lots",
                """
                SELECT COUNT(*)
                FROM remediations r
                LEFT JOIN inventory_lots l ON l.lot_id = r.lot_id
                WHERE r.lot_id IS NOT NULL
                AND l.lot_id IS NULL
                """
            ),
        ]

        for label, query in orphan_checks:
            try:
                count = cur.execute(query).fetchone()[0]
                print(f"{label}: {count}")
            except sqlite3.OperationalError as error:
                print(f"{label}: CHECK SKIPPED ({error})")

        print("\n--- ALARM TYPE COUNTS ---")

        if table_exists(conn, "alarms"):
            rows = cur.execute(
                """
                SELECT alarm_type, COUNT(*)
                FROM alarms
                GROUP BY alarm_type
                ORDER BY alarm_type
                """
            ).fetchall()

            for alarm_type, count in rows:
                print(f"{alarm_type}: {count:,}")

        print("\n--- INSPECTION STATUS COUNTS ---")

        if table_exists(conn, "inspections"):
            rows = cur.execute(
                """
                SELECT inspection_status, COUNT(*)
                FROM inspections
                GROUP BY inspection_status
                ORDER BY inspection_status
                """
            ).fetchall()

            for status, count in rows:
                print(f"{status}: {count:,}")

        print("\n--- REMEDIATION STATUS COUNTS ---")

        if table_exists(conn, "remediations"):
            rows = cur.execute(
                """
                SELECT remediation_status, COUNT(*)
                FROM remediations
                GROUP BY remediation_status
                ORDER BY remediation_status
                """
            ).fetchall()

            for status, count in rows:
                print(f"{status}: {count:,}")

        print("\n--- DATABASE INTEGRITY ---")

        integrity = cur.execute(
            "PRAGMA integrity_check"
        ).fetchall()

        for result in integrity:
            print(result[0])

        valid = (
            len(foreign_key_errors) == 0
            and len(integrity) == 1
            and integrity[0][0] == "ok"
        )

        print("\n===== VALIDATION RESULT =====")
        print("PASS" if valid else "CHECK REQUIRED")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
