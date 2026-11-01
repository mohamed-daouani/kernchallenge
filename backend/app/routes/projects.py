from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Project, ProjectStatus, TimeEntry, UserRole

bp = Blueprint("projects", __name__)


def _is_admin():
    return current_user.role == UserRole.admin


def _get_accessible_project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None
    if project.owner_id != current_user.id and not _is_admin():
        return None
    return project


def _validate(data, partial=False):
    cleaned, errors = {}, {}

    if not partial or "name" in data:
        name = data.get("name")
        name = name.strip() if isinstance(name, str) else ""
        if not name or len(name) > 120:
            errors["name"] = "Required, 120 characters max"
        else:
            cleaned["name"] = name

    if not partial or "code" in data:
        code = data.get("code")
        code = code.strip().upper() if isinstance(code, str) else ""
        if not (1 <= len(code) <= 4) or not code.isalnum():
            errors["code"] = "1 to 4 letters or digits"
        else:
            cleaned["code"] = code

    if "description" in data:
        desc = data["description"]
        if desc is not None and not isinstance(desc, str):
            errors["description"] = "Must be a string or null"
        else:
            cleaned["description"] = desc

    if "status" in data:
        try:
            cleaned["status"] = ProjectStatus(data["status"])
        except ValueError:
            allowed = [s.value for s in ProjectStatus]
            errors["status"] = f"Must be one of {allowed}"

    return cleaned, errors


@bp.get("")
@jwt_required()
def list_projects():
    query = Project.query
    if not _is_admin():
        query = query.filter_by(owner_id=current_user.id)

    status = request.args.get("status")
    if status:
        try:
            query = query.filter_by(status=ProjectStatus(status))
        except ValueError:
            return jsonify(error="Invalid status filter"), 400

    projects = query.order_by(Project.name).all()
    return jsonify(projects=[p.to_dict() for p in projects])


@bp.post("")
@jwt_required()
def create_project():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON body required"), 400

    cleaned, errors = _validate(data)
    if errors:
        return jsonify(errors=errors), 400

    project = Project(owner_id=current_user.id, **cleaned)
    db.session.add(project)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(errors={"code": "This code is already used"}), 409

    return jsonify(project=project.to_dict()), 201


@bp.get("/<int:project_id>")
@jwt_required()
def get_project(project_id):
    project = _get_accessible_project(project_id)
    if project is None:
        return jsonify(error="Project not found"), 404
    return jsonify(project=project.to_dict())


@bp.patch("/<int:project_id>")
@jwt_required()
def update_project(project_id):
    project = _get_accessible_project(project_id)
    if project is None:
        return jsonify(error="Project not found"), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON body required"), 400

    cleaned, errors = _validate(data, partial=True)
    if errors:
        return jsonify(errors=errors), 400

    for field, value in cleaned.items():
        setattr(project, field, value)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(errors={"code": "This code is already used"}), 409

    return jsonify(project=project.to_dict())


@bp.delete("/<int:project_id>")
@jwt_required()
def delete_project(project_id):
    project = _get_accessible_project(project_id)
    if project is None:
        return jsonify(error="Project not found"), 404

    has_entries = db.session.query(
        TimeEntry.query.filter_by(project_id=project.id).exists()
    ).scalar()
    if has_entries:
        return jsonify(
            error="Project has time entries. Set its status to 'archived' instead."
        ), 409

    db.session.delete(project)
    db.session.commit()
    return "", 204