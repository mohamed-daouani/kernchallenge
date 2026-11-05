from app.extensions import db
from app.models import RevokedToken


def test_login_success(client, user):
    res = client.post("/api/auth/login", json={"email": user.email, "password": "password123"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["access_token"]
    assert body["user"]["email"] == user.email
    assert "password_hash" not in body["user"]


def test_login_updates_last_login(client, user):
    assert user.last_login_at is None
    client.post("/api/auth/login", json={"email": user.email, "password": "password123"})
    db.session.refresh(user)
    assert user.last_login_at is not None


def test_login_wrong_password_and_unknown_email_look_the_same(client, user):
    wrong = client.post("/api/auth/login", json={"email": user.email, "password": "nope"})
    unknown = client.post("/api/auth/login", json={"email": "ghost@test.dev", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json() == unknown.get_json()


def test_login_requires_fields(client):
    assert client.post("/api/auth/login", json={}).status_code == 400


def test_inactive_user_cannot_login(client, make_user):
    inactive = make_user(email="off@test.dev", is_active=False)
    res = client.post("/api/auth/login", json={"email": inactive.email, "password": "password123"})
    assert res.status_code == 403


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_current_user(client, auth, user):
    res = client.get("/api/auth/me", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["user"]["email"] == user.email


def test_logout_revokes_token(client, auth):
    assert client.post("/api/auth/logout", headers=auth).status_code == 200
    assert client.get("/api/auth/me", headers=auth).status_code == 401
    assert RevokedToken.query.count() == 1


VALID_SIGNUP = {
    "email": "New@Test.dev ",  # majuscules + espace : doit être normalisé
    "password": "password123",
    "first_name": "New",
    "last_name": "User",
}


def test_register_creates_user(client):
    res = client.post("/api/auth/register", json=VALID_SIGNUP)
    assert res.status_code == 201
    created = res.get_json()["user"]
    assert created["email"] == "new@test.dev"
    assert created["role"] == "user"
    assert "password_hash" not in created


def test_registered_user_can_login(client):
    client.post("/api/auth/register", json=VALID_SIGNUP)
    res = client.post("/api/auth/login", json={"email": "new@test.dev", "password": "password123"})
    assert res.status_code == 200


def test_register_ignores_role_in_payload(client):
    res = client.post("/api/auth/register", json={**VALID_SIGNUP, "role": "admin"})
    assert res.status_code == 201
    assert res.get_json()["user"]["role"] == "user"


def test_register_duplicate_email(client, user):
    res = client.post("/api/auth/register", json={**VALID_SIGNUP, "email": user.email.upper()})
    assert res.status_code == 409


def test_register_validation(client):
    res = client.post("/api/auth/register", json={"email": "nope", "password": "short"})
    assert res.status_code == 400
    assert set(res.get_json()["errors"]) == {"email", "password", "first_name", "last_name"}
