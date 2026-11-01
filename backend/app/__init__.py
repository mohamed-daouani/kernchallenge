from flask import Flask, jsonify
from .config import DevConfig
from .extensions import db, migrate, jwt, cors
from .cli import register_commands


def create_app(config_class=DevConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, ressources={r"/api/*": {"origins": "*"}})

    from . import models
    from .routes.health import bp as health_bp
    from . import jwt_callbacks
    from .routes.auth import bp as auth_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(health_bp, url_prefix="/api")

    register_commands(app)

    return app