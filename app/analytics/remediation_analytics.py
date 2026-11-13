
def get_remediation_analytics(conn):
    cur = conn.cursor()

    total = cur.execute("""
        SELECT COUNT(*) FROM remediations
    """).fetchone()[0]

    statuses = cur.execute("""
        SELECT remediation_status, COUNT(*)
        FROM remediations
        GROUP BY remediation_status
        ORDER BY remediation_status
    """).fetchall()

    types = cur.execute("""
        SELECT remediation_type, COUNT(*)
        FROM remediations
        GROUP BY remediation_type
        ORDER BY COUNT(*) DESC
    """).fetchall()

    completed = cur.execute("""
        SELECT COUNT(*)
        FROM remediations
        WHERE remediation_status = 'COMPLETED'
    """).fetchone()[0]

    in_progress = cur.execute("""
        SELECT COUNT(*)
        FROM remediations
        WHERE remediation_status = 'IN_PROGRESS'
    """).fetchone()[0]

    planned = cur.execute("""
        SELECT COUNT(*)
        FROM remediations
        WHERE remediation_status = 'PLANNED'
    """).fetchone()[0]

    failed = cur.execute("""
        SELECT COUNT(*)
        FROM remediations
        WHERE remediation_status = 'FAILED'
    """).fetchone()[0]

    cancelled = cur.execute("""
        SELECT COUNT(*)
        FROM remediations
        WHERE remediation_status = 'CANCELLED'
    """).fetchone()[0]

    completion_rate = (
        round((completed / total) * 100, 2)
        if total else 0.0
    )

    return {
        "total_remediations": total,
        "completed": completed,
        "in_progress": in_progress,
        "planned": planned,
        "failed": failed,
        "cancelled": cancelled,
        "completion_percentage": completion_rate,
        "by_status": [
            {"status": row[0], "count": row[1]}
            for row in statuses
        ],
        "by_type": [
            {"remediation_type": row[0], "count": row[1]}
            for row in types
        ]
    }
