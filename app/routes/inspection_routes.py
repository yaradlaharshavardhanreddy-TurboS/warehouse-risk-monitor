"""Inspection analytics API endpoints."""

import sqlite3

from flask import Blueprint, jsonify

from app.analytics.inspection_analytics import get_inspection_analytics
from app.database.database import DATABASE_PATH


inspection_bp = Blueprint("inspections", __name__)


@inspection_bp.route("/inspections", methods=["GET"])
def get_inspections():
    """Return inspection analytics."""

    connection = None

    try:
        connection = sqlite3.connect(
            f"file:{DATABASE_PATH.as_posix()}?mode=ro",
            uri=True
        )

        connection.execute("PRAGMA query_only = ON")

        analytics = get_inspection_analytics(connection)

        return jsonify({
            "status": "success",
            "data": analytics
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to retrieve inspection analytics."
        }), 500

    finally:
        if connection is not None:
            connection.close()
