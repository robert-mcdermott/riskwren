"""Campaigns: a set of people asked to do one thing by a date, each item with what became of
it, and what a control's owner last attested (OVS-04, RSK-12, CTL-09, EVD-05, AST-08).

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "CMP", "value": 0}])
    op.create_table(
        "campaign",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("questionnaire_id", sa.Integer(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=True),
        sa.Column("org_unit_id", sa.Integer(), nullable=True),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.Column("wanted", sa.Text(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_by_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("closed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("closed_by_name", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "kind IN ('attestation', 'self_assessment', 'completeness', 'profile', 'evidence')",
            name=op.f("ck_campaign_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'closed', 'cancelled')", name=op.f("ck_campaign_status")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_campaign_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["questionnaire_id"],
            ["questionnaire.id"],
            name=op.f("fk_campaign_questionnaire_id_questionnaire"),
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name=op.f("fk_campaign_scope_id_scope")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign")),
        sa.UniqueConstraint("ref", name=op.f("uq_campaign_ref")),
    )
    op.create_table(
        "campaign_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("subject_ref", sa.String(length=24), nullable=True),
        sa.Column("subject_name", sa.String(length=200), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("account_name", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("response_id", sa.Integer(), nullable=True),
        sa.Column("evidence_id", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(length=40), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("completed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("completed_by_name", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'done', 'excused')", name=op.f("ck_campaign_item_status")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_campaign_item_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign.id"],
            name=op.f("fk_campaign_item_campaign_id_campaign"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["evidence.id"], name=op.f("fk_campaign_item_evidence_id_evidence")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_campaign_item_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["response_id"], ["response.id"], name=op.f("fk_campaign_item_response_id_response")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_item")),
        sa.UniqueConstraint(
            "campaign_id",
            "subject_type",
            "subject_id",
            name=op.f("uq_campaign_item_campaign_id_subject_type_subject_id"),
        ),
    )
    with op.batch_alter_table("campaign_item", schema=None) as batch_op:
        batch_op.create_index("ix_campaign_item_account_id", ["account_id", "status"], unique=False)

    with op.batch_alter_table("control", schema=None) as batch_op:
        batch_op.add_column(sa.Column("attested_operates", sa.String(length=16), nullable=True))
        batch_op.add_column(
            sa.Column("attested_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("attested_by_name", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.execute("DELETE FROM counter WHERE prefix = 'CMP'")
    with op.batch_alter_table("control", schema=None) as batch_op:
        batch_op.drop_column("attested_by_name")
        batch_op.drop_column("attested_at")
        batch_op.drop_column("attested_operates")

    with op.batch_alter_table("campaign_item", schema=None) as batch_op:
        batch_op.drop_index("ix_campaign_item_account_id")

    op.drop_table("campaign_item")
    op.drop_table("campaign")
