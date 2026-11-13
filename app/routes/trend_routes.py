"""Trend analytics API endpoints."""

import sqlite3

from flask import Blueprint, jsonify

from app.analytics.trend_analytics import get_trend_analytics
from app.database.database import DATABASE_PATH


trend_bp = Blueprint("trends", __name__)


@trend_bp.route("/trends", methods=["GET"])
def get_trends():
    """Return trend analytics."""

    connection = None

    try:
        connection = sqlite3.connect(
            f"file:{DATABASE_PATH.as_posix()}?mode=ro",
            uri=True
        )

        connection.execute("PRAGMA query_only = ON")

        analytics = get_trend_analytics(connection)

        return jsonify({
            "status": "success",
            "data": analytics
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to retrieve trend analytics."
        }), 500

    finally:
        if connection is not None:
            connection.close()
