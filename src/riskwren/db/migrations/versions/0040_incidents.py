"""Incidents: reporting, reporting without a name, and triage (INC-01 to INC-03).

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "INC", "value": 0}])
    op.create_table(
        "incident",
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("anonymous", sa.Boolean(), nullable=False),
        sa.Column("follow_up_hash", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=True),
        sa.Column("triaged_by", sa.Integer(), nullable=True),
        sa.Column("triaged_by_name", sa.String(length=200), nullable=True),
        sa.Column("triaged_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("closure_note", sa.Text(), nullable=True),
        sa.Column("closed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
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
            "kind IN ('incident', 'near_miss', 'concern')", name=op.f("ck_incident_kind")
        ),
        sa.CheckConstraint(
            "severity IN ('critical', 'high', 'moderate', 'low')", name=op.f("ck_incident_severity")
        ),
        sa.CheckConstraint(
            "status IN ('reported', 'handling', 'closed')", name=op.f("ck_incident_status")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_incident_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["triaged_by"], ["account.id"], name=op.f("fk_incident_triaged_by_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident")),
        sa.UniqueConstraint("ref", name=op.f("uq_incident_ref")),
    )
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.create_index("ix_incident_follow_up_hash", ["follow_up_hash"], unique=True)
        batch_op.create_index("ix_incident_org_unit_id", ["org_unit_id"], unique=False)
        batch_op.create_index("ix_incident_status", ["status"], unique=False)

    op.create_table(
        "incident_message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("from_reporter", sa.Boolean(), nullable=False),
        sa.Column("shared", sa.Boolean(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("author_name", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"], ["account.id"], name=op.f("fk_incident_message_author_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident.id"],
            name=op.f("fk_incident_message_incident_id_incident"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_message")),
    )
    with op.batch_alter_table("incident_message", schema=None) as batch_op:
        batch_op.create_index("ix_incident_message_incident_id", ["incident_id"], unique=False)

    op.create_table(
        "incident_subject",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "subject_type IN ('system', 'service', 'information', 'third_party', 'process', "
            "'risk', 'control', 'scope')",
            name=op.f("ck_incident_subject_subject_type"),
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident.id"],
            name=op.f("fk_incident_subject_incident_id_incident"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_subject")),
        sa.UniqueConstraint(
            "incident_id", "subject_type", "subject_id", name="uq_incident_subject"
        ),
    )
    with op.batch_alter_table("incident_subject", schema=None) as batch_op:
        batch_op.create_index(
            "ix_incident_subject_subject", ["subject_type", "subject_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("incident_subject", schema=None) as batch_op:
        batch_op.drop_index("ix_incident_subject_subject")

    op.drop_table("incident_subject")
    with op.batch_alter_table("incident_message", schema=None) as batch_op:
        batch_op.drop_index("ix_incident_message_incident_id")

    op.drop_table("incident_message")
    with op.batch_alter_table("incident", schema=None) as batch_op:
        batch_op.drop_index("ix_incident_status")
        batch_op.drop_index("ix_incident_org_unit_id")
        batch_op.drop_index("ix_incident_follow_up_hash")

    op.drop_table("incident")
    op.execute("DELETE FROM counter WHERE prefix = 'INC'")
