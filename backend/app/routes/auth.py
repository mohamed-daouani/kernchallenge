import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, current_user, get_jwt, jwt_required

from app.extensions import db
from app.models import RevokedToken, User

bp = Blueprint("auth", __name__)


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(error="Email and password are required"), 400

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return jsonify(error="Invalid credentials"), 401
    if not user.is_active:
        return jsonify(error="Account disabled"), 403

    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    token = create_access_token(
        identity=str(user.id),  
        additional_claims={"role": user.role.value},
    )
    return jsonify(access_token=token, user=user.to_dict())


@bp.post("/logout")
@jwt_required()
def logout():
    payload = get_jwt()
    db.session.add(
        RevokedToken(
            jti=uuid.UUID(payload["jti"]),
            user_id=current_user.id,
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    )
    db.session.commit()
    return jsonify(message="Logged out")


@bp.get("/me")
@jwt_required()
def me():
    return jsonify(user=current_user.to_dict())