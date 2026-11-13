"""Application and database health endpoints."""

import sqlite3

from flask import Blueprint, current_app, jsonify


health_bp = Blueprint("health", __name__)

REQUIRED_TABLES = {
    "warehouses",
    "zones",
    "sensor_readings",
    "inventory_lots",
    "alarms",
    "alarm_lots",
    "inspections",
    "remediations"
}


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Check application and database availability."""

    database_path = current_app.config["DATABASE_PATH"]

    if not database_path.exists():
        return jsonify({
            "status": "unhealthy",
            "application": "warehouse-risk-monitor",
            "database": "unavailable",
            "message": "Database file does not exist."
        }), 503

    connection = None

    try:
        connection = sqlite3.connect(
            f"file:{database_path.as_posix()}?mode=ro",
            uri=True,
            timeout=5
        )

        connection.execute("PRAGMA query_only = ON")

        connection.execute("SELECT 1").fetchone()

        tables = {
            row[0]
            for row in connection.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
            """).fetchall()
        }

        missing_tables = sorted(
            REQUIRED_TABLES - tables
        )

        if missing_tables:
            return jsonify({
                "status": "unhealthy",
                "application": "warehouse-risk-monitor",
                "database": "connected",
                "missing_tables": missing_tables
            }), 503

        return jsonify({
            "status": "healthy",
            "application": "warehouse-risk-monitor",
            "database": "connected",
            "database_mode": "read_only",
            "required_tables": len(REQUIRED_TABLES),
            "message": "Application and database are operational."
        }), 200

    except sqlite3.Error as error:
        return jsonify({
            "status": "unhealthy",
            "application": "warehouse-risk-monitor",
            "database": "error",
            "message": str(error)
        }), 503

    finally:
        if connection is not None:
            connection.close()
