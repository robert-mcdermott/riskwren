"""Breach assessment (INC-05): whether an incident involving protected information must be
notified, by when, and each notification made.

An assessment records when the breach was discovered (the clock starts then), what
protected information was involved and about how many people, whether it was secured, any
exception that applies, the four factors that decide how likely it is that the information
was compromised, and the conclusion, with the rules that apply to it. It is never edited: a
new assessment supersedes the last, and the history keeps them all.

The rules built in are written for the United States: the HIPAA Breach Notification Rule
(as a covered entity, and as a business associate), the FTC Safeguards Rule, and DFARS
252.204-7012. A state's breach law and a contract's notice term are named and timed by the
organization, since they differ from one to the next. What each rule requires, and by when,
follows from the assessment; each notification made is recorded against it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, PermissionDenied
from riskwren.db.models import BreachAssessment, BreachNotification, Incident, RecordOwner
from riskwren.db.models.incidents import BREACH_CONCLUSIONS
from riskwren.events import audit
from riskwren.incidents import reports
from riskwren.inventory import records
from riskwren.program import vocab

# The four factors of a risk assessment of whether information was compromised, as the
# HIPAA Breach Notification Rule names them (45 CFR 164.402), in plain words.
FACTORS = {
    "nature": ("What was involved",
               "The kind and extent of the information: the identifiers in it, and how likely "
               "it is that the people it is about could be identified"),
    "recipient": ("Who used or received it",
                  "Whoever used the information, or was given it, without being allowed to"),
    "acquired": ("Whether it was taken or seen",
                 "Whether the information was actually acquired or viewed, or only exposed"),
    "mitigated": ("What has been done about it",
                  "How far the risk has been reduced: returned, destroyed, or promised not to be "
                  "used or shared, and how far that promise can be relied on"),
}  # fmt: skip
LEVELS = ("low", "moderate", "high")
# The three exceptions to what counts as a breach (45 CFR 164.402), in plain words.
EXCEPTIONS = {
    "workforce": "Unintentional, in good faith, by someone working for the organization or "
    "under its authority, within that authority, and not used or disclosed further",
    "authorized": "Inadvertent, from one person allowed to see the information to another "
    "allowed to see it at the same organization or its business associate, and not used or "
    "disclosed further",
    "could_not_retain": "To someone who, in good faith, could not reasonably have kept it",
}
CONCLUDED = {
    "notify": "it must be notified",
    "no_notification": "it need not be notified",
    "undecided": "not yet decided",
}
LONGEST_CUSTOM_DAYS = 365
LONGEST_CUSTOM_HOURS = 2000


@dataclass(frozen=True)
class Duty:
    key: str
    to: str
    rule: str
    days: int | None = None
    hours: int | None = None
    # Whether it applies to this assessment: a threshold of people, say.
    applies: Callable[[BreachAssessment], bool] = lambda assessment: True
    # The due date, where it is not a plain count of days or hours from discovery.
    due: Callable[[BreachAssessment], date] | None = None


@dataclass(frozen=True)
class Regime:
    key: str
    label: str
    cite: str | None
    suggested_for: tuple[str, ...]
    duties: tuple[Duty, ...]
    named: bool = False  # the organization names it and says how long it allows
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _day_found(assessment: BreachAssessment) -> date:
    return assessment.discovered_at.astimezone(UTC).date()


def _secretary_due(assessment: BreachAssessment) -> date:
    """500 or more: with the individuals' notice. Fewer: within 60 days of the end of the
    calendar year in which it was discovered (45 CFR 164.408(b), (c))."""
    found = _day_found(assessment)
    if (assessment.people or 0) >= 500:
        return found + timedelta(days=60)
    return date(found.year, 12, 31) + timedelta(days=60)


REGIMES: dict[str, Regime] = {
    regime.key: regime
    for regime in (
        Regime(
            "hipaa", "HIPAA Breach Notification Rule", "45 CFR 164.404 to 164.408", ("health",),
            (
                Duty("individuals", "Each individual affected", "45 CFR 164.404(b)", days=60),
                Duty("secretary", "The Secretary of Health and Human Services",
                     "45 CFR 164.408", due=_secretary_due),
                Duty("media", "Prominent media outlets serving each state or jurisdiction with "
                     "more than 500 residents affected", "45 CFR 164.406(b)", days=60,
                     applies=lambda a: (a.most_in_one_state or 0) > 500),
            ),
            note="For a covered entity. A breach affecting fewer than 500 people is reported "
            "to the Secretary within 60 days after the end of the year it was discovered.",
        ),
        Regime(
            "hipaa_business_associate", "HIPAA, as a business associate", "45 CFR 164.410",
            (),
            (Duty("covered_entity", "The covered entity", "45 CFR 164.410(b)", days=60),),
            note="When the organization holds the information for a covered entity.",
        ),
        Regime(
            "ftc_safeguards", "FTC Safeguards Rule", "16 CFR 314.4(j)", ("financial",),
            (Duty("ftc", "The Federal Trade Commission", "16 CFR 314.4(j)(1)", days=30,
                  applies=lambda a: (a.people or 0) >= 500),),
            note="Customer information that was not encrypted, of 500 or more consumers.",
        ),
        Regime(
            "dfars", "DFARS 252.204-7012", "DFARS 252.204-7012(c)", ("controlled",),
            (Duty("dod", "The Department of Defense, through DIBNet",
                  "DFARS 252.204-7012(c)(1)(ii)", hours=72),),
            note="Covered defense information, under a contract that includes the clause.",
        ),
        Regime(
            "state", "A state's breach law", None, ("personal",),
            (Duty("residents", "Each resident affected, and whoever else the law names",
                  "the state's law"),),
            named=True,
            note="Name the state and how long its law allows. Laws differ: check each one.",
        ),
        Regime(
            "contract", "A contract or agreement", None, ("participant",),
            (Duty("party", "The party the contract names", "the contract's terms"),),
            named=True,
            note="A sponsor's, a funder's, or a partner's notice term: name it and its time.",
        ),
    )
}  # fmt: skip


# --- Reading ------------------------------------------------------------------------------


def current(session: Session, incident: Incident) -> BreachAssessment | None:
    return session.scalars(
        select(BreachAssessment)
        .where(
            BreachAssessment.incident_id == incident.id, BreachAssessment.superseded_by.is_(None)
        )
        .order_by(BreachAssessment.id.desc())
    ).first()


def instance(item: Mapping[str, Any]) -> str:
    """What names one rule that applies: its key, or for one the organization names, the
    key and the name."""
    return f"{item['key']}:{item['name']}" if item.get("name") else str(item["key"])


def suggestion(assessment: BreachAssessment) -> dict[str, str]:
    """What the factors point to. A use or disclosure not allowed is presumed a breach
    unless an exception applies, the information was secured, or the factors show a low
    probability that it was compromised."""
    if assessment.secured:
        return {"key": "secured", "text": "It was secured (unusable, unreadable, or "
                "indecipherable to anyone not allowed to see it), so it is not a breach of "
                "unsecured information."}  # fmt: skip
    if assessment.exception:
        return {"key": "exception", "text": "An exception applies, so it is not a breach."}
    levels = [(assessment.factors or {}).get(name, {}).get("level") for name in FACTORS]
    if levels and all(level == "low" for level in levels):
        return {"key": "low", "text": "Every factor is low: the probability that the "
                "information was compromised may be shown to be low. Say why, if so."}  # fmt: skip
    return {"key": "presumed", "text": "It is presumed a breach, to be notified, unless the "
            "factors show a low probability that the information was compromised."}  # fmt: skip


def obligations(
    session: Session, incident: Incident, assessment: BreachAssessment | None
) -> list[dict[str, Any]]:
    """What the rules that apply require, by when, and whether it has been done."""
    if assessment is None or assessment.conclusion == "no_notification":
        return []
    made = session.scalars(
        select(BreachNotification).where(BreachNotification.incident_id == incident.id)
    ).all()
    found = assessment.discovered_at
    now = utc_now()
    out = []
    for chosen in assessment.regimes or []:
        regime = REGIMES.get(chosen["key"])
        if regime is None:
            continue
        name = instance(chosen)
        for duty in regime.duties:
            if not duty.applies(assessment):
                continue
            hours = duty.hours or (chosen.get("hours") if regime.named else None)
            days = duty.days or (chosen.get("days") if regime.named else None)
            if duty.due is not None:
                due_at = datetime.combine(duty.due(assessment), time(23, 59), tzinfo=UTC)
            elif hours:
                due_at = found + timedelta(hours=int(hours))
            elif days:
                due_at = datetime.combine(
                    _day_found(assessment) + timedelta(days=int(days)), time(23, 59), tzinfo=UTC
                )
            else:
                due_at = None
            done = [row for row in made if row.regime == name and row.duty == duty.key]
            out.append(
                {
                    "regime": name,
                    "regime_label": f"{regime.label}: {chosen['name']}"
                    if chosen.get("name")
                    else regime.label,
                    "duty": duty.key,
                    "to": duty.to,
                    "rule": duty.rule,
                    "within": f"{hours} hours" if hours else f"{days} days" if days else None,
                    "due_at": due_at,
                    "done": bool(done),
                    "done_on": min(row.sent_on for row in done) if done else None,
                    "overdue": not done and due_at is not None and due_at < now,
                    "if_breach": assessment.conclusion == "undecided",
                }
            )
    return sorted(out, key=lambda item: (item["done"], item["due_at"] or now))


def _assessment_view(row: BreachAssessment) -> dict[str, Any]:
    return {
        "id": row.id,
        "discovered_at": row.discovered_at,
        "information": row.information or [],
        "people": row.people,
        "most_in_one_state": row.most_in_one_state,
        "secured": row.secured,
        "exception": row.exception,
        "factors": row.factors or {},
        "conclusion": row.conclusion,
        "rationale": row.rationale,
        "regimes": row.regimes or [],
        "assessed_by": row.assessed_by_name,
        "assessed_at": row.assessed_at,
    }


def view(session: Session, principal: Principal, incident: Incident) -> dict[str, Any]:
    records.require_whole(session, principal, reports.INCIDENT, incident)
    assessment = current(session, incident)
    earlier = session.scalars(
        select(BreachAssessment)
        .where(
            BreachAssessment.incident_id == incident.id,
            BreachAssessment.superseded_by.is_not(None),
        )
        .order_by(BreachAssessment.id.desc())
    ).all()
    made = session.scalars(
        select(BreachNotification)
        .where(BreachNotification.incident_id == incident.id)
        .order_by(BreachNotification.sent_on, BreachNotification.id)
    ).all()
    labels = {instance(item): item for item in (assessment.regimes if assessment else [])}
    return {
        "assessment": _assessment_view(assessment) if assessment else None,
        "suggestion": suggestion(assessment) if assessment else None,
        "obligations": obligations(session, incident, assessment),
        "notifications": [
            {
                "id": row.id,
                "regime": row.regime,
                "regime_label": _label(labels.get(row.regime), row.regime),
                "duty": row.duty,
                "recipient": row.recipient,
                "count": row.count,
                "sent_on": row.sent_on,
                "method": row.method,
                "reference": row.reference,
                "note": row.note,
                "recorded_by": row.recorded_by_name,
            }
            for row in made
        ],
        "earlier": [
            {
                "assessed_at": row.assessed_at,
                "assessed_by": row.assessed_by_name,
                "conclusion": row.conclusion,
            }
            for row in earlier
        ],
        "can_assess": incident.status in reports.LIVE
        and reports.can_edit(session, principal, incident),
        "choices": choices(),
    }


def _label(item: Mapping[str, Any] | None, fallback: str) -> str:
    if item is None:
        key = fallback.split(":", 1)
        regime = REGIMES.get(key[0])
        return (
            f"{regime.label}: {key[1]}"
            if regime and len(key) == 2
            else (regime.label if regime else fallback)
        )
    regime = REGIMES[item["key"]]
    return f"{regime.label}: {item['name']}" if item.get("name") else regime.label


def choices() -> dict[str, Any]:
    return {
        "factors": [
            {"key": key, "label": label, "help": help_} for key, (label, help_) in FACTORS.items()
        ],
        "levels": list(LEVELS),
        "exceptions": [{"key": key, "label": text} for key, text in EXCEPTIONS.items()],
        "conclusions": list(BREACH_CONCLUSIONS),
        "regimes": [
            {
                "key": regime.key,
                "label": regime.label,
                "cite": regime.cite,
                "named": regime.named,
                "note": regime.note,
                "suggested_for": list(regime.suggested_for),
                "duties": [
                    {"key": duty.key, "to": duty.to, "rule": duty.rule,
                     "within": f"{duty.hours} hours" if duty.hours else
                     f"{duty.days} days" if duty.days else None}
                    for duty in regime.duties
                ],
            }
            for regime in REGIMES.values()
        ],
    }  # fmt: skip


# --- Assessing ----------------------------------------------------------------------------


def _require(session: Session, principal: Principal, incident: Incident) -> None:
    if not reports.can_edit(session, principal, incident):
        raise PermissionDenied("A breach is assessed by those who handle or triage the incident.")
    if incident.status not in reports.LIVE:
        raise Conflict("This is closed. Reopen it to assess it again.")


def _moment(value: Any, field: str, errors: records.Errors) -> datetime | None:
    if value in (None, ""):
        errors.add(field, "Say when it was discovered.")
        return None
    try:
        if isinstance(value, datetime):
            moment = value
        elif isinstance(value, date):
            moment = datetime.combine(value, time(9, 0))
        else:
            text = str(value).strip()
            moment = (
                datetime.combine(date.fromisoformat(text), time(9, 0))
                if len(text) == 10
                else datetime.fromisoformat(text.replace("Z", "+00:00"))
            )
    except ValueError:
        errors.add(field, "Give a date and time, as year-month-day and hours:minutes.")
        return None
    moment = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    if moment > utc_now() + timedelta(minutes=5):
        errors.add(field, "That has not happened yet.")
        return None
    return moment


def _count(value: Any, field: str, errors: records.Errors) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors.add(field, "Give a whole number.")
        return None
    if number < 0:
        errors.add(field, "It cannot be fewer than none.")
        return None
    return number


def _regimes(values: Any, errors: records.Errors) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values or []:
        if not isinstance(item, Mapping) or item.get("key") not in REGIMES:
            errors.add("regimes", "Choose rules from the list.")
            continue
        regime = REGIMES[item["key"]]
        chosen: dict[str, Any] = {"key": regime.key}
        if regime.named:
            name = records.text(item.get("name"))
            if not name or len(name) > 60:
                errors.add("regimes", f"Name the {regime.label.lower().removeprefix('a ')} "
                           "in at most 60 characters.")  # fmt: skip
                continue
            chosen["name"] = name
            days, hours = item.get("days"), item.get("hours")
            try:
                if hours not in (None, ""):
                    chosen["hours"] = int(hours)
                    if not 1 <= chosen["hours"] <= LONGEST_CUSTOM_HOURS:
                        raise ValueError
                elif days not in (None, ""):
                    chosen["days"] = int(days)
                    if not 1 <= chosen["days"] <= LONGEST_CUSTOM_DAYS:
                        raise ValueError
                else:
                    raise ValueError
            except (TypeError, ValueError):
                errors.add("regimes", f"Say how many days or hours {name} allows.")
                continue
        key = instance(chosen)
        if key in seen:
            continue
        seen.add(key)
        out.append(chosen)
    return out


def assess(
    session: Session, principal: Principal, incident: Incident, values: Mapping[str, Any]
) -> BreachAssessment:
    _require(session, principal, incident)
    errors = records.Errors()
    discovered = _moment(values.get("discovered_at"), "discovered_at", errors)
    information = list(dict.fromkeys(values.get("information") or []))
    allowed = vocab.keys(session, "protected_information")
    if any(item not in allowed for item in information):
        errors.add("information", "Choose from the kinds of protected information.")
    people = _count(values.get("people"), "people", errors)
    most = _count(values.get("most_in_one_state"), "most_in_one_state", errors)
    if people is not None and most is not None and most > people:
        errors.add("most_in_one_state", "It cannot be more than the number affected.")
    exception = records.text(values.get("exception"))
    if exception is not None and exception not in EXCEPTIONS:
        errors.add("exception", "Choose an exception from the list, or none.")
    factors: dict[str, Any] = {}
    for name, given in (values.get("factors") or {}).items():
        if name not in FACTORS or not isinstance(given, Mapping):
            errors.add("factors", "Weigh the four factors, and only them.")
            continue
        level = given.get("level")
        if level in (None, ""):
            continue
        if level not in LEVELS:
            errors.add("factors", "Say low, moderate, or high.")
            continue
        factors[name] = {"level": level, "note": records.text(given.get("note"))}
    conclusion = values.get("conclusion") or "undecided"
    if conclusion not in BREACH_CONCLUSIONS:
        errors.add("conclusion", "Conclude notify, no notification, or not yet decided.")
    rationale = records.text(values.get("rationale"))
    if conclusion != "undecided" and not rationale:
        errors.add("rationale", "Say why: the conclusion is what a regulator will ask about.")
    regimes = _regimes(values.get("regimes"), errors)
    if conclusion == "notify" and not regimes:
        errors.add("regimes", "Say which rules require it to be notified.")
    if errors or discovered is None:
        raise Invalid("The assessment was not saved.", errors)
    before = current(session, incident)
    now = utc_now()
    row = BreachAssessment(
        incident_id=incident.id, discovered_at=discovered, information=information,
        people=people, most_in_one_state=most, secured=bool(values.get("secured")),
        exception=exception, factors=factors, conclusion=conclusion, rationale=rationale,
        regimes=regimes, assessed_by=principal.account_id, assessed_by_name=principal.name,
        assessed_at=now,
    )  # fmt: skip
    with audit.operation(session, "incident.breach_assessment", conclusion=conclusion):
        session.add(row)
        session.flush()
        if before is not None:
            before.superseded_by = row.id
        records.touch(session, incident)
        incident.updated_at = now
        session.flush()
    return row


def notify(
    session: Session, principal: Principal, incident: Incident, values: Mapping[str, Any]
) -> BreachNotification:
    """Record a notification made, under one of the rules the current assessment names."""
    _require(session, principal, incident)
    assessment = current(session, incident)
    if assessment is None:
        raise Conflict("Assess whether it must be notified first.")
    errors = records.Errors()
    chosen = {instance(item): item for item in assessment.regimes or []}
    regime = str(values.get("regime") or "")
    duty = str(values.get("duty") or "")
    if regime not in chosen:
        errors.add("regime", "Choose one of the rules the assessment names.")
    elif duty not in {each.key for each in REGIMES[chosen[regime]["key"]].duties}:
        errors.add("duty", "Choose whom that rule says to notify.")
    recipient = records.text(values.get("recipient"))
    if not recipient or len(recipient) > 200:
        errors.add("recipient", "Say who was notified, in at most 200 characters.")
    sent_on = None
    raw = values.get("sent_on")
    try:
        sent_on = raw if isinstance(raw, date) else date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        errors.add("sent_on", "Give the day it was sent, as year-month-day.")
    if sent_on is not None and sent_on > utc_now().date():
        errors.add("sent_on", "That day has not come yet.")
    count = _count(values.get("count"), "count", errors)
    texts = {}
    for name in ("method", "reference"):
        text = records.text(values.get(name))
        if text is not None and len(text) > 200:
            errors.add(name, "Keep it to 200 characters.")
        texts[name] = text
    if errors or sent_on is None:
        raise Invalid("The notification was not recorded.", errors)
    row = BreachNotification(
        incident_id=incident.id, regime=regime, duty=duty, recipient=recipient, count=count,
        sent_on=sent_on, method=texts["method"], reference=texts["reference"],
        note=records.text(values.get("note")), recorded_by=principal.account_id,
        recorded_by_name=principal.name, recorded_at=utc_now(),
    )  # fmt: skip
    with audit.operation(session, "incident.notification"):
        session.add(row)
        records.touch(session, incident)
        incident.updated_at = utc_now()
        session.flush()
    return row


# --- What waits on someone ----------------------------------------------------------------


def waiting_on(session: Session, principal: Principal) -> list[tuple[Incident, dict[str, Any]]]:
    """Notifications still to make, for each incident the person handles."""
    if principal.account_id is None:
        return []
    handled = select(RecordOwner.record_id).where(
        RecordOwner.record_type == reports.KEY,
        RecordOwner.account_id == principal.account_id,
        RecordOwner.kind == records.OWNER,
    )
    out = []
    for incident in session.scalars(
        select(Incident).where(Incident.id.in_(handled), Incident.status.in_(reports.LIVE))
    ):
        for duty in obligations(session, incident, current(session, incident)):
            if not duty["done"] and duty["due_at"] is not None:
                out.append((incident, duty))
    return out


def install_history() -> None:
    """Titles for the history of an incident's assessments and notifications."""
    previous = reports.INCIDENT.extra.get("history_title")

    def title(event: Any, lookups: Any) -> str | None:
        changes = event.changes or {}

        def now(name: str) -> Any:
            pair = changes.get(name) or [None, None]
            return pair[1] if pair[1] is not None else pair[0]

        if event.subject_type == "breach_assessment" and event.action == "created":
            said = CONCLUDED.get(now("conclusion"), "")
            return f"Assessed whether it must be notified: {said}"
        if event.subject_type == "breach_assessment":
            return "An earlier assessment was superseded"
        if event.subject_type == "breach_notification" and event.action == "created":
            return f"Recorded a notification to {now('recipient')}"
        return previous(event, lookups) if previous is not None else None

    reports.INCIDENT.extra["history_title"] = title


install_history()
