"""Framework updates: the version a framework follows, the publisher's mappings between
requirements, suggested crosswalks set aside, and mappings carried across to a new version
(CMP-10, CMP-11).

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "framework_mapping",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_key", sa.String(length=80), nullable=False),
        sa.Column("from_code", sa.String(length=120), nullable=False),
        sa.Column("relation", sa.String(length=24), nullable=False),
        sa.Column("to_key", sa.String(length=80), nullable=False),
        sa.Column("to_code", sa.String(length=120), nullable=False),
        sa.Column("pack_key", sa.String(length=80), nullable=False),
        sa.CheckConstraint(
            "relation IN ('derived_from', 'moved_to', 'incorporated_into')",
            name=op.f("ck_framework_mapping_relation"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_framework_mapping")),
        sa.UniqueConstraint(
            "from_key",
            "from_code",
            "relation",
            "to_key",
            "to_code",
            name=op.f("uq_framework_mapping_from_key_from_code_relation_to_key_to_code"),
        ),
    )
    with op.batch_alter_table("framework_mapping", schema=None) as batch_op:
        batch_op.create_index("ix_framework_mapping_to", ["to_key", "to_code"], unique=False)

    op.create_table(
        "suggestion_set_aside",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("set_aside_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_suggestion_set_aside_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name=op.f("fk_suggestion_set_aside_control_id_control")
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirement.id"],
            name=op.f("fk_suggestion_set_aside_requirement_id_requirement"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suggestion_set_aside")),
        sa.UniqueConstraint(
            "control_id",
            "requirement_id",
            name=op.f("uq_suggestion_set_aside_control_id_requirement_id"),
        ),
    )
    with op.batch_alter_table("framework", schema=None) as batch_op:
        batch_op.add_column(sa.Column("follows", sa.String(length=80), nullable=True))

    with op.batch_alter_table("control_requirement", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_control_requirement_source"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_control_requirement_source"), "source IN ('pack', 'person', 'carried')"
        )


def downgrade() -> None:
    op.execute("UPDATE control_requirement SET source = 'person' WHERE source = 'carried'")
    with op.batch_alter_table("control_requirement", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_control_requirement_source"), type_="check")
        batch_op.create_check_constraint(
            batch_op.f("ck_control_requirement_source"), "source IN ('pack', 'person')"
        )

    with op.batch_alter_table("framework", schema=None) as batch_op:
        batch_op.drop_column("follows")

    op.drop_table("suggestion_set_aside")
    with op.batch_alter_table("framework_mapping", schema=None) as batch_op:
        batch_op.drop_index("ix_framework_mapping_to")

    op.drop_table("framework_mapping")
