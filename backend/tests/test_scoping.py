"""Shop and assignment scoping: nobody reads or writes another shop's records."""

from app.db.models import ChecklistTemplate, InspectionSession, SessionStatus, TemplateLifecycleStatus

DRAFT_BODY = {
    "name": "New draft",
    "items": {
        "name": "Draft",
        "sections": [{"id": "s1", "name": "S1", "items": [{"id": "i1", "name": "Item 1"}]}],
    },
    "is_provisional": False,
    "source_reference": "controlled sheet rev 2",
    "source_sha256": "c" * 64,
}


# --- sessions -----------------------------------------------------------------


def test_technician_lists_only_their_own_sessions(client, world, bearer):
    mine = world.legacy_session(world.tech_a1)
    world.legacy_session(world.tech_a2)
    world.legacy_session(world.tech_b)
    ids = {row["id"] for row in client.get("/sessions", headers=bearer(world.tech_a1)).json()}
    assert ids == {str(mine.id)}


def test_advisor_lists_their_whole_shop_and_nothing_else(client, world, bearer):
    a1 = world.legacy_session(world.tech_a1)
    a2 = world.legacy_session(world.tech_a2)
    world.legacy_session(world.tech_b)
    ids = {row["id"] for row in client.get("/sessions", headers=bearer(world.advisor_a)).json()}
    assert ids == {str(a1.id), str(a2.id)}


def test_technician_filter_cannot_widen_a_technicians_view(client, world, bearer):
    world.legacy_session(world.tech_a2)
    response = client.get(f"/sessions?technician_id={world.tech_a2.id}", headers=bearer(world.tech_a1))
    assert response.json() == []


def test_other_shop_session_is_not_found(client, world, bearer):
    other = world.legacy_session(world.tech_b)
    for path in (f"/sessions/{other.id}", f"/sessions/{other.id}/report", f"/sessions/{other.id}/inspection-workspace"):
        assert client.get(path, headers=bearer(world.advisor_a)).status_code == 404, path
    assert client.post(f"/sessions/{other.id}/findings", json={"transcript": "x"}, headers=bearer(world.tech_a1)).status_code == 404


def test_unassigned_technician_in_same_shop_is_refused(client, world, bearer):
    session = world.legacy_session(world.tech_a1)
    assert client.get(f"/sessions/{session.id}", headers=bearer(world.tech_a2)).status_code == 403
    assert client.post(f"/sessions/{session.id}/findings", json={"transcript": "x"}, headers=bearer(world.tech_a2)).status_code == 403
    assert client.post(f"/sessions/{session.id}/complete", headers=bearer(world.tech_a2)).status_code == 403


def test_unknown_status_filter_is_422_not_500(client, world, bearer):
    assert client.get("/sessions?status=nope", headers=bearer(world.advisor_a)).status_code == 422


def test_cross_shop_advisor_review_and_current_visit_are_not_found(client, world, bearer, db):
    session = world.template_session(world.tech_a1, world.template_a, status=SessionStatus.submitted)
    assert client.get(f"/sessions/{session.id}/advisor-review", headers=bearer(world.admin_b)).status_code == 404
    assert client.get(f"/sessions/{session.id}/current-visit", headers=bearer(world.admin_b)).status_code == 404


# --- templates ------------------------------------------------------------------


def test_admin_lists_only_their_shops_templates(client, world, bearer):
    rows = client.get("/checklists", headers=bearer(world.admin_a)).json()
    assert {row["id"] for row in rows} == {str(world.template_a.id)}


def test_admin_cannot_read_or_change_another_shops_template(client, world, bearer):
    other = world.template_b.id
    headers = bearer(world.admin_a)
    assert client.get(f"/checklists/{other}", headers=headers).status_code == 404
    assert client.patch(f"/checklists/{other}", json={"name": "mine now"}, headers=headers).status_code == 404
    assert client.post(f"/checklists/{other}/retire", json={"confirm_retirement": True}, headers=headers).status_code == 404
    assert client.post(f"/checklists/{other}/approve", json={"confirm_controlled_artifact": True}, headers=headers).status_code == 404


def test_new_template_belongs_to_the_creators_shop(client, world, bearer, db):
    created = client.post("/checklists", json=DRAFT_BODY, headers=bearer(world.admin_a))
    assert created.status_code == 201, created.text
    assert str(db.get(ChecklistTemplate, created.json()["id"]).shop_id) == str(world.shop_a.id)


def test_approving_in_one_shop_does_not_deactivate_another_shops_template(client, world, bearer, db):
    draft = client.post("/checklists", json=DRAFT_BODY, headers=bearer(world.admin_a)).json()
    approved = client.post(f"/checklists/{draft['id']}/approve", json={"confirm_controlled_artifact": True}, headers=bearer(world.admin_a))
    assert approved.status_code == 200, approved.text
    db.expire_all()
    assert db.get(ChecklistTemplate, world.template_b.id).active_for_new_visits is True
    assert db.get(ChecklistTemplate, world.template_a.id).active_for_new_visits is False
    assert db.get(ChecklistTemplate, draft["id"]).active_for_new_visits is True


def test_non_admin_staff_cannot_read_templates(client, world, bearer):
    assert client.get(f"/checklists/{world.template_a.id}", headers=bearer(world.tech_a1)).status_code == 403
    assert client.get("/checklists", headers=bearer(world.advisor_a)).status_code == 403


# --- check-in -------------------------------------------------------------------


CHECKIN = {
    "vehicle_year": 2017,
    "vehicle_make": "Toyota",
    "vehicle_model": "Highlander",
    "customer_concern": "Grinding noise",
    "presence_mode": "waiter",
}


def test_checkin_options_offer_only_the_shops_own_template_and_technicians(client, world, bearer):
    options = client.get("/check-in/options", headers=bearer(world.advisor_a)).json()
    assert [row["id"] for row in options["checklists"]] == [str(world.template_a.id)]
    assert {row["id"] for row in options["technicians"]} == {str(world.tech_a1.id), str(world.tech_a2.id)}


def test_checkin_uses_the_shops_own_active_template(client, world, bearer, db):
    response = client.post("/check-in/sessions", json={**CHECKIN, "assigned_technician_id": str(world.tech_a1.id)}, headers=bearer(world.advisor_a))
    assert response.status_code == 201, response.text
    session = db.get(InspectionSession, response.json()["id"])
    assert session.checklist_template_id == world.template_a.id
    assert session.shop_id == world.shop_a.id
    assert session.status == SessionStatus.pending


def test_checkin_refuses_another_shops_technician(client, world, bearer):
    response = client.post("/check-in/sessions", json={**CHECKIN, "assigned_technician_id": str(world.tech_b.id)}, headers=bearer(world.advisor_a))
    assert response.status_code == 422


def test_checkin_fails_when_only_another_shop_has_an_active_template(client, world, bearer, db):
    db.get(ChecklistTemplate, world.template_a.id).active_for_new_visits = False
    db.commit()
    response = client.post("/check-in/sessions", json={**CHECKIN, "assigned_technician_id": str(world.tech_a1.id)}, headers=bearer(world.advisor_a))
    assert response.status_code == 422
    assert client.get("/check-in/options", headers=bearer(world.advisor_a)).json()["checklists"] == []


def test_checkin_rejects_a_body_shop_id(client, world, bearer):
    body = {**CHECKIN, "assigned_technician_id": str(world.tech_a1.id), "shop_id": str(world.shop_b.id)}
    assert client.post("/check-in/sessions", json=body, headers=bearer(world.advisor_a)).status_code == 422


def test_technician_cannot_use_checkin(client, world, bearer):
    assert client.get("/check-in/options", headers=bearer(world.tech_a1)).status_code == 403
