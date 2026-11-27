"""The leadership report (RPT-08): a report given once, and reopened exactly as it was.

A report covers a period, usually the one since the last report was issued. It gathers the
top risks and how they moved, appetite by family of risk, posture by framework, the third
parties with most at stake, the defined measures against the last report, and what is
overdue. Until it is issued it is worked out afresh each time it is looked at; issuing it
freezes what it says, with a fingerprint of that, and the history records the issue with the
same fingerprint. Whatever happens to the register afterwards, the report reopens unchanged,
and anyone may check that it is the report that was given.

Reports are the organization's: they are prepared and issued by managers for the whole
organization, and read by those who read everything, those who lead all of it, and whomever
else the program chooses (see ``readers``). A reader who may not see a record the report
names sees that it is there, but not its name.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.compliance.issues import ISSUE
from riskwren.core import scoring
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import Event, LeadershipReport, MeasureSnapshot, OrgUnit
from riskwren.db.refs import next_ref
from riskwren.events import audit
from riskwren.insight import measures, portfolio
from riskwren.inventory import access, records
from riskwren.inventory.registry import THIRD_PARTY, find_any
from riskwren.inventory.registry import find as find_record
from riskwren.reporting.service import count
from riskwren.risk import method as methods
from riskwren.risk.register import RISK
from riskwren.treatment import service as treatment

TOP = 10  # the top risks shown
LISTED = 10  # of each kind of overdue item, the most overdue shown
LONGEST = 366  # days a report may cover
DEFAULT_DAYS = 92  # a first report covers the last quarter


def may_read(principal: Principal) -> bool:
    return principal.reads_leadership


def may_issue(principal: Principal) -> bool:
    return principal.manages


def _require_read(principal: Principal) -> None:
    if not may_read(principal):
        raise PermissionDenied(
            "You are not among those who read the leadership reports. Who reads them is chosen "
            "under Admin, Program, Who sees what."
        )


def _require_issue(principal: Principal) -> None:
    if not may_issue(principal):
        raise PermissionDenied(
            "Only a manager for the whole organization prepares and issues leadership reports."
        )


# --- Fingerprints -------------------------------------------------------------------------


def _plain(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} cannot be written in a report")


def frozen(body: dict[str, Any]) -> dict[str, Any]:
    """The body as it is stored: plain JSON, so what is read back is what was hashed."""
    loaded: dict[str, Any] = json.loads(json.dumps(body, default=_plain))
    return loaded


def fingerprint(body: dict[str, Any]) -> str:
    """The SHA-256 of the body written canonically: keys sorted, no spaces, UTF-8."""
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- Periods ------------------------------------------------------------------------------


def latest(session: Session) -> LeadershipReport | None:
    return session.scalars(
        select(LeadershipReport)
        .order_by(LeadershipReport.issued_at.desc(), LeadershipReport.id.desc())
        .limit(1)
    ).first()


def period(
    session: Session, start: date | None = None, end: date | None = None
) -> tuple[date, date]:
    """The period a report covers: by default, from the day after the last report's period
    ended, or the last quarter if there has been none, to today."""
    today = utc_now().date()
    end = end or today
    if start is None:
        last = latest(session)
        if last is not None:
            start = min(last.period_end + timedelta(days=1), end)
        else:
            start = end - timedelta(days=DEFAULT_DAYS)
    problems = {}
    if end > today:
        problems["to"] = "A report cannot cover days that have not happened yet."
    if start > end:
        problems["from"] = "The period must start on or before the day it ends."
    elif (end - start).days > LONGEST:
        problems["from"] = "A report covers a year at most."
    if problems:
        raise Invalid("That period cannot be reported on.", problems)
    return start, end


def default_title(end: date) -> str:
    return f"Leadership report, {end.strftime('%B %Y')}"


# --- What a report says -------------------------------------------------------------------


def _units(session: Session) -> dict[int, str]:
    return {row.id: row.name for row in session.execute(select(OrgUnit.id, OrgUnit.name))}


def _before_figures(
    session: Session, previous: LeadershipReport | None, start: date
) -> tuple[dict[str, int], dict[str, Any] | None]:
    """The figures each measure is compared with: the last report's, or failing that, the
    organization's snapshot from the start of the period."""
    if previous is not None:
        figures = {row["key"]: row["value"] for row in previous.body.get("figures", [])}
        return figures, {"kind": "report", "ref": previous.ref, "on": previous.period_end}
    day = session.scalar(
        select(MeasureSnapshot.day)
        .where(MeasureSnapshot.day <= start)
        .order_by(MeasureSnapshot.day.desc())
        .limit(1)
    )
    if day is None:
        return {}, None
    rows = session.scalars(select(MeasureSnapshot).where(MeasureSnapshot.day == day))
    return {row.measure: row.value for row in rows}, {"kind": "snapshot", "on": day}


def _figures(
    session: Session, principal: Principal, before: dict[str, int]
) -> list[dict[str, Any]]:
    out = []
    for measure in measures.CATALOG:
        now = measures.value(session, principal, measure)
        then = before.get(measure.key)
        out.append(
            {
                "key": measure.key,
                "group": measure.group,
                "label": measure.label,
                "counts": measure.counts,
                "better": measure.better,
                "value": now,
                "before": then,
                "change": None if then is None else now - then,
            }
        )
    return out


def _top_risks(
    session: Session, principal: Principal, previous: LeadershipReport | None, start: date
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The open risks rated highest, each with how it moved since the last report, and the
    risks the last report listed that are no longer among them."""
    method = methods.current(session)
    labels = {rating["key"]: rating["label"] for rating in method["ratings"]}
    names = _units(session)
    rows, _ = records.search(
        session, principal, RISK, {"status": "open"}, sort="-residual_rating", limit=TOP
    )
    rows = [risk for risk in rows if risk.residual_rating]
    earlier = {row["ref"]: row for row in (previous.body.get("top_risks", []) if previous else [])}
    out = []
    for risk, card in zip(rows, records.cards(session, RISK, rows), strict=True):
        rating = risk.residual_rating
        was = earlier.get(risk.ref)
        if previous is None:
            movement = None
        elif was is None:
            movement = "added" if risk.created_at >= previous.issued_at else "entered"
        else:
            then = scoring.position(method, was.get("rating"))
            now = scoring.position(method, rating)
            movement = "up" if now > then else "down" if now < then else "same"
        out.append(
            {
                "ref": risk.ref,
                "name": risk.name,
                "unit": names.get(risk.org_unit_id),
                "category": card["category_label"],
                "appetite": card["appetite"],
                "rating": rating,
                "rating_label": labels.get(rating or "", rating),
                "place": scoring.position(method, rating),
                "places": len(method["ratings"]),
                "standing": risk.standing,
                "response": risk.response,
                "owners": [owner["name"] for owner in card["owners"]],
                "next_review_on": risk.next_review_on,
                "review_overdue": card["review_overdue"],
                "movement": movement,
                "was": was.get("rating_label") if was else None,
            }
        )
    listed = {row["ref"] for row in out}
    left = []
    for ref, was in earlier.items():
        if ref in listed:
            continue
        try:
            risk = find_record(session, RISK, ref)
        except NotFound:
            continue
        left.append(
            {
                "ref": ref,
                "name": risk.name,
                "was": was.get("rating_label"),
                "status": risk.status,
                "rating_label": labels.get(risk.residual_rating or "", risk.residual_rating),
            }
        )
    return out, left


def _overdue(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """What is past its date, of each kind: how many, and the most overdue."""
    today = utc_now().date()

    def listed(record_type: Any, filters: dict[str, Any], due: str) -> dict[str, Any]:
        rows, total = records.search(session, principal, record_type, filters, limit=200)
        rows = sorted(rows, key=lambda row: (getattr(row, due) or today, row.ref))[:LISTED]
        items = [
            {
                "ref": row.ref,
                "name": row.name,
                "due_on": getattr(row, due),
                "days": (today - getattr(row, due)).days if getattr(row, due) else None,
            }
            for row in rows
        ]
        return {"total": total, "items": items}

    actions, total = treatment.search_actions(
        session, principal, {"status": "open", "overdue": True}, limit=200
    )
    actions = sorted(actions, key=lambda item: item.get("due_on") or today)[:LISTED]
    return [
        {
            "key": "issues",
            "label": "Issues past their date",
            **listed(ISSUE, {"status": "live", "overdue": True}, "due_on"),
        },
        {
            "key": "risk_reviews",
            "label": "Risk reviews overdue",
            **listed(RISK, {"status": "open", "overdue": True}, "next_review_on"),
        },
        {
            "key": "third_party_reviews",
            "label": "Third-party reviews overdue",
            **listed(THIRD_PARTY, {"status": "active", "review": "due"}, "next_review_on"),
        },
        {
            "key": "actions",
            "label": "Actions past their date",
            "total": total,
            "items": [
                {
                    "ref": item.get("ref"),
                    "name": item["title"],
                    "due_on": item.get("due_on"),
                    "days": (today - item["due_on"]).days if item.get("due_on") else None,
                    "of": item["plan"] or (item.get("source") or {}).get("ref"),
                }
                for item in actions
            ],
        },
    ]


def _frozen_rows(data: dict[str, Any], keep: tuple[str, ...]) -> list[dict[str, Any]]:
    """A portfolio view's rows as a report keeps them: the figures' counts, not their lists,
    since the lists move on and the report does not."""
    out = []
    for row in data["rows"]:
        kept = {key: row.get(key) for key in keep}
        kept["figures"] = {key: figure["count"] for key, figure in row["figures"].items()}
        out.append(kept)
    return out


def build(
    session: Session, principal: Principal, start: date, end: date, *, summary: str | None = None
) -> dict[str, Any]:
    """What a report for the period says, as of now."""
    previous = latest(session)
    before, against = _before_figures(session, previous, start)
    window = portfolio.as_range(start, end)
    top, left = _top_risks(session, principal, previous, start)
    category = portfolio.by_category(session, principal, "quarter")
    framework = portfolio.by_framework(session, principal, "quarter")
    parties = portfolio.by_third_party(session, principal, "quarter")
    earlier_posture = {
        row["key"]: row.get("share")
        for row in (previous.body.get("posture", []) if previous else [])
    }
    posture = []
    for row in framework["rows"]:
        posture.append(
            {
                "key": row["key"],
                "label": row["label"],
                "scopes": [scope["name"] for scope in row["scopes"]],
                "applicable": row["applicable"],
                "ready": row["ready"],
                "share": row["share"],
                "before": earlier_posture.get(row["key"]),
                "issues": row["figures"]["issues"]["count"],
                "overdue": row["figures"]["overdue"]["count"],
                "exceptions": row["figures"]["exceptions"]["count"],
            }
        )
    in_period = {
        "risks_added": count(session, principal, RISK, {"added": window}),
        "issues_raised": count(session, principal, ISSUE, {"raised": window}),
        "issues_closed": count(session, principal, ISSUE, {"status": "closed", "closed": window}),
    }
    return frozen(
        {
            "from": start,
            "to": end,
            "summary": summary or None,
            "previous": (
                {"ref": previous.ref, "title": previous.title, "to": previous.period_end}
                if previous
                else None
            ),
            "against": against,
            "in_period": in_period,
            "figures": _figures(session, principal, before),
            "groups": measures.GROUPS,
            "top_risks": top,
            "left_top": left,
            "appetite": [
                {
                    "key": row["key"],
                    "label": row["label"],
                    "appetite": (row.get("note") or "").removeprefix("Appetite: ") or None,
                    "open": row["figures"]["risks"]["count"],
                    "above": row["figures"]["above"]["count"],
                    "decide": row["figures"]["decide"]["count"],
                    "overdue": row["figures"]["overdue"]["count"],
                }
                for row in category["rows"]
            ],
            "posture": posture,
            "third_parties": _frozen_rows(parties, ("ref", "label", "note", "next_review_on")),
            "overdue": _overdue(session, principal),
        }
    )


# --- Preparing, issuing, and reopening ----------------------------------------------------


def draft(
    session: Session, principal: Principal, start: date | None = None, end: date | None = None
) -> dict[str, Any]:
    """The next report as it stands now: not stored, and different each time it is looked
    at until it is issued."""
    _require_issue(principal)
    start, end = period(session, start, end)
    return {
        "title": default_title(end),
        "issued": False,
        "body": build(session, principal, start, end),
    }


def issue(
    session: Session,
    principal: Principal,
    *,
    title: str | None = None,
    summary: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> LeadershipReport:
    """Freeze the report for the period as it stands now, with its fingerprint."""
    _require_issue(principal)
    start, end = period(session, start, end)
    title = (title or "").strip() or default_title(end)
    if len(title) > 200:
        raise Invalid("The title is too long.", {"title": "At most 200 characters."})
    summary = (summary or "").strip() or None
    previous = latest(session)
    with audit.operation(session, "issue_leadership_report"):
        ref = next_ref(session, "LDR")
        now = utc_now().replace(microsecond=0)
        body = build(session, principal, start, end, summary=summary)
        body["report"] = frozen(
            {
                "ref": ref,
                "title": title,
                "issued_at": now,
                "issued_by": principal.name,
            }
        )
        report = LeadershipReport(
            ref=ref,
            title=title,
            period_start=start,
            period_end=end,
            summary=summary,
            body=body,
            fingerprint=fingerprint(body),
            previous_id=previous.id if previous else None,
            issued_by=principal.account_id,
            issued_by_name=principal.name,
            issued_at=now,
        )
        session.add(report)
        session.flush()
    return report


def find(session: Session, principal: Principal, ref: str) -> LeadershipReport:
    _require_read(principal)
    report = session.scalars(select(LeadershipReport).where(LeadershipReport.ref == ref)).first()
    if report is None:
        raise NotFound(f"There is no leadership report {ref}.")
    return report


def verify(session: Session, report: LeadershipReport) -> dict[str, Any]:
    """Whether the report is the one that was issued: its body still hashes to its
    fingerprint, and that fingerprint is the one the history recorded when it was issued."""
    computed = fingerprint(report.body)
    recorded = None
    event = session.scalars(
        select(Event).where(
            Event.subject_type == "leadership_report",
            Event.subject_id == report.id,
            Event.action == audit.CREATED,
        )
    ).first()
    if event is not None:
        recorded = (event.changes.get("fingerprint") or [None, None])[1]
    return {
        "fingerprint": report.fingerprint,
        "computed": computed,
        "recorded": recorded,
        "event": event.id if event is not None else None,
        "verified": computed == report.fingerprint == recorded,
    }


def listing(session: Session, principal: Principal) -> dict[str, Any]:
    _require_read(principal)
    rows = session.scalars(
        select(LeadershipReport).order_by(
            LeadershipReport.issued_at.desc(), LeadershipReport.id.desc()
        )
    ).all()
    return {
        "reports": [
            {
                "ref": row.ref,
                "title": row.title,
                "from": row.period_start,
                "to": row.period_end,
                "issued_at": row.issued_at,
                "issued_by": row.issued_by_name,
                "fingerprint": row.fingerprint,
            }
            for row in rows
        ],
        "can_issue": may_issue(principal),
        "next": (
            dict(zip(("from", "to"), period(session), strict=True))
            if may_issue(principal)
            else None
        ),
    }


def view(session: Session, principal: Principal, ref: str) -> dict[str, Any]:
    report = find(session, principal, ref)
    body, withheld = withhold(session, principal, report.body)
    return {
        "ref": report.ref,
        "title": report.title,
        "issued": True,
        "issued_at": report.issued_at,
        "issued_by": report.issued_by_name,
        "body": body,
        "withheld": withheld,
        "check": verify(session, report),
    }


def withhold(
    session: Session, principal: Principal, body: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    """The report as this reader may read it: a record they may not see keeps its place and
    its rating, but not its reference, name, unit, or owners, since they may not know that it
    exists. The report itself is unchanged, and its fingerprint is checked against what was
    issued, not against this copy."""
    if principal.reads_all or principal.everywhere(roles.LEADER):
        return body, 0
    body = copy.deepcopy(body)
    known: dict[str, bool] = {}

    def visible(ref: str) -> bool:
        if ref not in known:
            if ref.startswith("ACT-"):
                found, _ = treatment.search_actions(session, principal, {"q": ref}, limit=5)
                known[ref] = any(item.get("ref") == ref for item in found)
            else:
                try:
                    record_type, record = find_any(session, ref)
                except NotFound:
                    known[ref] = True  # gone since: the report is all there is of it
                else:
                    known[ref] = access.can_see(session, principal, record_type, record)
        return known[ref]

    count = 0
    rows = [*body.get("top_risks", []), *body.get("left_top", [])]
    rows += [item for group in body.get("overdue", []) for item in group.get("items", [])]
    for row in rows:
        ref = row.get("ref")
        if ref and not visible(ref):
            row.update(ref=None, name=None, unit=None, category=None, owners=[], of=None)
            row["withheld"] = True
            count += 1
    return body, count
