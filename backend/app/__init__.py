from flask import Flask, jsonify
from .config import DevConfig
from .extensions import db, migrate, jwt, cors


def create_app(config_class=DevConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    from . import models
    from .routes.health import bp as health_bp
    from . import jwt_callbacks
    from .routes.auth import bp as auth_bp
    from .routes.projects import bp as projects_bp
    from .routes.entries import bp as entries_bp
    from .routes.stats import bp as stats_bp
    from .cli import register_commands
    from .errors import register_error_handlers


    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(projects_bp, url_prefix="/api/projects")
    app.register_blueprint(entries_bp, url_prefix="/api/time-entries")
    app.register_blueprint(stats_bp, url_prefix="/api/dashboard")


    register_commands(app)
    register_error_handlers(app)

    return app 