"""Inventory analytics API endpoints."""

import sqlite3

from flask import Blueprint, jsonify

from app.analytics.inventory_analytics import get_inventory_analytics
from app.database.database import DATABASE_PATH


inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/inventory", methods=["GET"])
def get_inventory():
    """Return inventory analytics."""

    connection = None

    try:
        connection = sqlite3.connect(
            f"file:{DATABASE_PATH.as_posix()}?mode=ro",
            uri=True
        )

        connection.execute("PRAGMA query_only = ON")

        analytics = get_inventory_analytics(connection)

        return jsonify({
            "status": "success",
            "data": analytics
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to retrieve inventory analytics."
        }), 500

    finally:
        if connection is not None:
            connection.close()
