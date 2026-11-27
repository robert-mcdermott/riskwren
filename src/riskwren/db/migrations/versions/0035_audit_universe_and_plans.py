"""Internal audit: the universe, the plans, and their engagements (AUD-01, AUD-02).

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "APL", "value": 0}, {"prefix": "AUD", "value": 0}])
    op.create_table(
        "audit_entity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("adjustment", sa.Integer(), nullable=False),
        sa.Column("adjustment_reason", sa.Text(), nullable=True),
        sa.Column("last_audited_on", sa.Date(), nullable=True),
        sa.Column("last_audit_note", sa.Text(), nullable=True),
        sa.Column("left_out", sa.Boolean(), nullable=False),
        sa.Column("left_out_reason", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_by_name", sa.String(length=200), nullable=False),
        sa.Column("updated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "subject_type IN ('unit', 'process', 'system', 'third_party', 'scope')",
            name=op.f("ck_audit_entity_subject_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_entity")),
        sa.UniqueConstraint(
            "subject_type", "subject_id", name=op.f("uq_audit_entity_subject_type_subject_id")
        ),
    )
    op.create_table(
        "audit_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_by_name", sa.String(length=200), nullable=True),
        sa.Column("approved_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("approval_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'closed')", name=op.f("ck_audit_plan_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_plan")),
        sa.UniqueConstraint("ref", name=op.f("uq_audit_plan_ref")),
    )
    op.create_table(
        "engagement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=True),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_end", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("dropped_reason", sa.Text(), nullable=True),
        sa.Column("reported_on", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('planned', 'planning', 'fieldwork', 'reporting', 'reported', 'dropped')",
            name=op.f("ck_engagement_status"),
        ),
        sa.CheckConstraint(
            "subject_type IN ('unit', 'process', 'system', 'third_party', 'scope')",
            name=op.f("ck_engagement_subject_type"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["audit_plan.id"], name=op.f("fk_engagement_plan_id_audit_plan")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_engagement")),
        sa.UniqueConstraint("ref", name=op.f("uq_engagement_ref")),
    )
    with op.batch_alter_table("engagement", schema=None) as batch_op:
        batch_op.create_index("ix_engagement_plan_id", ["plan_id"], unique=False)
        batch_op.create_index("ix_engagement_subject", ["subject_type", "subject_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("engagement", schema=None) as batch_op:
        batch_op.drop_index("ix_engagement_subject")
        batch_op.drop_index("ix_engagement_plan_id")

    op.drop_table("engagement")
    op.drop_table("audit_plan")
    op.drop_table("audit_entity")
    op.execute("DELETE FROM counter WHERE prefix IN ('APL', 'AUD')")
