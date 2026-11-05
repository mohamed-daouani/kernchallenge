import json

from flask import jsonify
from werkzeug.exceptions import HTTPException

from app.extensions import db, jwt


def register_error_handlers(app):
    # --- Erreurs HTTP (404, 405, 413, ...) : JSON au lieu de la page HTML ---
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        # get_response() conserve les en-têtes utiles (ex. "Allow" pour un 405)
        response = error.get_response()
        response.set_data(json.dumps({"error": error.name}))
        response.content_type = "application/json"
        return response

    # --- Erreurs inattendues : 500 JSON, sans fuite de détails internes ---
    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):
        app.logger.exception("Unhandled exception")
        db.session.rollback()
        return jsonify(error="Internal server error"), 500

    # --- Erreurs JWT : même format {"error": ...} que le reste de l'API ---
    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify(error="Authentication required"), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify(error="Invalid token"), 401

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_data):
        return jsonify(error="Token has expired"), 401

    @jwt.revoked_token_loader
    def revoked_token(jwt_header, jwt_data):
        return jsonify(error="Token has been revoked"), 401

    @jwt.user_lookup_error_loader
    def unknown_user(jwt_header, jwt_data):
        return jsonify(error="User not found or disabled"), 401
