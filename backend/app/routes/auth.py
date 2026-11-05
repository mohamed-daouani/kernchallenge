import re
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, current_user, get_jwt, jwt_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import RevokedToken, User

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


@bp.post("/register")
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON body required"), 400

    errors = {}

    email = data.get("email")
    email = email.strip().lower() if isinstance(email, str) else ""
    if not EMAIL_RE.match(email) or len(email) > 255:
        errors["email"] = "A valid email is required"

    password = data.get("password")
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        errors["password"] = "Required, between 8 and 128 characters"

    names = {}
    for field in ("first_name", "last_name"):
        value = data.get(field)
        value = value.strip() if isinstance(value, str) else ""
        if not value or len(value) > 100:
            errors[field] = "Required, 100 characters max"
        names[field] = value

    job_title = data.get("job_title")
    if job_title is not None:
        if not isinstance(job_title, str) or len(job_title.strip()) > 100:
            errors["job_title"] = "Must be a string, 100 characters max"
        else:
            job_title = job_title.strip() or None

    if errors:
        return jsonify(errors=errors), 400

    if User.query.filter_by(email=email).first():
        return jsonify(errors={"email": "This email is already registered"}), 409

    # Le rôle n'est jamais lu depuis la requête : un nouvel inscrit est toujours "user"
    user = User(email=email, job_title=job_title, **names)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:  # deux inscriptions simultanées avec le même email
        db.session.rollback()
        return jsonify(errors={"email": "This email is already registered"}), 409

    return jsonify(user=user.to_dict()), 201


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