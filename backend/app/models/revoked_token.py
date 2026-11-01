from sqlalchemy import Uuid

from app.extensions import db


class RevokedToken(db.Model):
    __tablename__ = "revoked_tokens"

    jti = db.Column(Uuid(as_uuid=True), primary_key=True)
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    user = db.relationship("User", back_populates="revoked_tokens")