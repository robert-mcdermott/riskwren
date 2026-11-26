"""Issues: what is wrong, who is fixing it, and by when (see spec/engine.md).

An issue comes from somewhere (a failed test, a gap, an audit, an incident, a review, or
somebody noticing), has a severity whose meaning is defined, and is due on a date that
follows from that severity. It is put right through actions. Its owner proposes closure,
saying what was done and why it happened; it closes when someone who does not own it has
confirmed that. Nobody confirms the closure of their own issue.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.compliance import evidence, frameworks
from riskwren.compliance.scopes import SCOPE
from riskwren.controls.service import CONTROL
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Action,
    Assessment,
    Control,
    ControlTest,
    Evidence,
    EvidenceLink,
    Framework,
    Implementation,
    Issue,
    IssueSubject,
    RecordOwner,
    Requirement,
    Scope,
    TestResult,
)
from riskwren.db.models.compliance import SEVERITIES
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import RecordType, find, find_any, register
from riskwren.people import notices
from riskwren.program import rules, vocab
from riskwren.risk.register import RISK
from riskwren.treatment import service as treatment

KEY = "issue"
LIVE = ("open", "proposed")
DUE_DAYS = {"critical": 30, "high": 90, "moderate": 180, "low": 365}
# Bands of age, in days since an issue was raised: youngest and oldest, inclusive.
AGES: dict[str, tuple[int, int | None]] = {
    "0-30": (0, 30), "31-90": (31, 90), "91-180": (91, 180), "181+": (181, None),
}  # fmt: skip
# What an issue can be about. A requirement is not a record of its own, so it is named by
# its framework and code.
SUBJECTS: dict[str, RecordType] = {"control": CONTROL, "scope": SCOPE, "risk": RISK}
TRUSTED = (roles.STEWARD, roles.LEADER, roles.MANAGER)
SECOND_LINE = (roles.ASSESSOR, roles.MANAGER)


# --- Who may see it, raise it, and confirm it ---------------------------------------------


def _in(units: frozenset[int] | None, unit: int) -> bool:
    return units is None or unit in units


def _works_on(session: Session, issue_id: int, account_id: int | None) -> bool:
    if account_id is None:
        return False
    return (
        session.scalars(
            select(Action.id).where(
                Action.source_type == KEY,
                Action.source_id == issue_id,
                Action.owner_id == account_id,
            )
        ).first()
        is not None
    )


def can_see(session: Session, principal: Principal, issue: Issue) -> bool:
    """An issue is known to those with a part in it: whoever raised it, those named on it,
    those with an action on it, and those with a role over its unit."""
    if principal.reads_all or _in(principal.units_for(*TRUSTED), issue.org_unit_id):
        return True
    me = principal.account_id
    if me is not None and issue.created_by == me:
        return True
    if access.owner_kinds(session, ISSUE, issue.id, me) or _works_on(session, issue.id, me):
        return True
    if issue.restricted:
        return False
    return _in(principal.units_for(roles.ASSESSOR), issue.org_unit_id)


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
            RecordOwner.record_type == KEY,
            RecordOwner.record_id == Issue.id,
            RecordOwner.account_id == me,
        )
    )
    working = exists(
        select(Action.id).where(
            Action.source_type == KEY, Action.source_id == Issue.id, Action.owner_id == me
        )
    )
    found: list[Any] = [named, working, Issue.created_by == me]
    if trusted:
        found.append(Issue.org_unit_id.in_(trusted))
    assessed = principal.units_for(roles.ASSESSOR)
    if assessed is None:
        found.append(Issue.restricted.is_(False))
    elif assessed:
        found.append(and_(Issue.restricted.is_(False), Issue.org_unit_id.in_(assessed)))
    return or_(*found)


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    """Anyone may say that something is wrong in a unit they work in or have a role over."""
    return evidence.can_add(principal, org_unit_id)


def _owns(session: Session, principal: Principal, issue: Issue) -> bool:
    kinds = access.owner_kinds(session, ISSUE, issue.id, principal.account_id)
    return bool(kinds & set(access.EDITING_KINDS))


def can_validate(session: Session, principal: Principal, issue: Issue) -> bool:
    """Closure is confirmed by the second line, and never by whoever owns the issue or
    proposed that it be closed."""
    me = principal.account_id
    return (
        principal.assesses_unit(issue.org_unit_id)
        and not _owns(session, principal, issue)
        and (me is None or me != issue.proposed_by)
    )


# --- The clock ----------------------------------------------------------------------------


def due_days(session: Session, severity: str) -> int:
    table = rules.get(session, "cadences").get("issue_due_days") or {}
    return int(table.get(severity, DUE_DAYS[severity]))


def due_for(session: Session, severity: str, raised: date) -> date:
    """When an issue of this severity, raised on this day, is due."""
    return raised + timedelta(days=due_days(session, severity))


# --- The record type ----------------------------------------------------------------------


def _new(issue: Issue) -> None:
    issue.status, issue.source_kind, issue.extensions = "open", "observation", []


def _apply(
    session: Session, issue: Issue, values: Mapping[str, Any], errors: records.Errors,
    creating: bool,
) -> None:  # fmt: skip
    if not creating and issue.status not in LIVE and set(values) - {"tags", "restricted"}:
        errors.add("status", "This issue is closed. Reopen it to change it.")
        return
    if "severity" in values or creating:
        severity = records.text(values.get("severity"))
        if severity not in SEVERITIES:
            errors.add("severity", "Choose critical, high, moderate, or low.")
        elif creating or severity != issue.severity:
            # The date follows the severity, counted from the day the issue was raised.
            # Changing the severity sets the date again by the rule; a date moved by hand
            # is put aside, and the history keeps both.
            raised = utc_now().date() if creating else issue.created_at.date()
            issue.severity = severity
            issue.due_on = due_for(session, severity, raised)
            if creating:
                issue.original_due_on = issue.due_on
    if "source_kind" in values or creating:
        kind = records.choice(
            session, "issue_sources", values.get("source_kind") or "observation",
            "source_kind", errors,
        )  # fmt: skip
        if kind:
            issue.source_kind = kind


def _progress(session: Session, ids: list[int]) -> dict[int, dict[str, int]]:
    found = {key: {"done": 0, "total": 0} for key in ids}
    if not ids:
        return found
    for issue_id, status, count in session.execute(
        select(Action.source_id, Action.status, func.count())
        .where(Action.source_type == KEY, Action.source_id.in_(ids), Action.status != "cancelled")
        .group_by(Action.source_id, Action.status)
    ):
        found[issue_id]["total"] += int(count)
        if status == "done":
            found[issue_id]["done"] += int(count)
    return found


def _cards(session: Session, rows: list[Issue]) -> list[dict[str, Any]]:
    today = utc_now().date()
    progress = _progress(session, [row.id for row in rows])
    return [
        {
            "severity": row.severity,
            "status": row.status,
            "source_kind": row.source_kind,
            "due_on": row.due_on,
            "original_due_on": row.original_due_on,
            "moved": len(row.extensions or []),
            "overdue": row.status in LIVE and row.due_on < today,
            "closed_at": row.closed_at,
            "created_at": row.created_at,
            "progress": progress[row.id],
        }
        for row in rows
    ]


def subjects_of(session: Session, principal: Principal, issue: Issue) -> dict[str, Any]:
    """What the issue is about, cut to what the person may see."""
    shown: list[dict[str, Any]] = []
    required: list[dict[str, Any]] = []
    hidden = 0
    for link in session.scalars(
        select(IssueSubject).where(IssueSubject.issue_id == issue.id).order_by(IssueSubject.id)
    ):
        if link.subject_type == "requirement":
            requirement = session.get(Requirement, link.subject_id)
            framework = session.get(Framework, requirement.framework_id) if requirement else None
            if requirement is not None and framework is not None:
                required.append(
                    {"framework": {"key": framework.key, "title": framework.title},
                     "code": requirement.code, "title": requirement.title}
                )  # fmt: skip
            continue
        record_type = SUBJECTS.get(link.subject_type)
        subject = session.get(record_type.model, link.subject_id) if record_type else None
        if subject is None or record_type is None:
            continue
        if access.can_see(session, principal, record_type, subject):
            shown.append(records.chip(record_type, subject))
        else:
            hidden += 1
    return {"records": shown, "requirements": required, "hidden": hidden}


def source_of(session: Session, issue: Issue) -> dict[str, Any] | None:
    """Where a test-raised issue came from: the assessment and what its test found."""
    if issue.source_type != "test_result" or issue.source_id is None:
        return None
    result = session.get(TestResult, issue.source_id)
    assessment = session.get(Assessment, result.assessment_id) if result else None
    if result is None or assessment is None:
        return None
    return {
        "assessment": {"ref": assessment.ref, "name": assessment.name},
        "design": result.design,
        "operation": result.operation,
        "tested_by": result.tested_by_name,
        "tested_at": result.tested_at,
    }


def actions_of(session: Session, principal: Principal, issue: Issue) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Action)
        .where(Action.source_type == KEY, Action.source_id == issue.id)
        .order_by(Action.due_on, Action.id)
    ).all()
    return [treatment.action_view(session, principal, row) for row in rows]


def closure_evidence(session: Session, principal: Principal, issue: Issue) -> list[dict[str, Any]]:
    cited = session.scalars(
        select(Evidence)
        .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
        .where(EvidenceLink.subject_type == KEY, EvidenceLink.subject_id == issue.id)
        .order_by(Evidence.id)
    ).all()
    return [
        {"ref": item.ref, "name": item.name, "state": evidence.state_of(item)}
        for item in cited
        if evidence.can_see(session, principal, item)
    ]


def _detail(session: Session, principal: Principal, issue: Issue) -> dict[str, Any]:
    live = issue.status in LIVE
    editable = access.can_edit(session, principal, ISSUE, issue)
    second = principal.assesses_unit(issue.org_unit_id)
    return {
        "extensions": issue.extensions or [],
        "root_cause": issue.root_cause,
        "closure_note": issue.closure_note,
        "return_note": issue.return_note,
        "proposed": {"by": issue.proposed_by_name, "at": issue.proposed_at}
        if issue.proposed_at
        else None,
        "validated": {"by": issue.validated_by_name, "at": issue.validated_at}
        if issue.validated_at
        else None,
        "due_days": due_days(session, issue.severity),
        "subjects": subjects_of(session, principal, issue),
        "source": source_of(session, issue),
        "actions": actions_of(session, principal, issue),
        "closure_evidence": closure_evidence(session, principal, issue),
        "can_act": {
            "work": editable and issue.status == "open",
            "propose": editable and issue.status == "open",
            "validate": issue.status == "proposed" and can_validate(session, principal, issue),
            "owns": _owns(session, principal, issue),
            "cancel": live and second,
            "reopen": not live and second,
        },
    }


def _about(subject_type: str, ids: Any) -> Any:
    return exists(
        select(IssueSubject.id).where(
            IssueSubject.issue_id == Issue.id,
            IssueSubject.subject_type == subject_type,
            IssueSubject.subject_id.in_(ids),
        )
    )


def in_scope(scope: Scope) -> Any:
    """Issues that bear on a scope: those about the scope itself, or about a control it uses,
    whether it does that control itself or inherits it."""
    used = select(Implementation.control_id).where(Implementation.scope_id == scope.id)
    return or_(_about("scope", [scope.id]), _about("control", used))


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    status = filters.get("status")
    if status == "live":
        found.append(Issue.status.in_(LIVE))
    elif status:
        found.append(Issue.status == status)
    if filters.get("overdue"):
        found += [Issue.status.in_(LIVE), Issue.due_on < utc_now().date()]
    age = AGES.get(str(filters.get("age") or ""))
    if age is not None:
        # How long ago it was raised, in days: a band of the aging table.
        today = utc_now()
        youngest, oldest = age
        found.append(Issue.created_at <= today - timedelta(days=youngest))
        if oldest is not None:
            found.append(Issue.created_at > today - timedelta(days=oldest + 1))
    if filters.get("about"):
        try:
            record_type, subject = find_any(session, str(filters["about"]))
        except NotFound:
            return [Issue.id < 0]
        if record_type.key == "scope":
            found.append(in_scope(subject))
        else:
            found.append(_about(record_type.key, [subject.id]))
    return found


def _history_title(event: Any, lookups: Any) -> str | None:
    if event.subject_type == "action":
        changes = event.changes or {}
        title = (changes.get("title") or [None, None])[1]
        if event.action == "created" and title:
            return f"Added an action: {title}"
        return None
    if event.subject_type != "issue_subject":
        return None
    return "Changed what it is about"


ISSUE = register(
    RecordType(
        KEY,
        Issue,
        "ISS",
        "issues",
        "issue",
        "issues",
        is_thing=False,
        sorts=("updated_at", "name", "ref", "status", "due_on", "created_at"),
        filters=("severity", "source_kind"),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_see": can_see,
            "visible": visible,
            "can_add": can_add,
            "add_refusal": "An issue is raised for a unit you work in or have a role over.",
            "history_title": _history_title,
            "history_vocabularies": {
                "severity": "issue_severities",
                "source_kind": "issue_sources",
                "root_cause": "root_causes",
            },
            "history_labels": {
                "due_on": "Due",
                "original_due_on": "First due",
                "source_kind": "Source",
                "root_cause": "Root cause",
                "closure_note": "What was done",
                "return_note": "Sent back because",
                "closed_at": "Closed",
            },
            "history_quiet": (
                "proposed_by", "proposed_by_name", "proposed_at", "validated_by",
                "validated_by_name", "validated_at", "extensions", "source_type", "source_id",
            ),
        },
    )
)  # fmt: skip


# --- Raising ------------------------------------------------------------------------------


def _link(session: Session, issue: Issue, subject_type: str, subject_id: int) -> None:
    have = session.scalars(
        select(IssueSubject.id).where(
            IssueSubject.issue_id == issue.id,
            IssueSubject.subject_type == subject_type,
            IssueSubject.subject_id == subject_id,
        )
    ).first()
    if have is None:
        session.add(
            IssueSubject(issue_id=issue.id, subject_type=subject_type, subject_id=subject_id)
        )


def _wanted(
    session: Session, principal: Principal, values: Mapping[str, Any]
) -> list[tuple[str, int]]:
    """What a new issue is said to be about, checked against what its author may see."""
    errors = records.Errors()
    found: list[tuple[str, int]] = []
    for ref in dict.fromkeys(values.get("subjects") or []):
        try:
            record_type, subject = find_any(session, str(ref))
        except NotFound:
            record_type, subject = None, None
        if (
            record_type is None
            or record_type.key not in SUBJECTS
            or not access.can_see(session, principal, record_type, subject)
        ):
            errors.add("subjects", f"{ref} is not a control, a scope, or a risk you can see.")
        else:
            found.append((record_type.key, subject.id))
    for item in values.get("requirements") or []:
        try:
            framework = frameworks.by_key(session, str(item.get("framework", "")))
            requirement = frameworks.find(session, framework, str(item.get("code", "")))
        except NotFound as missing:
            errors.add("requirements", str(missing))
        else:
            found.append(("requirement", requirement.id))
    if errors:
        raise Invalid("The issue was not saved.", errors)
    return found


def create(session: Session, principal: Principal, values: Mapping[str, Any]) -> Issue:
    """Raise an issue. Whoever raises it answers for it until an owner is named."""
    about = _wanted(session, principal, values)
    owner = values.get("owner_id")
    with audit.operation(session, "issue.create"):
        issue: Issue = records.create(session, principal, ISSUE, values)
        for subject_type, subject_id in about:
            _link(session, issue, subject_type, subject_id)
        session.flush()
        if owner not in (None, "") and int(owner) != principal.account_id:
            _hand_to(session, issue, [int(owner)])
            notices.tell(
                session, int(owner), "issue",
                f"{issue.ref} is yours to put right: {issue.name}", f"/issues/{issue.ref}",
                by=principal,
            )  # fmt: skip
    return issue


def _hand_to(session: Session, issue: Issue, account_ids: list[int]) -> None:
    """Make these people the issue's owners, in place of whoever raised it."""
    for row in session.scalars(
        select(RecordOwner).where(RecordOwner.record_type == KEY, RecordOwner.record_id == issue.id)
    ):
        session.delete(row)
    session.flush()
    for account_id in dict.fromkeys(account_ids):
        session.add(
            RecordOwner(record_type=KEY, record_id=issue.id, account_id=account_id, kind="owner")
        )
    session.flush()


def open_for_test(
    session: Session, control: Control, *, besides: int | None = None
) -> Issue | None:
    """The issue already open because a test found this control wanting, if there is one."""
    return session.scalars(
        select(Issue)
        .where(
            Issue.status.in_(LIVE),
            Issue.source_kind == "test",
            Issue.id != (besides or 0),
            _about("control", [control.id]),
        )
        .order_by(Issue.id)
    ).first()


def from_test(
    session: Session,
    principal: Principal,
    result: TestResult,
    test: ControlTest,
    assessment: Assessment,
    control: Control,
) -> Issue | None:
    """A test found a control partly effective or ineffective: open an issue for it, filled
    in from the result, owned by the control's owners, and naming every scope that relies on
    the control. If one is already open for the same control, that one stands."""
    outcome = "ineffective" if "ineffective" in (result.design, result.operation) else "partly"
    if open_for_test(session, control) is not None:
        return None
    word = "ineffective" if outcome == "ineffective" else "partly effective"
    looked = f"\n\nWhat was looked at: {result.sample}" if result.sample else ""
    now = utc_now()
    severity = "high" if outcome == "ineffective" else "moderate"
    with audit.operation(session, "issue.from_test"):
        issue = Issue(
            name=f"{control.name}: found {word} in {assessment.ref}"[:200],
            summary=f"{result.note}{looked}",
            org_unit_id=control.org_unit_id,
            severity=severity,
            source_kind="test",
            source_type="test_result",
            source_id=result.id,
            due_on=due_for(session, severity, now.date()),
            status="open",
            extensions=[],
            tags=[],
            restricted=control.restricted,
            version=1,
            created_by=principal.account_id,
            created_at=now,
            updated_at=now,
        )
        issue.original_due_on = issue.due_on
        from riskwren.db.refs import next_ref

        issue.ref = next_ref(session, ISSUE.prefix)
        session.add(issue)
        session.flush()
        _link(session, issue, "control", control.id)
        for scope_id in session.scalars(
            select(Implementation.scope_id)
            .where(Implementation.control_id == control.id)
            .order_by(Implementation.scope_id)
        ):
            _link(session, issue, "scope", scope_id)
        owners = [
            row.account_id
            for row in session.scalars(
                select(RecordOwner).where(
                    RecordOwner.record_type == CONTROL.key,
                    RecordOwner.record_id == control.id,
                    RecordOwner.kind.in_(access.EDITING_KINDS),
                )
            )
        ]
        _hand_to(session, issue, owners)
        notices.tell_all(
            session, owners, "issue",
            f"{issue.ref} was opened by a test of {control.name}, which you own",
            f"/issues/{issue.ref}", by=principal,
        )  # fmt: skip
    return issue


def set_subjects(
    session: Session, principal: Principal, issue: Issue, values: Mapping[str, Any]
) -> None:
    """Say what the issue is about. What the person cannot see stays as it is."""
    if not access.can_edit(session, principal, ISSUE, issue):
        raise PermissionDenied("You cannot edit this issue.")
    wanted = set(_wanted(session, principal, values))
    with audit.operation(session, "issue.subjects"):
        for link in session.scalars(select(IssueSubject).where(IssueSubject.issue_id == issue.id)):
            key = (link.subject_type, link.subject_id)
            record_type = SUBJECTS.get(link.subject_type)
            subject = session.get(record_type.model, link.subject_id) if record_type else None
            mine = link.subject_type == "requirement" or (
                subject is not None
                and record_type is not None
                and access.can_see(session, principal, record_type, subject)
            )
            if mine and key not in wanted:
                session.delete(link)
        session.flush()
        for subject_type, subject_id in sorted(wanted):
            _link(session, issue, subject_type, subject_id)
        issue.updated_at = utc_now()


# --- Working on it ------------------------------------------------------------------------


def _open(session: Session, principal: Principal, issue: Issue) -> None:
    if not access.can_edit(session, principal, ISSUE, issue):
        raise PermissionDenied("You cannot change this issue.")
    if issue.status != "open":
        raise Conflict(
            "Closure has been proposed, so the issue waits for that to be confirmed or sent back."
            if issue.status == "proposed"
            else "This issue is closed."
        )


def add_action(
    session: Session,
    principal: Principal,
    issue: Issue,
    *,
    title: str | None,
    owner_id: Any,
    due_on: Any,
    detail: str | None = None,
) -> Action:
    _open(session, principal, issue)
    action = treatment.new_action(
        session, principal, KEY, issue.id, title=title, owner_id=owner_id, due_on=due_on,
        detail=detail,
    )  # fmt: skip
    issue.updated_at = utc_now()
    notices.tell(
        session, action.owner_id, "action",
        f"{action.ref} is yours, for {issue.ref}: {action.title}", f"/issues/{issue.ref}",
        by=principal,
    )  # fmt: skip
    return action


def reschedule(
    session: Session, principal: Principal, issue: Issue, *, due_on: Any, reason: str | None
) -> Issue:
    """Move the date. It needs a reason, and where it started and every move stay on the
    record."""
    _open(session, principal, issue)
    errors = records.Errors()
    try:
        due = due_on if isinstance(due_on, date) else date.fromisoformat(str(due_on))
    except ValueError:
        due = None
        errors.add("due_on", "Give a date, as year-month-day.")
    why = records.text(reason)
    if not why:
        errors.add("reason", "Say why the date is moving.")
    if due is not None and due == issue.due_on:
        errors.add("due_on", "That is the date it already has.")
    if errors:
        raise Invalid("The date was not moved.", errors)
    assert due is not None and why is not None
    with audit.operation(session, "issue.reschedule"):
        issue.extensions = [
            *(issue.extensions or []),
            {"from": issue.due_on.isoformat(), "to": due.isoformat(), "reason": why,
             "by": principal.name, "on": utc_now().date().isoformat()},
        ]  # fmt: skip
        issue.due_on = due
        records.touch(session, issue)
    return issue


def _open_actions(session: Session, issue: Issue) -> int:
    return int(
        session.execute(
            select(func.count())
            .select_from(Action)
            .where(
                Action.source_type == KEY,
                Action.source_id == issue.id,
                Action.status.in_(treatment.OPEN),
            )
        ).scalar_one()
    )


def propose(
    session: Session,
    principal: Principal,
    issue: Issue,
    *,
    note: str | None,
    root_cause: str | None,
    evidence_refs: list[str] | None = None,
) -> Issue:
    """Its owner says the issue is put right: what was done, why it happened, and what shows
    it. It then waits for someone else to confirm."""
    _open(session, principal, issue)
    left = _open_actions(session, issue)
    if left:
        raise Conflict(
            f"{left} of its actions {'is' if left == 1 else 'are'} still open. "
            "Finish or cancel them first."
        )
    errors = records.Errors()
    done = records.text(note)
    if not done:
        errors.add("note", "Say what was done to put it right.")
    cause = records.choice(session, "root_causes", root_cause, "root_cause", errors, required=True)
    cited: list[Evidence] = []
    for ref in dict.fromkeys(evidence_refs or []):
        try:
            item = find(session, evidence.EVIDENCE, ref)
        except NotFound:
            item = None
        if item is None or not evidence.can_see(session, principal, item):
            errors.add("evidence", f"There is no evidence {ref}.")
        else:
            cited.append(item)
    if errors:
        raise Invalid("Closure was not proposed.", errors)
    with audit.operation(session, "issue.propose"):
        for link in session.scalars(
            select(EvidenceLink).where(
                EvidenceLink.subject_type == KEY, EvidenceLink.subject_id == issue.id
            )
        ):
            session.delete(link)
        session.flush()
        for item in cited:
            session.add(EvidenceLink(evidence_id=item.id, subject_type=KEY, subject_id=issue.id))
        issue.status, issue.closure_note, issue.root_cause = "proposed", done, cause
        issue.return_note = None
        issue.proposed_by, issue.proposed_by_name = principal.account_id, principal.name
        issue.proposed_at = utc_now()
        records.touch(session, issue)
        session.flush()
        owners = set(notices.owners(session, KEY, issue.id))
        second = [
            person
            for person in notices.holders(session, SECOND_LINE, issue.org_unit_id)
            if person not in owners
        ]
        notices.tell_all(
            session, second, "closure",
            f"{issue.ref} is said to be put right, and waits for someone to confirm it",
            f"/issues/{issue.ref}", by=principal,
        )  # fmt: skip
    return issue


def validate(
    session: Session, principal: Principal, issue: Issue, *, confirm: bool, note: str | None
) -> Issue:
    """Someone who does not own the issue confirms that it is put right, and it closes; or
    sends it back, saying what is missing."""
    if issue.status != "proposed":
        raise Conflict("Nobody has proposed closing this issue.")
    if _owns(session, principal, issue):
        raise PermissionDenied("Nobody confirms the closure of an issue they own.")
    if principal.account_id is not None and principal.account_id == issue.proposed_by:
        raise PermissionDenied("Nobody confirms a closure they proposed. Ask someone else.")
    if not principal.assesses_unit(issue.org_unit_id):
        raise PermissionDenied("Closure is confirmed by an assessor or a manager for the unit.")
    said = records.text(note)
    if not confirm and not said:
        raise Invalid("It was not sent back.", {"note": "Say what is still missing."})
    with audit.operation(session, "issue.validate"):
        if confirm:
            issue.status, issue.closed_at = "closed", utc_now()
            issue.validated_by, issue.validated_by_name = principal.account_id, principal.name
            issue.validated_at = issue.closed_at
        else:
            issue.status, issue.return_note = "open", said
        records.touch(session, issue)
        session.flush()
        told = (
            f"{issue.ref} is closed: {principal.name} confirmed it"
            if confirm
            else f"{issue.ref} was sent back by {principal.name}: {said}"
        )
        notices.tell_all(
            session, [*notices.owners(session, KEY, issue.id), issue.proposed_by], "closure",
            told, f"/issues/{issue.ref}", by=principal,
        )  # fmt: skip
    return issue


def cancel(session: Session, principal: Principal, issue: Issue, *, reason: str | None) -> Issue:
    """Withdraw an issue raised in error. That is for the second line, since an owner who
    could cancel their own issue would never need to have its closure confirmed."""
    if not principal.assesses_unit(issue.org_unit_id):
        raise PermissionDenied("An issue is withdrawn by an assessor or a manager for the unit.")
    if issue.status not in LIVE:
        raise Conflict("This issue is already closed.")
    why = records.text(reason)
    if not why:
        raise Invalid("The issue was not withdrawn.", {"reason": "Say why it is withdrawn."})
    with audit.operation(session, "issue.cancel"):
        issue.status, issue.closure_note, issue.closed_at = "cancelled", why, utc_now()
        for action in session.scalars(
            select(Action).where(
                Action.source_type == KEY,
                Action.source_id == issue.id,
                Action.status.in_(treatment.OPEN),
            )
        ):
            action.status = "cancelled"
        records.touch(session, issue)
        session.flush()
        notices.tell_all(
            session, notices.owners(session, KEY, issue.id), "issue",
            f"{issue.ref} was withdrawn by {principal.name}: {why}", f"/issues/{issue.ref}",
            by=principal,
        )  # fmt: skip
    return issue


def reopen(session: Session, principal: Principal, issue: Issue, *, reason: str | None) -> Issue:
    """Open a closed issue again, because it turned out not to be put right."""
    if not principal.assesses_unit(issue.org_unit_id):
        raise PermissionDenied("An issue is reopened by an assessor or a manager for the unit.")
    if issue.status in LIVE:
        raise Conflict("This issue is open.")
    why = records.text(reason)
    if not why:
        raise Invalid("The issue was not reopened.", {"reason": "Say why it is open again."})
    with audit.operation(session, "issue.reopen"):
        issue.status, issue.return_note, issue.closed_at = "open", why, None
        issue.validated_by, issue.validated_by_name, issue.validated_at = None, None, None
        records.touch(session, issue)
        session.flush()
        notices.tell_all(
            session, notices.owners(session, KEY, issue.id), "issue",
            f"{issue.ref} is open again: {why}", f"/issues/{issue.ref}", by=principal,
        )  # fmt: skip
    return issue


# --- Its actions, as the action list sees them --------------------------------------------


def _manage(session: Session, principal: Principal, issue_id: int) -> bool:
    issue = session.get(Issue, issue_id)
    return issue is not None and access.can_edit(session, principal, ISSUE, issue)


def _settle(session: Session, issue_id: int) -> None:
    """When the last action on an issue is done, its owners are told it is theirs to close."""
    issue = session.get(Issue, issue_id)
    if issue is None or issue.status != "open":
        return
    issue.updated_at = utc_now()
    progress = _progress(session, [issue_id])[issue_id]
    if progress["total"] and progress["done"] == progress["total"]:
        notices.tell_all(
            session, notices.owners(session, KEY, issue_id), "issue",
            f"Every action on {issue.ref} is done. Say what was done, and propose closing it",
            f"/issues/{issue.ref}",
        )  # fmt: skip


def _describe(session: Session, principal: Principal, issue_id: int) -> dict[str, Any] | None:
    issue = session.get(Issue, issue_id)
    if issue is None or not can_see(session, principal, issue):
        return None
    return records.chip(ISSUE, issue)


def _action_visible(session: Session, principal: Principal) -> Any:
    seen = visible(session, principal)
    of_issue = select(Issue.id).where(Issue.id == Action.source_id)
    return exists(of_issue.where(seen) if seen is not None else of_issue)


def _action_in_units(within: list[int]) -> Any:
    return exists(
        select(Issue.id).where(Issue.id == Action.source_id, Issue.org_unit_id.in_(within))
    )


treatment.register_source(
    treatment.Source(KEY, _manage, _settle, _describe, _action_visible, _action_in_units)
)


# --- Lists that other pages need ----------------------------------------------------------


def plan_of_action(session: Session, principal: Principal, scope: Scope) -> dict[str, Any]:
    """The open issues that bear on a scope, each with its milestones: what a plan of action
    and milestones prints."""
    conditions = [Issue.status.in_(LIVE), in_scope(scope)]
    seen = visible(session, principal)
    if seen is not None:
        conditions.append(seen)
    order = {key: index for index, key in enumerate(SEVERITIES)}
    rows = sorted(
        session.scalars(select(Issue).where(*conditions)).all(),
        key=lambda row: (order[row.severity], row.due_on, row.id),
    )
    cards = records.cards(session, ISSUE, list(rows))
    for card, row in zip(cards, rows, strict=True):
        card["subjects"] = subjects_of(session, principal, row)
        card["actions"] = actions_of(session, principal, row)
        card["extensions"] = row.extensions or []
    counts = {key: sum(1 for row in rows if row.severity == key) for key in SEVERITIES}
    return {
        "issues": cards,
        "counts": counts,
        "overdue": sum(1 for card in cards if card["overdue"]),
        "severities": vocab.labels(session, "issue_severities"),
    }


def waiting_on(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """Issues a person owns that are still open, and closures that wait for them to confirm."""
    me = principal.account_id
    if me is None:
        return []
    found: list[dict[str, Any]] = []
    owned = select(RecordOwner.record_id).where(
        RecordOwner.record_type == KEY,
        RecordOwner.account_id == me,
        RecordOwner.kind.in_(access.EDITING_KINDS),
    )
    for issue in session.scalars(
        select(Issue).where(Issue.id.in_(owned), Issue.status == "open").order_by(Issue.due_on)
    ):
        found.append({"kind": "issue", "issue": issue})
    second = principal.units_for(*SECOND_LINE)
    if second is None or second:
        statement = select(Issue).where(Issue.status == "proposed", Issue.id.not_in(owned))
        if second is not None:
            statement = statement.where(Issue.org_unit_id.in_(second))
        for issue in session.scalars(statement.order_by(Issue.proposed_at).limit(25)):
            if issue.proposed_by != me and can_see(session, principal, issue):
                found.append({"kind": "closure", "issue": issue})
    return found
