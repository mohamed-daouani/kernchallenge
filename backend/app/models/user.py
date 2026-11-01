from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from .enums import UserRole


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    job_title = db.Column(db.String(100))
    role = db.Column(
        db.Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.user,
        server_default=UserRole.user.value,
    )
    weekly_target_minutes = db.Column(db.Integer, nullable=False, server_default="2400")
    is_active = db.Column(db.Boolean, nullable=False, server_default=db.true())
    last_login_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    projects = db.relationship("Project", back_populates="owner")
    entries = db.relationship("TimeEntry", back_populates="user")
    revoked_tokens = db.relationship(
        "RevokedToken", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)