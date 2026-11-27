"""Resilience: continuity plans, as documents of their own kind, what each restores, and
the exercises that test them (RES-03, RES-04).

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "continuity_cover",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("process_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["policy_document.id"],
            name=op.f("fk_continuity_cover_document_id_policy_document"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["process_id"], ["process.id"], name=op.f("fk_continuity_cover_process_id_process")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_continuity_cover")),
        sa.UniqueConstraint("document_id", "process_id", name="uq_continuity_cover"),
    )
    with op.batch_alter_table("continuity_cover", schema=None) as batch_op:
        batch_op.create_index("ix_continuity_cover_process_id", ["process_id"], unique=False)

    op.create_table(
        "continuity_exercise",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("held_on", sa.Date(), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("participants", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("achieved_hours", sa.Integer(), nullable=True),
        sa.Column("recorded_by", sa.Integer(), nullable=True),
        sa.Column("recorded_by_name", sa.String(length=200), nullable=False),
        sa.Column("recorded_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('tabletop', 'walkthrough', 'simulation', 'full')",
            name=op.f("ck_continuity_exercise_kind"),
        ),
        sa.CheckConstraint(
            "result IN ('met', 'partly', 'not_met')", name=op.f("ck_continuity_exercise_result")
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["policy_document.id"],
            name=op.f("fk_continuity_exercise_document_id_policy_document"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"], ["account.id"], name=op.f("fk_continuity_exercise_recorded_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["policy_version.id"],
            name=op.f("fk_continuity_exercise_version_id_policy_version"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_continuity_exercise")),
    )
    with op.batch_alter_table("continuity_exercise", schema=None) as batch_op:
        batch_op.create_index("ix_continuity_exercise_document_id", ["document_id"], unique=False)

    with op.batch_alter_table("policy_document", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_policy_document_kind"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_policy_document_kind"),
            "kind IN ('policy', 'standard', 'procedure', 'plan', 'guideline')",
        )


def downgrade() -> None:
    with op.batch_alter_table("policy_document", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_policy_document_kind"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_policy_document_kind"),
            "kind IN ('policy', 'standard', 'procedure', 'guideline')",
        )

    with op.batch_alter_table("continuity_exercise", schema=None) as batch_op:
        batch_op.drop_index("ix_continuity_exercise_document_id")

    op.drop_table("continuity_exercise")
    with op.batch_alter_table("continuity_cover", schema=None) as batch_op:
        batch_op.drop_index("ix_continuity_cover_process_id")

    op.drop_table("continuity_cover")
