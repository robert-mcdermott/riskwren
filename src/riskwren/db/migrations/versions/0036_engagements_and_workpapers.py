"""Internal audit: engagement teams, stages, workpapers, and review notes (AUD-03, AUD-04).

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "engagement_member",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("engagement_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.CheckConstraint("role IN ('lead', 'member')", name=op.f("ck_engagement_member_role")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_engagement_member_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagement.id"],
            name=op.f("fk_engagement_member_engagement_id_engagement"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_engagement_member")),
        sa.UniqueConstraint(
            "engagement_id",
            "account_id",
            name=op.f("uq_engagement_member_engagement_id_account_id"),
        ),
    )
    op.create_table(
        "workpaper",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("engagement_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("procedure", sa.Text(), nullable=True),
        sa.Column("done", sa.Text(), nullable=True),
        sa.Column("found", sa.Text(), nullable=True),
        sa.Column("evidence", riskwren.db.types.JsonType, nullable=False),
        sa.Column("prepared_by", sa.Integer(), nullable=True),
        sa.Column("prepared_by_name", sa.String(length=200), nullable=True),
        sa.Column("prepared_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("signed_off_by", sa.Integer(), nullable=True),
        sa.Column("signed_off_by_name", sa.String(length=200), nullable=True),
        sa.Column("signed_off_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["engagement.id"], name=op.f("fk_workpaper_engagement_id_engagement")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workpaper")),
    )
    with op.batch_alter_table("workpaper", schema=None) as batch_op:
        batch_op.create_index("ix_workpaper_engagement_id", ["engagement_id"], unique=False)

    op.create_table(
        "review_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("engagement_id", sa.Integer(), nullable=False),
        sa.Column("workpaper_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("by", sa.Integer(), nullable=True),
        sa.Column("by_name", sa.String(length=200), nullable=False),
        sa.Column("at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("cleared_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagement.id"],
            name=op.f("fk_review_note_engagement_id_engagement"),
        ),
        sa.ForeignKeyConstraint(
            ["workpaper_id"], ["workpaper.id"], name=op.f("fk_review_note_workpaper_id_workpaper")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_note")),
    )
    with op.batch_alter_table("review_note", schema=None) as batch_op:
        batch_op.create_index("ix_review_note_workpaper_id", ["workpaper_id"], unique=False)

    with op.batch_alter_table("engagement", schema=None) as batch_op:
        batch_op.add_column(sa.Column("started_on", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("fieldwork_on", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("reporting_on", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("scope_note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("report_summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("opinion", sa.String(length=24), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("engagement", schema=None) as batch_op:
        batch_op.drop_column("opinion")
        batch_op.drop_column("report_summary")
        batch_op.drop_column("scope_note")
        batch_op.drop_column("reporting_on")
        batch_op.drop_column("fieldwork_on")
        batch_op.drop_column("started_on")

    with op.batch_alter_table("review_note", schema=None) as batch_op:
        batch_op.drop_index("ix_review_note_workpaper_id")

    op.drop_table("review_note")
    with op.batch_alter_table("workpaper", schema=None) as batch_op:
        batch_op.drop_index("ix_workpaper_engagement_id")

    op.drop_table("workpaper")
    op.drop_table("engagement_member")
