"""Coverage: the third parties an agreement is with, and services among what it covers
(TPR-05, TPR-06).

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agreement_party",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agreement_id", sa.Integer(), nullable=False),
        sa.Column("third_party_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["agreement_id"],
            ["agreement.id"],
            name=op.f("fk_agreement_party_agreement_id_agreement"),
        ),
        sa.ForeignKeyConstraint(
            ["third_party_id"],
            ["third_party.id"],
            name=op.f("fk_agreement_party_third_party_id_third_party"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agreement_party")),
        sa.UniqueConstraint(
            "agreement_id",
            "third_party_id",
            name=op.f("uq_agreement_party_agreement_id_third_party_id"),
        ),
    )
    with op.batch_alter_table("agreement_party", schema=None) as batch_op:
        batch_op.create_index("ix_agreement_party_third_party_id", ["third_party_id"], unique=False)

    # An agreement may cover a service as well as systems, information, and scopes.
    with op.batch_alter_table("agreement_coverage", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_agreement_coverage_subject_type"), type_="check")
        batch_op.create_check_constraint(
            op.f("ck_agreement_coverage_subject_type"),
            "subject_type IN ('system', 'information', 'scope', 'service')",
        )


def downgrade() -> None:
    op.execute("DELETE FROM agreement_coverage WHERE subject_type = 'service'")
    with op.batch_alter_table("agreement_coverage", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_agreement_coverage_subject_type"), type_="check")
        batch_op.create_check_constraint(
            op.f("ck_agreement_coverage_subject_type"),
            "subject_type IN ('system', 'information', 'scope')",
        )
    with op.batch_alter_table("agreement_party", schema=None) as batch_op:
        batch_op.drop_index("ix_agreement_party_third_party_id")

    op.drop_table("agreement_party")
