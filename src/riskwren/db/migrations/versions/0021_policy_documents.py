"""Policy documents: policies, standards, procedures, and guidelines, their versions, and the
approvals each version was published on (POL-01, POL-02, POL-03, POL-07).

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "POL", "value": 0}])
    op.create_table(
        "policy_document",
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("review_months", sa.Integer(), nullable=True),
        sa.Column("published_version_id", sa.Integer(), nullable=True),
        sa.Column("last_reviewed_on", sa.Date(), nullable=True),
        sa.Column("next_review_on", sa.Date(), nullable=True),
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
            "kind IN ('policy', 'standard', 'procedure', 'guideline')",
            name=op.f("ck_policy_document_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'retired')", name=op.f("ck_policy_document_status")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_policy_document_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["policy_document.id"],
            name=op.f("fk_policy_document_parent_id_policy_document"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_document")),
        sa.UniqueConstraint("ref", name=op.f("uq_policy_document_ref")),
    )
    with op.batch_alter_table("policy_document", schema=None) as batch_op:
        batch_op.create_index("ix_policy_document_org_unit_id", ["org_unit_id"], unique=False)
        batch_op.create_index("ix_policy_document_parent_id", ["parent_id"], unique=False)

    op.create_table(
        "policy_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("form", sa.String(length=8), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=200), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("review_round", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_by_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("submitted_by", sa.Integer(), nullable=True),
        sa.Column("submitted_by_name", sa.String(length=200), nullable=True),
        sa.Column("submitted_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("published_by_name", sa.String(length=200), nullable=True),
        sa.Column("published_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.CheckConstraint("form IN ('text', 'link', 'file')", name=op.f("ck_policy_version_form")),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'published', 'superseded', 'discarded')",
            name=op.f("ck_policy_version_status"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["policy_document.id"],
            name=op.f("fk_policy_version_document_id_policy_document"),
        ),
        sa.ForeignKeyConstraint(
            ["file_id"], ["stored_file.id"], name=op.f("fk_policy_version_file_id_stored_file")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_version")),
        sa.UniqueConstraint(
            "document_id", "number", name=op.f("uq_policy_version_document_id_number")
        ),
    )
    with op.batch_alter_table("policy_version", schema=None) as batch_op:
        batch_op.create_index("ix_policy_version_document_id", ["document_id"], unique=False)

    op.create_table(
        "policy_approval",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("review_round", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("account_name", sa.String(length=200), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("asked_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("decided_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "decision IN ('pending', 'approved', 'returned', 'cancelled')",
            name=op.f("ck_policy_approval_decision"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_policy_approval_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["policy_document.id"],
            name=op.f("fk_policy_approval_document_id_policy_document"),
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["policy_version.id"],
            name=op.f("fk_policy_approval_version_id_policy_version"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_approval")),
        sa.UniqueConstraint(
            "version_id",
            "review_round",
            "account_id",
            name=op.f("uq_policy_approval_version_id_review_round_account_id"),
        ),
    )
    with op.batch_alter_table("policy_approval", schema=None) as batch_op:
        batch_op.create_index("ix_policy_approval_account_id", ["account_id"], unique=False)


def downgrade() -> None:
    op.execute("DELETE FROM counter WHERE prefix = 'POL'")
    with op.batch_alter_table("policy_approval", schema=None) as batch_op:
        batch_op.drop_index("ix_policy_approval_account_id")

    op.drop_table("policy_approval")
    with op.batch_alter_table("policy_version", schema=None) as batch_op:
        batch_op.drop_index("ix_policy_version_document_id")

    op.drop_table("policy_version")
    with op.batch_alter_table("policy_document", schema=None) as batch_op:
        batch_op.drop_index("ix_policy_document_parent_id")
        batch_op.drop_index("ix_policy_document_org_unit_id")

    op.drop_table("policy_document")
