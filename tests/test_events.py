"""The history: automatic events, the hash chain, and the ways it refuses to be bypassed."""

from __future__ import annotations

import re
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import DBAPIError

from riskwren.core.clock import frozen_at
from riskwren.core.errors import AuditError
from riskwren.db.engine import Database
from riskwren.db.models import Event
from riskwren.events import audit, chain
from riskwren.events.actor import Actor
from tests.conftest import TESTER
from tests.models import Part, Scratch, Widget

pytestmark = pytest.mark.usefixtures("test_tables")
SRC = Path(__file__).resolve().parent.parent / "src" / "riskwren"


def events(db: Database) -> list[Event]:
    with db.read() as session:
        return list(session.scalars(select(Event).order_by(Event.id)))


def verify(db: Database) -> chain.ChainReport:
    with db.engine.connect() as conn:
        return chain.verify(conn)


def test_creating_a_row_records_what_it_was_given(db: Database) -> None:
    moment = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    actor = Actor.account(7, "Dana Okafor")
    with frozen_at(moment), db.write(actor) as session:
        session.add(Widget(name="first", size=3, ref="UC-0001"))
    [event] = events(db)
    assert (event.id, event.action, event.subject_type) == (1, "created", "widget")
    assert (event.actor_kind, event.actor_id, event.actor_label) == ("account", 7, "Dana Okafor")
    assert event.subject_id == 1 and event.subject_ref == "UC-0001"
    assert event.at == moment
    assert event.changes == {
        "id": [None, 1], "name": [None, "first"], "size": [None, 3], "ref": [None, "UC-0001"],
    }  # fmt: skip
    assert event.prev_hash == chain.GENESIS and len(event.hash) == 64


def test_changing_a_row_records_before_and_after(db: Database) -> None:
    with db.write(TESTER) as session:
        session.add(Widget(name="first", size=3))
    with db.write(TESTER) as session:
        widget = session.scalars(select(Widget)).one()
        widget.size = 5
        widget.name = "first"  # set to what it already was: not a change
    assert events(db)[-1].changes == {"size": [3, 5]}
    assert events(db)[-1].action == "updated"


def test_a_change_that_changes_nothing_records_nothing(db: Database) -> None:
    with db.write(TESTER) as session:
        session.add(Widget(name="same"))
    with db.write(TESTER) as session:
        session.scalars(select(Widget)).one().name = "same"
    assert len(events(db)) == 1


def test_deleting_a_row_records_what_was_lost(db: Database) -> None:
    with db.write(TESTER) as session:
        session.add(Widget(name="gone", size=9))
    with db.write(TESTER) as session:
        session.delete(session.scalars(select(Widget)).one())
    last = events(db)[-1]
    assert last.action == "deleted"
    assert last.changes == {"id": [1, None], "name": ["gone", None], "size": [9, None]}


def test_redacted_columns_show_that_they_changed_but_not_how(db: Database) -> None:
    with db.write(TESTER) as session:
        session.add(Widget(name="safe", secret="hunter2"))
    with db.write(TESTER) as session:
        session.scalars(select(Widget)).one().secret = "correct horse"
    first, second = events(db)
    assert first.changes["secret"] == [None, audit.REDACTED]
    assert second.changes["secret"] == [audit.REDACTED, audit.REDACTED]
    assert "hunter2" not in str(first.changes) + str(second.changes)


def test_a_child_row_names_the_record_it_belongs_to(db: Database) -> None:
    with db.write(TESTER) as session:
        widget = Widget(name="parent")
        session.add(widget)
        session.flush()
        session.add(Part(widget_id=widget.id, label="wheel"))
    part = events(db)[-1]
    assert (part.subject_type, part.parent_type, part.parent_id) == ("part", "widget", 1)


def test_unaudited_tables_leave_no_events(db: Database) -> None:
    with db.write(TESTER) as session:
        session.add(Scratch(note="bookkeeping"))
    assert events(db) == []


def test_an_operation_names_what_the_changes_were_part_of(db: Database) -> None:
    with db.write(TESTER, context={"request": "abc"}) as session:
        session.add(Widget(name="before"))
        with audit.operation(session, "widget.assemble", review="RV-0003"):
            session.add(Widget(name="during"))
        session.add(Widget(name="after"))
    before, during, after = events(db)
    assert before.context == {"request": "abc"}
    assert during.context == {"request": "abc", "op": "widget.assemble", "review": "RV-0003"}
    assert after.context == {"request": "abc"}


def test_things_that_are_not_changes_can_be_recorded(db: Database) -> None:
    with db.write(TESTER) as session:
        widget = Widget(name="read me", ref="EV-0001")
        session.add(widget)
        audit.record(session, "downloaded", widget, context={"file": "report.pdf"})
        audit.record(session, "exported", subject_kind="inventory", changes={"rows": 12})
    created, downloaded, exported = events(db)
    assert created.action == "created"
    assert (downloaded.action, downloaded.subject_ref) == ("downloaded", "EV-0001")
    assert downloaded.context == {"file": "report.pdf"}
    assert (exported.subject_type, exported.subject_id, exported.changes) == (
        "inventory",
        None,
        {"rows": 12},
    )


def test_a_write_with_no_actor_is_refused(db: Database) -> None:
    with db.read() as session:
        session.add(Widget(name="anonymous"))
        with pytest.raises(AuditError, match="no actor"):
            session.flush()
        session.rollback()
        with pytest.raises(AuditError, match="needs an actor"):
            audit.record(session, "looked")
    assert events(db) == []


@pytest.mark.parametrize(
    "statement",
    [
        update(Widget).values(name="quietly"),
        delete(Widget),
        insert(Widget).values(name="quietly"),
        update(Widget.__table__).values(name="quietly"),
    ],
)
def test_bulk_statements_on_audited_tables_are_refused(db: Database, statement) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(AuditError, match="without recording events"), db.write(TESTER) as session:
        session.execute(statement)


def test_bulk_statements_on_unaudited_tables_are_allowed(db: Database) -> None:
    with db.write(TESTER) as session:
        session.execute(insert(Scratch).values(note="fine"))
        session.execute(update(Scratch).values(note="still fine"))


def test_only_the_history_and_the_model_reach_past_the_session() -> None:
    """``session.connection()`` is the one way around the audit, so only the code that
    implements the audit, references, and migrations may use it."""
    allowed = {"events", "db"}
    offenders = [
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if path.relative_to(SRC).parts[0] not in allowed
        and re.search(r"\.connection\(\)", path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_the_chain_links_every_event_to_the_one_before(db: Database) -> None:
    for name in ("a", "b", "c"):
        with db.write(TESTER) as session:
            session.add(
                Widget(name=name, details={"unicode": "naïve — ✓", "ratio": 0.25, "big": 1e20})
            )
    recorded = events(db)
    assert [e.id for e in recorded] == [1, 2, 3]
    assert recorded[1].prev_hash == recorded[0].hash
    report = verify(db)
    assert report.ok and report.events == 3 and report.head == recorded[-1].hash


def _unguard(db: Database) -> None:
    """What someone with the database password would have to do first."""
    with db.engine.begin() as conn:
        if db.dialect == "sqlite":
            conn.execute(text("DROP TRIGGER event_no_update"))
            conn.execute(text("DROP TRIGGER event_no_delete"))
        else:
            conn.execute(text("ALTER TABLE event DISABLE TRIGGER USER"))


def _three(db: Database) -> None:
    for name in ("a", "b", "c"):
        with db.write(TESTER) as session:
            session.add(Widget(name=name))


def test_the_database_refuses_to_change_the_history(db: Database) -> None:
    _three(db)
    for statement in ("UPDATE event SET actor_label = 'someone else'", "DELETE FROM event"):
        with pytest.raises(DBAPIError, match="append-only"), db.engine.begin() as conn:
            conn.execute(text(statement))
    assert verify(db).ok


def test_an_altered_event_is_found(db: Database) -> None:
    _three(db)
    _unguard(db)
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE event SET actor_label = 'someone else' WHERE id = 2"))
    report = verify(db)
    assert not report.ok
    assert report.broken_at == 2 and "altered" in report.reason and report.events == 1


def test_an_altered_change_is_found(db: Database) -> None:
    _three(db)
    _unguard(db)
    with db.write(TESTER) as session:
        session.execute(update(Event).where(Event.id == 3).values(changes={"name": [None, "z"]}))
    report = verify(db)
    assert (report.ok, report.broken_at) == (False, 3)


def test_a_removed_event_is_found(db: Database) -> None:
    _three(db)
    _unguard(db)
    with db.engine.begin() as conn:
        conn.execute(text("DELETE FROM event WHERE id = 2"))
    report = verify(db)
    assert (report.ok, report.broken_at) == (False, 2) and "missing" in report.reason


def test_events_removed_from_the_end_are_found(db: Database) -> None:
    _three(db)
    _unguard(db)
    with db.engine.begin() as conn:
        conn.execute(text("DELETE FROM event WHERE id = 3"))
    report = verify(db)
    assert not report.ok and "removed from the end" in report.reason


def test_a_rewritten_event_with_a_fresh_hash_still_breaks_what_follows(db: Database) -> None:
    _three(db)
    _unguard(db)
    with db.engine.connect() as conn:
        row = conn.execute(select(Event).where(Event.id == 1)).one()._asdict()
    row["actor_label"] = "someone else"
    forged = chain.link(chain.GENESIS, chain.canonical(1, row["at"], row))
    with db.engine.begin() as conn:
        conn.execute(
            text("UPDATE event SET actor_label = 'someone else', hash = :h WHERE id = 1"),
            {"h": forged},
        )
    report = verify(db)
    assert (report.ok, report.broken_at) == (False, 2)


def test_writers_at_the_same_time_take_turns(db: Database) -> None:
    failures: list[BaseException] = []

    def work(who: int) -> None:
        try:
            for n in range(15):
                with db.write(Actor.account(who, f"Writer {who}")) as session:
                    session.add(Widget(name=f"{who}-{n}"))
        except BaseException as exc:
            failures.append(exc)

    threads = [threading.Thread(target=work, args=(who,)) for who in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert failures == []
    report = verify(db)
    assert report.ok and report.events == 60
    assert [e.id for e in events(db)] == list(range(1, 61))
