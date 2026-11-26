"""Evidence: items with their validity, what each supports, and files stored by digest
(EVD-01 to EVD-04, EVD-06).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "EV", "value": 0}])
    op.create_table(
        "stored_file",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(length=120), nullable=False),
        sa.Column("extension", sa.String(length=12), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stored_file")),
        sa.UniqueConstraint("sha256", name=op.f("uq_stored_file_sha256")),
    )
    op.create_table(
        "evidence",
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=200), nullable=True),
        sa.Column("url", sa.String(length=300), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("data_class", sa.String(length=40), nullable=True),
        sa.Column("collected_on", sa.Date(), nullable=False),
        sa.Column("covers_from", sa.Date(), nullable=True),
        sa.Column("covers_to", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
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
            "kind IN ('file', 'link', 'note', 'attestation')", name=op.f("ck_evidence_kind")
        ),
        sa.CheckConstraint("status IN ('active', 'retired')", name=op.f("ck_evidence_status")),
        sa.ForeignKeyConstraint(
            ["file_id"], ["stored_file.id"], name=op.f("fk_evidence_file_id_stored_file")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_unit.id"], name=op.f("fk_evidence_org_unit_id_org_unit")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
        sa.UniqueConstraint("ref", name=op.f("uq_evidence_ref")),
    )
    with op.batch_alter_table("evidence", schema=None) as batch_op:
        batch_op.create_index("ix_evidence_org_unit_id", ["org_unit_id"], unique=False)
        batch_op.create_index("ix_evidence_valid_until", ["valid_until"], unique=False)

    op.create_table(
        "evidence_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.id"],
            name=op.f("fk_evidence_link_evidence_id_evidence"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_link")),
        sa.UniqueConstraint("evidence_id", "subject_type", "subject_id", name="uq_evidence_link"),
    )
    with op.batch_alter_table("evidence_link", schema=None) as batch_op:
        batch_op.create_index(
            "ix_evidence_link_subject", ["subject_type", "subject_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("evidence_link", schema=None) as batch_op:
        batch_op.drop_index("ix_evidence_link_subject")

    op.drop_table("evidence_link")
    with op.batch_alter_table("evidence", schema=None) as batch_op:
        batch_op.drop_index("ix_evidence_valid_until")
        batch_op.drop_index("ix_evidence_org_unit_id")

    op.drop_table("evidence")
    op.drop_table("stored_file")
    op.execute("DELETE FROM counter WHERE prefix = 'EV'")
