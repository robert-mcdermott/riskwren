"""Assurance documents: the structured review of a report or certificate about a third party,
with the responsibilities it leaves to the organization joined to its controls (TPR-04).

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assurance_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("third_party_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("issuer", sa.String(length=200), nullable=True),
        sa.Column("opinion", sa.String(length=16), nullable=False),
        sa.Column("services", riskwren.db.types.JsonType, nullable=False),
        sa.Column("carve_outs", sa.Text(), nullable=True),
        sa.Column("exceptions", riskwren.db.types.JsonType, nullable=False),
        sa.Column("reliance", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_name", sa.String(length=200), nullable=False),
        sa.Column("reviewed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "opinion IN ('unqualified', 'qualified', 'adverse', 'none')",
            name=op.f("ck_assurance_review_opinion"),
        ),
        sa.CheckConstraint(
            "reliance IN ('relies', 'partly', 'cannot')", name=op.f("ck_assurance_review_reliance")
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["evidence.id"], name=op.f("fk_assurance_review_evidence_id_evidence")
        ),
        sa.ForeignKeyConstraint(
            ["third_party_id"],
            ["third_party.id"],
            name=op.f("fk_assurance_review_third_party_id_third_party"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assurance_review")),
    )
    with op.batch_alter_table("assurance_review", schema=None) as batch_op:
        batch_op.create_index("ix_assurance_review_evidence_id", ["evidence_id"], unique=False)
        batch_op.create_index(
            "ix_assurance_review_third_party_id", ["third_party_id"], unique=False
        )

    op.create_table(
        "assurance_responsibility",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("third_party_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "status IN ('in_place', 'not_in_place', 'not_applicable')",
            name=op.f("ck_assurance_responsibility_status"),
        ),
        sa.ForeignKeyConstraint(
            ["control_id"],
            ["control.id"],
            name=op.f("fk_assurance_responsibility_control_id_control"),
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["assurance_review.id"],
            name=op.f("fk_assurance_responsibility_review_id_assurance_review"),
        ),
        sa.ForeignKeyConstraint(
            ["third_party_id"],
            ["third_party.id"],
            name=op.f("fk_assurance_responsibility_third_party_id_third_party"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assurance_responsibility")),
    )
    with op.batch_alter_table("assurance_responsibility", schema=None) as batch_op:
        batch_op.create_index(
            "ix_assurance_responsibility_control_id", ["control_id"], unique=False
        )
        batch_op.create_index("ix_assurance_responsibility_review_id", ["review_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("assurance_responsibility", schema=None) as batch_op:
        batch_op.drop_index("ix_assurance_responsibility_review_id")
        batch_op.drop_index("ix_assurance_responsibility_control_id")

    op.drop_table("assurance_responsibility")
    with op.batch_alter_table("assurance_review", schema=None) as batch_op:
        batch_op.drop_index("ix_assurance_review_third_party_id")
        batch_op.drop_index("ix_assurance_review_evidence_id")

    op.drop_table("assurance_review")
