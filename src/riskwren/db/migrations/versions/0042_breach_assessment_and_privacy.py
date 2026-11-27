"""Incidents: breach assessments and notifications (INC-05); campaigns that ask for a privacy
impact assessment (INC-07).

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "breach_assessment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("discovered_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("information", riskwren.db.types.JsonType, nullable=False),
        sa.Column("people", sa.Integer(), nullable=True),
        sa.Column("most_in_one_state", sa.Integer(), nullable=True),
        sa.Column("secured", sa.Boolean(), nullable=False),
        sa.Column("exception", sa.String(length=40), nullable=True),
        sa.Column("factors", riskwren.db.types.JsonType, nullable=False),
        sa.Column("conclusion", sa.String(length=24), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("regimes", riskwren.db.types.JsonType, nullable=False),
        sa.Column("assessed_by", sa.Integer(), nullable=True),
        sa.Column("assessed_by_name", sa.String(length=200), nullable=False),
        sa.Column("assessed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "conclusion IN ('undecided', 'notify', 'no_notification')",
            name=op.f("ck_breach_assessment_conclusion"),
        ),
        sa.ForeignKeyConstraint(
            ["assessed_by"], ["account.id"], name=op.f("fk_breach_assessment_assessed_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident.id"],
            name=op.f("fk_breach_assessment_incident_id_incident"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_breach_assessment")),
    )
    with op.batch_alter_table("breach_assessment", schema=None) as batch_op:
        batch_op.create_index("ix_breach_assessment_incident_id", ["incident_id"], unique=False)

    op.create_table(
        "breach_notification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("regime", sa.String(length=120), nullable=False),
        sa.Column("duty", sa.String(length=40), nullable=False),
        sa.Column("recipient", sa.String(length=200), nullable=False),
        sa.Column("count", sa.Integer(), nullable=True),
        sa.Column("sent_on", sa.Date(), nullable=False),
        sa.Column("method", sa.String(length=200), nullable=True),
        sa.Column("reference", sa.String(length=200), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Integer(), nullable=True),
        sa.Column("recorded_by_name", sa.String(length=200), nullable=False),
        sa.Column("recorded_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident.id"],
            name=op.f("fk_breach_notification_incident_id_incident"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"], ["account.id"], name=op.f("fk_breach_notification_recorded_by_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_breach_notification")),
    )
    with op.batch_alter_table("breach_notification", schema=None) as batch_op:
        batch_op.create_index("ix_breach_notification_incident_id", ["incident_id"], unique=False)

    with op.batch_alter_table("campaign", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_campaign_kind"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_campaign_kind"),
            "kind IN ('attestation', 'self_assessment', 'completeness', 'profile', 'evidence', "
            "'acknowledgment', 'privacy_impact')",
        )


def downgrade() -> None:
    with op.batch_alter_table("campaign", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_campaign_kind"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_campaign_kind"),
            "kind IN ('attestation', 'self_assessment', 'completeness', 'profile', 'evidence', "
            "'acknowledgment')",
        )

    with op.batch_alter_table("breach_notification", schema=None) as batch_op:
        batch_op.drop_index("ix_breach_notification_incident_id")

    op.drop_table("breach_notification")
    with op.batch_alter_table("breach_assessment", schema=None) as batch_op:
        batch_op.drop_index("ix_breach_assessment_incident_id")

    op.drop_table("breach_assessment")
