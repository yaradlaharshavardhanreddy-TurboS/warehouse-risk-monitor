"""Warehouse analytics API endpoints."""

import sqlite3

from flask import Blueprint, jsonify

from app.analytics.warehouse_analytics import get_warehouse_analytics
from app.database.database import DATABASE_PATH


warehouse_bp = Blueprint("warehouses", __name__)


@warehouse_bp.route("/warehouses", methods=["GET"])
def get_warehouses():
    """Return warehouse analytics."""

    connection = None

    try:
        connection = sqlite3.connect(
            f"file:{DATABASE_PATH.as_posix()}?mode=ro",
            uri=True
        )

        connection.execute("PRAGMA query_only = ON")

        analytics = get_warehouse_analytics(connection)

        return jsonify({
            "status": "success",
            "data": analytics
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to retrieve warehouse analytics."
        }), 500

    finally:
        if connection is not None:
            connection.close()
