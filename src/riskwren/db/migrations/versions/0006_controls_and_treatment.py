"""Controls and treatment: controls and their ratings, links to risks, plans, actions, and
acceptances (CTL-01 to CTL-05, TRT-01 to TRT-05).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("CTL", "PLN", "ACT")


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "control_library",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("nature", sa.String(length=40), nullable=True),
        sa.Column("frequency", sa.String(length=40), nullable=True),
        sa.Column("reduces", sa.String(length=16), nullable=False),
        sa.Column("source_pack", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_library")),
        sa.UniqueConstraint("key", name=op.f("uq_control_library_key")),
    )
    op.create_table(
        "action",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("original_due_on", sa.Date(), nullable=False),
        sa.Column("extensions", riskwren.db.types.JsonType, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("completed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("completion_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'done', 'cancelled')", name=op.f("ck_action_status")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["account.id"], name=op.f("fk_action_owner_id_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_action")),
        sa.UniqueConstraint("ref", name=op.f("uq_action_ref")),
    )
    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.create_index("ix_action_due_on", ["due_on"], unique=False)
        batch_op.create_index("ix_action_owner_id", ["owner_id"], unique=False)
        batch_op.create_index("ix_action_source", ["source_type", "source_id"], unique=False)

    op.create_table(
        "control",
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("nature", sa.String(length=40), nullable=True),
        sa.Column("frequency", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("is_key", sa.Boolean(), nullable=False),
        sa.Column("design", sa.String(length=16), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("rated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("library_key", sa.String(length=80), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tags", riskwren.db.types.JsonType, nullable=False),
        sa.Column("restricted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "design IN ('effective', 'partly', 'ineffective', 'not_assessed')",
            name=op.f("ck_control_design"),
        ),
        sa.CheckConstraint(
            "operation IN ('effective', 'partly', 'ineffective', 'not_assessed')",
            name=op.f("ck_control_operation"),
        ),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_control_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_control_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control")),
        sa.UniqueConstraint("ref", name=op.f("uq_control_ref")),
    )
    with op.batch_alter_table("control", schema=None) as batch_op:
        batch_op.create_index("ix_control_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "acceptance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.Column("rating_accepted", sa.String(length=40), nullable=False),
        sa.Column("likelihood", sa.Integer(), nullable=False),
        sa.Column("impact", sa.Integer(), nullable=False),
        sa.Column("appetite", sa.String(length=40), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("accepted_by", sa.Integer(), nullable=False),
        sa.Column("accepted_by_name", sa.String(length=200), nullable=False),
        sa.Column("accepted_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=False),
        sa.Column("withdrawn_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_by_name", sa.String(length=200), nullable=True),
        sa.Column("withdrawn_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["accepted_by"], ["account.id"], name=op.f("fk_acceptance_accepted_by_account")
        ),
        sa.ForeignKeyConstraint(["risk_id"], ["risk.id"], name=op.f("fk_acceptance_risk_id_risk")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_acceptance")),
    )
    with op.batch_alter_table("acceptance", schema=None) as batch_op:
        batch_op.create_index("ix_acceptance_expires_on", ["expires_on"], unique=False)
        batch_op.create_index("ix_acceptance_risk_id", ["risk_id"], unique=False)

    op.create_table(
        "control_rating",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("design", sa.String(length=16), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("basis", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("rated_by", sa.Integer(), nullable=True),
        sa.Column("rated_by_name", sa.String(length=200), nullable=False),
        sa.Column("rated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "basis IN ('judgment', 'attestation', 'test')", name=op.f("ck_control_rating_basis")
        ),
        sa.CheckConstraint(
            "design IN ('effective', 'partly', 'ineffective', 'not_assessed')",
            name=op.f("ck_control_rating_design"),
        ),
        sa.CheckConstraint(
            "operation IN ('effective', 'partly', 'ineffective', 'not_assessed')",
            name=op.f("ck_control_rating_operation"),
        ),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name=op.f("fk_control_rating_control_id_control")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_rating")),
    )
    with op.batch_alter_table("control_rating", schema=None) as batch_op:
        batch_op.create_index("ix_control_rating_control_id", ["control_id"], unique=False)

    op.create_table(
        "risk_control",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("reduces", sa.String(length=16), nullable=False),
        sa.Column("reliance", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.CheckConstraint(
            "reduces IN ('likelihood', 'impact', 'both')", name=op.f("ck_risk_control_reduces")
        ),
        sa.CheckConstraint(
            "reliance IN ('primary', 'supporting')", name=op.f("ck_risk_control_reliance")
        ),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name=op.f("fk_risk_control_control_id_control")
        ),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name=op.f("fk_risk_control_risk_id_risk")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_control")),
        sa.UniqueConstraint(
            "risk_id", "control_id", name=op.f("uq_risk_control_risk_id_control_id")
        ),
    )
    with op.batch_alter_table("risk_control", schema=None) as batch_op:
        batch_op.create_index("ix_risk_control_control_id", ["control_id"], unique=False)

    op.create_table(
        "treatment_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("target_rating", sa.String(length=40), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("closed_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("closed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'complete', 'cancelled')", name=op.f("ck_treatment_plan_status")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["account.id"], name=op.f("fk_treatment_plan_owner_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name=op.f("fk_treatment_plan_risk_id_risk")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_treatment_plan")),
        sa.UniqueConstraint("ref", name=op.f("uq_treatment_plan_ref")),
    )
    with op.batch_alter_table("treatment_plan", schema=None) as batch_op:
        batch_op.create_index("ix_treatment_plan_owner_id", ["owner_id"], unique=False)
        batch_op.create_index("ix_treatment_plan_risk_id", ["risk_id"], unique=False)


def downgrade() -> None:
    op.execute("DELETE FROM counter WHERE prefix IN ('CTL', 'PLN', 'ACT')")
    with op.batch_alter_table("treatment_plan", schema=None) as batch_op:
        batch_op.drop_index("ix_treatment_plan_risk_id")
        batch_op.drop_index("ix_treatment_plan_owner_id")

    op.drop_table("treatment_plan")
    with op.batch_alter_table("risk_control", schema=None) as batch_op:
        batch_op.drop_index("ix_risk_control_control_id")

    op.drop_table("risk_control")
    with op.batch_alter_table("control_rating", schema=None) as batch_op:
        batch_op.drop_index("ix_control_rating_control_id")

    op.drop_table("control_rating")
    with op.batch_alter_table("acceptance", schema=None) as batch_op:
        batch_op.drop_index("ix_acceptance_risk_id")
        batch_op.drop_index("ix_acceptance_expires_on")

    op.drop_table("acceptance")
    with op.batch_alter_table("control", schema=None) as batch_op:
        batch_op.drop_index("ix_control_org_unit_id")

    op.drop_table("control")
    with op.batch_alter_table("action", schema=None) as batch_op:
        batch_op.drop_index("ix_action_source")
        batch_op.drop_index("ix_action_owner_id")
        batch_op.drop_index("ix_action_due_on")

    op.drop_table("action")
    op.drop_table("control_library")
