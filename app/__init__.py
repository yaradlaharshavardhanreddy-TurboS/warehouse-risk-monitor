"""Warehouse Risk Monitoring Flask application."""

from flask import Flask, jsonify

from config import Config
from app.routes import register_routes


def create_app(config_class=Config):
    """Create and configure the Flask application."""

    app = Flask(__name__)

    app.config.from_object(config_class)

    register_routes(app)

    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "application": "Warehouse Risk Monitoring",
            "version": "1.0.0",
            "status": "running",
            "health_endpoint": "/api/health"
        })

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "error": "Not Found",
            "message": "The requested endpoint does not exist."
        }), 404

    return app
