"""make checklist templates shop-owned

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
Create Date: 2026-10-22 23:30:00.000000

Templates were global: any shop's admin could edit, approve or retire every
template, and approving one deactivated the single active template for every
shop. This migration gives each template an owning shop.

Backfill (additive; nothing is dropped, every shop keeps every template it
could see before):

* Each existing template is owned by the shop whose inspection sessions use
  it most (ties: earliest shop). A template no session uses goes to the
  earliest shop.
* Every other shop gets its own copy with identical content and governance
  columns (lifecycle, provisional flags, active flag, source reference/hash,
  approval/retirement audit), so lifecycle state and Current Visit provenance
  checks are unchanged.
* Sessions in those other shops that referenced the original are re-pointed
  to their shop's copy. The copy has the same content, version and
  provenance, and the session keeps its own template snapshot, so nothing a
  technician or advisor recorded changes.

With one shop (production and the test stack today) this only fills in
shop_id: no copies are made and no session row is touched.

Then:
* the global "single active template" index becomes one active template
  per shop;
* (checklist_template_id, shop_id) on inspection_sessions must reference a
  template in the same shop (same pattern as the vehicle/customer FKs).
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "c9d0e1f2a3b4"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None

_COPY_COLUMNS = (
    "name",
    "vehicle_filter",
    "version",
    "items",
    "lifecycle_status",
    "is_provisional",
    "locked_provisional",
    "active_for_new_visits",
    "source_reference",
    "source_sha256",
    "approved_at",
    "approved_by_user_id",
    "retired_at",
    "retired_by_user_id",
    "created_at",
    "updated_at",
)


def _backfill(bind) -> None:
    shops = [row[0] for row in bind.execute(sa.text("SELECT id FROM shops ORDER BY created_at ASC NULLS LAST, id ASC"))]
    if not shops:
        return
    templates = [row[0] for row in bind.execute(sa.text("SELECT id FROM checklist_templates WHERE shop_id IS NULL ORDER BY created_at ASC NULLS LAST, id ASC"))]
    columns = ", ".join(_COPY_COLUMNS)
    for template_id in templates:
        usage = bind.execute(
            sa.text(
                "SELECT s.shop_id FROM inspection_sessions s JOIN shops sh ON sh.id = s.shop_id "
                "WHERE s.checklist_template_id = :template_id "
                "GROUP BY s.shop_id, sh.created_at ORDER BY count(*) DESC, sh.created_at ASC NULLS LAST, s.shop_id ASC"
            ),
            {"template_id": template_id},
        ).fetchall()
        owner = usage[0][0] if usage else shops[0]
        bind.execute(
            sa.text("UPDATE checklist_templates SET shop_id = :shop_id WHERE id = :template_id"),
            {"shop_id": owner, "template_id": template_id},
        )
        for shop_id in shops:
            if shop_id == owner:
                continue
            copy_id = uuid.uuid4()
            bind.execute(
                sa.text(
                    f"INSERT INTO checklist_templates (id, shop_id, {columns}) "
                    f"SELECT :copy_id, :shop_id, {columns} FROM checklist_templates WHERE id = :template_id"
                ),
                {"copy_id": copy_id, "shop_id": shop_id, "template_id": template_id},
            )
            bind.execute(
                sa.text(
                    "UPDATE inspection_sessions SET checklist_template_id = :copy_id "
                    "WHERE checklist_template_id = :template_id AND shop_id = :shop_id"
                ),
                {"copy_id": copy_id, "template_id": template_id, "shop_id": shop_id},
            )


def upgrade():
    op.add_column("checklist_templates", sa.Column("shop_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_checklist_templates_shop", "checklist_templates", "shops", ["shop_id"], ["id"])
    op.create_index("ix_checklist_templates_shop_id", "checklist_templates", ["shop_id"])

    # The global single-active index would reject one active copy per shop.
    op.execute("DROP INDEX IF EXISTS uq_checklist_templates_single_active_approved")
    _backfill(op.get_bind())
    op.execute(
        "CREATE UNIQUE INDEX uq_checklist_templates_one_active_per_shop "
        "ON checklist_templates (shop_id) WHERE active_for_new_visits = TRUE"
    )

    op.create_unique_constraint("uq_checklist_templates_id_shop", "checklist_templates", ["id", "shop_id"])
    op.create_foreign_key(
        "fk_inspection_sessions_checklist_template_shop",
        "inspection_sessions",
        "checklist_templates",
        ["checklist_template_id", "shop_id"],
        ["id", "shop_id"],
    )


def downgrade():
    bind = op.get_bind()
    active = bind.execute(sa.text("SELECT count(*) FROM checklist_templates WHERE active_for_new_visits")).scalar_one()
    if active > 1:
        raise RuntimeError(
            "Cannot restore the global single-active-template index: more than one shop has an active template. "
            "Retire or deactivate all but one active template first."
        )
    op.drop_constraint("fk_inspection_sessions_checklist_template_shop", "inspection_sessions", type_="foreignkey")
    op.drop_constraint("uq_checklist_templates_id_shop", "checklist_templates", type_="unique")
    op.execute("DROP INDEX IF EXISTS uq_checklist_templates_one_active_per_shop")
    op.execute(
        "CREATE UNIQUE INDEX uq_checklist_templates_single_active_approved "
        "ON checklist_templates (active_for_new_visits) WHERE active_for_new_visits = TRUE"
    )
    # Per-shop copies made by upgrade() stay as ordinary rows; sessions keep
    # pointing at the copy they were moved to.
    op.drop_index("ix_checklist_templates_shop_id", table_name="checklist_templates")
    op.drop_constraint("fk_checklist_templates_shop", "checklist_templates", type_="foreignkey")
    op.drop_column("checklist_templates", "shop_id")
