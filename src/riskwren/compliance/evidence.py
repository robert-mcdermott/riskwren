"""Evidence: what shows that a control is done.

An item is a file, a link, a note, or an attestation. It has an owner, the day it was
collected, the period it covers, and a date until which it holds. It is collected once and
attached to as many controls and scopes as it supports. Past its date it stays on the
record and stops counting.

Evidence is more closely held than the rest of the register. Whoever collected it, those
named on it, and those with a role over its unit see it. Beyond them it is seen by people
who may see something it is attached to, unless it is restricted or of the most sensitive
class, in which case being attached to something is not enough.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.compliance.scopes import SCOPE
from riskwren.controls.service import CONTROL
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import Evidence, EvidenceLink, RecordOwner, StoredFile
from riskwren.db.models.compliance import EVIDENCE_KINDS
from riskwren.db.models.inventory import RECORD_STATUSES
from riskwren.events import audit
from riskwren.files import store
from riskwren.inventory import access, records
from riskwren.inventory.registry import RecordType, find_any, register
from riskwren.program import rules, vocab

KIND_LABELS = {
    "file": "File",
    "link": "Link",
    "note": "Note",
    "attestation": "Attestation",
}
SOON = 30  # days before its date at which evidence is flagged to its owner
# What evidence can be attached to. Tests and issues join these in the slices that add them.
SUBJECTS: dict[str, RecordType] = {"control": CONTROL, "scope": SCOPE}
TRUSTED = (roles.STEWARD, roles.LEADER, roles.MANAGER)


# --- Who may see it -----------------------------------------------------------------------


def _sensitive(session: Session) -> str | None:
    """The most sensitive class of data, by the organization's own ordering."""
    classes = vocab.keys(session, "data_classes", active_only=False)
    return classes[-1] if classes else None


def _in(units: frozenset[int] | None, unit: int) -> bool:
    return units is None or unit in units


def can_see(session: Session, principal: Principal, item: Evidence) -> bool:
    if principal.reads_all or _in(principal.units_for(*TRUSTED), item.org_unit_id):
        return True
    me = principal.account_id
    if me is not None and item.created_by == me:
        return True
    if access.owner_kinds(session, EVIDENCE, item.id, me):
        return True
    if item.restricted:
        return False
    if _in(principal.units_for(roles.ASSESSOR), item.org_unit_id):
        return True
    if item.data_class is not None and item.data_class == _sensitive(session):
        return False
    for link in session.scalars(select(EvidenceLink).where(EvidenceLink.evidence_id == item.id)):
        record_type = SUBJECTS.get(link.subject_type)
        subject = session.get(record_type.model, link.subject_id) if record_type else None
        attached = subject is not None and record_type is not None
        if attached and access.can_see(session, principal, record_type, subject):
            return True
    return False


def visible(session: Session, principal: Principal) -> Any:
    """The same rule as a condition, for lists and counts."""
    if principal.reads_all:
        return None
    trusted = principal.units_for(*TRUSTED)
    if trusted is None:
        return None
    me = principal.account_id
    named = exists(
        select(RecordOwner.id).where(
            RecordOwner.record_type == "evidence",
            RecordOwner.record_id == Evidence.id,
            RecordOwner.account_id == me,
        )
    )
    found: list[Any] = [named, Evidence.created_by == me]
    if trusted:
        found.append(Evidence.org_unit_id.in_(trusted))
    ordinary = Evidence.restricted.is_(False)
    assessed = principal.units_for(roles.ASSESSOR)
    if assessed is None:
        found.append(ordinary)
        return or_(*found)
    if assessed:
        found.append(and_(ordinary, Evidence.org_unit_id.in_(assessed)))
    top = _sensitive(session)
    open_enough = and_(ordinary, or_(Evidence.data_class.is_(None), Evidence.data_class != top))
    for key, record_type in SUBJECTS.items():
        model: Any = record_type.model
        seen = access.visible(session, principal, record_type)
        attached = select(EvidenceLink.id).join(model, model.id == EvidenceLink.subject_id).where(
            EvidenceLink.evidence_id == Evidence.id, EvidenceLink.subject_type == key
        )  # fmt: skip
        if seen is not None:
            attached = attached.where(seen)
        found.append(and_(open_enough, exists(attached)))
    return or_(*found)


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    """Evidence is collected by the people who do the work: anyone may add it for a unit
    they work in or have a role over."""
    if principal.account_id is None or org_unit_id is None:
        return principal.manages
    if org_unit_id in principal.member_units:
        return True
    return any(principal.covers(role, org_unit_id) for role in (*TRUSTED, roles.ASSESSOR))


# --- The record type ----------------------------------------------------------------------


def _day(value: Any, field: str, errors: records.Errors, *, required: bool = False) -> date | None:
    if value in (None, ""):
        if required:
            errors.add(field, "Give a date, as year-month-day.")
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        errors.add(field, "Give a date, as year-month-day.")
        return None


def _new(item: Evidence) -> None:
    item.status, item.kind = "active", "note"


def _apply(
    session: Session, item: Evidence, values: Mapping[str, Any], errors: records.Errors,
    creating: bool,
) -> None:  # fmt: skip
    if "kind" in values or creating:
        kind = values.get("kind") or "note"
        if kind not in EVIDENCE_KINDS:
            errors.add("kind", f"Use one of: {', '.join(EVIDENCE_KINDS)}.")
        elif not creating and kind != item.kind:
            errors.add("kind", "What kind of evidence it is does not change. Add another item.")
        else:
            item.kind = kind
    if "url" in values:
        item.url = records.url(values["url"], "url", errors)
    if "note" in values:
        item.note = records.text(values["note"])
    if "data_class" in values:
        item.data_class = records.choice(
            session, "data_classes", values["data_class"], "data_class", errors
        )
    if values.get("status") is not None:
        if values["status"] not in RECORD_STATUSES:
            errors.add("status", "Use active or retired.")
        else:
            item.status = values["status"]
    if "collected_on" in values or creating:
        day = _day(values.get("collected_on") or utc_now().date(), "collected_on", errors)
        if day is not None:
            if day > utc_now().date():
                errors.add("collected_on", "Evidence cannot be collected in the future.")
            else:
                item.collected_on = day
    for name in ("covers_from", "covers_to"):
        if name in values:
            setattr(item, name, _day(values[name], name, errors))
    if item.covers_from and item.covers_to and item.covers_to < item.covers_from:
        errors.add("covers_to", "The period ends before it begins.")
    if "valid_until" in values or creating:
        until = _day(values.get("valid_until"), "valid_until", errors)
        if until is None and "valid_until" not in errors and item.collected_on is not None:
            # Evidence holds for as long as a control's rating does, unless said otherwise.
            months = int(rules.get(session, "cadences").get("control_rating_months", 12))
            until = rules.add_months(item.collected_on, months)
        if until is not None:
            if item.collected_on is not None and until < item.collected_on:
                errors.add("valid_until", "It cannot stop holding before it was collected.")
            else:
                item.valid_until = until
    if item.kind == "link" and not item.url and "url" not in errors:
        errors.add("url", "Give the address of what it links to.")
    if item.kind in ("note", "attestation") and not item.note:
        errors.add("note", "Say what was seen, or what is being attested to.")


def state_of(item: Evidence, today: date | None = None) -> str:
    """Whether an item still counts: current, expiring (within a month), or stale."""
    today = today or utc_now().date()
    if item.valid_until < today:
        return "stale"
    return "expiring" if item.valid_until <= today + timedelta(days=SOON) else "current"


def _file_view(session: Session, item: Evidence) -> dict[str, Any] | None:
    stored = session.get(StoredFile, item.file_id) if item.file_id else None
    if stored is None:
        return None
    return {"name": item.file_name, "size": stored.size, "media_type": stored.media_type,
            "sha256": stored.sha256}  # fmt: skip


def _cards(session: Session, rows: list[Evidence]) -> list[dict[str, Any]]:
    today = utc_now().date()
    counts = dict(
        session.execute(
            select(EvidenceLink.evidence_id, func.count())
            .where(EvidenceLink.evidence_id.in_([row.id for row in rows] or [0]))
            .group_by(EvidenceLink.evidence_id)
        ).all()
    )
    return [
        {
            "kind": row.kind,
            "status": row.status,
            "state": state_of(row, today),
            "data_class": row.data_class,
            "collected_on": row.collected_on,
            "valid_until": row.valid_until,
            "supports": counts.get(row.id, 0),
            "has_file": row.file_id is not None,
        }
        for row in rows
    ]


def _detail(session: Session, principal: Principal, item: Evidence) -> dict[str, Any]:
    return {
        "url": item.url,
        "note": item.note,
        "covers_from": item.covers_from,
        "covers_to": item.covers_to,
        "file": _file_view(session, item),
        "subjects": subjects_of(session, principal, item),
    }


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    today = utc_now().date()
    state = filters.get("state")
    if state == "stale":
        found.append(Evidence.valid_until < today)
    elif state == "expiring":
        found.append(Evidence.valid_until.between(today, today + timedelta(days=SOON)))
    elif state == "current":
        found.append(Evidence.valid_until >= today)
    if filters.get("kind"):
        found.append(Evidence.kind == str(filters["kind"]))
    if filters.get("subject"):
        try:
            record_type, subject = find_any(session, str(filters["subject"]))
        except NotFound:
            return [Evidence.id < 0]
        found.append(
            Evidence.id.in_(
                select(EvidenceLink.evidence_id).where(
                    EvidenceLink.subject_type == record_type.key,
                    EvidenceLink.subject_id == subject.id,
                )
            )
        )
    return found


EVIDENCE = register(
    RecordType(
        "evidence",
        Evidence,
        "EV",
        "evidence",
        "evidence item",
        "evidence items",
        is_thing=False,
        sorts=("updated_at", "name", "ref", "collected_on", "valid_until", "status"),
        filters=("status",),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_see": can_see,
            "visible": visible,
            "can_add": can_add,
            "add_refusal": "Evidence is added for a unit you work in or have a role over.",
            "history_labels": {
                "collected_on": "Collected",
                "valid_until": "Holds until",
                "covers_from": "Covers from",
                "covers_to": "Covers to",
                "file_name": "File",
                "url": "Link",
                "data_class": "Data class",
            },
            "history_quiet": ("file_id",),
        },
    )
)


# --- What it supports ---------------------------------------------------------------------


def subjects_of(session: Session, principal: Principal, item: Evidence) -> dict[str, Any]:
    shown, hidden = [], 0
    for link in session.scalars(
        select(EvidenceLink).where(EvidenceLink.evidence_id == item.id).order_by(EvidenceLink.id)
    ):
        record_type = SUBJECTS.get(link.subject_type)
        subject = session.get(record_type.model, link.subject_id) if record_type else None
        if subject is None or record_type is None:
            continue
        if access.can_see(session, principal, record_type, subject):
            shown.append(records.chip(record_type, subject))
        else:
            hidden += 1
    return {"records": shown, "hidden": hidden}


def _may_attach(
    session: Session, principal: Principal, record_type: RecordType, subject: Any
) -> bool:
    """Evidence is put on a control or a scope by those who keep it or assess it."""
    return access.can_assess(session, principal, record_type, subject)


def set_subjects(session: Session, principal: Principal, item: Evidence, refs: list[str]) -> None:
    """Say what the evidence supports. What the person cannot see stays as it is."""
    if not access.can_edit(session, principal, EVIDENCE, item):
        raise PermissionDenied("You cannot edit this evidence.")
    wanted: dict[tuple[str, int], tuple[RecordType, Any]] = {}
    for ref in dict.fromkeys(refs):
        try:
            record_type, subject = find_any(session, ref)
        except NotFound as missing:
            raise Invalid(
                "What it supports was not saved.", {"subjects": str(missing)}
            ) from missing
        if record_type.key not in SUBJECTS or not access.can_see(
            session, principal, record_type, subject
        ):
            raise Invalid(
                "What it supports was not saved.",
                {"subjects": f"{ref} is not a control or a scope."},
            )
        wanted[(record_type.key, subject.id)] = (record_type, subject)
    have: dict[tuple[str, int], EvidenceLink] = {}
    for link in session.scalars(select(EvidenceLink).where(EvidenceLink.evidence_id == item.id)):
        have[(link.subject_type, link.subject_id)] = link
    with audit.operation(session, "evidence.attach"):
        for key, link in have.items():
            record_type = SUBJECTS.get(key[0])
            subject = session.get(record_type.model, key[1]) if record_type else None
            mine = (
                subject is not None
                and record_type is not None
                and access.can_see(session, principal, record_type, subject)
            )
            if mine and key not in wanted:
                session.delete(link)
        for key, (record_type, subject) in wanted.items():
            if key in have:
                continue
            if not _may_attach(session, principal, record_type, subject):
                raise PermissionDenied(
                    f"Evidence is attached to {subject.ref} by those who keep it or assess it."
                )
            session.add(EvidenceLink(evidence_id=item.id, subject_type=key[0], subject_id=key[1]))
        records.touch(session, item)


def of_subject(
    session: Session, principal: Principal, record_type: RecordType, subject: Any
) -> dict[str, Any]:
    """The evidence attached to a control or a scope, cut to what the person may see, with
    how much of it still counts."""
    rows = session.scalars(
        select(Evidence)
        .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
        .where(
            EvidenceLink.subject_type == record_type.key,
            EvidenceLink.subject_id == subject.id,
            Evidence.status == "active",
        )
        .order_by(Evidence.valid_until.desc(), Evidence.id)
    ).all()
    seen = [row for row in rows if can_see(session, principal, row)]
    cards = records.cards(session, EVIDENCE, seen)
    return {
        "items": cards,
        "hidden": len(rows) - len(seen),
        "current": sum(1 for row in rows if state_of(row) != "stale"),
        "can_add": _may_attach(session, principal, record_type, subject),
    }


def current_for(session: Session, record_type: RecordType, subject_id: int) -> int:
    """How many items of evidence on something still count, whoever is asking."""
    today = utc_now().date()
    return int(
        session.execute(
            select(func.count())
            .select_from(Evidence)
            .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
            .where(
                EvidenceLink.subject_type == record_type.key,
                EvidenceLink.subject_id == subject_id,
                Evidence.status == "active",
                Evidence.valid_until >= today,
            )
        ).scalar_one()
    )


# --- Files --------------------------------------------------------------------------------


def attach_file(
    session: Session, principal: Principal, item: Evidence, root: Path, data: bytes,
    name: str | None,
) -> Evidence:  # fmt: skip
    """Store a file and make it this item's. Its type is judged by its content."""
    if not access.can_edit(session, principal, EVIDENCE, item):
        raise PermissionDenied("You cannot edit this evidence.")
    if item.kind != "file":
        raise Invalid("The file was not stored.", {"file": "This item is not a file."})
    digest, kind = store.save(root, data)
    stored = session.scalars(select(StoredFile).where(StoredFile.sha256 == digest)).first()
    if stored is None:
        stored = StoredFile(
            sha256=digest, size=len(data), media_type=kind.media_type, extension=kind.extension,
            created_at=utc_now(),
        )  # fmt: skip
        session.add(stored)
        session.flush()
    with audit.operation(session, "evidence.file", sha256=digest, size=len(data)):
        item.file_id, item.file_name = stored.id, store.safe_name(name, kind)
        records.touch(session, item)
    return item


def download(
    session: Session, principal: Principal, item: Evidence, root: Path
) -> tuple[Path, str, str]:
    """Where the file is, what to call it, and its type, for someone who may see the item.
    Each download is recorded."""
    if not can_see(session, principal, item):
        raise NotFound(f"There is no evidence item {item.ref}.")
    stored = session.get(StoredFile, item.file_id) if item.file_id else None
    if stored is None:
        raise NotFound("This item has no file.")
    path = store.path_of(root, stored.sha256)
    if not path.is_file():
        raise NotFound("The file is missing from the data home.")
    audit.record(session, "evidence.downloaded", item, changes={"file": [None, item.file_name]})
    return path, item.file_name or f"{item.ref}.{stored.extension}", stored.media_type


def due(session: Session, principal: Principal) -> list[Evidence]:
    """A person's own evidence that has stopped counting or is about to."""
    me = principal.account_id
    if me is None:
        return []
    soon = utc_now().date() + timedelta(days=SOON)
    owned = exists(
        select(RecordOwner.id).where(
            RecordOwner.record_type == "evidence",
            RecordOwner.record_id == Evidence.id,
            RecordOwner.account_id == me,
            RecordOwner.kind.in_(access.EDITING_KINDS),
        )
    )
    in_use = exists(select(EvidenceLink.id).where(EvidenceLink.evidence_id == Evidence.id))
    return list(
        session.scalars(
            select(Evidence)
            .where(Evidence.status == "active", Evidence.valid_until <= soon, owned, in_use)
            .order_by(Evidence.valid_until)
            .limit(20)
        )
    )
