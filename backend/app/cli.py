import click
from datetime import datetime, timedelta, timezone

from .extensions import db
from .models import User, Project, TimeEntry, UserRole


def register_commands(app):
    @app.cli.command("seed")
    def seed():
        if User.query.filter_by(email="demo@kern.test").first():
            click.echo("Déjà seedé.")
            return

        user = User(
            email="demo@kern.test",
            first_name="Demo",
            last_name="User",
            job_title="Developer",
            role=UserRole.admin,
        )
        user.set_password("demo1234")
        db.session.add(user)
        db.session.flush()  

        p1 = Project(owner_id=user.id, name="Site web", code="WEB", description="Refonte du site")
        p2 = Project(owner_id=user.id, name="Application mobile", code="MOB")
        db.session.add_all([p1, p2])
        db.session.flush()

        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        entries = [
            TimeEntry(user_id=user.id, project_id=p1.id, description="Maquettes",
                      start_at=now - timedelta(hours=3), end_at=now - timedelta(hours=1, minutes=30)),
            TimeEntry(user_id=user.id, project_id=p2.id, description="Réunion",
                      start_at=now - timedelta(hours=1), end_at=now - timedelta(minutes=15)),
        ]
        for e in entries:
            e.compute_duration()
        db.session.add_all(entries)
        db.session.commit()
        click.echo("Seed terminé.")