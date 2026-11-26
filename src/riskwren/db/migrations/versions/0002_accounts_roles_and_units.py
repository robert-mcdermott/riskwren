"""Accounts, credentials, roles, units, and sign-in sessions (PLT-03, PLT-04, INV-01).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("time_zone", sa.String(length=64), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('invited', 'active', 'disabled')", name=op.f("ck_account_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account")),
        sa.UniqueConstraint("email", name=op.f("uq_account_email")),
    )
    op.create_table(
        "failed_sign_in",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("failed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_failed_sign_in")),
    )
    with op.batch_alter_table("failed_sign_in", schema=None) as batch_op:
        batch_op.create_index("ix_failed_sign_in_key_hash", ["key_hash", "failed_at"], unique=False)

    op.create_table(
        "org_unit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'closed')", name=op.f("ck_org_unit_status")),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["org_unit.id"], name=op.f("fk_org_unit_parent_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_org_unit")),
        sa.UniqueConstraint("code", name=op.f("uq_org_unit_code")),
    )
    with op.batch_alter_table("org_unit", schema=None) as batch_op:
        batch_op.create_index("ix_org_unit_parent_id", ["parent_id"], unique=False)

    op.create_table(
        "credential",
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("changed_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_credential_account_id_account")
        ),
        sa.PrimaryKeyConstraint("account_id", name=op.f("pk_credential")),
    )
    op.create_table(
        "membership",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_membership_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_membership_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_membership")),
        sa.UniqueConstraint(
            "account_id", "org_unit_id", name=op.f("uq_membership_account_id_org_unit_id")
        ),
    )
    with op.batch_alter_table("membership", schema=None) as batch_op:
        batch_op.create_index("ix_membership_org_unit_id", ["org_unit_id"], unique=False)

    op.create_table(
        "role_grant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=True),
        sa.Column("accept_limit", sa.String(length=40), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column("granted_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('local', 'provider')", name=op.f("ck_role_grant_source")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_role_grant_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_role_grant_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_grant")),
    )
    with op.batch_alter_table("role_grant", schema=None) as batch_op:
        batch_op.create_index("ix_role_grant_account_id", ["account_id"], unique=False)
        batch_op.create_index("ix_role_grant_role", ["role"], unique=False)

    op.create_table(
        "session_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("expires_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_session_token_account_id_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_session_token_token_hash")),
    )
    with op.batch_alter_table("session_token", schema=None) as batch_op:
        batch_op.create_index("ix_session_token_account_id", ["account_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("session_token", schema=None) as batch_op:
        batch_op.drop_index("ix_session_token_account_id")

    op.drop_table("session_token")
    with op.batch_alter_table("role_grant", schema=None) as batch_op:
        batch_op.drop_index("ix_role_grant_role")
        batch_op.drop_index("ix_role_grant_account_id")

    op.drop_table("role_grant")
    with op.batch_alter_table("membership", schema=None) as batch_op:
        batch_op.drop_index("ix_membership_org_unit_id")

    op.drop_table("membership")
    op.drop_table("credential")
    with op.batch_alter_table("org_unit", schema=None) as batch_op:
        batch_op.drop_index("ix_org_unit_parent_id")

    op.drop_table("org_unit")
    with op.batch_alter_table("failed_sign_in", schema=None) as batch_op:
        batch_op.drop_index("ix_failed_sign_in_key_hash")

    op.drop_table("failed_sign_in")
    op.drop_table("account")
