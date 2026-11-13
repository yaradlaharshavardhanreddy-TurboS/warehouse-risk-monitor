"""Application route registration."""

from app.routes.frontend_routes import frontend_bp
from app.routes.health_routes import health_bp
from app.routes.dashboard_routes import dashboard_bp
from app.routes.alarm_routes import alarm_bp
from app.routes.warehouse_routes import warehouse_bp
from app.routes.inventory_routes import inventory_bp
from app.routes.inspection_routes import inspection_bp
from app.routes.remediation_routes import remediation_bp
from app.routes.trend_routes import trend_bp


def register_routes(app):
    """Register all application blueprints."""

    app.register_blueprint(frontend_bp)

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(dashboard_bp, url_prefix="/api")
    app.register_blueprint(alarm_bp, url_prefix="/api")
    app.register_blueprint(warehouse_bp, url_prefix="/api")
    app.register_blueprint(inventory_bp, url_prefix="/api")
    app.register_blueprint(inspection_bp, url_prefix="/api")
    app.register_blueprint(remediation_bp, url_prefix="/api")
    app.register_blueprint(trend_bp, url_prefix="/api")