"""Assessments: assessments of a scope, the tests planned in each, and their results
(AST-01 to AST-05).

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "ASM", "value": 0}])
    op.create_table(
        "assessment",
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("framework_id", sa.Integer(), nullable=True),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("approach", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("completed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
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
            "status IN ('planned', 'in_progress', 'complete', 'cancelled')",
            name=op.f("ck_assessment_status"),
        ),
        sa.ForeignKeyConstraint(
            ["framework_id"], ["framework.id"], name=op.f("fk_assessment_framework_id_framework")
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["account.id"], name=op.f("fk_assessment_lead_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_assessment_org_unit_id_org_unit")
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name=op.f("fk_assessment_scope_id_scope")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment")),
        sa.UniqueConstraint("ref", name=op.f("uq_assessment_ref")),
    )
    with op.batch_alter_table("assessment", schema=None) as batch_op:
        batch_op.create_index("ix_assessment_org_unit_id", ["org_unit_id"], unique=False)
        batch_op.create_index("ix_assessment_scope_id", ["scope_id"], unique=False)

    op.create_table(
        "control_test",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("implementation_id", sa.Integer(), nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("procedure", sa.Text(), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "method IN ('examine', 'interview', 'test')", name=op.f("ck_control_test_method")
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessment.id"],
            name=op.f("fk_control_test_assessment_id_assessment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"], ["account.id"], name=op.f("fk_control_test_assigned_to_account")
        ),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name=op.f("fk_control_test_control_id_control")
        ),
        sa.ForeignKeyConstraint(
            ["implementation_id"],
            ["implementation.id"],
            name=op.f("fk_control_test_implementation_id_implementation"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_test")),
        sa.UniqueConstraint("assessment_id", "control_id", name="uq_control_test"),
    )
    with op.batch_alter_table("control_test", schema=None) as batch_op:
        batch_op.create_index("ix_control_test_assigned_to", ["assigned_to"], unique=False)
        batch_op.create_index("ix_control_test_control_id", ["control_id"], unique=False)

    op.create_table(
        "test_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("sample", sa.Text(), nullable=True),
        sa.Column("design", sa.String(length=16), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("tested_by", sa.Integer(), nullable=True),
        sa.Column("tested_by_name", sa.String(length=200), nullable=False),
        sa.Column("tested_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("review", sa.String(length=16), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_name", sa.String(length=200), nullable=True),
        sa.Column("reviewed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "design IN ('effective', 'partly', 'ineffective')", name=op.f("ck_test_result_design")
        ),
        sa.CheckConstraint(
            "operation IN ('effective', 'partly', 'ineffective')",
            name=op.f("ck_test_result_operation"),
        ),
        sa.CheckConstraint(
            "review IS NULL OR review IN ('confirmed', 'returned')",
            name=op.f("ck_test_result_review"),
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessment.id"],
            name=op.f("fk_test_result_assessment_id_assessment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["account.id"], name=op.f("fk_test_result_reviewed_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["test_id"],
            ["control_test.id"],
            name=op.f("fk_test_result_test_id_control_test"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tested_by"], ["account.id"], name=op.f("fk_test_result_tested_by_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_result")),
    )
    with op.batch_alter_table("test_result", schema=None) as batch_op:
        batch_op.create_index("ix_test_result_test_id", ["test_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("test_result", schema=None) as batch_op:
        batch_op.drop_index("ix_test_result_test_id")

    op.drop_table("test_result")
    with op.batch_alter_table("control_test", schema=None) as batch_op:
        batch_op.drop_index("ix_control_test_control_id")
        batch_op.drop_index("ix_control_test_assigned_to")

    op.drop_table("control_test")
    with op.batch_alter_table("assessment", schema=None) as batch_op:
        batch_op.drop_index("ix_assessment_scope_id")
        batch_op.drop_index("ix_assessment_org_unit_id")

    op.drop_table("assessment")
    op.execute("DELETE FROM counter WHERE prefix = 'ASM'")
