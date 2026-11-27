"""Policy documents: policies, standards, procedures, and guidelines (POL-01 to POL-03, POL-07).

A document is a record like any other: an owner, a unit, a history. What it says is in its
versions. A version starts as a draft, written here, linked to where the organization keeps
it, or attached as a file. Its author sends it to named people to approve; none of them may
be its author. When all have approved, it can be published: it is numbered, it replaces the
version that was in force, and it is never changed again. Each document is looked at again
on a cadence the program sets, either leaving it as it is or starting a new draft.

The text of a version is not copied into the history. The history holds its fingerprint,
taken when it was published, so that what is shown can be checked against it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Account,
    DocumentControl,
    DocumentRequirement,
    Event,
    PolicyApproval,
    PolicyDocument,
    PolicyVersion,
    RecordOwner,
    StoredFile,
)
from riskwren.db.models.documents import DOCUMENT_KINDS, VERSION_FORMS
from riskwren.events import audit
from riskwren.files import store
from riskwren.inventory import access, records
from riskwren.inventory.completeness import Expected
from riskwren.inventory.registry import RecordType, register
from riskwren.people import accounts, notices
from riskwren.program import rules

KIND_LABELS = {
    "policy": "Policy",
    "standard": "Standard",
    "procedure": "Procedure",
    "plan": "Continuity plan",
    "guideline": "Guideline",
}
RANK = {kind: place for place, kind in enumerate(DOCUMENT_KINDS)}
RANK_ORDER = case(RANK, value=PolicyDocument.kind)
OPEN = ("draft", "in_review", "approved")  # a version still being worked on
SHOWN = ("published", "superseded")  # versions anyone who sees the document may read
MOST_TEXT = 200_000
MOST_APPROVERS = 10
SOON = 30  # days before its date at which a review is said to be due
MONTHS = (1, 120)
ROLE_WORDS = {
    "admin": "an administrator", "manager": "a manager", "assessor": "an assessor",
    "auditor": "an auditor", "leader": "a leader", "steward": "a steward",
}  # fmt: skip


# --- Who may do what ------------------------------------------------------------------------


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    """A unit's documents are added by its steward or its leader, or by a manager."""
    return access.can_add(principal, org_unit_id) or principal.leads_unit(org_unit_id)


def can_edit(session: Session, principal: Principal, document: PolicyDocument) -> bool:
    """Its owners and delegates, and the steward, leader, or manager of its unit."""
    unit = document.org_unit_id
    if principal.manages_unit(unit) or principal.stewards_unit(unit) or principal.leads_unit(unit):
        return True
    kinds = access.owner_kinds(session, DOCUMENT, document.id, principal.account_id)
    return bool(kinds & set(access.EDITING_KINDS))


def _asked(session: Session, principal: Principal, version: PolicyVersion) -> bool:
    if principal.account_id is None:
        return False
    return (
        session.scalars(
            select(PolicyApproval.id).where(
                PolicyApproval.version_id == version.id,
                PolicyApproval.account_id == principal.account_id,
            )
        ).first()
        is not None
    )


def can_read_version(
    session: Session, principal: Principal, document: PolicyDocument, version: PolicyVersion
) -> bool:
    """A published version is for everyone who may see the document. One still being worked
    on is for those who may edit it, those asked to approve it, and those who read
    everything."""
    if not access.can_see(session, principal, DOCUMENT, document):
        return False
    if version.status in SHOWN:
        return True
    return (
        principal.reads_all
        or can_edit(session, principal, document)
        or _asked(session, principal, version)
    )


# --- The record -----------------------------------------------------------------------------


def _new(document: PolicyDocument) -> None:
    document.status, document.kind = "active", "policy"


def _ancestors(session: Session, document_id: int | None) -> list[PolicyDocument]:
    found: list[PolicyDocument] = []
    while document_id is not None and len(found) < 20:
        row = session.get(PolicyDocument, document_id)
        if row is None:
            break
        found.append(row)
        document_id = row.parent_id
    return found


def _apply(
    session: Session, document: PolicyDocument, values: Mapping[str, Any],
    errors: records.Errors, creating: bool,
) -> None:  # fmt: skip
    if "kind" in values or creating:
        kind = values.get("kind")
        if kind not in DOCUMENT_KINDS:
            errors.add(
                "kind", "Say whether it is a policy, standard, procedure, plan, or guideline."
            )
        else:
            document.kind = kind
    if "parent" in values:
        given = records.text(values.get("parent"))
        if given is None:
            document.parent_id = None
        else:
            parent = session.scalars(
                select(PolicyDocument).where(PolicyDocument.ref == given.upper())
            ).first()
            if parent is None or parent.status != "active":
                errors.add("parent", f"There is no document {given} in use.")
            elif parent.id == document.id or (
                document.id is not None
                and any(row.id == document.id for row in _ancestors(session, parent.id))
            ):
                errors.add("parent", "A document cannot implement itself.")
            else:
                document.parent_id = parent.id
    if values.get("acknowledge") is not None:
        document.acknowledge = bool(values["acknowledge"])
    if "review_months" in values:
        months = values.get("review_months")
        if months in (None, ""):
            document.review_months = None
        elif (
            isinstance(months, bool)
            or not isinstance(months, int)
            or not MONTHS[0] <= months <= MONTHS[1]
        ):
            errors.add("review_months", "Give a number of months, from 1 to 120.")
        else:
            document.review_months = months
    if document.parent_id is not None and "parent" not in errors and "kind" not in errors:
        parent = session.get(PolicyDocument, document.parent_id)
        if parent is not None and RANK[parent.kind] > RANK[document.kind]:
            errors.add(
                "parent",
                f"A {document.kind} implements a document of its own kind or a broader one, "
                f"not a {parent.kind}.",
            )
    if document.id is not None and "kind" in values and "kind" not in errors:
        beneath = session.scalars(
            select(PolicyDocument).where(PolicyDocument.parent_id == document.id)
        ).all()
        if any(RANK[child.kind] < RANK[document.kind] for child in beneath):
            errors.add("kind", "Documents of a broader kind implement this one.")
    if not errors and not creating:
        document.next_review_on = next_review(session, document)


def review_every(session: Session, document: PolicyDocument) -> int:
    """Months between reviews: the document's own, or the program's."""
    if document.review_months:
        return document.review_months
    return int(rules.get(session, "cadences").get("document_review_months", 12))


def next_review(session: Session, document: PolicyDocument) -> date | None:
    """A document in force is looked at again so long after it was last looked at."""
    if document.status != "active" or document.published_version_id is None:
        return None
    since = document.last_reviewed_on
    if since is None:
        return None
    return rules.add_months(since, review_every(session, document))


def review_state(document: PolicyDocument, today: date | None = None) -> str | None:
    """Whether its review is due soon or overdue."""
    if document.next_review_on is None:
        return None
    today = today or utc_now().date()
    if document.next_review_on < today:
        return "overdue"
    if (document.next_review_on - today).days <= SOON:
        return "due"
    return "ok"


def published(session: Session, document: PolicyDocument) -> PolicyVersion | None:
    if document.published_version_id is None:
        return None
    return session.get(PolicyVersion, document.published_version_id)


def open_version(session: Session, document: PolicyDocument) -> PolicyVersion | None:
    """The version being written, reviewed, or waiting to be published, if there is one."""
    return session.scalars(
        select(PolicyVersion)
        .where(PolicyVersion.document_id == document.id, PolicyVersion.status.in_(OPEN))
        .order_by(PolicyVersion.id.desc())
    ).first()


def _chip(document: PolicyDocument) -> dict[str, Any]:
    return {"type": "document", "ref": document.ref, "name": document.name, "kind": document.kind,
            "status": document.status}  # fmt: skip


def _cards(session: Session, rows: list[PolicyDocument]) -> list[dict[str, Any]]:
    ids = [row.id for row in rows] or [0]
    numbers = dict(
        session.execute(
            select(PolicyVersion.id, PolicyVersion.number).where(
                PolicyVersion.id.in_(
                    [row.published_version_id for row in rows if row.published_version_id] or [0]
                )
            )
        ).all()
    )
    working = dict(
        session.execute(
            select(PolicyVersion.document_id, PolicyVersion.status).where(
                PolicyVersion.document_id.in_(ids), PolicyVersion.status.in_(OPEN)
            )
        ).all()
    )
    parents = {
        row.id: row
        for row in session.scalars(
            select(PolicyDocument).where(
                PolicyDocument.id.in_([row.parent_id for row in rows if row.parent_id] or [0])
            )
        )
    }
    from riskwren.policy import governs  # it builds on this module

    governed = governs.counts(session, [row.id for row in rows])
    today = utc_now().date()
    return [
        {
            "kind": row.kind,
            "status": row.status,
            "number": numbers.get(row.published_version_id),
            "controls": governed.get(row.id, (0, 0))[0],
            "requirements": governed.get(row.id, (0, 0))[1],
            "working": working.get(row.id),
            "next_review_on": row.next_review_on,
            "review_state": review_state(row, today),
            "parent": _chip(parents[row.parent_id]) if row.parent_id in parents else None,
        }
        for row in rows
    ]


def _fingerprint(form: str, body: str | None, url: str | None, file_sha: str | None) -> str | None:
    if form == "text":
        text = (body or "").replace("\r\n", "\n").strip()
        return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
    if form == "link":
        return hashlib.sha256(url.encode("utf-8")).hexdigest() if url else None
    return file_sha


def _file(session: Session, version: PolicyVersion) -> dict[str, Any] | None:
    stored = session.get(StoredFile, version.file_id) if version.file_id else None
    if stored is None:
        return None
    return {"name": version.file_name, "size": stored.size, "media_type": stored.media_type}


def version_view(
    session: Session, principal: Principal, document: PolicyDocument, version: PolicyVersion,
    *, words: bool = True,
) -> dict[str, Any]:  # fmt: skip
    """A version as it is shown: what it says, who made it, and who approved it."""
    approvals = session.scalars(
        select(PolicyApproval)
        .where(PolicyApproval.version_id == version.id)
        .order_by(PolicyApproval.review_round, PolicyApproval.id)
    ).all()
    current = [row for row in approvals if row.review_round == version.review_round]
    returned = next((row for row in reversed(approvals) if row.decision == "returned"), None)
    mine = next(
        (
            row for row in current
            if row.account_id == principal.account_id and row.decision == "pending"
        ),
        None,
    )  # fmt: skip
    return {
        "id": version.id,
        "number": version.number,
        "status": version.status,
        "form": version.form,
        "body": version.body if words and version.form == "text" else None,
        "url": version.url if version.form == "link" else None,
        "file": _file(session, version) if version.form == "file" else None,
        "fingerprint": version.fingerprint,
        "change_note": version.change_note,
        "ask_again": version.ask_again,
        "created_by": version.created_by_name,
        "created_at": version.created_at,
        "updated_at": version.updated_at,
        "submitted_by": version.submitted_by_name,
        "submitted_at": version.submitted_at,
        "published_by": version.published_by_name,
        "published_at": version.published_at,
        "superseded_at": version.superseded_at,
        "approvals": [
            {
                "name": row.account_name,
                "account_id": row.account_id,
                "decision": row.decision,
                "note": row.note,
                "decided_at": row.decided_at,
            }
            for row in current
        ],
        "approved_by": [row.account_name for row in current if row.decision == "approved"],
        "returned": {"by": returned.account_name, "note": returned.note, "at": returned.decided_at}
        if returned is not None and version.status == "draft"
        else None,
        "awaiting_me": mine is not None,
    }


def _detail(session: Session, principal: Principal, document: PolicyDocument) -> dict[str, Any]:
    editable = can_edit(session, principal, document)
    parent = session.get(PolicyDocument, document.parent_id) if document.parent_id else None
    children = session.scalars(
        select(PolicyDocument)
        .where(PolicyDocument.parent_id == document.id)
        .order_by(PolicyDocument.kind, PolicyDocument.name)
    ).all()
    in_force = published(session, document)
    working = open_version(session, document)
    every = session.scalars(
        select(PolicyVersion)
        .where(PolicyVersion.document_id == document.id, PolicyVersion.status.in_(SHOWN))
        .order_by(PolicyVersion.number.desc())
    ).all()
    seen_working = working is not None and can_read_version(session, principal, document, working)
    return {
        "kind": document.kind,
        "status": document.status,
        "parent": _chip(parent)
        if parent is not None and access.can_see(session, principal, DOCUMENT, parent)
        else None,
        "children": [
            _chip(child)
            for child in children
            if child.status == "active" and access.can_see(session, principal, DOCUMENT, child)
        ],
        "review_months": document.review_months,
        "review_every": review_every(session, document),
        "last_reviewed_on": document.last_reviewed_on,
        "next_review_on": document.next_review_on,
        "review_state": review_state(document),
        "published": version_view(session, principal, document, in_force) if in_force else None,
        "working": version_view(session, principal, document, working) if seen_working else None,
        "working_status": working.status if working is not None else None,
        "versions": [version_view(session, principal, document, row, words=False) for row in every],
        "acknowledge": document.acknowledge,
        **_audience_and_standing(session, principal, document),
        **_governs_and_exceptions(session, principal, document),
        "can": {
            "edit": editable,
            "draft": editable and working is None and document.status == "active",
            "review": editable and in_force is not None and document.status == "active",
        },
    }


def _governs_and_exceptions(
    session: Session, principal: Principal, document: PolicyDocument
) -> dict[str, Any]:
    """How many controls it directs and requirements it answers, and the exceptions to it the
    reader may see, those still to be decided or in force first."""
    from riskwren.compliance import exceptions  # they build on this module
    from riskwren.policy import governs

    directs, answers = governs.counts(session, [document.id]).get(document.id, (0, 0))
    shown = [
        item
        for item in session.scalars(
            select(exceptions.ExceptionRequest)
            .where(
                exceptions.ExceptionRequest.subject_type == "document",
                exceptions.ExceptionRequest.subject_id == document.id,
            )
            .order_by(exceptions.ExceptionRequest.expires_on.desc())
        )
        if exceptions.can_see(session, principal, item)
    ]
    order = {"requested": 0, "expiring": 1, "in_force": 2, "upcoming": 3}
    found = sorted(
        ({"ref": item.ref, "name": item.name, "status": item.status,
          "state": exceptions.state_of(item), "starts_on": item.starts_on,
          "expires_on": item.expires_on} for item in shown),
        key=lambda row: order.get(row["state"], 9),
    )  # fmt: skip
    return {
        "governs": {"controls": directs, "requirements": answers},
        "exceptions": found,
        "can_ask_exception": document.status == "active"
        and document.published_version_id is not None
        and exceptions.may_ask_document(session, principal, document),
    }


def _audience_and_standing(
    session: Session, principal: Principal, document: PolicyDocument
) -> dict[str, Any]:
    """Who it applies to; whether it applies to the reader; and, for those who look after
    it, how many of those it applies to have acknowledged it."""
    from riskwren.policy import library  # it builds on this module

    out: dict[str, Any] = {
        "audience": library.audience_of(session, document),
        "applies_to_me": library.applies(session, document, principal),
    }
    if document.acknowledge and library.may_see_standing(session, principal, document):
        found = library.standing(session, document)
        kept = ("required", "people", "acknowledged", "outstanding")
        out["acknowledgments"] = {key: found[key] for key in kept}
    return out


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    model = PolicyDocument
    if filters.get("kind") in DOCUMENT_KINDS:
        found.append(model.kind == filters["kind"])
    if filters.get("status") in ("active", "retired"):
        found.append(model.status == filters["status"])
    working = exists(
        select(PolicyVersion.id).where(
            PolicyVersion.document_id == model.id, PolicyVersion.status.in_(OPEN)
        )
    )
    state = filters.get("state")
    today = utc_now().date()
    if state in ("draft", "in_review", "approved"):
        found.append(
            exists(
                select(PolicyVersion.id).where(
                    PolicyVersion.document_id == model.id, PolicyVersion.status == state
                )
            )
        )
    elif state == "working":
        found.append(working)
    elif state == "unpublished":
        found += [model.published_version_id.is_(None), model.status == "active"]
    elif state == "overdue":
        found += [model.next_review_on < today, model.status == "active"]
    elif state == "due":
        found += [
            model.next_review_on <= date.fromordinal(today.toordinal() + SOON),
            model.status == "active",
        ]
    if filters.get("acknowledge"):
        found += [model.acknowledge.is_(True), model.published_version_id.is_not(None)]
    if filters.get("parent"):
        above = select(PolicyDocument.id).where(
            PolicyDocument.ref == str(filters["parent"]).strip().upper()
        )
        found.append(model.parent_id.in_(above))
    if filters.get("awaiting_me") and principal.account_id is not None:
        found.append(
            exists(
                select(PolicyApproval.id)
                .join(PolicyVersion, PolicyVersion.id == PolicyApproval.version_id)
                .where(
                    PolicyApproval.document_id == model.id,
                    PolicyApproval.account_id == principal.account_id,
                    PolicyApproval.decision == "pending",
                    PolicyApproval.review_round == PolicyVersion.review_round,
                    PolicyVersion.status == "in_review",
                )
            )
        )
    return found


def _history_title(event: Any, lookups: Any) -> str | None:
    changes = event.changes or {}
    op = (event.context or {}).get("op")

    def now(field: str) -> Any:
        pair = changes.get(field) or [None, None]
        return pair[1] if pair[1] is not None else pair[0]

    if event.subject_type == "policy_approval":
        row = lookups.session.get(PolicyApproval, event.subject_id) if event.subject_id else None
        name = now("account_name") or (row.account_name if row else "someone")
        if event.action == "created":
            return f"Asked {name} to approve it"
        decision = (changes.get("decision") or [None, None])[1]
        if decision == "approved":
            return f"{name} approved it"
        if decision == "returned":
            return f"{name} returned it: {now('note')}" if now("note") else f"{name} returned it"
        return f"{name} no longer needs to approve it"
    if event.subject_type == "policy_version":
        if op == "document.publish":
            if "number" in changes:
                return f"Published version {now('number')}"
            return "The version it replaces is superseded"
        if op == "document.submit":
            return "Sent the draft for approval"
        if op == "document.withdraw":
            return "Took the draft back from approval"
        if op in ("document.discard", "document.retire"):
            return "Discarded the draft"
        if op == "document.approved":
            return "Every approval is in: it can be published"
        if op == "document.decide":
            return "The draft is back with its author"
        if event.action == "created":
            return "Started the first draft" if op == "document.create" else "Started a new draft"
        if op == "document.save":
            return "Edited the draft"
        return "Changed the draft"
    if op == "document.review":
        note = (event.context or {}).get("note")
        kept = "Reviewed it and kept it as it is"
        return f"{kept}: {note}" if note else kept
    if op == "document.retire":
        note = (event.context or {}).get("note")
        return f"Retired it: {note}" if note else "Retired it"
    if op == "document.reinstate":
        return "Put it back in use"
    context = event.context or {}
    if op in ("document.direct", "document.undirect") and context.get("control"):
        what = f"{context['control']} {context.get('called') or ''}".strip()
        if op == "document.undirect":
            return f"No longer directs {what}"
        return f"Directs {what}" if event.action == "created" else f"Changed the note on {what}"
    if op in ("document.answer", "document.unanswer") and context.get("code"):
        what = f"{context['code']} of {context.get('framework') or 'a framework'}"
        if op == "document.unanswer":
            return f"No longer answers {what}"
        return f"Answers {what}" if event.action == "created" else f"Changed the note on {what}"
    if event.subject_type == "policy_audience":
        if now("role"):
            what = f"everyone who is {ROLE_WORDS.get(now('role'), now('role'))}"
        else:
            unit = lookups.name("unit", now("org_unit_id")) or "a unit"
            what = f"{unit} and the units beneath it"
        return (
            f"Now applies to {what}"
            if event.action == "created"
            else f"No longer applies to {what}"
        )
    return None


def _history_value(lookups: Any, field: str, value: Any) -> Any:
    if field == "parent_id":
        row = lookups.session.get(PolicyDocument, value) if value else None
        return f"{row.ref} {row.name}" if row else None
    if field == "kind":
        return KIND_LABELS.get(value, value)
    return None


def _never_published(model: Any) -> Any:
    return model.published_version_id.is_(None)


def _implements_nothing(model: Any) -> Any:
    return and_(model.parent_id.is_(None), model.kind != "policy")


def _governs_nothing(model: Any) -> Any:
    """A policy, standard, or procedure that directs no control and answers no requirement.
    A guideline is advice, and is not expected to; a continuity plan restores processes."""
    return and_(
        model.kind.not_in(("guideline", "plan")),
        ~exists(select(DocumentControl.id).where(DocumentControl.document_id == model.id)),
        ~exists(select(DocumentRequirement.id).where(DocumentRequirement.document_id == model.id)),
    )


DOCUMENT: RecordType = register(
    RecordType(
        "document",
        PolicyDocument,
        "POL",
        "documents",
        "document",
        "documents",
        is_thing=False,
        open=True,
        sorts=("updated_at", "name", "ref", "kind", "next_review_on"),
        filters=("kind",),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_add": can_add,
            "can_edit": can_edit,
            # Broadest first, as the documents sit beneath one another.
            "sort_columns": {"kind": lambda session, model: case(RANK, value=model.kind)},
            "add_refusal": "Documents are added by a unit's steward or leader, or by a manager.",
            "expected": [
                Expected(
                    "published",
                    "a version in force",
                    _never_published,
                    "Nobody can read it yet: nothing has been published.",
                ),
                Expected(
                    "parent",
                    "what it implements",
                    _implements_nothing,
                    "A standard, procedure, or guideline that names no policy has nothing "
                    "behind it.",
                ),
                Expected(
                    "governs",
                    "a control it directs or a requirement it answers",
                    _governs_nothing,
                    "Nothing shows what it governs, or what puts it into effect.",
                ),
            ],
            "live_statuses": ("active",),
            "history_title": _history_title,
            "history_value": _history_value,
            "history_keeps_titled": True,
            # Each acknowledgment is on the document's Acknowledgments tab, not its history.
            "history_hidden": ("policy_acknowledgment",),
            "history_labels": {
                "kind": "Kind",
                "parent_id": "Implements",
                "review_months": "Reviewed every (months)",
                "change_note": "What changed",
                "url": "Where it is kept",
                "file_name": "File",
                "form": "Held as",
                "acknowledge": "Asks people to acknowledge it",
                "for_everyone": "Applies to everyone",
                "ask_again": "Must be acknowledged again",
            },
            "history_quiet": (
                "document_id",
                "control_id",
                "requirement_id",
                "created_by",
                "created_at",
                "published_version_id",
                "last_reviewed_on",
                "next_review_on",
                "fingerprint",
                "updated_at",
                "review_round",
                "submitted_by",
                "submitted_by_name",
                "submitted_at",
                "published_by_name",
                "published_at",
                "superseded_at",
                "number",
                "status",
                "decided_at",
                "asked_at",
            ),
        },
    )
)


# --- Writing a version ------------------------------------------------------------------------


def _editable(session: Session, principal: Principal, document: PolicyDocument) -> None:
    if not can_edit(session, principal, document):
        raise PermissionDenied(
            "A document is changed by its owners, or by the steward, leader, or manager of its "
            "unit."
        )
    if document.status != "active":
        raise Conflict("This document is retired. Put it back in use first.")


def _touch(document: PolicyDocument) -> None:
    document.updated_at = utc_now()


def _content(
    session: Session, version: PolicyVersion, values: Mapping[str, Any], errors: records.Errors
) -> None:
    if values.get("form") is not None:
        if values["form"] not in VERSION_FORMS:
            errors.add("form", "Write it here, link to it, or attach it as a file.")
        else:
            version.form = values["form"]
    if "body" in values:
        body = (values.get("body") or "").replace("\r\n", "\n")
        if len(body) > MOST_TEXT:
            errors.add("body", f"Keep the text under {MOST_TEXT:,} characters, or attach a file.")
        else:
            version.body = body.strip("\n") or None
    if "url" in values:
        version.url = records.url(values.get("url"), "url", errors, max_length=500)
    if values.get("ask_again") is not None:
        version.ask_again = bool(values["ask_again"])
    if "change_note" in values:
        note = records.text(values.get("change_note"))
        if note and len(note) > 4000:
            errors.add("change_note", "Keep this to 4,000 characters.")
        else:
            version.change_note = note
    stored = session.get(StoredFile, version.file_id) if version.file_id else None
    version.fingerprint = _fingerprint(
        version.form, version.body, version.url, stored.sha256 if stored else None
    )


def create(session: Session, principal: Principal, values: Mapping[str, Any]) -> PolicyDocument:
    """Add a document, and its first draft with whatever of its content was given."""
    document: PolicyDocument = records.create(session, principal, DOCUMENT, values)
    version = PolicyVersion(
        document_id=document.id, status="draft", form="text", review_round=0,
        created_by=principal.account_id, created_by_name=principal.name,
        created_at=utc_now(), updated_at=utc_now(),
    )  # fmt: skip
    errors = records.Errors()
    _content(session, version, values, errors)
    if errors:
        raise Invalid("The document was not saved.", errors)
    with audit.operation(session, "document.create"):
        session.add(version)
        session.flush()
    return document


def start_draft(session: Session, principal: Principal, document: PolicyDocument) -> PolicyVersion:
    """Start the next version from the one in force."""
    _editable(session, principal, document)
    if open_version(session, document) is not None:
        raise Conflict("A new version is already being written. Carry on with that one.")
    base = published(session, document)
    version = PolicyVersion(
        document_id=document.id, status="draft", review_round=0,
        form=base.form if base else "text", body=base.body if base else None,
        url=base.url if base else None, file_id=base.file_id if base else None,
        file_name=base.file_name if base else None,
        fingerprint=base.fingerprint if base else None,
        created_by=principal.account_id, created_by_name=principal.name,
        created_at=utc_now(), updated_at=utc_now(),
    )  # fmt: skip
    with audit.operation(session, "document.draft"):
        session.add(version)
        _touch(document)
        session.flush()
    return version


def draft_of(session: Session, document: PolicyDocument) -> PolicyVersion:
    version = open_version(session, document)
    if version is None:
        raise NotFound("No new version is being written. Start one first.")
    return version


def save_draft(
    session: Session, principal: Principal, document: PolicyDocument, values: Mapping[str, Any]
) -> PolicyVersion:
    version = draft_of(session, document)
    _editable(session, principal, document)
    if version.status != "draft":
        raise Conflict("This version has been sent for approval. Take it back to change it.")
    errors = records.Errors()
    with audit.operation(session, "document.save"):
        _content(session, version, values, errors)
        if errors:
            session.expire(version)
            raise Invalid("The draft was not saved.", errors)
        version.updated_at = utc_now()
        _touch(document)
        session.flush()
    return version


def attach_file(
    session: Session, principal: Principal, document: PolicyDocument, root: Path, data: bytes,
    name: str | None,
) -> PolicyVersion:  # fmt: skip
    """Keep a file as the draft's content. Its type is judged by its content."""
    version = draft_of(session, document)
    _editable(session, principal, document)
    if version.status != "draft":
        raise Conflict("This version has been sent for approval. Take it back to change it.")
    digest, kind = store.save(root, data)
    stored = session.scalars(select(StoredFile).where(StoredFile.sha256 == digest)).first()
    if stored is None:
        stored = StoredFile(
            sha256=digest, size=len(data), media_type=kind.media_type, extension=kind.extension,
            created_at=utc_now(),
        )  # fmt: skip
        session.add(stored)
        session.flush()
    with audit.operation(session, "document.save", sha256=digest, size=len(data)):
        version.form, version.file_id = "file", stored.id
        version.file_name = store.safe_name(name, kind)
        version.fingerprint = digest
        version.updated_at = utc_now()
        _touch(document)
        session.flush()
    return version


def _owners(session: Session, document: PolicyDocument) -> list[int]:
    return notices.owners(session, "document", document.id)


def _href(document: PolicyDocument, tab: str | None = None) -> str:
    return f"/documents/{document.ref}" + (f"?tab={tab}" if tab else "")


def submit(
    session: Session, principal: Principal, document: PolicyDocument, approvers: Iterable[Any]
) -> PolicyVersion:
    """Send the draft to the people who are to approve it."""
    version = draft_of(session, document)
    _editable(session, principal, document)
    if version.status != "draft":
        raise Conflict("This version has already been sent for approval.")
    errors = records.Errors()
    if version.fingerprint is None:
        errors.add("content", "Write the document, link to where it is kept, or attach it first.")
    if document.published_version_id is not None and not version.change_note:
        errors.add("change_note", "Say what changed, and why.")
    authors = {principal.account_id, version.created_by}
    chosen: list[Account] = []
    for given in dict.fromkeys(approvers):
        account = session.get(Account, int(given)) if str(given).isdigit() else None
        if account is None or account.status == "disabled":
            errors.add("approvers", "Choose people whose accounts are not disabled.")
        elif account.id in authors:
            errors.add(
                "approvers",
                f"{account.display_name} wrote or sent this version, so may not approve it.",
            )
        elif not access.can_see(
            session, accounts.principal_for(session, account), DOCUMENT, document
        ):
            errors.add("approvers", f"{account.display_name} may not see this document.")
        else:
            chosen.append(account)
    if not chosen and "approvers" not in errors:
        errors.add("approvers", "Name at least one person to approve it.")
    if len(chosen) > MOST_APPROVERS:
        errors.add("approvers", f"Name at most {MOST_APPROVERS} people.")
    if errors:
        raise Invalid("The draft was not sent.", errors)
    now = utc_now()
    with audit.operation(session, "document.submit"):
        version.review_round += 1
        version.status = "in_review"
        version.submitted_by, version.submitted_by_name, version.submitted_at = (
            principal.account_id, principal.name, now,
        )  # fmt: skip
        for account in chosen:
            session.add(
                PolicyApproval(
                    document_id=document.id, version_id=version.id,
                    review_round=version.review_round, account_id=account.id,
                    account_name=account.display_name, decision="pending", asked_at=now,
                )
            )  # fmt: skip
        _touch(document)
        session.flush()
    notices.tell_all(
        session, [account.id for account in chosen], "document",
        f"{principal.name} asks you to approve a new version of {document.ref} {document.name}.",
        _href(document, "draft"), by=principal,
    )  # fmt: skip
    return version


def _round(session: Session, version: PolicyVersion) -> list[PolicyApproval]:
    return list(
        session.scalars(
            select(PolicyApproval).where(
                PolicyApproval.version_id == version.id,
                PolicyApproval.review_round == version.review_round,
            )
        )
    )


def decide(
    session: Session, principal: Principal, document: PolicyDocument, decision: str,
    note: str | None,
) -> PolicyVersion:  # fmt: skip
    """Approve the version, or return it to its author with a reason."""
    version = draft_of(session, document)
    if version.status != "in_review":
        raise Conflict("This version is not waiting for approval.")
    mine = next(
        (row for row in _round(session, version) if row.account_id == principal.account_id), None
    )
    if mine is None:
        raise PermissionDenied("You were not asked to approve this version.")
    if mine.decision != "pending":
        raise Conflict("You have already said what you think of this version.")
    said = records.text(note)
    if decision not in ("approved", "returned"):
        raise Invalid("Nothing was recorded.", {"decision": "Approve it, or return it."})
    if decision == "returned" and not said:
        raise Invalid("Nothing was recorded.", {"note": "Say what needs to change."})
    now = utc_now()
    told = [*_owners(session, document), version.submitted_by]
    with audit.operation(session, "document.decide", decision=decision):
        mine.decision, mine.note, mine.decided_at = decision, said, now
        session.flush()
        left = [row for row in _round(session, version) if row.decision == "pending"]
        if decision == "returned":
            for row in left:
                row.decision = "cancelled"
            version.status = "draft"
        _touch(document)
        session.flush()
    if decision == "returned":
        notices.tell_all(
            session, told, "document",
            f"{principal.name} returned the new version of {document.ref} {document.name}: {said}",
            _href(document, "draft"), by=principal,
        )  # fmt: skip
    elif not left:
        with audit.operation(session, "document.approved"):
            version.status = "approved"
            session.flush()
        notices.tell_all(
            session, told, "document",
            f"Every approval is in for {document.ref} {document.name}. It can be published.",
            _href(document, "draft"), by=principal,
        )  # fmt: skip
    return version


def withdraw(session: Session, principal: Principal, document: PolicyDocument) -> PolicyVersion:
    """Take a version back from approval to change it. Those not yet asked are released."""
    version = draft_of(session, document)
    _editable(session, principal, document)
    if version.status not in ("in_review", "approved"):
        raise Conflict("This version has not been sent for approval.")
    pending = [row.account_id for row in _round(session, version) if row.decision == "pending"]
    with audit.operation(session, "document.withdraw"):
        for row in _round(session, version):
            if row.decision == "pending":
                row.decision = "cancelled"
        version.status = "draft"
        _touch(document)
        session.flush()
    notices.tell_all(
        session, pending, "document",
        f"{principal.name} took back the new version of {document.ref} {document.name}; "
        "your approval is no longer needed.",
        _href(document), by=principal,
    )  # fmt: skip
    return version


def publish(session: Session, principal: Principal, document: PolicyDocument) -> PolicyVersion:
    """Put an approved version in force. It is numbered and never changed again."""
    version = draft_of(session, document)
    _editable(session, principal, document)
    if version.status != "approved":
        raise Conflict("A version is published once everyone named for it has approved it.")
    if version.fingerprint is None:
        raise Conflict("This version says nothing yet.")
    number = (
        session.execute(
            select(func.max(PolicyVersion.number)).where(PolicyVersion.document_id == document.id)
        ).scalar_one()
        or 0
    ) + 1
    before = published(session, document)
    now = utc_now()
    taken = {"number": number, "fingerprint": version.fingerprint}
    with audit.operation(session, "document.publish", **taken):
        if before is not None:
            before.status, before.superseded_at = "superseded", now
            session.flush()  # so that the history reads in the order it happened
        version.status, version.number = "published", number
        version.published_by_name, version.published_at = principal.name, now
        document.published_version_id = version.id
        document.last_reviewed_on = now.date()
        document.next_review_on = next_review(session, document)
        session.flush()
    notices.tell_all(
        session,
        _owners(session, document),
        "document",
        f"Version {number} of {document.ref} {document.name} is published.",
        _href(document),
        by=principal,
    )
    from riskwren.policy import library  # it builds on this module

    library.tell_to_acknowledge(session, principal, document, version)  # fmt: skip
    return version


def discard(session: Session, principal: Principal, document: PolicyDocument) -> None:
    """Drop a draft that was never sent, or was taken back."""
    version = draft_of(session, document)
    _editable(session, principal, document)
    if version.status != "draft":
        raise Conflict("Take the version back from approval before discarding it.")
    with audit.operation(session, "document.discard"):
        version.status = "discarded"
        _touch(document)
        session.flush()


def review(
    session: Session, principal: Principal, document: PolicyDocument, note: str | None
) -> PolicyDocument:
    """Look at the document again and keep it as it is. Its next review moves on."""
    _editable(session, principal, document)
    if document.published_version_id is None:
        raise Conflict("Nothing has been published yet, so there is nothing to keep.")
    said = records.text(note)
    if not said:
        raise Invalid("The review was not recorded.", {"note": "Say what was looked at."})
    with audit.operation(session, "document.review", note=said[:1000]):
        document.last_reviewed_on = utc_now().date()
        document.next_review_on = next_review(session, document)
        _touch(document)
        session.flush()
    return document


def retire(
    session: Session, principal: Principal, document: PolicyDocument, note: str | None
) -> PolicyDocument:
    """Take a document out of use. Its versions stay on record; a draft is discarded."""
    _editable(session, principal, document)
    said = records.text(note)
    if not said:
        raise Invalid("The document was not retired.", {"note": "Say why it is no longer needed."})
    beneath = session.scalars(
        select(PolicyDocument.ref).where(
            PolicyDocument.parent_id == document.id, PolicyDocument.status == "active"
        )
    ).all()
    if beneath:
        raise Conflict(
            f"{', '.join(beneath)} implement this document. Retire them, or move them under "
            "another, first."
        )
    working = open_version(session, document)
    with audit.operation(session, "document.retire", note=said[:1000]):
        if working is not None:
            for row in _round(session, working):
                if row.decision == "pending":
                    row.decision = "cancelled"
            working.status = "discarded"
        document.status = "retired"
        document.next_review_on = None
        _touch(document)
        session.flush()
    return document


def reinstate(session: Session, principal: Principal, document: PolicyDocument) -> PolicyDocument:
    if not can_edit(session, principal, document):
        raise PermissionDenied("A document is changed by its owners, or by those over its unit.")
    with audit.operation(session, "document.reinstate"):
        document.status = "active"
        document.next_review_on = next_review(session, document)
        _touch(document)
        session.flush()
    return document


# --- Reading versions -----------------------------------------------------------------------------


def version_of(
    session: Session, principal: Principal, document: PolicyDocument, version_id: int
) -> PolicyVersion:
    version = session.get(PolicyVersion, version_id)
    if (
        version is None
        or version.document_id != document.id
        or not can_read_version(session, principal, document, version)
    ):
        raise NotFound(f"{document.ref} has no such version.")
    return version


def compare(
    session: Session, principal: Principal, document: PolicyDocument, older: int, newer: int
) -> dict[str, Any]:
    """Two versions side by side, with what differs marked."""
    from riskwren.policy.compare import compare as differ

    one = version_of(session, principal, document, older)
    other = version_of(session, principal, document, newer)

    def label(version: PolicyVersion) -> dict[str, Any]:
        return {"id": version.id, "number": version.number, "status": version.status,
                "form": version.form, "published_at": version.published_at,
                "url": version.url, "file": _file(session, version)}  # fmt: skip

    out: dict[str, Any] = {"before": label(one), "after": label(other)}
    if one.form == "text" and other.form == "text":
        out.update(differ(one.body, other.body))
    else:
        out.update({"rows": [], "counts": None, "same": one.fingerprint == other.fingerprint})
    return out


def download(
    session: Session, principal: Principal, document: PolicyDocument, version_id: int, root: Path
) -> tuple[Path, str, str]:
    version = version_of(session, principal, document, version_id)
    stored = (
        session.get(StoredFile, version.file_id)
        if version.form == "file" and version.file_id
        else None
    )
    if stored is None:
        raise NotFound("This version has no file.")
    path = store.path_of(root, stored.sha256)
    if not path.is_file():
        raise NotFound("The file is missing from the data home.")
    said = {"file": [None, version.file_name]}
    audit.record(session, "document.downloaded", document, changes=said)
    name = version.file_name or f"{document.ref}-{version.number or 'draft'}.{stored.extension}"
    return path, name, stored.media_type


# --- What is waiting on whom ----------------------------------------------------------------------


def awaiting(session: Session, principal: Principal) -> list[tuple[PolicyDocument, PolicyVersion]]:
    """Versions the person has been asked to approve and has not yet."""
    if principal.account_id is None:
        return []
    rows = session.execute(
        select(PolicyDocument, PolicyVersion)
        .join(PolicyVersion, PolicyVersion.document_id == PolicyDocument.id)
        .join(PolicyApproval, PolicyApproval.version_id == PolicyVersion.id)
        .where(
            PolicyApproval.account_id == principal.account_id,
            PolicyApproval.decision == "pending",
            PolicyApproval.review_round == PolicyVersion.review_round,
            PolicyVersion.status == "in_review",
        )
        .order_by(PolicyVersion.submitted_at)
    ).all()
    return [(document, version) for document, version in rows]


def owned(session: Session, principal: Principal) -> list[PolicyDocument]:
    """Active documents the person owns."""
    if principal.account_id is None:
        return []
    return list(
        session.scalars(
            select(PolicyDocument)
            .join(
                RecordOwner,
                and_(
                    RecordOwner.record_type == "document",
                    RecordOwner.record_id == PolicyDocument.id,
                ),
            )
            .where(
                RecordOwner.account_id == principal.account_id,
                RecordOwner.kind.in_(access.EDITING_KINDS),
                PolicyDocument.status == "active",
            )
            .order_by(PolicyDocument.next_review_on, PolicyDocument.ref)
            .distinct()
        )
    )


# --- Checking what was published ---------------------------------------------------------------


def check_fingerprints(session: Session, root: Path | None = None) -> dict[str, Any]:
    """Every published version against the fingerprint the history took when it was
    published, and its words or file against its own fingerprint."""
    problems: list[str] = []
    checked = 0
    taken: dict[int, str] = {}
    for event in session.scalars(
        select(Event).where(Event.subject_type == "policy_version", Event.action == "updated")
    ):
        context = event.context or {}
        # The event that numbered the version, not the one that later superseded it.
        published_now = "number" in (event.changes or {})
        if context.get("op") == "document.publish" and published_now and event.subject_id:
            taken[event.subject_id] = str(context.get("fingerprint"))
    for version in session.scalars(
        select(PolicyVersion).where(PolicyVersion.status.in_(SHOWN)).order_by(PolicyVersion.id)
    ):
        checked += 1
        document = session.get(PolicyDocument, version.document_id)
        name = f"{document.ref if document else '?'} version {version.number}"
        stored = session.get(StoredFile, version.file_id) if version.file_id else None
        digest = stored.sha256 if stored else None
        now = _fingerprint(version.form, version.body, version.url, digest)
        if version.id not in taken:
            problems.append(f"{name} has no fingerprint in the history.")
        elif taken[version.id] != version.fingerprint or now != version.fingerprint:
            problems.append(f"{name} is not what was published.")
        elif stored is not None and root is not None:
            path = store.path_of(root, stored.sha256)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != stored.sha256:
                problems.append(f"{name}: its file is missing or has changed.")
    return {"checked": checked, "problems": problems}
