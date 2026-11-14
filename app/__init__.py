"""Warehouse Risk Monitoring Flask application factory."""


def create_app(config_class=None):
    """Create the Flask app; import web dependencies only when serving HTTP."""
    from flask import Flask, jsonify, redirect
    from config import Config
    from app.routes import register_routes

    app = Flask(__name__)
    app.config.from_object(config_class or Config)
    register_routes(app)

    @app.route('/', methods=['GET'])
    def index():
        return redirect('/monitor')

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not Found', 'message': 'The requested endpoint does not exist.'}), 404

    return app
