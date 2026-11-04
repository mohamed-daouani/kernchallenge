from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Project, ProjectStatus, TimeEntry, UserRole

bp = Blueprint("entries", __name__)

MAX_DURATION = timedelta(hours=24)


def _is_admin():
    return current_user.role == UserRole.admin


def _aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _parse_dt(value, assume_utc=False):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if dt.tzinfo is None:
        if not assume_utc:
            return None  
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_accessible_entry(entry_id):
    entry = db.session.get(TimeEntry, entry_id)
    if entry is None:
        return None
    if entry.user_id != current_user.id and not _is_admin():
        return None  
    return entry


def _check_range(start, end):
    if end <= start:
        return "end_at must be after start_at"
    if end - start > MAX_DURATION:
        return "An entry cannot exceed 24 hours"
    return None


def _check_project(project_id):
    project = db.session.get(Project, project_id)
    if project is None or (project.owner_id != current_user.id and not _is_admin()):
        return "Project not found"
    if project.status != ProjectStatus.active:
        return "Project is not active"
    return None


def _validate(data, partial=False):
    cleaned, errors = {}, {}

    if not partial or "project_id" in data:
        pid = data.get("project_id")
        if not isinstance(pid, int) or isinstance(pid, bool):
            errors["project_id"] = "Required, must be an integer"
        else:
            cleaned["project_id"] = pid

    if not partial or "description" in data:
        desc = data.get("description")
        desc = desc.strip() if isinstance(desc, str) else ""
        if not desc or len(desc) > 2000:
            errors["description"] = "Required, 2000 characters max"
        else:
            cleaned["description"] = desc

    for field in ("start_at", "end_at"):
        if not partial or field in data:
            dt = _parse_dt(data.get(field))
            if dt is None:
                errors[field] = "Required, ISO 8601 with timezone (e.g. 2026-11-04T09:00:00Z)"
            else:
                cleaned[field] = dt

    return cleaned, errors

@bp.post("")
@jwt_required()
def create_entry():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON body required"), 400

    cleaned, errors = _validate(data)
    if not errors:
        msg = _check_range(cleaned["start_at"], cleaned["end_at"])
        if msg:
            errors["end_at"] = msg
        msg = _check_project(cleaned["project_id"])
        if msg:
            errors["project_id"] = msg
    if errors:
        return jsonify(errors=errors), 400

    entry = TimeEntry(user_id=current_user.id, **cleaned)
    entry.compute_duration()
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry=entry.to_dict()), 201

@bp.get("")
@jwt_required()
def list_entries():
    query = TimeEntry.query.options(joinedload(TimeEntry.project))
    if not _is_admin():
        query = query.filter(TimeEntry.user_id == current_user.id)

    errors = {}

    date_from = request.args.get("from")
    if date_from:
        dt = _parse_dt(date_from, assume_utc=True)
        if dt is None:
            errors["from"] = "Invalid date"
        else:
            query = query.filter(TimeEntry.start_at >= dt)

    date_to = request.args.get("to")
    if date_to:
        dt = _parse_dt(date_to, assume_utc=True)
        if dt is None:
            errors["to"] = "Invalid date"
        else:
            query = query.filter(TimeEntry.start_at < dt)

    pid = request.args.get("project_id")
    if pid:
        if not pid.isdigit():
            errors["project_id"] = "Must be an integer"
        else:
            query = query.filter(TimeEntry.project_id == int(pid))

    if errors:
        return jsonify(errors=errors), 400

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    pagination = query.order_by(TimeEntry.start_at.desc()).paginate(
        page=page, per_page=per_page, max_per_page=100, error_out=False
    )

    return jsonify(
        entries=[e.to_dict() for e in pagination.items],
        page=pagination.page,
        per_page=pagination.per_page,
        total=pagination.total,
    )

@bp.get("/<int:entry_id>")
@jwt_required()
def get_entry(entry_id):
    entry = _get_accessible_entry(entry_id)
    if entry is None:
        return jsonify(error="Entry not found"), 404
    return jsonify(entry=entry.to_dict())


@bp.patch("/<int:entry_id>")
@jwt_required()
def update_entry(entry_id):
    entry = _get_accessible_entry(entry_id)
    if entry is None:
        return jsonify(error="Entry not found"), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON body required"), 400

    cleaned, errors = _validate(data, partial=True)
    if not errors:
        start = cleaned.get("start_at", _aware(entry.start_at))
        end = cleaned.get("end_at", _aware(entry.end_at))
        msg = _check_range(start, end)
        if msg:
            errors["end_at"] = msg
        if "project_id" in cleaned and cleaned["project_id"] != entry.project_id:
            msg = _check_project(cleaned["project_id"])
            if msg:
                errors["project_id"] = msg
    if errors:
        return jsonify(errors=errors), 400

    for field, value in cleaned.items():
        setattr(entry, field, value)
    entry.compute_duration()
    db.session.commit()
    return jsonify(entry=entry.to_dict())


@bp.delete("/<int:entry_id>")
@jwt_required()
def delete_entry(entry_id):
    entry = _get_accessible_entry(entry_id)
    if entry is None:
        return jsonify(error="Entry not found"), 404
    db.session.delete(entry)
    db.session.commit()
    return "", 204