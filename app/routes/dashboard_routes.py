"""Dashboard analytics API endpoints."""

from flask import Blueprint, current_app, jsonify

from app.analytics.analytics_engine import generate_analytics


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET"])
def get_dashboard():
    """Return the complete warehouse analytics report."""

    try:
        report = generate_analytics()

        return jsonify({
            "status": "success",
            "data": report
        }), 200

    except Exception:
        current_app.logger.exception(
            "Failed to generate dashboard analytics."
        )

        return jsonify({
            "status": "error",
            "message": "Unable to generate dashboard analytics."
        }), 500