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