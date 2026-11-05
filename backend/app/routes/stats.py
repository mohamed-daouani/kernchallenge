from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import func

from app.extensions import db
from app.models import Project, TimeEntry

bp = Blueprint("stats", __name__)


def _week_bounds(day, zone):
    monday = day - timedelta(days=day.weekday())
    start_local = datetime.combine(monday, time.min, tzinfo=zone)
    end_local = datetime.combine(monday + timedelta(days=7), time.min, tzinfo=zone)
    return monday, start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


@bp.get("/summary")
@jwt_required()
def summary():
    tz_name = request.args.get("tz", "UTC")
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return jsonify(errors={"tz": "Unknown timezone (e.g. Europe/Brussels)"}), 400

    week_param = request.args.get("week")
    if week_param:
        try:
            day = date.fromisoformat(week_param)
        except ValueError:
            return jsonify(errors={"week": "Invalid date, expected YYYY-MM-DD"}), 400
    else:
        day = datetime.now(zone).date()

    monday, start_utc, end_utc = _week_bounds(day, zone)
    in_week = (
        TimeEntry.user_id == current_user.id,
        TimeEntry.start_at >= start_utc,
        TimeEntry.start_at < end_utc,
    )

    total_col = func.sum(TimeEntry.duration_minutes)
    rows = (
        db.session.query(Project.id, Project.name, Project.code, total_col)
        .join(TimeEntry, TimeEntry.project_id == Project.id)
        .filter(*in_week)
        .group_by(Project.id, Project.name, Project.code)
        .order_by(total_col.desc())
        .all()
    )
    by_project = [
        {"project_id": pid, "name": name, "code": code, "minutes": int(minutes or 0)}
        for pid, name, code, minutes in rows
    ]
    total_minutes = sum(p["minutes"] for p in by_project)

    days = {monday + timedelta(days=i): 0 for i in range(7)}
    entries = (
        db.session.query(TimeEntry.start_at, TimeEntry.duration_minutes)
        .filter(*in_week)
        .all()
    )
    for start_at, minutes in entries:
        if minutes is None:
            continue
        if start_at.tzinfo is None:  
            start_at = start_at.replace(tzinfo=timezone.utc)
        local_day = start_at.astimezone(zone).date()
        if local_day in days:
            days[local_day] += minutes
    by_day = [{"date": d.isoformat(), "minutes": m} for d, m in days.items()]

    target = current_user.weekly_target_minutes
    progress = round(total_minutes / target * 100, 1) if target else 0.0

    return jsonify(
        week={
            "start": monday.isoformat(),
            "end": (monday + timedelta(days=6)).isoformat(),
            "tz": tz_name,
        },
        target_minutes=target,
        total_minutes=total_minutes,
        remaining_minutes=max(0, target - total_minutes),
        progress_percent=progress,
        by_project=by_project,
        by_day=by_day,
    )