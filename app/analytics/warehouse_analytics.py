
def get_warehouse_analytics(conn):
    cur = conn.cursor()

    warehouses = cur.execute("""
        SELECT
            w.warehouse_id,
            w.warehouse_name,
            w.location,
            COUNT(DISTINCT a.alarm_id) AS total_alarms,
            COUNT(DISTINCT CASE
                WHEN a.severity IN ('HIGH', 'CRITICAL')
                THEN a.alarm_id
            END) AS high_risk_alarms,
            COUNT(DISTINCT al.lot_id) AS affected_lots
        FROM warehouses w
        LEFT JOIN alarms a
            ON a.warehouse_id = w.warehouse_id
        LEFT JOIN alarm_lots al
            ON al.alarm_id = a.alarm_id
        GROUP BY
            w.warehouse_id,
            w.warehouse_name,
            w.location
        ORDER BY total_alarms DESC
    """).fetchall()

    results = []

    for row in warehouses:
        warehouse_id = row[0]

        pending_inspections = cur.execute("""
            SELECT COUNT(*)
            FROM inspections i
            JOIN alarms a
                ON a.alarm_id = i.alarm_id
            WHERE a.warehouse_id = ?
            AND i.inspection_status IN (
                'SCHEDULED', 'IN_PROGRESS'
            )
        """, (warehouse_id,)).fetchone()[0]

        results.append({
            "warehouse_id": row[0],
            "warehouse_name": row[1],
            "location": row[2],
            "total_alarms": row[3],
            "high_risk_alarms": row[4],
            "affected_unique_lots": row[5],
            "pending_inspections": pending_inspections
        })

    return {
        "total_warehouses": len(results),
        "warehouse_comparison": results
    }
