"""Foundation: the history, the head of its chain, and reference counters (PLT-05).

Revision ID: 0001
Revises:
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import riskwren.db.types

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GENESIS = "0" * 64

# The history is append-only. The application never updates or deletes an event, and these
# triggers refuse anyone else who tries. Dropping a trigger is itself a deliberate act that
# `riskwren doctor` reports.
SQLITE_TRIGGERS = (
    """
    CREATE TRIGGER event_no_update BEFORE UPDATE ON event
    BEGIN SELECT RAISE(ABORT, 'the history is append-only'); END
    """,
    """
    CREATE TRIGGER event_no_delete BEFORE DELETE ON event
    BEGIN SELECT RAISE(ABORT, 'the history is append-only'); END
    """,
)
POSTGRES_TRIGGERS = (
    """
    CREATE FUNCTION event_append_only() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'the history is append-only'; END
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER event_no_change BEFORE UPDATE OR DELETE ON event
    FOR EACH ROW EXECUTE FUNCTION event_append_only()
    """,
    """
    CREATE TRIGGER event_no_truncate BEFORE TRUNCATE ON event
    FOR EACH STATEMENT EXECUTE FUNCTION event_append_only()
    """,
)


def upgrade() -> None:
    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("at", riskwren.db.types.UtcDateTime(timezone=True), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_label", sa.String(length=200), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("subject_ref", sa.String(length=24), nullable=True),
        sa.Column("parent_type", sa.String(length=40), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("changes", riskwren.db.types.JsonType, nullable=False),
        sa.Column("context", riskwren.db.types.JsonType, nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event")),
    )
    op.create_index("ix_event_subject", "event", ["subject_type", "subject_id", "id"])
    op.create_index("ix_event_parent", "event", ["parent_type", "parent_id", "id"])
    op.create_index("ix_event_actor", "event", ["actor_id", "id"])
    op.create_index("ix_event_at", "event", ["at"])

    chain_head = op.create_table(
        "chain_head",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_chain_head_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chain_head")),
    )
    op.bulk_insert(chain_head, [{"id": 1, "seq": 0, "hash": GENESIS}])

    op.create_table(
        "counter",
        sa.Column("prefix", sa.String(length=8), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("prefix", name=op.f("pk_counter")),
    )

    triggers = SQLITE_TRIGGERS if op.get_bind().dialect.name == "sqlite" else POSTGRES_TRIGGERS
    for statement in triggers:
        op.execute(statement)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER event_no_truncate ON event")
        op.execute("DROP TRIGGER event_no_change ON event")
        op.execute("DROP FUNCTION event_append_only()")
    op.drop_table("counter")
    op.drop_table("chain_head")
    op.drop_table("event")
