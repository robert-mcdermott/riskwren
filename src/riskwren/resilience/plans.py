"""Continuity plans and exercises (RES-03, RES-04).

A continuity plan is a document of the kind "plan": written, approved by named people,
published, and reviewed as any document is, so its versions, owners, and review dates are a
document's. What is particular to a plan is kept here: the processes it restores, with what
each needs and what it relies on; a copy that prints cleanly, or downloads as one file, for
use when systems are down; and the exercises that test it, whose findings are issues.
"""

from __future__ import annotations

import html
import re
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import issues
from riskwren.compliance.issues import ISSUE
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Account,
    ContinuityCover,
    ContinuityExercise,
    Issue,
    PolicyDocument,
    PolicyVersion,
    Process,
)
from riskwren.db.models.resilience import EXERCISE_KINDS, EXERCISE_RESULTS
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import PROCESS, TYPES, find
from riskwren.policy import documents
from riskwren.policy.documents import DOCUMENT
from riskwren.program import rules, vocab
from riskwren.resilience import check, current_analysis

KIND = "plan"
EXERCISE_LABELS = {
    "tabletop": "Tabletop", "walkthrough": "Walk-through", "simulation": "Simulation",
    "full": "Full interruption",
}  # fmt: skip
RESULT_LABELS = {"met": "Objectives met", "partly": "Partly met", "not_met": "Not met"}


# --- Which plan, and who may do what ------------------------------------------------------


def load(session: Session, principal: Principal, ref: str) -> PolicyDocument:
    document = records.load(session, principal, DOCUMENT, ref)
    if document.kind != KIND:
        raise NotFound(f"{document.ref} is not a continuity plan.")
    return document


def can_change(session: Session, principal: Principal, document: PolicyDocument) -> bool:
    return documents.can_edit(session, principal, document)


def can_exercise(session: Session, principal: Principal, document: PolicyDocument) -> bool:
    """Its editors, and those who assess for its unit, who often run exercises."""
    return can_change(session, principal, document) or principal.assesses_unit(document.org_unit_id)


def exercise_months(session: Session) -> int:
    return int(rules.get(session, "cadences").get("plan_exercise_months") or 12)


# --- What it restores ---------------------------------------------------------------------


def set_covers(
    session: Session, principal: Principal, document: PolicyDocument, refs: list[str]
) -> None:
    """Say every process the plan restores, by reference."""
    if not can_change(session, principal, document):
        raise PermissionDenied("What a plan restores is said by those who keep the plan.")
    errors = records.Errors()
    wanted: set[int] = set()
    for ref in dict.fromkeys(str(each).strip().upper() for each in refs if str(each).strip()):
        try:
            process = find(session, PROCESS, ref)
        except NotFound:
            errors.add("processes", f"There is no process {ref}.")
            continue
        wanted.add(process.id)
    if errors:
        raise Invalid("What it restores was not changed.", errors)
    have = {
        row.process_id: row
        for row in session.scalars(
            select(ContinuityCover).where(ContinuityCover.document_id == document.id)
        )
    }
    with audit.operation(session, "plan.covers"):
        for process_id, row in have.items():
            if process_id not in wanted:
                session.delete(row)
        for process_id in sorted(wanted - set(have)):
            session.add(ContinuityCover(document_id=document.id, process_id=process_id))
        records.touch(session, document)
        session.flush()


def covers(
    session: Session, principal: Principal, document: PolicyDocument
) -> list[dict[str, Any]]:
    """Each process the plan restores: how soon, within what loss, the least it needs, and
    each thing it relies on, against what that can deliver."""
    out = []
    for row in session.scalars(
        select(ContinuityCover).where(ContinuityCover.document_id == document.id)
    ):
        process = session.get(Process, row.process_id)
        if process is None:
            continue
        analysis = current_analysis(session, process.id)
        out.append(
            {
                **records.chip(PROCESS, process),
                "org_unit_id": process.org_unit_id,
                "recovery_hours": analysis.recovery_hours if analysis else None,
                "data_loss_hours": analysis.data_loss_hours if analysis else None,
                "minimum": analysis.minimum if analysis else None,
                "dependencies": check(session, process, analysis),
            }
        )
    return sorted(
        out, key=lambda item: (item["recovery_hours"] is None, item["recovery_hours"] or 0)
    )


def plans_of(session: Session, principal: Principal, process: Process) -> list[dict[str, Any]]:
    """The continuity plans that restore a process."""
    rows = session.scalars(
        select(PolicyDocument)
        .join(ContinuityCover, ContinuityCover.document_id == PolicyDocument.id)
        .where(ContinuityCover.process_id == process.id, PolicyDocument.status == "active")
        .order_by(PolicyDocument.ref)
    ).all()
    return [
        {**records.chip(DOCUMENT, row), "published": row.published_version_id is not None}
        for row in rows
        if access.can_see(session, principal, DOCUMENT, row)
    ]


def contacts(
    session: Session, document: PolicyDocument, covered: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Whom to call: the plan's owners, and the owners of what it restores and relies on."""
    people: dict[int, dict[str, Any]] = {}

    def add(record_type: Any, record_id: int, why: str) -> None:
        for owner in records.owners_of(session, record_type, [record_id]).get(record_id, []):
            if not owner["active"]:
                continue
            found = people.setdefault(owner["account_id"], {
                "account_id": owner["account_id"], "name": owner["name"], "email": owner["email"],
                "title": None, "for": []})  # fmt: skip
            if why not in found["for"]:
                found["for"].append(why)

    add(DOCUMENT, document.id, "This plan")
    for item in covered:
        process = session.scalars(select(Process).where(Process.ref == item["ref"])).first()
        if process is not None:
            add(PROCESS, process.id, item["name"])
        for dependency in item["dependencies"]:
            record_type = TYPES[dependency["type"]]
            thing = session.scalars(
                select(record_type.model).where(record_type.model.ref == dependency["ref"])
            ).first()
            if thing is not None:
                add(record_type, thing.id, dependency["name"])
    titles = dict(
        session.execute(
            select(Account.id, Account.title).where(Account.id.in_(list(people) or [0]))
        ).all()
    )
    for account_id, person in people.items():
        person["title"] = titles.get(account_id)
    return sorted(people.values(), key=lambda person: person["name"])


# --- Exercises ----------------------------------------------------------------------------


def _day(value: Any, field: str, errors: records.Errors) -> date | None:
    try:
        day = value if isinstance(value, date) else date.fromisoformat(str(value))
    except (TypeError, ValueError):
        errors.add(field, "Give the day, as year-month-day.")
        return None
    if day > utc_now().date():
        errors.add(field, "That day has not come yet.")
        return None
    return day


def record_exercise(
    session: Session, principal: Principal, document: PolicyDocument, values: Mapping[str, Any]
) -> ContinuityExercise:
    if not can_exercise(session, principal, document):
        raise PermissionDenied("An exercise is recorded by those who keep the plan or assess it.")
    errors = records.Errors()
    kind = values.get("kind")
    if kind not in EXERCISE_KINDS:
        errors.add("kind", "Say what kind of exercise it was.")
    held_on = _day(values.get("held_on"), "held_on", errors)
    scenario = records.text(values.get("scenario"))
    if not scenario:
        errors.add("scenario", "Say what was tried: the scenario the plan was put to.")
    outcome = records.text(values.get("outcome"))
    if not outcome:
        errors.add("outcome", "Say what happened.")
    result = values.get("result")
    if result not in EXERCISE_RESULTS:
        errors.add("result", "Say whether its recovery objectives were met.")
    achieved = values.get("achieved_hours")
    if achieved not in (None, ""):
        try:
            achieved = int(achieved)
            if achieved < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.add("achieved_hours", "Give a whole number of hours.")
            achieved = None
    else:
        achieved = None
    if errors or held_on is None:
        raise Invalid("The exercise was not recorded.", errors)
    row = ContinuityExercise(
        document_id=document.id, version_id=document.published_version_id, kind=kind,
        held_on=held_on, scenario=scenario, participants=records.text(values.get("participants")),
        outcome=outcome, result=result, achieved_hours=achieved,
        recorded_by=principal.account_id, recorded_by_name=principal.name, recorded_at=utc_now(),
    )  # fmt: skip
    with audit.operation(session, "plan.exercise"):
        session.add(row)
        records.touch(session, document)
        session.flush()
    return row


def raise_finding(
    session: Session,
    principal: Principal,
    document: PolicyDocument,
    exercise_id: int,
    values: Mapping[str, Any],
) -> Issue:
    """A finding of an exercise: an issue in the one register, with the exercise as its
    source, raised for the plan's unit by whoever may record exercises of it."""
    exercise = session.get(ContinuityExercise, exercise_id)
    if exercise is None or exercise.document_id != document.id:
        raise NotFound("There is no such exercise of this plan.")
    if not can_exercise(session, principal, document):
        raise PermissionDenied("Findings are raised by those who keep the plan or assess it.")
    kind = "exercise" if "exercise" in vocab.keys(session, "issue_sources") else "review"
    with audit.operation(session, "plan.finding", plan=document.ref):
        issue = issues.create(
            session,
            Principal.for_command(principal.name),
            {
                "name": values.get("name"),
                "summary": values.get("summary"),
                "severity": values.get("severity"),
                "org_unit_id": document.org_unit_id,
                "source_kind": kind,
                "subjects": list(values.get("subjects") or []),
                "owner_id": values.get("owner_id") or principal.account_id,
            },
        )
        issue.source_type, issue.source_id = "exercise", exercise.id
        issue.created_by = principal.account_id
        session.flush()
    return issue


def exercises(
    session: Session, principal: Principal, document: PolicyDocument
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(ContinuityExercise)
        .where(ContinuityExercise.document_id == document.id)
        .order_by(ContinuityExercise.held_on.desc(), ContinuityExercise.id.desc())
    ).all()
    numbers = dict(
        session.execute(
            select(PolicyVersion.id, PolicyVersion.number).where(
                PolicyVersion.id.in_([row.version_id for row in rows if row.version_id] or [0])
            )
        ).all()
    )
    found = session.scalars(
        select(Issue).where(
            Issue.source_type == "exercise", Issue.source_id.in_([row.id for row in rows] or [0])
        )
    ).all()
    out = []
    for row in rows:
        mine = [
            {**records.chip(ISSUE, issue), "status": issue.status, "severity": issue.severity}
            for issue in found
            if issue.source_id == row.id and access.can_see(session, principal, ISSUE, issue)
        ]
        out.append({
            "id": row.id, "kind": row.kind, "kind_label": EXERCISE_LABELS[row.kind],
            "held_on": row.held_on, "scenario": row.scenario, "participants": row.participants,
            "outcome": row.outcome, "result": row.result, "result_label": RESULT_LABELS[row.result],
            "achieved_hours": row.achieved_hours, "version": numbers.get(row.version_id),
            "recorded_by": row.recorded_by_name, "findings": mine,
        })  # fmt: skip
    return out


def _schedule(session: Session, document: PolicyDocument) -> dict[str, Any]:
    last = session.scalars(
        select(ContinuityExercise.held_on)
        .where(ContinuityExercise.document_id == document.id)
        .order_by(ContinuityExercise.held_on.desc())
    ).first()
    months = exercise_months(session)
    due = (
        rules.add_months(last, months)
        if last
        else (document.created_at.date() + timedelta(days=90))
    )
    return {
        "last_exercised": last,
        "next_exercise_on": due,
        "exercise_overdue": due < utc_now().date(),
        "exercise_months": months,
    }


# --- Showing it ---------------------------------------------------------------------------


def _published(session: Session, document: PolicyDocument) -> PolicyVersion | None:
    return documents.published(session, document)


def view(session: Session, principal: Principal, document: PolicyDocument) -> dict[str, Any]:
    covered = covers(session, principal, document)
    version = _published(session, document)
    owners = records.owners_of(session, DOCUMENT, [document.id]).get(document.id, [])
    return {
        "ref": document.ref,
        "name": document.name,
        "summary": document.summary,
        "org_unit_id": document.org_unit_id,
        "status": document.status,
        "owners": owners,
        "next_review_on": document.next_review_on,
        "version": {
            "number": version.number,
            "form": version.form,
            "body": version.body,
            "url": version.url,
            "file_name": version.file_name,
            "published_at": getattr(version, "published_at", None),
        }
        if version
        else None,
        "covers": covered,
        "contacts": contacts(session, document, covered),
        "exercises": exercises(session, principal, document),
        **_schedule(session, document),
        "can": {
            "change": can_change(session, principal, document),
            "exercise": can_exercise(session, principal, document),
        },
        "choices": {"kinds": EXERCISE_LABELS, "results": RESULT_LABELS},
    }


def overview(session: Session, principal: Principal) -> dict[str, Any]:
    """Every continuity plan in use, and the processes with an impact analysis that no plan
    restores."""
    plans = []
    covered: set[int] = set()
    for document in session.scalars(
        select(PolicyDocument)
        .where(PolicyDocument.kind == KIND, PolicyDocument.status == "active")
        .order_by(PolicyDocument.name)
    ):
        if not access.can_see(session, principal, DOCUMENT, document):
            continue
        processes = [
            row.process_id
            for row in session.scalars(
                select(ContinuityCover).where(ContinuityCover.document_id == document.id)
            )
        ]
        covered |= set(processes)
        version = _published(session, document)
        plans.append({
            **records.chip(DOCUMENT, document), "org_unit_id": document.org_unit_id,
            "processes": len(processes), "version": version.number if version else None,
            "next_review_on": document.next_review_on, **_schedule(session, document),
        })  # fmt: skip
    from riskwren.db.models import ImpactAnalysis

    analysed = session.scalars(
        select(Process)
        .join(ImpactAnalysis, ImpactAnalysis.process_id == Process.id)
        .where(ImpactAnalysis.superseded_by.is_(None), Process.status == "active")
        .order_by(Process.name)
    ).all()
    uncovered = [
        {
            **records.chip(PROCESS, process),
            "recovery_hours": current_analysis(session, process.id).recovery_hours,
        }  # type: ignore[union-attr]
        for process in dict.fromkeys(analysed)
        if process.id not in covered
    ]
    return {"plans": plans, "uncovered": uncovered, "can_add": documents.can_add(principal, None)}


# --- A copy for when the systems are down -------------------------------------------------

STYLE = """
body { font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; color: #1b1f24;
  max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; }
h1 { font-size: 1.7rem; margin: 0 0 .25rem; } h2 { font-size: 1.25rem; margin: 2rem 0 .5rem;
  border-bottom: 1px solid #c9ced6; padding-bottom: .25rem; } h3 { font-size: 1.05rem; }
.muted { color: #555d68; } .notice { border: 2px solid #1b1f24; padding: .5rem .75rem; }
table { border-collapse: collapse; width: 100%; margin: .5rem 0 1rem; }
th, td { text-align: left; vertical-align: top; border: 1px solid #d5d9df; padding: .35rem .5rem; }
th { background: #f1f3f5; }
@media print { body { margin: 0; max-width: none; } h2 { break-after: avoid; }
  tr { break-inside: avoid; } }
"""
INLINE = re.compile(r"\*\*(.+?)\*\*")


def text_to_html(text: str | None) -> str:
    """A plan's words, written in the app's plain markdown, as HTML: headings, lists,
    paragraphs, and bold. Everything is escaped first."""
    out: list[str] = []
    listing: str | None = None
    paragraph: list[str] = []

    def inline(line: str) -> str:
        return INLINE.sub(r"<strong>\1</strong>", html.escape(line))

    def flush() -> None:
        nonlocal listing
        if paragraph:
            out.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()
        if listing:
            out.append(f"</{listing}>")
            listing = None

    for raw in (text or "").splitlines():
        line = raw.strip()
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        bullet = re.match(r"^[-*]\s+(.*)$", line)
        number = re.match(r"^\d+[.)]\s+(.*)$", line)
        if not line:
            flush()
        elif heading:
            flush()
            level = min(len(heading.group(1)) + 1, 4)
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        elif bullet or number:
            kind = "ul" if bullet else "ol"
            if paragraph:
                out.append(f"<p>{inline(' '.join(paragraph))}</p>")
                paragraph.clear()
            if listing != kind:
                if listing:
                    out.append(f"</{listing}>")
                out.append(f"<{kind}>")
                listing = kind
            out.append(f"<li>{inline((bullet or number).group(1))}</li>")  # type: ignore[union-attr]
        else:
            if listing:
                out.append(f"</{listing}>")
                listing = None
            paragraph.append(line)
    flush()
    return "\n".join(out)


def offline(session: Session, principal: Principal, document: PolicyDocument) -> bytes:
    """The plan in force as one file, with everything needed to use it with no system to
    hand: what it says, what it restores and in what order, what each relies on, and whom
    to call."""
    version = _published(session, document)
    if version is None:
        raise Conflict("The plan has no published version yet. Publish one first.")
    found = view(session, principal, document)

    def e(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    now = utc_now()

    def hours(value: Any) -> str:
        return "Not analysed" if value is None else f"{value} hours"

    def row(*cells: Any) -> str:
        return "<tr>" + "".join(f"<td>{e(cell)}</td>" for cell in cells) + "</tr>"

    def table(head: list[str], rows: list[str], empty: str) -> str:
        top = "".join(f"<th>{e(each)}</th>" for each in head)
        body = "".join(rows) or f'<tr><td colspan="{len(head)}">{e(empty)}</td></tr>'
        return f"<table><thead><tr>{top}</tr></thead><tbody>{body}</tbody></table>"

    if version.form == "text":
        words = text_to_html(version.body)
    elif version.form == "link":
        where = e(version.url or "")
        words = (
            f'<p>The plan\'s words are kept at <a href="{where}">{where}</a>. Keep a '
            "printed copy of them with this.</p>"
        )
    else:
        words = (
            f"<p>The plan's words are in the file {e(version.file_name or '')}. Keep a "
            "printed copy of it with this.</p>"
        )
    restores = [
        row(f"{item['name']} ({item['ref']})", hours(item["recovery_hours"]),
            hours(item["data_loss_hours"]), item["minimum"] or "")
        for item in found["covers"]
    ]  # fmt: skip
    relies = [
        row(item["name"], f"{dep['name']} ({dep['ref']})",
            hours(dep["capability"]["recovery_hours"]) if dep["capability"] else "Not known",
            " ".join(dep["problems"]) or "In time")
        for item in found["covers"]
        for dep in item["dependencies"]
    ]  # fmt: skip
    people = [
        row(person["name"], person["title"] or "", person["email"], ", ".join(person["for"]))
        for person in found["contacts"]
    ]
    last = found["exercises"][0] if found["exercises"] else None
    exercised = (
        f"{last['held_on']}: {last['kind_label']}, {last['result_label'].lower()}."
        if last
        else "It has not been exercised yet."
    )
    taken = now.strftime("%Y-%m-%d %H:%M")
    parts = [
        f"<h1>{e(document.name)}</h1>",
        f'<p class="muted">{e(document.ref)}, version {e(version.number)}. '
        f"Taken on {e(taken)} UTC.</p>",
        '<p class="notice">A copy, for when the systems are down. The version in force may '
        f"have changed since it was taken: when you can, check that version "
        f"{e(version.number)} is still the one in force.</p>",
        "<h2>The plan</h2>", words,
        "<h2>What it restores, soonest first</h2>",
        table(["Process", "Back within", "Information it can lose", "The least it needs"],
              restores, "No process is named."),
        "<h2>What each relies on</h2>",
        table(["Process", "Relies on", "Can be back within", "Against what it needs"],
              relies, "Nothing is recorded."),
        "<h2>Whom to call</h2>",
        table(["Name", "Title", "Email", "For"], people, "Nobody is named."),
        "<h2>When it was last exercised</h2>", f"<p>{e(exercised)}</p>",
    ]  # fmt: skip
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>{e(document.name)}</title><style>{STYLE}</style></head><body>"
        + "\n".join(parts)
        + "</body></html>\n"
    ).encode()


# --- What waits on someone ----------------------------------------------------------------


def waiting_on(session: Session, principal: Principal) -> list[tuple[PolicyDocument, date]]:
    """Plans the person owns whose exercise is due within a month, or overdue."""
    if principal.account_id is None:
        return []
    from riskwren.db.models import RecordOwner

    owned = select(RecordOwner.record_id).where(
        RecordOwner.record_type == DOCUMENT.key,
        RecordOwner.account_id == principal.account_id,
        RecordOwner.kind == records.OWNER,
    )
    out = []
    soon = utc_now().date() + timedelta(days=30)
    for document in session.scalars(
        select(PolicyDocument).where(
            PolicyDocument.id.in_(owned),
            PolicyDocument.kind == KIND,
            PolicyDocument.status == "active",
            PolicyDocument.published_version_id.is_not(None),
        )
    ):
        due = _schedule(session, document)["next_exercise_on"]
        if due <= soon:
            out.append((document, due))
    return out


def install() -> None:
    """A plan's history says what it restores and when it was exercised."""
    previous = DOCUMENT.extra.get("history_title")

    def title(event: Any, lookups: Any) -> str | None:
        changes = event.changes or {}

        def now(name: str) -> Any:
            pair = changes.get(name) or [None, None]
            return pair[1] if pair[1] is not None else pair[0]

        if event.subject_type == "continuity_cover":
            name = lookups.name("process", now("process_id"))
            return f"Restores {name}" if event.action == "created" else f"No longer restores {name}"
        if event.subject_type == "continuity_exercise" and event.action == "created":
            kind = EXERCISE_LABELS.get(now("kind"), "")
            return f"Exercised: {kind}, {RESULT_LABELS.get(now('result'), '').lower()}"
        return previous(event, lookups) if previous is not None else None

    DOCUMENT.extra["history_title"] = title


install()
