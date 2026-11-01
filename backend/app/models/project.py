from app.extensions import db
from .enums import ProjectStatus


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.BigInteger, primary_key=True)
    owner_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(4), unique=True, nullable=False)
    description = db.Column(db.Text)
    status = db.Column(
        db.Enum(ProjectStatus, name="project_status"),
        nullable=False,
        default=ProjectStatus.active,
        server_default=ProjectStatus.active.value,
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    owner = db.relationship("User", back_populates="projects")
    entries = db.relationship("TimeEntry", back_populates="project")