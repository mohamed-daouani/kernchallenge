from app.extensions import db


class TimeEntry(db.Model):
    __tablename__ = "time_entries"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id = db.Column(
        db.BigInteger, db.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    description = db.Column(db.Text, nullable=False)
    start_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    end_at = db.Column(db.DateTime(timezone=True), nullable=False)
    duration_minutes = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    user = db.relationship("User", back_populates="entries")
    project = db.relationship("Project", back_populates="entries")

    __table_args__ = (
        db.CheckConstraint("end_at > start_at", name="ck_entry_end_after_start"),
    )

    def compute_duration(self):
        self.duration_minutes = int((self.end_at - self.start_at).total_seconds() // 60)