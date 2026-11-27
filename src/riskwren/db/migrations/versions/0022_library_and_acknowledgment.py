"""Library and acknowledgment: who a document applies to, who has said they read it, and
campaigns that ask them to (POL-05, POL-06).

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_audience",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=24), nullable=True),
        sa.CheckConstraint(
            "(org_unit_id IS NULL) != (role IS NULL)", name=op.f("ck_policy_audience_one_of_them")
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["policy_document.id"],
            name=op.f("fk_policy_audience_document_id_policy_document"),
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_policy_audience_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_audience")),
    )
    with op.batch_alter_table("policy_audience", schema=None) as batch_op:
        batch_op.create_index("ix_policy_audience_document_id", ["document_id"], unique=False)

    op.create_table(
        "policy_acknowledgment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("account_name", sa.String(length=200), nullable=False),
        sa.Column("acknowledged_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_policy_acknowledgment_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["policy_document.id"],
            name=op.f("fk_policy_acknowledgment_document_id_policy_document"),
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["policy_version.id"],
            name=op.f("fk_policy_acknowledgment_version_id_policy_version"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_acknowledgment")),
        sa.UniqueConstraint(
            "version_id", "account_id", name=op.f("uq_policy_acknowledgment_version_id_account_id")
        ),
    )
    with op.batch_alter_table("policy_acknowledgment", schema=None) as batch_op:
        batch_op.create_index(
            "ix_policy_acknowledgment_account", ["account_id", "document_id"], unique=False
        )

    with op.batch_alter_table("campaign", schema=None) as batch_op:
        batch_op.add_column(sa.Column("document_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_campaign_document_id_policy_document"),
            "policy_document",
            ["document_id"],
            ["id"],
        )
        batch_op.drop_constraint(batch_op.f("ck_campaign_kind"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_campaign_kind"),
            "kind IN ('attestation', 'self_assessment', 'completeness', 'profile', 'evidence', "
            "'acknowledgment')",
        )

    with op.batch_alter_table("policy_document", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("for_everyone", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column("acknowledge", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table("policy_version", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ask_again", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    with op.batch_alter_table("campaign_item", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("uq_campaign_item_campaign_id_subject_type_subject_id"), type_="unique"
        )
        batch_op.create_unique_constraint(
            batch_op.f("uq_campaign_item_campaign_id_subject_type_subject_id_account_id"),
            ["campaign_id", "subject_type", "subject_id", "account_id"],
        )

    # The defaults were for rows already there; new rows take theirs from the models.
    with op.batch_alter_table("policy_document", schema=None) as batch_op:
        batch_op.alter_column("for_everyone", server_default=None)
        batch_op.alter_column("acknowledge", server_default=None)
    with op.batch_alter_table("policy_version", schema=None) as batch_op:
        batch_op.alter_column("ask_again", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("policy_version", schema=None) as batch_op:
        batch_op.drop_column("ask_again")

    with op.batch_alter_table("policy_document", schema=None) as batch_op:
        batch_op.drop_column("acknowledge")
        batch_op.drop_column("for_everyone")

    op.execute(
        "DELETE FROM campaign_item WHERE campaign_id IN "
        "(SELECT id FROM campaign WHERE kind = 'acknowledgment')"
    )
    op.execute("DELETE FROM campaign WHERE kind = 'acknowledgment'")
    with op.batch_alter_table("campaign_item", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("uq_campaign_item_campaign_id_subject_type_subject_id_account_id"),
            type_="unique",
        )
        batch_op.create_unique_constraint(
            batch_op.f("uq_campaign_item_campaign_id_subject_type_subject_id"),
            ["campaign_id", "subject_type", "subject_id"],
        )
    with op.batch_alter_table("campaign", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_campaign_kind"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_campaign_kind"),
            "kind IN ('attestation', 'self_assessment', 'completeness', 'profile', 'evidence')",
        )
        batch_op.drop_constraint(
            batch_op.f("fk_campaign_document_id_policy_document"), type_="foreignkey"
        )
        batch_op.drop_column("document_id")

    with op.batch_alter_table("policy_acknowledgment", schema=None) as batch_op:
        batch_op.drop_index("ix_policy_acknowledgment_account")

    op.drop_table("policy_acknowledgment")
    with op.batch_alter_table("policy_audience", schema=None) as batch_op:
        batch_op.drop_index("ix_policy_audience_document_id")

    op.drop_table("policy_audience")
