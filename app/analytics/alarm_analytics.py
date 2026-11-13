
def get_alarm_analytics(conn):
    cur = conn.cursor()

    total = cur.execute(
        "SELECT COUNT(*) FROM alarms"
    ).fetchone()[0]

    def grouped_query(query):
        return [
            {"category": row[0], "count": row[1]}
            for row in cur.execute(query).fetchall()
        ]

    by_type = grouped_query("""
        SELECT alarm_type, COUNT(*)
        FROM alarms
        GROUP BY alarm_type
        ORDER BY COUNT(*) DESC
    """)

    by_severity = grouped_query("""
        SELECT severity, COUNT(*)
        FROM alarms
        GROUP BY severity
        ORDER BY
            CASE severity
                WHEN 'CRITICAL' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'MEDIUM' THEN 3
                WHEN 'LOW' THEN 4
                ELSE 5
            END
    """)

    by_status = grouped_query("""
        SELECT lifecycle_state, COUNT(*)
        FROM alarms
        GROUP BY lifecycle_state
        ORDER BY COUNT(*) DESC
    """)

    by_warehouse = cur.execute("""
        SELECT
            w.warehouse_id,
            w.warehouse_name,
            COUNT(a.alarm_id)
        FROM warehouses w
        LEFT JOIN alarms a
            ON a.warehouse_id = w.warehouse_id
        GROUP BY w.warehouse_id, w.warehouse_name
        ORDER BY COUNT(a.alarm_id) DESC
    """).fetchall()

    top_zones = cur.execute("""
        SELECT
            z.zone_id,
            z.zone_name,
            w.warehouse_name,
            COUNT(a.alarm_id) AS alarm_count
        FROM zones z
        JOIN warehouses w
            ON w.warehouse_id = z.warehouse_id
        LEFT JOIN alarms a
            ON a.zone_id = z.zone_id
        GROUP BY z.zone_id, z.zone_name, w.warehouse_name
        HAVING COUNT(a.alarm_id) > 0
        ORDER BY alarm_count DESC
        LIMIT 10
    """).fetchall()

    return {
        "total_alarms": total,
        "by_type": by_type,
        "by_severity": by_severity,
        "by_lifecycle_status": by_status,
        "by_warehouse": [
            {
                "warehouse_id": row[0],
                "warehouse_name": row[1],
                "alarm_count": row[2]
            }
            for row in by_warehouse
        ],
        "top_10_risk_zones": [
            {
                "zone_id": row[0],
                "zone_name": row[1],
                "warehouse_name": row[2],
                "alarm_count": row[3]
            }
            for row in top_zones
        ]
    }
