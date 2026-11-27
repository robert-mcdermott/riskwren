"""Scheduled work and email: each job's next turn and its runs, reminders already sent, the
email outbox, how each person wants notices by email, and what became of each notice as
email (OVS-01, OVS-03, OVS-05).

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("claimed_until", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("last_started_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("last_finished_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=16), nullable=True),
        sa.Column("last_summary", sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_job")),
    )
    op.create_table(
        "job_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_key", sa.String(length=40), nullable=False),
        sa.Column("started_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("finished_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("counts", riskwren.db.types.JsonType, nullable=False),
        sa.Column("error", sa.String(length=600), nullable=True),
        sa.CheckConstraint("status IN ('ok', 'failed')", name=op.f("ck_job_run_status")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_run")),
    )
    with op.batch_alter_table("job_run", schema=None) as batch_op:
        batch_op.create_index("ix_job_run_job_key", ["job_key", "id"], unique=False)

    op.create_table(
        "reminder",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("stage", sa.String(length=24), nullable=False),
        sa.Column("sent_on", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reminder")),
        sa.UniqueConstraint(
            "subject_type",
            "subject_id",
            "due_on",
            "stage",
            name=op.f("uq_reminder_subject_type_subject_id_due_on_stage"),
        ),
    )
    op.create_table(
        "outbox_message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("to_address", sa.String(length=254), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("digest_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("created_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("send_after", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("sent_at", riskwren.db.types.UtcDateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'sending', 'sent', 'failed')",
            name=op.f("ck_outbox_message_status"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_outbox_message_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_message")),
        sa.UniqueConstraint(
            "account_id", "digest_on", name=op.f("uq_outbox_message_account_id_digest_on")
        ),
    )
    with op.batch_alter_table("outbox_message", schema=None) as batch_op:
        batch_op.create_index("ix_outbox_message_status", ["status", "send_after"], unique=False)

    with op.batch_alter_table("account", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "email_notices", sa.String(length=16), nullable=False, server_default="immediate"
            )
        )
    with op.batch_alter_table("account", schema=None) as batch_op:
        batch_op.alter_column("email_notices", server_default=None)

    with op.batch_alter_table("notice", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mail_state", sa.String(length=16), nullable=True))
        batch_op.create_index("ix_notice_mail_state", ["mail_state"], unique=False)
    # Notices written before email existed are never sent as email.
    op.execute("UPDATE notice SET mail_state = 'skipped'")


def downgrade() -> None:
    with op.batch_alter_table("notice", schema=None) as batch_op:
        batch_op.drop_index("ix_notice_mail_state")
        batch_op.drop_column("mail_state")

    with op.batch_alter_table("account", schema=None) as batch_op:
        batch_op.drop_column("email_notices")

    with op.batch_alter_table("outbox_message", schema=None) as batch_op:
        batch_op.drop_index("ix_outbox_message_status")

    op.drop_table("outbox_message")
    op.drop_table("reminder")
    with op.batch_alter_table("job_run", schema=None) as batch_op:
        batch_op.drop_index("ix_job_run_job_key")

    op.drop_table("job_run")
    op.drop_table("job")
