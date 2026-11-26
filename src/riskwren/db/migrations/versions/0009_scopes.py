"""Scopes: information assets, scopes with their boundary and frameworks, applicability,
and implementations with inheritance (INV-07, CMP-06, CMP-07, CTL-06 to CTL-08).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREFIXES = ("INF", "SCP")


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": prefix, "value": 0} for prefix in PREFIXES])
    op.create_table(
        "information",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("held_in", sa.Text(), nullable=True),
        sa.Column("shared_with", sa.Text(), nullable=True),
        sa.Column("agreement", sa.String(length=300), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_information_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_information_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_information")),
        sa.UniqueConstraint("ref", name=op.f("uq_information_ref")),
    )
    with op.batch_alter_table("information", schema=None) as batch_op:
        batch_op.create_index("ix_information_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "scope",
        sa.Column("boundary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("offers_controls", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_scope_status")),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_scope_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scope")),
        sa.UniqueConstraint("ref", name=op.f("uq_scope_ref")),
    )
    with op.batch_alter_table("scope", schema=None) as batch_op:
        batch_op.create_index("ix_scope_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "implementation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("responsibility", sa.String(length=200), nullable=True),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("inheritance", sa.String(length=16), nullable=False),
        sa.Column("inherits_from_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "inheritance IN ('none', 'inherited', 'shared')",
            name=op.f("ck_implementation_inheritance"),
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'partly', 'in_place', 'not_applicable')",
            name=op.f("ck_implementation_status"),
        ),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name=op.f("fk_implementation_control_id_control")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["account.id"], name=op.f("fk_implementation_created_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["inherits_from_id"],
            ["implementation.id"],
            name=op.f("fk_implementation_inherits_from_id_implementation"),
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"],
            ["scope.id"],
            name=op.f("fk_implementation_scope_id_scope"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_implementation")),
        sa.UniqueConstraint("scope_id", "control_id", name="uq_implementation_scope_control"),
    )
    with op.batch_alter_table("implementation", schema=None) as batch_op:
        batch_op.create_index("ix_implementation_control_id", ["control_id"], unique=False)
        batch_op.create_index(
            "ix_implementation_inherits_from_id", ["inherits_from_id"], unique=False
        )

    op.create_table(
        "scope_member",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scope_id"],
            ["scope.id"],
            name=op.f("fk_scope_member_scope_id_scope"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scope_member")),
        sa.UniqueConstraint("scope_id", "subject_type", "subject_id", name="uq_scope_member"),
    )
    with op.batch_alter_table("scope_member", schema=None) as batch_op:
        batch_op.create_index(
            "ix_scope_member_subject", ["subject_type", "subject_id"], unique=False
        )

    op.create_table(
        "scope_framework",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("framework_id", sa.Integer(), nullable=False),
        sa.Column("baseline_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["baseline_id"], ["baseline.id"], name=op.f("fk_scope_framework_baseline_id_baseline")
        ),
        sa.ForeignKeyConstraint(
            ["framework_id"],
            ["framework.id"],
            name=op.f("fk_scope_framework_framework_id_framework"),
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"],
            ["scope.id"],
            name=op.f("fk_scope_framework_scope_id_scope"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scope_framework")),
        sa.UniqueConstraint("scope_id", "framework_id", name="uq_scope_framework"),
    )
    with op.batch_alter_table("scope_framework", schema=None) as batch_op:
        batch_op.create_index("ix_scope_framework_framework_id", ["framework_id"], unique=False)

    op.create_table(
        "scope_requirement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.Column("applicable", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_by_name", sa.String(length=200), nullable=True),
        sa.Column("decided_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["account.id"], name=op.f("fk_scope_requirement_decided_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirement.id"],
            name=op.f("fk_scope_requirement_requirement_id_requirement"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"],
            ["scope.id"],
            name=op.f("fk_scope_requirement_scope_id_scope"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scope_requirement")),
        sa.UniqueConstraint("scope_id", "requirement_id", name="uq_scope_requirement"),
    )
    with op.batch_alter_table("scope_requirement", schema=None) as batch_op:
        batch_op.create_index(
            "ix_scope_requirement_requirement_id", ["requirement_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("scope_requirement", schema=None) as batch_op:
        batch_op.drop_index("ix_scope_requirement_requirement_id")

    op.drop_table("scope_requirement")
    with op.batch_alter_table("scope_framework", schema=None) as batch_op:
        batch_op.drop_index("ix_scope_framework_framework_id")

    op.drop_table("scope_framework")
    with op.batch_alter_table("scope_member", schema=None) as batch_op:
        batch_op.drop_index("ix_scope_member_subject")

    op.drop_table("scope_member")
    with op.batch_alter_table("implementation", schema=None) as batch_op:
        batch_op.drop_index("ix_implementation_inherits_from_id")
        batch_op.drop_index("ix_implementation_control_id")

    op.drop_table("implementation")
    with op.batch_alter_table("scope", schema=None) as batch_op:
        batch_op.drop_index("ix_scope_org_unit_id")

    op.drop_table("scope")
    with op.batch_alter_table("information", schema=None) as batch_op:
        batch_op.drop_index("ix_information_org_unit_id")

    op.drop_table("information")
    op.execute("DELETE FROM counter WHERE prefix IN ('INF', 'SCP')")
