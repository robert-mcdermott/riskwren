"""Policies in the web of records: the controls a document directs, the requirements it
answers, and exceptions to a document (POL-04, ISS-06).

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_control",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name=op.f("fk_document_control_control_id_control")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["account.id"], name=op.f("fk_document_control_created_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["policy_document.id"],
            name=op.f("fk_document_control_document_id_policy_document"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_control")),
        sa.UniqueConstraint(
            "document_id", "control_id", name=op.f("uq_document_control_document_id_control_id")
        ),
    )
    with op.batch_alter_table("document_control", schema=None) as batch_op:
        batch_op.create_index("ix_document_control_control_id", ["control_id"], unique=False)

    op.create_table(
        "document_requirement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["account.id"], name=op.f("fk_document_requirement_created_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["policy_document.id"],
            name=op.f("fk_document_requirement_document_id_policy_document"),
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirement.id"],
            name=op.f("fk_document_requirement_requirement_id_requirement"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_requirement")),
        sa.UniqueConstraint(
            "document_id",
            "requirement_id",
            name=op.f("uq_document_requirement_document_id_requirement_id"),
        ),
    )
    with op.batch_alter_table("document_requirement", schema=None) as batch_op:
        batch_op.create_index(
            "ix_document_requirement_requirement_id", ["requirement_id"], unique=False
        )

    with op.batch_alter_table("exception_request", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_exception_request_subject_type"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_exception_request_subject_type"),
            "subject_type IN ('control', 'requirement', 'document')",
        )


def downgrade() -> None:
    # An exception to a document cannot be held before this revision.
    op.execute(
        "UPDATE exception_request SET renews_id = NULL WHERE renews_id IN "
        "(SELECT id FROM exception_request WHERE subject_type = 'document')"
    )
    op.execute(
        "DELETE FROM record_owner WHERE record_type = 'exception' AND record_id IN "
        "(SELECT id FROM exception_request WHERE subject_type = 'document')"
    )
    op.execute("DELETE FROM exception_request WHERE subject_type = 'document'")
    with op.batch_alter_table("exception_request", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_exception_request_subject_type"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_exception_request_subject_type"),
            "subject_type IN ('control', 'requirement')",
        )

    with op.batch_alter_table("document_requirement", schema=None) as batch_op:
        batch_op.drop_index("ix_document_requirement_requirement_id")

    op.drop_table("document_requirement")
    with op.batch_alter_table("document_control", schema=None) as batch_op:
        batch_op.drop_index("ix_document_control_control_id")

    op.drop_table("document_control")
