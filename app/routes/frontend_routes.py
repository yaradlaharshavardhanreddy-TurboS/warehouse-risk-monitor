"""Frontend page routes."""

from flask import Blueprint, render_template

frontend_bp = Blueprint("frontend", __name__)


@frontend_bp.route("/monitor")
def dashboard_page():
    return render_template("dashboard.html")


@frontend_bp.route("/alarms")
def alarms_page():
    return render_template(
        "alarms.html",
        current_endpoint="/api/alarms"
    )


@frontend_bp.route("/warehouses")
def warehouses_page():
    return render_template(
        "warehouses.html",
        current_endpoint="/api/warehouses"
    )


@frontend_bp.route("/inventory")
def inventory_page():
    return render_template(
        "inventory.html",
        current_endpoint="/api/inventory"
    )


@frontend_bp.route("/inspections")
def inspections_page():
    return render_template(
        "inspections.html",
        current_endpoint="/api/inspections"
    )


@frontend_bp.route("/remediations")
def remediations_page():
    return render_template(
        "remediations.html",
        current_endpoint="/api/remediations"
    )


@frontend_bp.route("/analytics")
def analytics_page():
    return render_template(
        "analytics.html",
        current_endpoint="/api/dashboard"
    )
