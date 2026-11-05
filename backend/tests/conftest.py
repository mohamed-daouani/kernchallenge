import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User, UserRole

PASSWORD = "password123"


@pytest.fixture
def app():
    uri = TestConfig.SQLALCHEMY_DATABASE_URI or ""
    # Sécurité : drop_all() efface tout, donc on refuse de tourner hors d'une base *_test
    assert uri.rsplit("/", 1)[-1].endswith("_test"), "TEST_DATABASE_URL must point to a *_test database"

    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()  # libère les verrous avant de supprimer les tables
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    def _make(email="user@test.dev", role=UserRole.user, **extra):
        user = User(email=email, first_name="Test", last_name="User", role=role, **extra)
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        return user

    return _make


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def login(client):
    def _login(email):
        res = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert res.status_code == 200, res.get_json()
        return {"Authorization": f"Bearer {res.get_json()['access_token']}"}

    return _login


@pytest.fixture
def auth(user, login):
    """Headers d'authentification de l'utilisateur de test."""
    return login(user.email)


@pytest.fixture
def create_project(client):
    def _create(headers, name="Intranet", code="INT", **extra):
        payload = {"name": name, "code": code, **extra}
        return client.post("/api/projects", json=payload, headers=headers)

    return _create


@pytest.fixture
def project_id(create_project, auth):
    return create_project(auth).get_json()["project"]["id"]


@pytest.fixture
def create_entry(client):
    def _create(headers, project_id, start, end, description="Work", **extra):
        payload = {
            "project_id": project_id,
            "description": description,
            "start_at": start,
            "end_at": end,
            **extra,
        }
        return client.post("/api/time-entries", json=payload, headers=headers)

    return _create