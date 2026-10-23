"""Isolated acceptance harness for controlled template governance.

Run only with a disposable migrated database. It verifies that source-backed,
non-provisional approval is the only route to an active Check-in template.
"""

from fastapi.testclient import TestClient

from app.auth import StaffActor, get_current_actor
from app.db.models import Shop, User, UserRole
from app.db.session import SessionLocal
from app.main import app


DOCUMENT = {
    "name": "Controlled test template",
    "description": "Acceptance-harness content only.",
    "sections": [{"id": "safety", "name": "Safety", "items": [{"id": "brk_001", "name": "Brake condition", "type": "condition", "options": ["Good", "Worn"]}]}],
}


def as_actor(user_id, shop_id, role, name):
    app.dependency_overrides[get_current_actor] = lambda: StaffActor(user_id, shop_id, role, name, f"auth0|{name.lower()}")


def create_draft(client: TestClient, name: str, *, provisional: bool, source: bool):
    payload = {"name": name, "items": DOCUMENT, "is_provisional": provisional}
    if source:
        payload.update({"source_reference": f"controlled artifact for {name}", "source_sha256": ("a" if name.endswith("A") else "b") * 64})
    response = client.post("/checklists", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


with SessionLocal() as db:
    shop = Shop(name="Template Governance Shop")
    admin = User(shop=shop, auth0_id="auth0|admin", role=UserRole.admin, name="Admin", active=True)
    advisor = User(shop=shop, auth0_id="auth0|advisor", role=UserRole.advisor, name="Advisor", active=True)
    tech = User(shop=shop, auth0_id="auth0|tech", role=UserRole.technician, name="Technician", active=True)
    db.add_all([shop, admin, advisor, tech])
    db.commit()
    admin_id, advisor_id, tech_id, shop_id = admin.id, advisor.id, tech.id, shop.id

with TestClient(app) as client:
    as_actor(advisor_id, shop_id, UserRole.advisor, "Advisor")
    assert client.get("/check-in/options").status_code == 200
    assert client.get("/check-in/options").json()["checklists"] == []

    as_actor(admin_id, shop_id, UserRole.admin, "Admin")
    provisional = create_draft(client, "Provisional template", provisional=True, source=False)
    assert client.post(f"/checklists/{provisional['id']}/approve", json={"confirm_controlled_artifact": True}).status_code == 422

    draft_a = create_draft(client, "Controlled template A", provisional=False, source=True)
    assert client.patch(f"/checklists/{draft_a['id']}", json={"name": "Controlled template A revised"}).status_code == 200
    approved_a = client.post(f"/checklists/{draft_a['id']}/approve", json={"confirm_controlled_artifact": True})
    assert approved_a.status_code == 200, approved_a.text
    assert approved_a.json()["active_for_new_visits"] is True
    assert client.patch(f"/checklists/{draft_a['id']}", json={"name": "Attempted approved rewrite"}).status_code == 409

    draft_b = create_draft(client, "Controlled template B", provisional=False, source=True)
    approved_b = client.post(f"/checklists/{draft_b['id']}/approve", json={"confirm_controlled_artifact": True})
    assert approved_b.status_code == 200, approved_b.text
    registry = client.get("/checklists").json()
    active = [template for template in registry if template["active_for_new_visits"]]
    assert len(active) == 1 and active[0]["id"] == draft_b["id"], active

    as_actor(advisor_id, shop_id, UserRole.advisor, "Advisor")
    options = client.get("/check-in/options")
    assert options.status_code == 200 and [item["id"] for item in options.json()["checklists"]] == [draft_b["id"]], options.text
    stale_selection = client.post("/check-in/sessions", json={
        "vehicle_year": 2022,
        "vehicle_make": "Toyota",
        "vehicle_model": "Camry",
        "vehicle_vin": "4T1G11AK7NU123456",
        "vehicle_mileage": 25000,
        "customer_concern": "Customer reports brake pedal vibration.",
        "presence_mode": "waiter",
        "checklist_template_id": draft_a["id"],
        "assigned_technician_id": str(tech_id),
    })
    assert stale_selection.status_code == 422, stale_selection.text
    created = client.post("/check-in/sessions", json={
        "vehicle_year": 2022,
        "vehicle_make": "Toyota",
        "vehicle_model": "Camry",
        "vehicle_vin": "4T1G11AK7NU123456",
        "vehicle_mileage": 25000,
        "customer_concern": "Customer reports brake pedal vibration.",
        "presence_mode": "waiter",
        "assigned_technician_id": str(tech_id),
    })
    assert created.status_code == 201, created.text

    as_actor(admin_id, shop_id, UserRole.admin, "Admin")
    retired = client.post(f"/checklists/{draft_b['id']}/retire", json={"confirm_retirement": True})
    assert retired.status_code == 200 and retired.json()["lifecycle_status"] == "retired", retired.text
    assert retired.json()["active_for_new_visits"] is False

    as_actor(advisor_id, shop_id, UserRole.advisor, "Advisor")
    assert client.get("/check-in/options").json()["checklists"] == []
    blocked = client.post("/check-in/sessions", json={
        "vehicle_year": 2022,
        "vehicle_make": "Toyota",
        "vehicle_model": "Camry",
        "customer_concern": "Customer reports brake pedal vibration.",
        "presence_mode": "waiter",
        "assigned_technician_id": str(tech_id),
    })
    assert blocked.status_code == 422, blocked.text

app.dependency_overrides.clear()
print("PASS: only a source-hashed non-provisional approved template can be active for Check-in; drafts are editable and retired/legacy records cannot start visits")
