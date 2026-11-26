"""Assessments and tests: finding out whether controls work.

An assessment looks at a scope's controls over a period. Each control in it has a test: a
procedure and a method. What a test found is a result, recorded by someone who does not own
the control and confirmed by a second person before it counts.

A result that counts becomes the control's rating. Because a control is described once, that
one result moves every requirement the control is mapped to, in every scope that uses or
inherits it, and the suggested rating of every risk it reduces. This is what *test once*
means.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import evidence, scopes
from riskwren.compliance.scopes import SCOPE
from riskwren.controls import service as controls
from riskwren.controls.service import CONTROL
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Account,
    Assessment,
    Control,
    ControlRequirement,
    ControlTest,
    Evidence,
    EvidenceLink,
    Framework,
    Implementation,
    Scope,
    ScopeFramework,
    TestResult,
)
from riskwren.db.models.compliance import TEST_METHODS, TEST_RESULTS
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import Field, RecordType, find, register

METHOD_LABELS = {"examine": "Examine", "interview": "Interview", "test": "Test"}
OPEN = ("planned", "in_progress")


# --- Who may do what ----------------------------------------------------------------------


def can_add(principal: Principal, org_unit_id: int | None) -> bool:
    """Assessing is the second line's work: assessors and managers whose scope covers it."""
    return principal.assesses_unit(org_unit_id)


def can_run(session: Session, principal: Principal, assessment: Assessment) -> bool:
    """Whether the person may plan and run this assessment: its lead, or an assessor or
    manager for its unit."""
    if principal.assesses_unit(assessment.org_unit_id):
        return True
    return principal.account_id is not None and principal.account_id == assessment.lead_id


def _owns(session: Session, principal: Principal, control_id: int) -> bool:
    return bool(
        access.owner_kinds(session, CONTROL, control_id, principal.account_id)
        & set(access.EDITING_KINDS)
    )


# --- The record type ----------------------------------------------------------------------


def _day(value: Any, field: str, errors: records.Errors) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        errors.add(field, "Give a date, as year-month-day.")
        return None


def _new(assessment: Assessment) -> None:
    assessment.status = "planned"


def _apply(
    session: Session, assessment: Assessment, values: Mapping[str, Any], errors: records.Errors,
    creating: bool,
) -> None:  # fmt: skip
    if creating:
        scope = values.get("_scope")
        if not isinstance(scope, Scope):
            errors.add("scope", "Say which scope is being assessed.")
        else:
            assessment.scope_id = scope.id
    if "framework" in values and (creating or assessment.status == "planned"):
        key = records.text(values["framework"])
        assessment.framework_id = None
        if key:
            framework = session.scalars(select(Framework).where(Framework.key == key)).first()
            held = (
                framework is not None
                and session.scalars(
                    select(ScopeFramework.id).where(
                        ScopeFramework.scope_id == assessment.scope_id,
                        ScopeFramework.framework_id == framework.id,
                    )
                ).first()
            )
            if framework is None or not held:
                errors.add("framework", "The scope is not held to that framework.")
            else:
                assessment.framework_id = framework.id
    if "lead_id" in values or creating:
        given = values.get("lead_id")
        lead = session.get(Account, int(given)) if str(given).isdigit() else None
        if given in (None, "") and creating:
            assessment.lead_id = assessment.created_by
        elif lead is None or lead.status == "disabled":
            errors.add("lead_id", "Choose a person whose account is not disabled.")
        else:
            assessment.lead_id = lead.id
    for name in ("period_start", "period_end"):
        if name in values:
            setattr(assessment, name, _day(values[name], name, errors))
    if (
        assessment.period_start
        and assessment.period_end
        and assessment.period_end < assessment.period_start
    ):
        errors.add("period_end", "The period ends before it begins.")


def _progress(session: Session, ids: list[int]) -> dict[int, dict[str, int]]:
    """For each assessment: how many of its tests are counted, waiting, and still to do."""
    found = {key: {"tests": 0, "counted": 0, "awaiting": 0, "failing": 0} for key in ids}
    if not ids:
        return found
    for assessment_id, count in session.execute(
        select(ControlTest.assessment_id, func.count())
        .where(ControlTest.assessment_id.in_(ids))
        .group_by(ControlTest.assessment_id)
    ):
        found[assessment_id]["tests"] = int(count)
    for result in session.scalars(
        select(TestResult).where(
            TestResult.assessment_id.in_(ids), TestResult.superseded_by.is_(None)
        )
    ):
        tally = found[result.assessment_id]
        if result.review == "confirmed":
            tally["counted"] += 1
            if min((result.design, result.operation), key=TEST_RESULTS[::-1].index) != "effective":
                tally["failing"] += 1
        elif result.review is None:
            tally["awaiting"] += 1
    return found


def _cards(session: Session, rows: list[Assessment]) -> list[dict[str, Any]]:
    progress = _progress(session, [row.id for row in rows])
    out = []
    for row in rows:
        scope = session.get(Scope, row.scope_id)
        framework = session.get(Framework, row.framework_id) if row.framework_id else None
        lead = session.get(Account, row.lead_id) if row.lead_id else None
        out.append(
            {
                "status": row.status,
                "scope": {"ref": scope.ref, "name": scope.name} if scope else None,
                "framework": {"key": framework.key, "title": framework.title}
                if framework
                else None,
                "lead": {"id": lead.id, "name": lead.display_name} if lead else None,
                "period_start": row.period_start,
                "period_end": row.period_end,
                "completed_at": row.completed_at,
                **progress[row.id],
            }
        )
    return out


def _detail(session: Session, principal: Principal, assessment: Assessment) -> dict[str, Any]:
    return {"can_run": can_run(session, principal, assessment) and assessment.status in OPEN}


def _conditions(session: Session, principal: Principal, filters: Mapping[str, Any]) -> list[Any]:
    found: list[Any] = []
    if filters.get("scope"):
        try:
            scope = find(session, SCOPE, str(filters["scope"]))
        except NotFound:
            return [Assessment.id < 0]
        found.append(Assessment.scope_id == scope.id)
    if filters.get("lead"):
        found.append(Assessment.lead_id == int(filters["lead"]))
    return found


def _history_title(event: Any, lookups: Any) -> str | None:
    """What happened to a test or a result, said with the control's name."""
    if event.subject_type not in ("control_test", "test_result"):
        return None
    changes = event.changes or {}

    def now(field: str) -> Any:
        pair = changes.get(field) or [None, None]
        return pair[1] if pair[1] is not None else pair[0]

    session = lookups.session
    if event.subject_type == "control_test":
        row = session.get(ControlTest, event.subject_id)
        control = session.get(Control, row.control_id if row else now("control_id"))
        name = control.name if control else "a control"
        if event.action == "created":
            return f"Planned a test of {name}"
        if event.action == "deleted":
            return f"Took {name} out"
        return f"Changed the plan for testing {name}"
    result = session.get(TestResult, event.subject_id)
    test = session.get(ControlTest, result.test_id) if result else None
    control = session.get(Control, test.control_id) if test else None
    name = control.name if control else "a control"
    if event.action == "created":
        words = {
            "effective": "effective",
            "partly": "partly effective",
            "ineffective": "ineffective",
        }
        design, operation = words.get(now("design"), ""), words.get(now("operation"), "")
        found = design if design == operation else f"design {design}, operation {operation}"
        return f"Recorded a result for {name}: {found}"
    if "review" in changes:
        if now("review") == "confirmed":
            return f"Confirmed the result for {name}"
        said = result.review_note if result else None
        return f"Returned the result for {name}" + (f": {said}" if said else "")
    if "superseded_by" in changes:
        return f"An earlier result for {name} was replaced"
    return None


ASSESSMENT = register(
    RecordType(
        "assessment",
        Assessment,
        "ASM",
        "assessments",
        "assessment",
        "assessments",
        fields=(Field("approach", "Approach", "long"),),
        is_thing=False,
        sorts=("updated_at", "name", "ref", "status", "period_end"),
        filters=("status",),
        extra={
            "new": _new,
            "apply": _apply,
            "cards": _cards,
            "detail": _detail,
            "conditions": _conditions,
            "can_add": can_add,
            "can_edit": can_run,
            "add_refusal": "An assessment is started by an assessor or a manager for the unit.",
            "history_title": _history_title,
            "history_keeps_titled": True,
            "history_labels": {
                "period_start": "Period from",
                "period_end": "Period to",
                "approach": "Approach",
                "completed_at": "Completed",
            },
        },
    )
)


# --- Planning -----------------------------------------------------------------------------


def _testable(session: Session, scope: Scope) -> dict[int, Implementation]:
    """What can be tested in a scope: the controls it does itself. One it inherits whole or
    shares is tested where it is provided."""
    rows = session.scalars(
        select(Implementation).where(
            Implementation.scope_id == scope.id,
            Implementation.inheritance == "none",
            Implementation.status != "not_applicable",
        )
    )
    return {row.control_id: row for row in rows}


def create(session: Session, principal: Principal, values: Mapping[str, Any]) -> Assessment:
    """Start an assessment of a scope. Unless particular controls are named, a test is planned
    for every control the scope does itself: all of them, or, with a framework, those that
    answer a requirement of it that applies."""
    try:
        scope = records.load(session, principal, SCOPE, str(values.get("scope") or ""))
    except NotFound as missing:
        raise Invalid("The assessment was not started.", {"scope": str(missing)}) from missing
    if scope.status != "active":
        raise Invalid("The assessment was not started.", {"scope": "That scope is retired."})
    given = {key: value for key, value in values.items() if key not in ("scope", "controls")}
    assessment: Assessment = records.create(
        session, principal, ASSESSMENT, {**given, "_scope": scope, "org_unit_id": scope.org_unit_id}
    )
    testable = _testable(session, scope)
    named = values.get("controls")
    if named:
        wanted = []
        for ref in dict.fromkeys(named):
            control = find(session, CONTROL, str(ref))
            if control.id not in testable:
                raise Invalid(
                    "The assessment was not started.",
                    {"controls": f"{ref} is not a control this scope does itself."},
                )
            wanted.append(control.id)
    elif assessment.framework_id is not None:
        framework = session.get(Framework, assessment.framework_id)
        applicable = scopes.applicable_ids(session, scope, framework)
        answering = set(
            session.scalars(
                select(ControlRequirement.control_id).where(
                    ControlRequirement.requirement_id.in_(applicable or {0}),
                    ControlRequirement.control_id.in_(list(testable) or [0]),
                )
            )
        )
        wanted = [control_id for control_id in testable if control_id in answering]
    else:
        wanted = list(testable)
    with audit.operation(session, "assessment.plan"):
        for control_id in wanted:
            _plan(session, assessment, testable[control_id])
        session.flush()
    return assessment


def _plan(session: Session, assessment: Assessment, row: Implementation) -> ControlTest:
    control = session.get(Control, row.control_id)
    assert control is not None
    test = ControlTest(
        assessment_id=assessment.id,
        implementation_id=row.id,
        control_id=control.id,
        procedure=f"Confirm that this is done as described: {control.statement}",
        method="examine",
    )
    session.add(test)
    return test


def _open(session: Session, principal: Principal, assessment: Assessment) -> None:
    if not can_run(session, principal, assessment):
        raise PermissionDenied("You cannot change this assessment.")
    if assessment.status not in OPEN:
        raise Conflict("This assessment is closed.")


def add_test(
    session: Session, principal: Principal, assessment: Assessment, control: Control
) -> ControlTest:
    _open(session, principal, assessment)
    scope = session.get(Scope, assessment.scope_id)
    assert scope is not None
    row = _testable(session, scope).get(control.id)
    if row is None:
        raise Invalid(
            "The test was not added.",
            {"control": "Only a control this scope does itself can be tested here."},
        )
    taken = session.scalars(
        select(ControlTest.id).where(
            ControlTest.assessment_id == assessment.id, ControlTest.control_id == control.id
        )
    ).first()
    if taken is not None:
        raise Conflict(f"{control.ref} is already in this assessment.")
    with audit.operation(session, "assessment.plan"):
        test = _plan(session, assessment, row)
        session.flush()
        records.touch(session, assessment)
    return test


def find_test(
    session: Session, principal: Principal, test_id: int
) -> tuple[ControlTest, Assessment]:
    test = session.get(ControlTest, test_id)
    assessment = session.get(Assessment, test.assessment_id) if test else None
    if test is None or assessment is None:
        raise NotFound("There is no such test.")
    if not access.can_see(session, principal, ASSESSMENT, assessment):
        raise NotFound("There is no such test.")
    return test, assessment


def update_test(
    session: Session, principal: Principal, test: ControlTest, changes: Mapping[str, Any]
) -> ControlTest:
    """Change how a control is to be tested, or who is to do it."""
    assessment = session.get(Assessment, test.assessment_id)
    assert assessment is not None
    _open(session, principal, assessment)
    errors = records.Errors()
    if "procedure" in changes:
        procedure = records.text(changes["procedure"])
        if not procedure:
            errors.add("procedure", "Say what is to be done to test it.")
        else:
            test.procedure = procedure
    if "method" in changes:
        if changes["method"] not in TEST_METHODS:
            errors.add("method", f"Use one of: {', '.join(TEST_METHODS)}.")
        else:
            test.method = changes["method"]
    if "assigned_to" in changes:
        given = changes["assigned_to"]
        person = session.get(Account, int(given)) if str(given).isdigit() else None
        if given in (None, ""):
            test.assigned_to = None
        elif person is None or person.status == "disabled":
            errors.add("assigned_to", "Choose a person whose account is not disabled.")
        else:
            test.assigned_to = person.id
    if errors:
        session.expire(test)
        raise Invalid("The test was not saved.", errors)
    with audit.operation(session, "assessment.plan"):
        session.flush()
    return test


def remove_test(session: Session, principal: Principal, test: ControlTest) -> None:
    assessment = session.get(Assessment, test.assessment_id)
    assert assessment is not None
    _open(session, principal, assessment)
    if session.scalars(select(TestResult.id).where(TestResult.test_id == test.id)).first():
        raise Conflict("This test has a result. Results are kept.")
    with audit.operation(session, "assessment.plan"):
        session.delete(test)
        records.touch(session, assessment)


# --- Results ------------------------------------------------------------------------------


def _latest(session: Session, test: ControlTest) -> TestResult | None:
    return session.scalars(
        select(TestResult)
        .where(TestResult.test_id == test.id, TestResult.superseded_by.is_(None))
        .order_by(TestResult.id.desc())
    ).first()


def state_of(result: TestResult | None) -> str:
    """Where a test stands: to do, awaiting review, returned to its tester, or counted."""
    if result is None:
        return "todo"
    return {None: "awaiting", "returned": "returned", "confirmed": "counted"}[result.review]


def record(
    session: Session,
    principal: Principal,
    test: ControlTest,
    *,
    design: str | None,
    operation: str | None,
    note: str | None,
    sample: str | None = None,
    evidence_refs: list[str] | None = None,
) -> TestResult:
    """Record what a test found. Nobody records a result for a control they own. A result is
    never edited: recording again supersedes the one before."""
    assessment = session.get(Assessment, test.assessment_id)
    assert assessment is not None
    if assessment.status not in OPEN:
        raise Conflict("This assessment is closed.")
    if not principal.assesses_unit(assessment.org_unit_id):
        raise PermissionDenied("Results are recorded by an assessor or a manager for the unit.")
    if _owns(session, principal, test.control_id):
        raise PermissionDenied("Nobody records the result of a test on a control they own.")
    errors = records.Errors()
    for field, value in (("design", design), ("operation", operation)):
        if value not in TEST_RESULTS:
            errors.add(field, "Choose effective, partly effective, or ineffective.")
    found = records.text(note)
    if not found:
        errors.add("note", "Say what was found.")
    cited: list[Evidence] = []
    for ref in dict.fromkeys(evidence_refs or []):
        try:
            item = find(session, evidence.EVIDENCE, ref)
        except NotFound:
            item = None
        if item is None or not evidence.can_see(session, principal, item):
            errors.add("evidence", f"There is no evidence item {ref}.")
        else:
            cited.append(item)
    if errors:
        raise Invalid("The result was not recorded.", errors)
    assert design is not None and operation is not None and found is not None
    before = _latest(session, test)
    with audit.operation(session, "test.record"):
        result = TestResult(
            test_id=test.id, assessment_id=assessment.id, sample=records.text(sample),
            design=design, operation=operation, note=found, tested_by=principal.account_id,
            tested_by_name=principal.name, tested_at=utc_now(),
        )  # fmt: skip
        session.add(result)
        session.flush()
        if before is not None:
            before.superseded_by = result.id
        for item in cited:
            session.add(
                EvidenceLink(evidence_id=item.id, subject_type="test_result", subject_id=result.id)
            )
        if assessment.status == "planned":
            assessment.status = "in_progress"
        records.touch(session, assessment)
        assessment.updated_at = utc_now()  # work in it is a change to it, for whoever lists them
    return result


def find_result(
    session: Session, principal: Principal, result_id: int
) -> tuple[TestResult, ControlTest, Assessment]:
    result = session.get(TestResult, result_id)
    if result is None:
        raise NotFound("There is no such result.")
    test, assessment = find_test(session, principal, result.test_id)
    return result, test, assessment


def review(
    session: Session, principal: Principal, result: TestResult, *, confirm: bool, note: str | None
) -> TestResult:
    """A second person confirms a result, and it counts; or returns it, saying why. Nobody
    reviews their own result, or one on a control they own."""
    test = session.get(ControlTest, result.test_id)
    assessment = session.get(Assessment, result.assessment_id)
    assert test is not None and assessment is not None
    if assessment.status not in OPEN:
        raise Conflict("This assessment is closed.")
    if not principal.assesses_unit(assessment.org_unit_id):
        raise PermissionDenied("Results are reviewed by an assessor or a manager for the unit.")
    if principal.account_id is not None and principal.account_id == result.tested_by:
        raise PermissionDenied("Nobody reviews their own result. Ask someone else.")
    if _owns(session, principal, test.control_id):
        raise PermissionDenied("Nobody reviews the result of a test on a control they own.")
    if result.superseded_by is not None or result.review is not None:
        raise Conflict("This result has already been reviewed or replaced.")
    said = records.text(note)
    if not confirm and not said:
        raise Invalid("The review was not recorded.", {"note": "Say what needs another look."})
    control = session.get(Control, test.control_id)
    assert control is not None
    with audit.operation(session, "test.review"):
        result.review = "confirmed" if confirm else "returned"
        result.review_note, result.reviewed_at = said, utc_now()
        result.reviewed_by, result.reviewed_by_name = principal.account_id, principal.name
        session.flush()
        if confirm:
            # The result becomes what is known about the control, everywhere it is used.
            controls.record_rating(
                session, control, design=result.design, operation=result.operation,
                note=f"Tested in {assessment.ref}: {result.note}", basis="test",
                by_id=result.tested_by, by_name=result.tested_by_name,
            )  # fmt: skip
        assessment.updated_at = utc_now()
    return result


def complete(session: Session, principal: Principal, assessment: Assessment) -> Assessment:
    """Close an assessment once every test in it has a result that counts."""
    _open(session, principal, assessment)
    tests = session.scalars(
        select(ControlTest).where(ControlTest.assessment_id == assessment.id)
    ).all()
    left = [test for test in tests if state_of(_latest(session, test)) != "counted"]
    if not tests:
        raise Conflict("There is nothing in this assessment to complete.")
    if left:
        raise Conflict(
            f"{len(left)} of its {len(tests)} tests have no result that counts yet. Record and "
            "review them, or take them out of the assessment."
        )
    with audit.operation(session, "assessment.complete"):
        assessment.status, assessment.completed_at = "complete", utc_now()
        records.touch(session, assessment)
    return assessment


def cancel(session: Session, principal: Principal, assessment: Assessment) -> Assessment:
    """Abandon an assessment. What it found already stays on the record and still counts."""
    _open(session, principal, assessment)
    with audit.operation(session, "assessment.cancel"):
        assessment.status = "cancelled"
        records.touch(session, assessment)
    return assessment


# --- Showing ------------------------------------------------------------------------------


def _result_view(session: Session, principal: Principal, result: TestResult) -> dict[str, Any]:
    cited = session.scalars(
        select(Evidence)
        .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
        .where(EvidenceLink.subject_type == "test_result", EvidenceLink.subject_id == result.id)
        .order_by(Evidence.id)
    ).all()
    return {
        "id": result.id,
        "sample": result.sample,
        "design": result.design,
        "operation": result.operation,
        "outcome": min((result.design, result.operation), key=TEST_RESULTS[::-1].index),
        "note": result.note,
        "tested_by": result.tested_by_name,
        "tested_at": result.tested_at,
        "review": result.review,
        "review_note": result.review_note,
        "reviewed_by": result.reviewed_by_name,
        "reviewed_at": result.reviewed_at,
        "evidence": [
            {"ref": item.ref, "name": item.name, "state": evidence.state_of(item)}
            for item in cited
            if evidence.can_see(session, principal, item)
        ],
    }


def view_of_test(session: Session, principal: Principal, test: ControlTest) -> dict[str, Any]:
    assessment = session.get(Assessment, test.assessment_id)
    control = session.get(Control, test.control_id)
    assert assessment is not None and control is not None
    latest = _latest(session, test)
    earlier = session.execute(
        select(func.count()).select_from(TestResult).where(TestResult.test_id == test.id)
    ).scalar_one()
    person = session.get(Account, test.assigned_to) if test.assigned_to else None
    is_open = assessment.status in OPEN
    assesses = principal.assesses_unit(assessment.org_unit_id)
    owns = _owns(session, principal, control.id)
    state = state_of(latest)
    return {
        "id": test.id,
        "control": {
            **records.chip(CONTROL, control),
            "statement": control.statement,
            "open": access.can_see(session, principal, CONTROL, control),
        },
        "procedure": test.procedure,
        "method": test.method,
        "assigned_to": {"id": person.id, "name": person.display_name} if person else None,
        "state": state,
        "result": _result_view(session, principal, latest) if latest else None,
        "results": int(earlier),
        "can": {
            "plan": is_open and can_run(session, principal, assessment),
            "record": is_open and assesses and not owns and state != "counted",
            "review": is_open
            and assesses
            and not owns
            and state == "awaiting"
            and latest is not None
            and latest.tested_by != principal.account_id,
            "owns": owns,
        },
    }


def tests_of(
    session: Session, principal: Principal, assessment: Assessment
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(ControlTest)
        .join(Control, Control.id == ControlTest.control_id)
        .where(ControlTest.assessment_id == assessment.id)
        .order_by(Control.ref)
    ).scalars()
    return [view_of_test(session, principal, row) for row in rows]


def waiting_on(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """Tests a person has been asked to do, and results in assessments they lead that wait
    for a second pair of eyes."""
    me = principal.account_id
    if me is None:
        return []
    found: list[dict[str, Any]] = []
    assigned = session.execute(
        select(ControlTest, Assessment, Control)
        .join(Assessment, Assessment.id == ControlTest.assessment_id)
        .join(Control, Control.id == ControlTest.control_id)
        .where(ControlTest.assigned_to == me, Assessment.status.in_(OPEN))
        .order_by(Assessment.period_end, ControlTest.id)
    ).all()
    for test, assessment, control in assigned:
        if state_of(_latest(session, test)) in ("todo", "returned"):
            found.append(
                {"kind": "test", "assessment": assessment, "control": control, "test": test}
            )
    led = session.execute(
        select(TestResult, Assessment, Control)
        .join(Assessment, Assessment.id == TestResult.assessment_id)
        .join(ControlTest, ControlTest.id == TestResult.test_id)
        .join(Control, Control.id == ControlTest.control_id)
        .where(
            Assessment.lead_id == me,
            Assessment.status.in_(OPEN),
            TestResult.review.is_(None),
            TestResult.superseded_by.is_(None),
            TestResult.tested_by != me,
        )
        .order_by(TestResult.tested_at)
    ).all()
    for _result, assessment, control in led:
        if not _owns(session, principal, control.id):  # which someone else must review
            found.append({"kind": "review", "assessment": assessment, "control": control})
    return found
