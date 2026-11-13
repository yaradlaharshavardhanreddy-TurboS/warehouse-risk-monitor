
def get_inspection_analytics(conn):
    cur = conn.cursor()

    total = cur.execute("""
        SELECT COUNT(*) FROM inspections
    """).fetchone()[0]

    statuses = cur.execute("""
        SELECT inspection_status, COUNT(*)
        FROM inspections
        GROUP BY inspection_status
        ORDER BY inspection_status
    """).fetchall()

    types = cur.execute("""
        SELECT inspection_type, COUNT(*)
        FROM inspections
        GROUP BY inspection_type
        ORDER BY inspection_type
    """).fetchall()

    completed = cur.execute("""
        SELECT COUNT(*)
        FROM inspections
        WHERE inspection_status = 'COMPLETED'
    """).fetchone()[0]

    in_progress = cur.execute("""
        SELECT COUNT(*)
        FROM inspections
        WHERE inspection_status = 'IN_PROGRESS'
    """).fetchone()[0]

    scheduled = cur.execute("""
        SELECT COUNT(*)
        FROM inspections
        WHERE inspection_status = 'SCHEDULED'
    """).fetchone()[0]

    cancelled = cur.execute("""
        SELECT COUNT(*)
        FROM inspections
        WHERE inspection_status = 'CANCELLED'
    """).fetchone()[0]

    completion_rate = (
        round((completed / total) * 100, 2)
        if total else 0.0
    )

    return {
        "total_inspections": total,
        "completed": completed,
        "in_progress": in_progress,
        "scheduled": scheduled,
        "cancelled": cancelled,
        "completion_percentage": completion_rate,
        "by_status": [
            {"status": row[0], "count": row[1]}
            for row in statuses
        ],
        "by_type": [
            {"inspection_type": row[0], "count": row[1]}
            for row in types
        ]
    }
