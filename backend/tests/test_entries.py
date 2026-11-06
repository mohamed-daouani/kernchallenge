START = "2026-11-04T09:00:00Z"
END = "2026-11-04T10:30:00Z"


def test_create_entry_computes_duration(create_entry, auth, project_id):
    res = create_entry(auth, project_id, START, END)
    assert res.status_code == 201
    entry = res.get_json()["entry"]
    assert entry["duration_minutes"] == 90
    assert entry["project"]["id"] == project_id
    assert entry["project"]["code"] == "INT"


def test_create_entry_accepts_timezone_offsets(create_entry, auth, project_id):
    # 10:00+01:00 == 09:00Z : la durée doit rester 90 minutes
    res = create_entry(auth, project_id, "2026-11-04T10:00:00+01:00", "2026-11-04T11:30:00+01:00")
    assert res.status_code == 201
    assert res.get_json()["entry"]["duration_minutes"] == 90


def test_create_entry_requires_token(client):
    assert client.post("/api/time-entries", json={}).status_code == 401


def test_missing_fields(create_entry, auth, client):
    res = client.post("/api/time-entries", json={}, headers=auth)
    assert res.status_code == 400
    assert set(res.get_json()["errors"]) == {"project_id", "description", "start_at", "end_at"}


def test_end_before_start_is_refused(create_entry, auth, project_id):
    res = create_entry(auth, project_id, END, START)
    assert res.status_code == 400
    assert "end_at" in res.get_json()["errors"]


def test_date_without_timezone_is_refused(create_entry, auth, project_id):
    res = create_entry(auth, project_id, "2026-11-04T09:00:00", END)
    assert res.status_code == 400
    assert "start_at" in res.get_json()["errors"]


def test_entry_cannot_exceed_24_hours(create_entry, auth, project_id):
    assert create_entry(auth, project_id, START, "2026-11-05T09:00:00Z").status_code == 201
    assert create_entry(auth, project_id, START, "2026-11-05T09:00:01Z").status_code == 400


def test_cannot_log_time_on_archived_project(client, create_entry, auth, project_id):
    client.patch(f"/api/projects/{project_id}", json={"status": "archived"}, headers=auth)
    res = create_entry(auth, project_id, START, END)
    assert res.status_code == 400
    assert "project_id" in res.get_json()["errors"]


def test_cannot_log_time_on_unknown_project(create_entry, auth):
    res = create_entry(auth, 999999, START, END)
    assert res.status_code == 400
    assert "project_id" in res.get_json()["errors"]


def test_cannot_log_time_on_someone_elses_project(create_entry, project_id, make_user, login):
    make_user(email="other@test.dev")
    other = login("other@test.dev")
    res = create_entry(other, project_id, START, END)
    assert res.status_code == 400
    assert "project_id" in res.get_json()["errors"]


def test_list_filters(client, create_entry, create_project, auth, project_id):
    mobile = create_project(auth, name="Mobile", code="MOB").get_json()["project"]["id"]
    create_entry(auth, project_id, "2026-11-02T09:00:00Z", "2026-11-02T10:00:00Z")
    create_entry(auth, project_id, "2026-11-04T09:00:00Z", "2026-11-04T10:00:00Z")
    create_entry(auth, mobile, "2026-11-04T13:00:00Z", "2026-11-04T14:00:00Z")

    def fetch(query=""):
        res = client.get(f"/api/time-entries?{query}", headers=auth)
        assert res.status_code == 200
        return res.get_json()

    assert len(fetch()["entries"]) == 3
    assert len(fetch(f"project_id={project_id}")["entries"]) == 2
    assert len(fetch("from=2026-11-03")["entries"]) == 2
    assert len(fetch("from=2026-11-02&to=2026-11-03")["entries"]) == 1
    assert len(fetch(f"project_id={mobile}&from=2026-11-04")["entries"]) == 1


def test_list_is_sorted_newest_first(client, create_entry, auth, project_id):
    create_entry(auth, project_id, "2026-11-02T09:00:00Z", "2026-11-02T10:00:00Z", description="ancienne")
    create_entry(auth, project_id, "2026-11-04T09:00:00Z", "2026-11-04T10:00:00Z", description="récente")
    entries = client.get("/api/time-entries", headers=auth).get_json()["entries"]
    assert [e["description"] for e in entries] == ["récente", "ancienne"]


def test_pagination(client, create_entry, auth, project_id):
    for day in (2, 3, 4):
        create_entry(auth, project_id, f"2026-11-0{day}T09:00:00Z", f"2026-11-0{day}T10:00:00Z")
    body = client.get("/api/time-entries?per_page=2&page=1", headers=auth).get_json()
    assert len(body["entries"]) == 2
    assert body["total"] == 3
    assert body["page"] == 1
    page2 = client.get("/api/time-entries?per_page=2&page=2", headers=auth).get_json()
    assert len(page2["entries"]) == 1


def test_invalid_filters(client, auth):
    assert client.get("/api/time-entries?from=nope", headers=auth).status_code == 400
    assert client.get("/api/time-entries?to=nope", headers=auth).status_code == 400
    assert client.get("/api/time-entries?project_id=abc", headers=auth).status_code == 400


def test_get_entry(client, create_entry, auth, project_id):
    entry_id = create_entry(auth, project_id, START, END).get_json()["entry"]["id"]
    res = client.get(f"/api/time-entries/{entry_id}", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["entry"]["id"] == entry_id


def test_update_recomputes_duration(client, create_entry, auth, project_id):
    entry_id = create_entry(auth, project_id, START, END).get_json()["entry"]["id"]

    res = client.patch(f"/api/time-entries/{entry_id}", json={"end_at": "2026-11-04T11:00:00Z"}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["entry"]["duration_minutes"] == 120

    # une fin antérieure au début existant est refusée
    res = client.patch(f"/api/time-entries/{entry_id}", json={"end_at": "2026-11-04T08:00:00Z"}, headers=auth)
    assert res.status_code == 400


def test_update_description_only_keeps_duration(client, create_entry, auth, project_id):
    entry_id = create_entry(auth, project_id, START, END).get_json()["entry"]["id"]
    res = client.patch(f"/api/time-entries/{entry_id}", json={"description": "Nouveau texte"}, headers=auth)
    assert res.status_code == 200
    entry = res.get_json()["entry"]
    assert entry["description"] == "Nouveau texte"
    assert entry["duration_minutes"] == 90


def test_move_entry_to_another_project(client, create_entry, create_project, auth, project_id):
    other = create_project(auth, name="Mobile", code="MOB").get_json()["project"]["id"]
    entry_id = create_entry(auth, project_id, START, END).get_json()["entry"]["id"]
    res = client.patch(f"/api/time-entries/{entry_id}", json={"project_id": other}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["entry"]["project"]["id"] == other


def test_can_edit_entry_of_archived_project(client, create_entry, auth, project_id):
    entry_id = create_entry(auth, project_id, START, END).get_json()["entry"]["id"]
    client.patch(f"/api/projects/{project_id}", json={"status": "archived"}, headers=auth)
    res = client.patch(f"/api/time-entries/{entry_id}", json={"description": "Correction"}, headers=auth)
    assert res.status_code == 200


def test_delete_entry(client, create_entry, auth, project_id):
    entry_id = create_entry(auth, project_id, START, END).get_json()["entry"]["id"]
    assert client.delete(f"/api/time-entries/{entry_id}", headers=auth).status_code == 204
    assert client.get(f"/api/time-entries/{entry_id}", headers=auth).status_code == 404


def test_users_cannot_access_each_others_entries(client, create_entry, auth, project_id, make_user, login):
    entry_id = create_entry(auth, project_id, START, END).get_json()["entry"]["id"]
    make_user(email="other@test.dev")
    other = login("other@test.dev")

    assert client.get("/api/time-entries", headers=other).get_json()["entries"] == []
    assert client.get(f"/api/time-entries/{entry_id}", headers=other).status_code == 404
    assert client.patch(f"/api/time-entries/{entry_id}", json={"description": "x"}, headers=other).status_code == 404
    assert client.delete(f"/api/time-entries/{entry_id}", headers=other).status_code == 404
