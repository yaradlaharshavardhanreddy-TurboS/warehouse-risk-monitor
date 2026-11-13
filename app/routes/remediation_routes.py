"""Remediation analytics API endpoints."""

import sqlite3

from flask import Blueprint, jsonify

from app.analytics.remediation_analytics import get_remediation_analytics
from app.database.database import DATABASE_PATH


remediation_bp = Blueprint("remediations", __name__)


@remediation_bp.route("/remediations", methods=["GET"])
def get_remediations():
    """Return remediation analytics."""

    connection = None

    try:
        connection = sqlite3.connect(
            f"file:{DATABASE_PATH.as_posix()}?mode=ro",
            uri=True
        )

        connection.execute("PRAGMA query_only = ON")

        analytics = get_remediation_analytics(connection)

        return jsonify({
            "status": "success",
            "data": analytics
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to retrieve remediation analytics."
        }), 500

    finally:
        if connection is not None:
            connection.close()
