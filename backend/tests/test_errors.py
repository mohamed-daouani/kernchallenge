from datetime import timedelta

from flask_jwt_extended import create_access_token

from app.extensions import db


def test_unknown_route_returns_json_404(client):
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
    assert res.is_json
    assert res.get_json() == {"error": "Not Found"}


def test_wrong_method_returns_json_405(client):
    res = client.delete("/api/health")
    assert res.status_code == 405
    assert res.is_json
    assert "Allow" in res.headers


def test_unhandled_error_returns_json_500_without_details(app, client):
    @app.get("/api/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    res = client.get("/api/boom")
    assert res.status_code == 500
    assert res.get_json() == {"error": "Internal server error"}
    assert "secret internal detail" not in res.get_data(as_text=True)


def test_missing_token_returns_json_401(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.get_json() == {"error": "Authentication required"}


def test_invalid_token_returns_json_401(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert res.status_code == 401
    assert res.get_json() == {"error": "Invalid token"}


def test_expired_token_returns_json_401(client, user):
    token = create_access_token(identity=str(user.id), expires_delta=timedelta(seconds=-1))
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.get_json() == {"error": "Token has expired"}


def test_revoked_token_returns_json_401(client, auth):
    client.post("/api/auth/logout", headers=auth)
    res = client.get("/api/auth/me", headers=auth)
    assert res.status_code == 401
    assert res.get_json() == {"error": "Token has been revoked"}


def test_token_of_disabled_account_is_rejected(client, auth, user):
    user.is_active = False
    db.session.commit()
    res = client.get("/api/auth/me", headers=auth)
    assert res.status_code == 401
    assert res.get_json() == {"error": "User not found or disabled"}
