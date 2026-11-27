"""What a document governs: the controls it directs and the requirements it answers (POL-04).

A control a document directs is how what the document requires is done; a requirement it
answers is one the organization meets, in part, by saying so in it. Both are kept from the
document's side, by those who may change the document, and shown from the other side too:
a control lists the documents that direct it, a requirement the published documents that
answer it, so that "is there a policy for this?" has an answer with a date on it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import frameworks
from riskwren.controls import service as controls
from riskwren.controls.service import CONTROL
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Control,
    DocumentControl,
    DocumentRequirement,
    Framework,
    PolicyDocument,
    PolicyVersion,
    Requirement,
)
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.policy import documents
from riskwren.policy.documents import DOCUMENT

NOTE = 300


def _editable(session: Session, principal: Principal, document: PolicyDocument) -> None:
    if not documents.can_edit(session, principal, document):
        raise PermissionDenied(
            "What a document governs is changed by its owners, or by the steward, leader, or "
            "manager of its unit."
        )


def _note(value: Any, errors: records.Errors) -> str | None:
    cleaned = records.text(value)
    if cleaned and len(cleaned) > NOTE:
        errors.add("note", f"Keep the note to {NOTE} characters.")
    return cleaned


def _short(framework: Framework) -> str:
    """A framework's title without its subtitle, as the history says it."""
    return framework.title.split(":")[0].strip()


def _published(session: Session, ids: list[int]) -> dict[int, int]:
    """The number of the version in force of each document that has one."""
    if not ids:
        return {}
    rows = session.execute(
        select(PolicyDocument.id, PolicyVersion.number)
        .join(PolicyVersion, PolicyVersion.id == PolicyDocument.published_version_id)
        .where(PolicyDocument.id.in_(ids))
    ).all()
    return dict(rows)


def _document_entry(
    session: Session, document: PolicyDocument, numbers: dict[int, int]
) -> dict[str, Any]:
    return {
        **records.chip(DOCUMENT, document),
        "kind": document.kind,
        "status": document.status,
        "number": numbers.get(document.id),
    }


# --- From the document's side -------------------------------------------------------------


def of_document(session: Session, principal: Principal, document: PolicyDocument) -> dict[str, Any]:
    """The controls a document directs and the requirements it answers, framework by
    framework. Controls the person may not open are counted, not named."""
    directed, hidden = [], 0
    for link, control in session.execute(
        select(DocumentControl, Control)
        .join(Control, Control.id == DocumentControl.control_id)
        .where(DocumentControl.document_id == document.id)
        .order_by(Control.ref)
    ).all():
        if not access.can_see(session, principal, CONTROL, control):
            hidden += 1
            continue
        directed.append({
            "id": link.id,
            "note": link.note,
            "control": {
                **records.chip(CONTROL, control),
                "status": control.status,
                "state": controls.state_of(session, control),
            },
        })  # fmt: skip
    groups: dict[str, dict[str, Any]] = {}
    answered = session.execute(
        select(DocumentRequirement, Requirement, Framework)
        .join(Requirement, Requirement.id == DocumentRequirement.requirement_id)
        .join(Framework, Framework.id == Requirement.framework_id)
        .where(DocumentRequirement.document_id == document.id)
        .order_by(Framework.title, Requirement.sequence)
    ).all()
    for link, requirement, framework in answered:
        group = groups.setdefault(
            framework.key,
            {"key": framework.key, "title": framework.title, "status": framework.status,
             "requirements": []},
        )  # fmt: skip
        group["requirements"].append({
            "id": link.id,
            "code": requirement.code,
            "title": requirement.title,
            "excerpt": frameworks.card(requirement)["excerpt"],
            "note": link.note,
        })  # fmt: skip
    return {
        "controls": directed,
        "hidden": hidden,
        "frameworks": list(groups.values()),
        "requirements": len(answered),
        "can_edit": documents.can_edit(session, principal, document)
        and document.status == "active",
    }


def counts(session: Session, ids: list[int]) -> dict[int, tuple[int, int]]:
    """For each document, how many controls it directs and requirements it answers."""
    if not ids:
        return {}
    directs = dict(
        session.execute(
            select(DocumentControl.document_id, func.count())
            .where(DocumentControl.document_id.in_(ids))
            .group_by(DocumentControl.document_id)
        ).all()
    )
    answers = dict(
        session.execute(
            select(DocumentRequirement.document_id, func.count())
            .where(DocumentRequirement.document_id.in_(ids))
            .group_by(DocumentRequirement.document_id)
        ).all()
    )
    return {each: (directs.get(each, 0), answers.get(each, 0)) for each in ids}


def direct(
    session: Session,
    principal: Principal,
    document: PolicyDocument,
    control_ref: str | None,
    note: str | None = None,
) -> DocumentControl:
    """Say that a document directs a control, or change the note on it."""
    _editable(session, principal, document)
    errors = records.Errors()
    control: Control | None = None
    try:
        control = records.load(session, principal, CONTROL, str(control_ref or "").strip())
    except NotFound as missing:
        errors.add("control", str(missing))
    else:
        if control.status != "active":
            errors.add("control", f"{control.ref} has been retired.")
    cleaned = _note(note, errors)
    if document.status != "active":
        errors.add("document", "A retired document governs nothing.")
    if errors:
        raise Invalid("The control was not added.", errors)
    assert control is not None
    found = session.scalars(
        select(DocumentControl).where(
            DocumentControl.document_id == document.id, DocumentControl.control_id == control.id
        )
    ).first()
    with audit.operation(session, "document.direct", control=control.ref, called=control.name):
        if found is None:
            found = DocumentControl(
                document_id=document.id, control_id=control.id, note=cleaned,
                created_by=principal.account_id, created_at=utc_now(),
            )  # fmt: skip
            session.add(found)
        else:
            found.note = cleaned
        session.flush()
    return found


def undirect(
    session: Session, principal: Principal, document: PolicyDocument, link_id: int
) -> None:
    _editable(session, principal, document)
    row = session.get(DocumentControl, link_id)
    if row is None or row.document_id != document.id:
        raise NotFound("This document does not direct that control.")
    control = session.get(Control, row.control_id)
    with audit.operation(
        session, "document.undirect",
        control=control.ref if control else None, called=control.name if control else None,
    ):  # fmt: skip
        session.delete(row)
        session.flush()


def answer(
    session: Session,
    principal: Principal,
    document: PolicyDocument,
    *,
    framework: str | None,
    code: str | None,
    note: str | None = None,
) -> DocumentRequirement:
    """Say that a document answers a requirement, or change the note on it."""
    _editable(session, principal, document)
    errors = records.Errors()
    requirement: Requirement | None = None
    source: Framework | None = None
    try:
        source = frameworks.by_key(session, str(framework or ""))
        if source.status != "active":
            errors.add("framework", f"{source.title} is retired.")
        requirement = frameworks.find(session, source, str(code or ""))
        if not requirement.is_citable:
            errors.add("code", "That is a heading. Choose a requirement beneath it.")
    except NotFound as missing:
        errors.add("code", str(missing))
    cleaned = _note(note, errors)
    if document.status != "active":
        errors.add("document", "A retired document governs nothing.")
    if errors:
        raise Invalid("The requirement was not added.", errors)
    assert requirement is not None and source is not None
    found = session.scalars(
        select(DocumentRequirement).where(
            DocumentRequirement.document_id == document.id,
            DocumentRequirement.requirement_id == requirement.id,
        )
    ).first()
    with audit.operation(
        session, "document.answer", framework=_short(source), code=requirement.code
    ):
        if found is None:
            found = DocumentRequirement(
                document_id=document.id, requirement_id=requirement.id, note=cleaned,
                created_by=principal.account_id, created_at=utc_now(),
            )  # fmt: skip
            session.add(found)
        else:
            found.note = cleaned
        session.flush()
    return found


def unanswer(
    session: Session, principal: Principal, document: PolicyDocument, link_id: int
) -> None:
    _editable(session, principal, document)
    row = session.get(DocumentRequirement, link_id)
    if row is None or row.document_id != document.id:
        raise NotFound("This document does not answer that requirement.")
    requirement = session.get(Requirement, row.requirement_id)
    framework = session.get(Framework, requirement.framework_id) if requirement else None
    with audit.operation(
        session, "document.unanswer",
        framework=_short(framework) if framework else None,
        code=requirement.code if requirement else None,
    ):  # fmt: skip
        session.delete(row)
        session.flush()


# --- From the other side ------------------------------------------------------------------


def _visible_documents(
    session: Session, principal: Principal, rows: list[tuple[Any, PolicyDocument]]
) -> tuple[list[tuple[Any, PolicyDocument]], int]:
    shown, hidden = [], 0
    for link, document in rows:
        if access.can_see(session, principal, DOCUMENT, document):
            shown.append((link, document))
        else:
            hidden += 1
    return shown, hidden


def of_control(session: Session, principal: Principal, control: Control) -> dict[str, Any]:
    """The documents that direct a control, those in force first."""
    rows = session.execute(
        select(DocumentControl, PolicyDocument)
        .join(PolicyDocument, PolicyDocument.id == DocumentControl.document_id)
        .where(DocumentControl.control_id == control.id)
        .order_by(PolicyDocument.status, documents.RANK_ORDER, PolicyDocument.name)
    ).all()
    shown, hidden = _visible_documents(session, principal, list(rows))
    numbers = _published(session, [document.id for _link, document in shown])
    return {
        "documents": [
            {**_document_entry(session, document, numbers), "note": link.note}
            for link, document in shown
        ],
        "hidden": hidden,
    }


def of_requirement(
    session: Session, principal: Principal, requirement: Requirement
) -> dict[str, Any]:
    """The documents in force that answer a requirement. A draft, or a document retired or
    never published, says nothing yet, and is not shown."""
    rows = session.execute(
        select(DocumentRequirement, PolicyDocument)
        .join(PolicyDocument, PolicyDocument.id == DocumentRequirement.document_id)
        .where(
            DocumentRequirement.requirement_id == requirement.id,
            PolicyDocument.status == "active",
            PolicyDocument.published_version_id.is_not(None),
        )
        .order_by(documents.RANK_ORDER, PolicyDocument.name)
    ).all()
    shown, hidden = _visible_documents(session, principal, list(rows))
    numbers = _published(session, [document.id for _link, document in shown])
    return {
        "documents": [
            {
                **_document_entry(session, document, numbers),
                "note": link.note,
                "next_review_on": document.next_review_on,
            }
            for link, document in shown
        ],
        "documents_hidden": hidden,
    }
