"""Objectives and sessions: strategic objectives that risks name, and committee sessions with
their agenda, decisions, and minutes (RSK-16, OVS-09).

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "OBJ", "value": 0}, {"prefix": "SES", "value": 0}])
    op.create_table(
        "committee_session",
        sa.Column("committee", sa.String(length=120), nullable=False),
        sa.Column("held_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attendees", sa.Text(), nullable=True),
        sa.Column("minutes", sa.Text(), nullable=True),
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
            "status IN ('planned', 'held', 'cancelled')", name=op.f("ck_committee_session_status")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_committee_session_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_committee_session")),
        sa.UniqueConstraint("ref", name=op.f("uq_committee_session_ref")),
    )
    with op.batch_alter_table("committee_session", schema=None) as batch_op:
        batch_op.create_index("ix_committee_session_held_on", ["held_on"], unique=False)

    op.create_table(
        "objective",
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("period", sa.String(length=120), nullable=True),
        sa.Column("measure", sa.Text(), nullable=True),
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
            "status IN ('active', 'achieved', 'retired')", name=op.f("ck_objective_status")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_objective_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_objective")),
        sa.UniqueConstraint("ref", name=op.f("uq_objective_ref")),
    )
    with op.batch_alter_table("objective", schema=None) as batch_op:
        batch_op.create_index("ix_objective_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "committee_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_by_name", sa.String(length=200), nullable=True),
        sa.Column("decided_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('noted', 'approved', 'declined', 'deferred')",
            name=op.f("ck_committee_item_outcome"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["account.id"], name=op.f("fk_committee_item_decided_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["committee_session.id"],
            name=op.f("fk_committee_item_session_id_committee_session"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_committee_item")),
    )
    with op.batch_alter_table("committee_item", schema=None) as batch_op:
        batch_op.create_index("ix_committee_item_session_id", ["session_id"], unique=False)
        batch_op.create_index(
            "ix_committee_item_subject", ["subject_type", "subject_id"], unique=False
        )

    op.create_table(
        "risk_objective",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.Column("objective_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["objective_id"],
            ["objective.id"],
            name=op.f("fk_risk_objective_objective_id_objective"),
        ),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name=op.f("fk_risk_objective_risk_id_risk")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_objective")),
        sa.UniqueConstraint(
            "risk_id", "objective_id", name=op.f("uq_risk_objective_risk_id_objective_id")
        ),
    )
    with op.batch_alter_table("risk_objective", schema=None) as batch_op:
        batch_op.create_index("ix_risk_objective_objective_id", ["objective_id"], unique=False)


def downgrade() -> None:
    op.execute("DELETE FROM record_owner WHERE record_type IN ('objective', 'committee_session')")
    op.execute("DELETE FROM counter WHERE prefix IN ('OBJ', 'SES')")
    with op.batch_alter_table("risk_objective", schema=None) as batch_op:
        batch_op.drop_index("ix_risk_objective_objective_id")

    op.drop_table("risk_objective")
    with op.batch_alter_table("committee_item", schema=None) as batch_op:
        batch_op.drop_index("ix_committee_item_subject")
        batch_op.drop_index("ix_committee_item_session_id")

    op.drop_table("committee_item")
    with op.batch_alter_table("objective", schema=None) as batch_op:
        batch_op.drop_index("ix_objective_org_unit_id")

    op.drop_table("objective")
    with op.batch_alter_table("committee_session", schema=None) as batch_op:
        batch_op.drop_index("ix_committee_session_held_on")

    op.drop_table("committee_session")
