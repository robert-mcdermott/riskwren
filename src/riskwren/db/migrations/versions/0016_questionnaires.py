"""Questionnaires: versioned documents of questions that appear by condition, and the answers
given to each version (OVS-07).

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "questionnaire",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint("origin IN ('pack', 'local')", name=op.f("ck_questionnaire_origin")),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_questionnaire_status")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questionnaire")),
        sa.UniqueConstraint("key", name=op.f("uq_questionnaire_key")),
    )
    op.create_table(
        "questionnaire_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("questionnaire_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("document", riskwren.db.types.JsonType, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("published_by_name", sa.String(length=200), nullable=False),
        sa.Column("published_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["questionnaire_id"],
            ["questionnaire.id"],
            name=op.f("fk_questionnaire_version_questionnaire_id_questionnaire"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questionnaire_version")),
        sa.UniqueConstraint(
            "questionnaire_id",
            "number",
            name=op.f("uq_questionnaire_version_questionnaire_id_number"),
        ),
    )
    op.create_table(
        "response",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("account_name", sa.String(length=200), nullable=False),
        sa.Column("answers", riskwren.db.types.JsonType, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('draft', 'submitted')", name=op.f("ck_response_status")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_response_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["questionnaire_version.id"],
            name=op.f("fk_response_version_id_questionnaire_version"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_response")),
    )
    with op.batch_alter_table("response", schema=None) as batch_op:
        batch_op.create_index("ix_response_account_id", ["account_id"], unique=False)
        batch_op.create_index("ix_response_subject", ["subject_type", "subject_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("response", schema=None) as batch_op:
        batch_op.drop_index("ix_response_subject")
        batch_op.drop_index("ix_response_account_id")

    op.drop_table("response")
    op.drop_table("questionnaire_version")
    op.drop_table("questionnaire")
