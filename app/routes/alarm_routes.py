"""Alarm analytics API endpoints."""

from flask import Blueprint, jsonify

from app.analytics.alarm_analytics import get_alarm_analytics
from app.database.database import DATABASE_PATH

import sqlite3


alarm_bp = Blueprint("alarms", __name__)


def get_readonly_connection():
    """Create a read-only database connection."""

    connection = sqlite3.connect(
        f"file:{DATABASE_PATH.as_posix()}?mode=ro",
        uri=True
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")

    return connection


@alarm_bp.route("/alarms", methods=["GET"])
def get_alarms():
    """Return alarm analytics."""

    connection = None

    try:
        connection = get_readonly_connection()

        analytics = get_alarm_analytics(connection)

        return jsonify({
            "status": "success",
            "data": analytics
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to retrieve alarm analytics."
        }), 500

    finally:
        if connection is not None:
            connection.close()