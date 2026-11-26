"""Single sign-on: who an account is at the identity provider, which of the provider's roles
or groups give which role here, and round trips in flight (PLT-13).

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sign_in_request",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("verifier", sa.String(length=128), nullable=False),
        sa.Column("next_path", sa.String(length=500), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sign_in_request")),
        sa.UniqueConstraint("state_hash", name=op.f("uq_sign_in_request_state_hash")),
    )
    op.create_table(
        "identity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("issuer", sa.String(length=300), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_identity_account_id_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity")),
        sa.UniqueConstraint("issuer", "subject", name=op.f("uq_identity_issuer_subject")),
    )
    with op.batch_alter_table("identity", schema=None) as batch_op:
        batch_op.create_index("ix_identity_account_id", ["account_id"], unique=False)

    op.create_table(
        "provider_mapping",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_value", sa.String(length=300), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("org_unit_id", sa.Integer(), nullable=True),
        sa.Column("accept_limit", sa.String(length=40), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_provider_mapping_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_mapping")),
    )
    with op.batch_alter_table("provider_mapping", schema=None) as batch_op:
        batch_op.create_index("ix_provider_mapping_claim_value", ["claim_value"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("provider_mapping", schema=None) as batch_op:
        batch_op.drop_index("ix_provider_mapping_claim_value")

    op.drop_table("provider_mapping")
    with op.batch_alter_table("identity", schema=None) as batch_op:
        batch_op.drop_index("ix_identity_account_id")

    op.drop_table("identity")
    op.drop_table("sign_in_request")
