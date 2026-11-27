"""Services and tiering: what each third party provides and touches, and its tier set by the
program's rules with the reasons shown (TPR-01, TPR-02).

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "SVC", "value": 0}])
    op.create_table(
        "service",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("third_party_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("criticality", sa.String(length=40), nullable=False),
        sa.Column("data_class", sa.String(length=40), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_service_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_service_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["third_party_id"],
            ["third_party.id"],
            name=op.f("fk_service_third_party_id_third_party"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service")),
        sa.UniqueConstraint("ref", name=op.f("uq_service_ref")),
    )
    with op.batch_alter_table("service", schema=None) as batch_op:
        batch_op.create_index("ix_service_org_unit_id", ["org_unit_id"], unique=False)
        batch_op.create_index("ix_service_third_party_id", ["third_party_id"], unique=False)

    op.create_table(
        "tier_assessment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("third_party_id", sa.Integer(), nullable=False),
        sa.Column("answers", riskwren.db.types.JsonType, nullable=False),
        sa.Column("facts", riskwren.db.types.JsonType, nullable=False),
        sa.Column("questionnaire_version_id", sa.Integer(), nullable=True),
        sa.Column("suggested", sa.String(length=24), nullable=False),
        sa.Column("reasons", riskwren.db.types.JsonType, nullable=False),
        sa.Column("tier", sa.String(length=24), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("assessed_by", sa.Integer(), nullable=True),
        sa.Column("assessed_by_name", sa.String(length=200), nullable=False),
        sa.Column("assessed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["questionnaire_version_id"],
            ["questionnaire_version.id"],
            name=op.f("fk_tier_assessment_questionnaire_version_id_questionnaire_version"),
        ),
        sa.ForeignKeyConstraint(
            ["third_party_id"],
            ["third_party.id"],
            name=op.f("fk_tier_assessment_third_party_id_third_party"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tier_assessment")),
    )
    with op.batch_alter_table("tier_assessment", schema=None) as batch_op:
        batch_op.create_index("ix_tier_assessment_third_party_id", ["third_party_id"], unique=False)

    with op.batch_alter_table("third_party", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tier", sa.String(length=24), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("third_party", schema=None) as batch_op:
        batch_op.drop_column("tier")

    with op.batch_alter_table("tier_assessment", schema=None) as batch_op:
        batch_op.drop_index("ix_tier_assessment_third_party_id")

    op.drop_table("tier_assessment")
    with op.batch_alter_table("service", schema=None) as batch_op:
        batch_op.drop_index("ix_service_third_party_id")
        batch_op.drop_index("ix_service_org_unit_id")

    op.drop_table("service")
    op.execute("DELETE FROM counter WHERE prefix = 'SVC'")
