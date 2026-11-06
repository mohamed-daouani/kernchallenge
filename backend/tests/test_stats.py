def summary(client, auth, query="week=2026-11-04&tz=Europe/Brussels"):
    res = client.get(f"/api/dashboard/summary?{query}", headers=auth)
    assert res.status_code == 200, res.get_json()
    return res.get_json()


def test_weekly_summary(client, auth, create_entry, create_project, project_id):
    mobile = create_project(auth, name="Mobile", code="MOB").get_json()["project"]["id"]
    create_entry(auth, project_id, "2026-11-02T09:00:00Z", "2026-11-02T11:00:00Z")  # lundi, 120
    create_entry(auth, mobile, "2026-11-03T13:00:00Z", "2026-11-03T14:30:00Z")      # mardi, 90
    create_entry(auth, project_id, "2026-11-04T09:00:00Z", "2026-11-04T11:30:00Z")  # mercredi, 150

    body = summary(client, auth)

    assert body["week"]["start"] == "2026-11-02"
    assert body["week"]["end"] == "2026-11-08"
    assert body["week"]["tz"] == "Europe/Brussels"
    assert body["target_minutes"] == 2400
    assert body["total_minutes"] == 360
    assert body["remaining_minutes"] == 2040
    assert body["progress_percent"] == 15.0
    assert [(p["code"], p["minutes"]) for p in body["by_project"]] == [("INT", 270), ("MOB", 90)]
    assert [d["minutes"] for d in body["by_day"]] == [120, 90, 150, 0, 0, 0, 0]
    assert [d["date"] for d in body["by_day"]][0] == "2026-11-02"


def test_week_param_can_be_any_day_of_the_week(client, auth, create_entry, project_id):
    create_entry(auth, project_id, "2026-11-02T09:00:00Z", "2026-11-02T10:00:00Z")
    for day in ("2026-11-02", "2026-11-05", "2026-11-08"):  # lundi, jeudi, dimanche
        assert summary(client, auth, f"week={day}&tz=UTC")["total_minutes"] == 60
    assert summary(client, auth, "week=2026-11-09&tz=UTC")["total_minutes"] == 0  # lundi suivant


def test_entries_outside_the_week_are_ignored(client, auth, create_entry, project_id):
    create_entry(auth, project_id, "2026-11-01T09:00:00Z", "2026-11-01T10:00:00Z")  # dimanche d avant
    create_entry(auth, project_id, "2026-11-09T09:00:00Z", "2026-11-09T10:00:00Z")  # lundi d après
    assert summary(client, auth)["total_minutes"] == 0


def test_day_depends_on_timezone(client, auth, create_entry, project_id):
    # 23:30 UTC mardi = 00:30 mercredi à Bruxelles (UTC+1 en novembre)
    create_entry(auth, project_id, "2026-11-03T23:30:00Z", "2026-11-04T00:30:00Z")

    def minutes_by_day(tz):
        return [d["minutes"] for d in summary(client, auth, f"week=2026-11-03&tz={tz}")["by_day"]]

    assert minutes_by_day("UTC")[1] == 60              # mardi
    assert minutes_by_day("Europe/Brussels")[2] == 60  # mercredi


def test_stats_are_personal(client, auth, create_entry, project_id, make_user, login):
    create_entry(auth, project_id, "2026-11-02T09:00:00Z", "2026-11-02T10:00:00Z")
    make_user(email="other@test.dev")
    other = login("other@test.dev")
    assert summary(client, other)["total_minutes"] == 0
    assert summary(client, auth)["total_minutes"] == 60


def test_progress_can_exceed_100_percent(client, auth, create_entry, project_id, user):
    from app.extensions import db

    user.weekly_target_minutes = 60
    db.session.commit()
    create_entry(auth, project_id, "2026-11-02T09:00:00Z", "2026-11-02T11:00:00Z")  # 120 min
    body = summary(client, auth)
    assert body["target_minutes"] == 60
    assert body["remaining_minutes"] == 0
    assert body["progress_percent"] == 200.0


def test_empty_week(client, auth):
    body = summary(client, auth, "week=2026-01-07")
    assert body["total_minutes"] == 0
    assert body["remaining_minutes"] == 2400
    assert body["progress_percent"] == 0.0
    assert body["by_project"] == []
    assert len(body["by_day"]) == 7


def test_default_params(client, auth):
    body = client.get("/api/dashboard/summary", headers=auth).get_json()
    assert body["week"]["tz"] == "UTC"
    assert len(body["by_day"]) == 7


def test_invalid_params(client, auth):
    assert client.get("/api/dashboard/summary?tz=Mars/Base", headers=auth).status_code == 400
    assert client.get("/api/dashboard/summary?week=nope", headers=auth).status_code == 400


def test_requires_token(client):
    assert client.get("/api/dashboard/summary").status_code == 401
