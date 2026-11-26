"""Issues, exceptions, and notices: what is wrong and who is fixing it, approved departures
that expire, and what each person has been told (ISS-01 to ISS-07, OVS-06).

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "ISS", "value": 0}, {"prefix": "EXC", "value": 0}])
    op.create_table(
        "issue",
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("original_due_on", sa.Date(), nullable=False),
        sa.Column("extensions", riskwren.db.types.JsonType, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("root_cause", sa.String(length=40), nullable=True),
        sa.Column("closure_note", sa.Text(), nullable=True),
        sa.Column("proposed_by", sa.Integer(), nullable=True),
        sa.Column("proposed_by_name", sa.String(length=200), nullable=True),
        sa.Column("proposed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("return_note", sa.Text(), nullable=True),
        sa.Column("validated_by", sa.Integer(), nullable=True),
        sa.Column("validated_by_name", sa.String(length=200), nullable=True),
        sa.Column("validated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
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
            "severity IN ('critical', 'high', 'moderate', 'low')", name=op.f("ck_issue_severity")
        ),
        sa.CheckConstraint(
            "status IN ('open', 'proposed', 'closed', 'cancelled')", name=op.f("ck_issue_status")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_issue_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["proposed_by"], ["account.id"], name=op.f("fk_issue_proposed_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["validated_by"], ["account.id"], name=op.f("fk_issue_validated_by_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_issue")),
        sa.UniqueConstraint("ref", name=op.f("uq_issue_ref")),
    )
    with op.batch_alter_table("issue", schema=None) as batch_op:
        batch_op.create_index("ix_issue_org_unit_id", ["org_unit_id"], unique=False)
        batch_op.create_index("ix_issue_source", ["source_type", "source_id"], unique=False)
        batch_op.create_index("ix_issue_status_due_on", ["status", "due_on"], unique=False)

    op.create_table(
        "notice",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("text", sa.String(length=400), nullable=False),
        sa.Column("href", sa.String(length=200), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("read_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_notice_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notice")),
    )
    with op.batch_alter_table("notice", schema=None) as batch_op:
        batch_op.create_index(
            "ix_notice_account_id_read_at", ["account_id", "read_at"], unique=False
        )

    op.create_table(
        "exception_request",
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("compensating", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("requested_by_name", sa.String(length=200), nullable=False),
        sa.Column("requested_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_by_name", sa.String(length=200), nullable=True),
        sa.Column("decided_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("renews_id", sa.Integer(), nullable=True),
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
            "status IN ('requested', 'approved', 'refused', 'withdrawn')",
            name=op.f("ck_exception_request_status"),
        ),
        sa.CheckConstraint(
            "subject_type IN ('control', 'requirement')",
            name=op.f("ck_exception_request_subject_type"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["account.id"], name=op.f("fk_exception_request_decided_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_exception_request_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["renews_id"],
            ["exception_request.id"],
            name=op.f("fk_exception_request_renews_id_exception_request"),
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["account.id"], name=op.f("fk_exception_request_requested_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name=op.f("fk_exception_request_scope_id_scope")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exception_request")),
        sa.UniqueConstraint("ref", name=op.f("uq_exception_request_ref")),
    )
    with op.batch_alter_table("exception_request", schema=None) as batch_op:
        batch_op.create_index("ix_exception_request_org_unit_id", ["org_unit_id"], unique=False)
        batch_op.create_index("ix_exception_request_scope_id", ["scope_id"], unique=False)
        batch_op.create_index(
            "ix_exception_request_subject", ["subject_type", "subject_id"], unique=False
        )

    op.create_table(
        "issue_subject",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["issue_id"],
            ["issue.id"],
            name=op.f("fk_issue_subject_issue_id_issue"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_issue_subject")),
        sa.UniqueConstraint("issue_id", "subject_type", "subject_id", name="uq_issue_subject"),
    )
    with op.batch_alter_table("issue_subject", schema=None) as batch_op:
        batch_op.create_index(
            "ix_issue_subject_subject", ["subject_type", "subject_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("issue_subject", schema=None) as batch_op:
        batch_op.drop_index("ix_issue_subject_subject")

    op.drop_table("issue_subject")
    with op.batch_alter_table("exception_request", schema=None) as batch_op:
        batch_op.drop_index("ix_exception_request_subject")
        batch_op.drop_index("ix_exception_request_scope_id")
        batch_op.drop_index("ix_exception_request_org_unit_id")

    op.drop_table("exception_request")
    with op.batch_alter_table("notice", schema=None) as batch_op:
        batch_op.drop_index("ix_notice_account_id_read_at")

    op.drop_table("notice")
    with op.batch_alter_table("issue", schema=None) as batch_op:
        batch_op.drop_index("ix_issue_status_due_on")
        batch_op.drop_index("ix_issue_source")
        batch_op.drop_index("ix_issue_org_unit_id")

    op.drop_table("issue")
    op.execute("DELETE FROM counter WHERE prefix IN ('ISS', 'EXC')")
