"""Migration c9d0e1f2a3b4 (shop-owned templates) on pre-existing data.

Runs last (file name): it rebuilds the schema at b7c8d9e0f1a2, seeds data the
way production could have it, upgrades to head, then leaves an empty head
schema behind for anything that runs after it.
"""

import pytest
from sqlalchemy import text

from app.db.session import engine

from .conftest import alembic_upgrade, reset_schema_to

SHOP_A = "11111111-1111-1111-1111-111111111111"
SHOP_B = "22222222-2222-2222-2222-222222222222"
ADMIN_A = "aaaaaaaa-0000-0000-0000-000000000001"
TECH_A = "aaaaaaaa-0000-0000-0000-000000000002"
TECH_B = "bbbbbbbb-0000-0000-0000-000000000001"
USED_MOSTLY_BY_B = "cccccccc-0000-0000-0000-000000000001"
ACTIVE = "cccccccc-0000-0000-0000-000000000002"
UNUSED = "cccccccc-0000-0000-0000-000000000003"


def _seed(connection, shops=(SHOP_A, SHOP_B)):
    connection.execute(text("INSERT INTO shops (id, name, created_at) VALUES (:a, 'A', '2026-01-01')"), {"a": SHOP_A})
    users = [(ADMIN_A, SHOP_A, "admin"), (TECH_A, SHOP_A, "technician")]
    if SHOP_B in shops:
        connection.execute(text("INSERT INTO shops (id, name, created_at) VALUES (:b, 'B', '2026-02-01')"), {"b": SHOP_B})
        users.append((TECH_B, SHOP_B, "technician"))
    for user_id, shop_id, role in users:
        connection.execute(
            text("INSERT INTO users (id, shop_id, auth0_id, role, name, active) VALUES (:id, :shop, :sub, :role, :name, true)"),
            {"id": user_id, "shop": shop_id, "sub": f"auth0|{user_id}", "role": role, "name": user_id[:8]},
        )
    connection.execute(
        text(
            "INSERT INTO checklist_templates (id, name, version, items, lifecycle_status, is_provisional, locked_provisional, "
            "active_for_new_visits, source_reference, source_sha256, approved_at, approved_by_user_id, created_at) VALUES "
            "(:t1, 'Used by B mostly', 1, '{\"items\": []}', 'draft', true, true, false, null, null, null, null, '2026-01-01'),"
            "(:t2, 'Active approved', 2, '{\"sections\": []}', 'approved', false, false, true, 'ref', repeat('a', 64), '2026-03-01', :admin, '2026-01-02'),"
            "(:t3, 'Unused', 1, '{\"items\": []}', 'draft', true, true, false, null, null, null, null, '2026-01-03')"
        ),
        {"t1": USED_MOSTLY_BY_B, "t2": ACTIVE, "t3": UNUSED, "admin": ADMIN_A},
    )
    sessions = [(TECH_A, SHOP_A, USED_MOSTLY_BY_B), (TECH_A, SHOP_A, ACTIVE)]
    if SHOP_B in shops:
        sessions += [(TECH_B, SHOP_B, USED_MOSTLY_BY_B), (TECH_B, SHOP_B, USED_MOSTLY_BY_B)]
    for number, (tech, shop, template) in enumerate(sessions, start=1):
        connection.execute(
            text(
                "INSERT INTO inspection_sessions (id, shop_id, technician_id, checklist_template_id, status, started_at) "
                "VALUES (:id, :shop, :tech, :template, 'completed', now())"
            ),
            {"id": f"dddddddd-0000-0000-0000-{number:012d}", "shop": shop, "tech": tech, "template": template},
        )


@pytest.fixture
def restore_head():
    yield
    reset_schema_to("head")


def test_single_shop_only_fills_in_shop_id(restore_head):
    reset_schema_to("b7c8d9e0f1a2")
    with engine.begin() as connection:
        _seed(connection, shops=(SHOP_A,))
        before = connection.execute(text("SELECT id, checklist_template_id FROM inspection_sessions ORDER BY id")).fetchall()
    alembic_upgrade("head")
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT id::text, shop_id::text FROM checklist_templates ORDER BY id")).fetchall()
        after = connection.execute(text("SELECT id, checklist_template_id FROM inspection_sessions ORDER BY id")).fetchall()
    assert rows == [(USED_MOSTLY_BY_B, SHOP_A), (ACTIVE, SHOP_A), (UNUSED, SHOP_A)]
    assert after == before


def test_two_shops_each_keep_every_template_and_sessions_stay_in_shop(restore_head):
    reset_schema_to("b7c8d9e0f1a2")
    with engine.begin() as connection:
        _seed(connection)
    alembic_upgrade("head")
    with engine.connect() as connection:
        templates = connection.execute(
            text("SELECT id::text, shop_id::text, name, active_for_new_visits, lifecycle_status::text, source_sha256 FROM checklist_templates")
        ).fetchall()
        mismatched = connection.execute(
            text(
                "SELECT count(*) FROM inspection_sessions s JOIN checklist_templates t ON t.id = s.checklist_template_id "
                "WHERE t.shop_id <> s.shop_id"
            )
        ).scalar_one()
        null_owner = connection.execute(text("SELECT count(*) FROM checklist_templates WHERE shop_id IS NULL")).scalar_one()

    by_shop = {}
    for template_id, shop_id, name, active, lifecycle, sha in templates:
        by_shop.setdefault(shop_id, {})[name] = (template_id, active, lifecycle, sha)
    # Every shop still sees all three templates.
    assert set(by_shop[SHOP_A]) == set(by_shop[SHOP_B]) == {"Used by B mostly", "Active approved", "Unused"}
    # Originals go to the heaviest user (else the earliest shop); others get copies.
    assert by_shop[SHOP_B]["Used by B mostly"][0] == USED_MOSTLY_BY_B
    assert by_shop[SHOP_A]["Active approved"][0] == ACTIVE
    assert by_shop[SHOP_A]["Unused"][0] == UNUSED
    # Copies keep governance state and provenance.
    assert by_shop[SHOP_B]["Active approved"][1:] == by_shop[SHOP_A]["Active approved"][1:]
    assert mismatched == 0
    assert null_owner == 0


def test_one_active_template_per_shop_is_enforced(restore_head):
    reset_schema_to("b7c8d9e0f1a2")
    with engine.begin() as connection:
        _seed(connection)
    alembic_upgrade("head")
    with pytest.raises(Exception, match="uq_checklist_templates_one_active_per_shop"):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE checklist_templates SET active_for_new_visits = true, lifecycle_status = 'approved', is_provisional = false, "
                     "locked_provisional = false, source_reference = 'ref-two', source_sha256 = repeat('b', 64), approved_at = now(), "
                     "approved_by_user_id = :admin WHERE id = :id"),
                {"admin": ADMIN_A, "id": UNUSED},
            )


def test_a_session_cannot_point_at_another_shops_template(restore_head):
    reset_schema_to("b7c8d9e0f1a2")
    with engine.begin() as connection:
        _seed(connection)
    alembic_upgrade("head")
    with pytest.raises(Exception, match="fk_inspection_sessions_checklist_template_shop"):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE inspection_sessions SET checklist_template_id = :b_owned WHERE shop_id = :a"),
                {"b_owned": USED_MOSTLY_BY_B, "a": SHOP_A},
            )
