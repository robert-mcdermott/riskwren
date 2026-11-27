"""Due diligence: contacts at third parties, reviews sent to them through links that need no
account, and answers given by a contact rather than an account (TPR-03).

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    counter = sa.table("counter", sa.column("prefix", sa.String), sa.column("value", sa.Integer))
    op.bulk_insert(counter, [{"prefix": "DDR", "value": 0}])
    op.create_table(
        "third_party_contact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("third_party_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'left')", name=op.f("ck_third_party_contact_status")
        ),
        sa.ForeignKeyConstraint(
            ["third_party_id"],
            ["third_party.id"],
            name=op.f("fk_third_party_contact_third_party_id_third_party"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_third_party_contact")),
    )
    with op.batch_alter_table("third_party_contact", schema=None) as batch_op:
        batch_op.create_index(
            "ix_third_party_contact_third_party_id", ["third_party_id"], unique=False
        )

    op.create_table(
        "respondent_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("expires_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("revoked_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("finished_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["third_party_contact.id"],
            name=op.f("fk_respondent_link_contact_id_third_party_contact"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_respondent_link")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_respondent_link_token_hash")),
    )
    with op.batch_alter_table("respondent_link", schema=None) as batch_op:
        batch_op.create_index(
            "ix_respondent_link_subject", ["subject_type", "subject_id"], unique=False
        )

    op.create_table(
        "third_party_review",
        sa.Column("third_party_id", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=24), nullable=True),
        sa.Column("questionnaire_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=True),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("sent_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("answered_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("conclusion", sa.String(length=16), nullable=True),
        sa.Column("conclusion_note", sa.Text(), nullable=True),
        sa.Column("concluded_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("concluded_by", sa.Integer(), nullable=True),
        sa.Column("concluded_by_name", sa.String(length=200), nullable=True),
        sa.Column("cancelled_note", sa.Text(), nullable=True),
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
            "conclusion IS NULL OR conclusion IN ('approved', 'conditions', 'declined')",
            name=op.f("ck_third_party_review_conclusion"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'sent', 'answered', 'concluded', 'cancelled')",
            name=op.f("ck_third_party_review_status"),
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["third_party_contact.id"],
            name=op.f("fk_third_party_review_contact_id_third_party_contact"),
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"],
            ["org_unit.id"],
            name=op.f("fk_third_party_review_org_unit_id_org_unit"),
        ),
        sa.ForeignKeyConstraint(
            ["questionnaire_id"],
            ["questionnaire.id"],
            name=op.f("fk_third_party_review_questionnaire_id_questionnaire"),
        ),
        sa.ForeignKeyConstraint(
            ["third_party_id"],
            ["third_party.id"],
            name=op.f("fk_third_party_review_third_party_id_third_party"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_third_party_review")),
        sa.UniqueConstraint("ref", name=op.f("uq_third_party_review_ref")),
    )
    with op.batch_alter_table("third_party_review", schema=None) as batch_op:
        batch_op.create_index("ix_third_party_review_org_unit_id", ["org_unit_id"], unique=False)
        batch_op.create_index(
            "ix_third_party_review_third_party_id", ["third_party_id"], unique=False
        )

    with op.batch_alter_table("response", schema=None) as batch_op:
        batch_op.add_column(sa.Column("contact_id", sa.Integer(), nullable=True))
        batch_op.alter_column("account_id", existing_type=sa.INTEGER(), nullable=True)
        batch_op.create_foreign_key(
            batch_op.f("fk_response_contact_id_third_party_contact"),
            "third_party_contact",
            ["contact_id"],
            ["id"],
        )


def downgrade() -> None:
    # Answers given through a link have no account; they go with the reviews they answered.
    op.execute("DELETE FROM response WHERE account_id IS NULL")
    with op.batch_alter_table("response", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_response_contact_id_third_party_contact"), type_="foreignkey"
        )
        batch_op.alter_column("account_id", existing_type=sa.INTEGER(), nullable=False)
        batch_op.drop_column("contact_id")

    with op.batch_alter_table("third_party_review", schema=None) as batch_op:
        batch_op.drop_index("ix_third_party_review_third_party_id")
        batch_op.drop_index("ix_third_party_review_org_unit_id")

    op.drop_table("third_party_review")
    with op.batch_alter_table("respondent_link", schema=None) as batch_op:
        batch_op.drop_index("ix_respondent_link_subject")

    op.drop_table("respondent_link")
    with op.batch_alter_table("third_party_contact", schema=None) as batch_op:
        batch_op.drop_index("ix_third_party_contact_third_party_id")

    op.drop_table("third_party_contact")
    op.execute("DELETE FROM counter WHERE prefix = 'DDR'")
