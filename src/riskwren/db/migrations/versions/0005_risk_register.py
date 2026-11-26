"""Risk register: categories, the scoring method, risks, assessments, and the library
(RSK-01 to RSK-11).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("RSK",)


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "risk_category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("appetite", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_risk_category_status")),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["risk_category.id"],
            name=op.f("fk_risk_category_parent_id_risk_category"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_category")),
        sa.UniqueConstraint("key", name=op.f("uq_risk_category_key")),
    )
    op.create_table(
        "risk_library",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("category_key", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("cause", sa.Text(), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("consequence", sa.Text(), nullable=False),
        sa.Column("suggested_controls", riskwren.db.types.JsonType, nullable=False),
        sa.Column("source_pack", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_library")),
        sa.UniqueConstraint("key", name=op.f("uq_risk_library_key")),
    )
    op.create_table(
        "scoring_method",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("definition", riskwren.db.types.JsonType, nullable=False),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("published_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('current', 'superseded')", name=op.f("ck_scoring_method_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scoring_method")),
        sa.UniqueConstraint("version", name=op.f("uq_scoring_method_version")),
    )
    op.create_table(
        "risk",
        sa.Column("cause", sa.Text(), nullable=True),
        sa.Column("event", sa.Text(), nullable=True),
        sa.Column("consequence", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("closed_reason", sa.Text(), nullable=True),
        sa.Column("response", sa.String(length=16), nullable=True),
        sa.Column("response_rationale", sa.Text(), nullable=True),
        sa.Column("inherent_likelihood", sa.Integer(), nullable=True),
        sa.Column("inherent_impact", sa.Integer(), nullable=True),
        sa.Column("inherent_rating", sa.String(length=40), nullable=True),
        sa.Column("residual_likelihood", sa.Integer(), nullable=True),
        sa.Column("residual_impact", sa.Integer(), nullable=True),
        sa.Column("residual_rating", sa.String(length=40), nullable=True),
        sa.Column("target_likelihood", sa.Integer(), nullable=True),
        sa.Column("target_impact", sa.Integer(), nullable=True),
        sa.Column("target_rating", sa.String(length=40), nullable=True),
        sa.Column("standing", sa.String(length=24), nullable=False),
        sa.Column("next_review_on", sa.Date(), nullable=True),
        sa.Column("residual_in_doubt", sa.Boolean(), nullable=False),
        sa.Column("residual_doubt_reason", sa.Text(), nullable=True),
        sa.Column("escalated_to_unit_id", sa.Integer(), nullable=True),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column("library_key", sa.String(length=80), nullable=True),
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
            "response IS NULL OR response IN ('reduce', 'accept', 'transfer', 'avoid')",
            name=op.f("ck_risk_response"),
        ),
        sa.CheckConstraint(
            "standing IN ('not_assessed', 'within', 'treated', 'accepted', 'needs_decision', 'closed')",
            name=op.f("ck_risk_standing"),
        ),
        sa.CheckConstraint("status IN ('draft', 'open', 'closed')", name=op.f("ck_risk_status")),
        sa.ForeignKeyConstraint(
            ["category_id"], ["risk_category.id"], name=op.f("fk_risk_category_id_risk_category")
        ),
        sa.ForeignKeyConstraint(
            ["escalated_to_unit_id"],
            ["org_unit.id"],
            name=op.f("fk_risk_escalated_to_unit_id_org_unit"),
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_risk_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk")),
        sa.UniqueConstraint("ref", name=op.f("uq_risk_ref")),
    )
    with op.batch_alter_table("risk", schema=None) as batch_op:
        batch_op.create_index("ix_risk_category_id", ["category_id"], unique=False)
        batch_op.create_index(
            "ix_risk_escalated_to_unit_id", ["escalated_to_unit_id"], unique=False
        )
        batch_op.create_index("ix_risk_org_unit_id", ["org_unit_id"], unique=False)
        batch_op.create_index("ix_risk_standing", ["standing"], unique=False)

    op.create_table(
        "risk_assessment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("likelihood", sa.Integer(), nullable=False),
        sa.Column("impact", sa.Integer(), nullable=False),
        sa.Column("impact_levels", riskwren.db.types.JsonType, nullable=False),
        sa.Column("rating", sa.String(length=40), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("suggested", riskwren.db.types.JsonType, nullable=True),
        sa.Column("method_id", sa.Integer(), nullable=False),
        sa.Column("assessed_by", sa.Integer(), nullable=True),
        sa.Column("assessed_by_name", sa.String(length=200), nullable=False),
        sa.Column("assessed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('inherent', 'residual', 'target')", name=op.f("ck_risk_assessment_kind")
        ),
        sa.ForeignKeyConstraint(
            ["method_id"],
            ["scoring_method.id"],
            name=op.f("fk_risk_assessment_method_id_scoring_method"),
        ),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name=op.f("fk_risk_assessment_risk_id_risk")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_assessment")),
    )
    with op.batch_alter_table("risk_assessment", schema=None) as batch_op:
        batch_op.create_index("ix_risk_assessment_risk_id", ["risk_id"], unique=False)

    op.create_table(
        "risk_subject",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name=op.f("fk_risk_subject_risk_id_risk")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_subject")),
        sa.UniqueConstraint(
            "risk_id",
            "subject_type",
            "subject_id",
            name=op.f("uq_risk_subject_risk_id_subject_type_subject_id"),
        ),
    )
    with op.batch_alter_table("risk_subject", schema=None) as batch_op:
        batch_op.create_index(
            "ix_risk_subject_subject", ["subject_type", "subject_id"], unique=False
        )


def downgrade() -> None:
    op.execute("DELETE FROM counter WHERE prefix IN ('RSK')")
    with op.batch_alter_table("risk_subject", schema=None) as batch_op:
        batch_op.drop_index("ix_risk_subject_subject")

    op.drop_table("risk_subject")
    with op.batch_alter_table("risk_assessment", schema=None) as batch_op:
        batch_op.drop_index("ix_risk_assessment_risk_id")

    op.drop_table("risk_assessment")
    with op.batch_alter_table("risk", schema=None) as batch_op:
        batch_op.drop_index("ix_risk_standing")
        batch_op.drop_index("ix_risk_org_unit_id")
        batch_op.drop_index("ix_risk_escalated_to_unit_id")
        batch_op.drop_index("ix_risk_category_id")

    op.drop_table("risk")
    op.drop_table("scoring_method")
    op.drop_table("risk_library")
    op.drop_table("risk_category")
