
def get_inventory_analytics(conn):
    cur = conn.cursor()

    total_lots = cur.execute("""
        SELECT COUNT(*) FROM inventory_lots
    """).fetchone()[0]

    alarm_lot_links = cur.execute("""
        SELECT COUNT(*) FROM alarm_lots
    """).fetchone()[0]

    unique_affected_lots = cur.execute("""
        SELECT COUNT(DISTINCT lot_id)
        FROM alarm_lots
        WHERE lot_id IS NOT NULL
    """).fetchone()[0]

    multiple_alarm_lots = cur.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT lot_id
            FROM alarm_lots
            WHERE lot_id IS NOT NULL
            GROUP BY lot_id
            HAVING COUNT(DISTINCT alarm_id) > 1
        )
    """).fetchone()[0]

    affected_by_lifecycle = cur.execute("""
        SELECT
            l.lifecycle_state,
            COUNT(DISTINCT l.lot_id)
        FROM inventory_lots l
        JOIN alarm_lots al
            ON al.lot_id = l.lot_id
        GROUP BY l.lifecycle_state
        ORDER BY COUNT(DISTINCT l.lot_id) DESC
    """).fetchall()

    exposure_by_alarm_type = cur.execute("""
        SELECT
            a.alarm_type,
            COUNT(DISTINCT al.lot_id),
            COUNT(*)
        FROM alarms a
        JOIN alarm_lots al
            ON al.alarm_id = a.alarm_id
        GROUP BY a.alarm_type
        ORDER BY COUNT(DISTINCT al.lot_id) DESC
    """).fetchall()

    top_affected_products = cur.execute("""
        SELECT
            l.product_type,
            COUNT(DISTINCT l.lot_id)
        FROM inventory_lots l
        JOIN alarm_lots al
            ON al.lot_id = l.lot_id
        GROUP BY l.product_type
        ORDER BY COUNT(DISTINCT l.lot_id) DESC
        LIMIT 10
    """).fetchall()

    return {
        "total_inventory_lots": total_lots,
        "alarm_lot_links": alarm_lot_links,
        "unique_affected_lots": unique_affected_lots,
        "lots_affected_by_multiple_alarms": multiple_alarm_lots,
        "affected_lots_by_lifecycle": [
            {
                "lifecycle_state": row[0],
                "lot_count": row[1]
            }
            for row in affected_by_lifecycle
        ],
        "exposure_by_alarm_type": [
            {
                "alarm_type": row[0],
                "unique_affected_lots": row[1],
                "alarm_lot_links": row[2]
            }
            for row in exposure_by_alarm_type
        ],
        "top_10_affected_product_types": [
            {
                "product_type": row[0],
                "affected_lots": row[1]
            }
            for row in top_affected_products
        ]
    }
