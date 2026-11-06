from app.models import UserRole


def test_create_project_normalizes_code(create_project, auth):
    res = create_project(auth, code="int")
    assert res.status_code == 201
    project = res.get_json()["project"]
    assert project["code"] == "INT"
    assert project["status"] == "active"


def test_duplicate_code_is_refused(create_project, auth):
    create_project(auth)
    res = create_project(auth, name="Autre")
    assert res.status_code == 409
    assert "code" in res.get_json()["errors"]


def test_invalid_payload(create_project, auth):
    res = create_project(auth, name="", code="TOOLONG", status="nope")
    assert res.status_code == 400
    assert set(res.get_json()["errors"]) == {"name", "code", "status"}


def test_json_body_required(client, auth):
    res = client.post("/api/projects", data="pas du json", headers=auth)
    assert res.status_code == 400


def test_requires_token(client):
    assert client.get("/api/projects").status_code == 401


def test_list_projects_sorted_by_name(client, create_project, auth):
    create_project(auth, name="Zeta", code="ZET")
    create_project(auth, name="Alpha", code="ALP")
    names = [p["name"] for p in client.get("/api/projects", headers=auth).get_json()["projects"]]
    assert names == ["Alpha", "Zeta"]


def test_filter_by_status(client, create_project, auth):
    create_project(auth, name="Actif", code="ACT")
    archived = create_project(auth, name="Vieux", code="OLD", status="archived")
    assert archived.status_code == 201

    def names(query):
        res = client.get(f"/api/projects?{query}", headers=auth)
        assert res.status_code == 200
        return [p["name"] for p in res.get_json()["projects"]]

    assert names("status=active") == ["Actif"]
    assert names("status=archived") == ["Vieux"]
    assert client.get("/api/projects?status=nope", headers=auth).status_code == 400


def test_get_project(client, auth, project_id):
    res = client.get(f"/api/projects/{project_id}", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["project"]["id"] == project_id


def test_get_unknown_project(client, auth):
    assert client.get("/api/projects/999999", headers=auth).status_code == 404


def test_update_project(client, auth, project_id):
    res = client.patch(
        f"/api/projects/{project_id}",
        json={"name": "Renommé", "status": "archived", "description": None},
        headers=auth,
    )
    assert res.status_code == 200
    project = res.get_json()["project"]
    assert project["name"] == "Renommé"
    assert project["status"] == "archived"
    assert project["code"] == "INT"  # champ non envoyé : inchangé


def test_update_to_existing_code_is_refused(client, create_project, auth):
    create_project(auth, name="Un", code="ONE")
    second = create_project(auth, name="Deux", code="TWO").get_json()["project"]["id"]
    res = client.patch(f"/api/projects/{second}", json={"code": "one"}, headers=auth)
    assert res.status_code == 409


def test_update_with_invalid_data(client, auth, project_id):
    res = client.patch(f"/api/projects/{project_id}", json={"name": ""}, headers=auth)
    assert res.status_code == 400
    assert "name" in res.get_json()["errors"]


def test_users_cannot_access_each_others_projects(client, auth, project_id, make_user, login):
    make_user(email="other@test.dev")
    other = login("other@test.dev")

    assert client.get("/api/projects", headers=other).get_json()["projects"] == []
    assert client.get(f"/api/projects/{project_id}", headers=other).status_code == 404
    assert client.patch(f"/api/projects/{project_id}", json={"name": "Hack"}, headers=other).status_code == 404
    assert client.delete(f"/api/projects/{project_id}", headers=other).status_code == 404


def test_admin_sees_all_projects(client, project_id, make_user, login):
    make_user(email="admin@test.dev", role=UserRole.admin)
    admin = login("admin@test.dev")
    projects = client.get("/api/projects", headers=admin).get_json()["projects"]
    assert [p["id"] for p in projects] == [project_id]


def test_delete_project_without_entries(client, auth, project_id):
    assert client.delete(f"/api/projects/{project_id}", headers=auth).status_code == 204
    assert client.get(f"/api/projects/{project_id}", headers=auth).status_code == 404


def test_delete_project_with_entries_is_refused(client, auth, project_id, create_entry):
    create_entry(auth, project_id, "2026-11-04T09:00:00Z", "2026-11-04T10:00:00Z")
    res = client.delete(f"/api/projects/{project_id}", headers=auth)
    assert res.status_code == 409
    assert client.get(f"/api/projects/{project_id}", headers=auth).status_code == 200
