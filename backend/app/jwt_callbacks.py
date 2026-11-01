import uuid

from app.extensions import db, jwt
from app.models import RevokedToken, User


@jwt.token_in_blocklist_loader
def is_token_revoked(jwt_header, jwt_payload):
    jti = uuid.UUID(jwt_payload["jti"])
    return db.session.get(RevokedToken, jti) is not None


@jwt.user_lookup_loader
def load_user(jwt_header, jwt_payload):
    user = db.session.get(User, int(jwt_payload["sub"]))
    if user is None or not user.is_active:
        return None  
    return user