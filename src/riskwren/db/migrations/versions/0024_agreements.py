"""Agreements: awards, data use agreements, and contracts, with their parties, dates, what
they cover, and the framework of the requirements they impose (CMP-12).

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "AGR", "value": 0}])
    op.create_table(
        "agreement",
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("parties", sa.String(length=300), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("url", sa.String(length=300), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("notice_days", sa.Integer(), nullable=True),
        sa.Column("renews", sa.Boolean(), nullable=False),
        sa.Column("framework_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("closed_on", sa.Date(), nullable=True),
        sa.Column("closed_note", sa.Text(), nullable=True),
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
            "kind IN ('award', 'data_use', 'business_associate', 'contract', 'confidentiality', 'memorandum', 'other')",
            name=op.f("ck_agreement_kind"),
        ),
        sa.CheckConstraint("status IN ('active', 'closed')", name=op.f("ck_agreement_status")),
        sa.ForeignKeyConstraint(
            ["framework_id"], ["framework.id"], name=op.f("fk_agreement_framework_id_framework")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_agreement_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agreement")),
        sa.UniqueConstraint("ref", name=op.f("uq_agreement_ref")),
    )
    with op.batch_alter_table("agreement", schema=None) as batch_op:
        batch_op.create_index("ix_agreement_ends_on", ["ends_on"], unique=False)
        batch_op.create_index("ix_agreement_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "agreement_coverage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agreement_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "subject_type IN ('system', 'information', 'scope')",
            name=op.f("ck_agreement_coverage_subject_type"),
        ),
        sa.ForeignKeyConstraint(
            ["agreement_id"],
            ["agreement.id"],
            name=op.f("fk_agreement_coverage_agreement_id_agreement"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agreement_coverage")),
        sa.UniqueConstraint(
            "agreement_id",
            "subject_type",
            "subject_id",
            name=op.f("uq_agreement_coverage_agreement_id_subject_type_subject_id"),
        ),
    )
    with op.batch_alter_table("agreement_coverage", schema=None) as batch_op:
        batch_op.create_index(
            "ix_agreement_coverage_subject", ["subject_type", "subject_id"], unique=False
        )

    with op.batch_alter_table("scope_framework", schema=None) as batch_op:
        batch_op.add_column(sa.Column("agreement_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_scope_framework_agreement_id_agreement"),
            "agreement",
            ["agreement_id"],
            ["id"],
        )


def downgrade() -> None:
    # A framework a scope holds only because of an agreement goes with the agreement.
    op.execute(
        "DELETE FROM scope_requirement WHERE EXISTS (SELECT 1 FROM scope_framework sf "
        "JOIN requirement r ON r.framework_id = sf.framework_id WHERE sf.agreement_id IS NOT NULL "
        "AND sf.scope_id = scope_requirement.scope_id AND r.id = scope_requirement.requirement_id)"
    )
    op.execute("DELETE FROM scope_framework WHERE agreement_id IS NOT NULL")
    op.execute("DELETE FROM record_owner WHERE record_type = 'agreement'")
    op.execute("DELETE FROM counter WHERE prefix = 'AGR'")
    with op.batch_alter_table("scope_framework", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_scope_framework_agreement_id_agreement"), type_="foreignkey"
        )
        batch_op.drop_column("agreement_id")

    with op.batch_alter_table("agreement_coverage", schema=None) as batch_op:
        batch_op.drop_index("ix_agreement_coverage_subject")

    op.drop_table("agreement_coverage")
    with op.batch_alter_table("agreement", schema=None) as batch_op:
        batch_op.drop_index("ix_agreement_org_unit_id")
        batch_op.drop_index("ix_agreement_ends_on")

    op.drop_table("agreement")
