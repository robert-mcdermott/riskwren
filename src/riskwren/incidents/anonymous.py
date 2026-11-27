"""Reporting without a name (INC-02).

Off until an administrator opens it. When it is open, anyone may report a concern, an
incident, or a near miss through a page that needs no sign-in, and keeps no account, no name,
and no address. The reporter is shown a follow-up code once; only its digest is kept. With
the code they see where their report stands, read what those handling it say to them, and
add to it.

Unlike the other links, failed codes are not counted against the address that sent them, so
nothing ties a report to where it came from. The code is long enough (100 bits) that
guessing one is hopeless. So that the page cannot be used to flood the organization, only so
many reports are taken in an hour, from everyone together.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, NotFound, PermissionDenied
from riskwren.db.models import Incident, IncidentMessage
from riskwren.events import audit
from riskwren.incidents import reports
from riskwren.program import settings

SETTING = "incidents.anonymous"
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # no I, L, O, or U to misread
GROUPS, GROUP = 4, 5
MOST_AN_HOUR = 30
NOBODY = Principal(None, "Reported without a name")


def is_open(session: Session) -> bool:
    return bool((settings.get(session, SETTING, None) or {}).get("open"))


def view_setting(session: Session) -> dict[str, Any]:
    return {"open": is_open(session), "most_an_hour": MOST_AN_HOUR}


def set_open(session: Session, principal: Principal, opened: bool) -> dict[str, Any]:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator opens or closes reporting without a name.")
    with audit.operation(session, "incidents.anonymous", open=bool(opened)):
        settings.put(session, SETTING, {"open": bool(opened)})
    return view_setting(session)


def new_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(GROUPS * GROUP))
    return "-".join(raw[i : i + GROUP] for i in range(0, len(raw), GROUP))


def normal(code: str) -> str:
    """A code as typed, made comparable: letters in capitals, read the way they were meant,
    and nothing but letters and digits."""
    cleaned = re.sub(r"[^0-9A-Z]", "", str(code).upper())
    return cleaned.translate(str.maketrans({"O": "0", "I": "1", "L": "1"}))


def digest(code: str) -> str:
    return hashlib.sha256(normal(code).encode("utf-8")).hexdigest()


def report(session: Session, values: Mapping[str, Any]) -> tuple[Incident, str]:
    """Take a report from someone without a name. Returns it and the code, which is shown
    to them once and never again."""
    if not is_open(session):
        raise NotFound("Reporting without a name is not open here.")
    since = utc_now() - timedelta(hours=1)
    taken = session.execute(
        select(func.count())
        .select_from(Incident)
        .where(Incident.anonymous.is_(True), Incident.created_at >= since)
    ).scalar_one()
    if taken >= MOST_AN_HOUR:
        raise Conflict(
            "Too many reports have come in this hour. Please try again in an hour, or report "
            "it to someone you trust."
        )
    wanted = {
        key: values.get(key) for key in ("kind", "name", "summary", "occurred_on", "location")
    }
    wanted["kind"] = wanted.get("kind") or "concern"
    code = new_code()
    incident = reports.create(session, NOBODY, wanted, anonymous=True, follow_up_hash=digest(code))
    return incident, code


def find(session: Session, code: str) -> Incident:
    incident = None
    if len(normal(code)) == GROUPS * GROUP:
        incident = session.scalars(
            select(Incident).where(
                Incident.anonymous.is_(True), Incident.follow_up_hash == digest(code)
            )
        ).first()
    if incident is None:
        raise NotFound("No report has that code. Check it, letter by letter.")
    return incident


def follow_up(session: Session, code: str) -> dict[str, Any]:
    """What the reporter may see: what they reported, where it stands, and what is said to
    them. Not who handles it, and nothing of the handling itself."""
    incident = find(session, code)
    said = session.scalars(
        select(IncidentMessage)
        .where(IncidentMessage.incident_id == incident.id, IncidentMessage.shared.is_(True))
        .order_by(IncidentMessage.created_at)
    )
    return {
        "ref": incident.ref,
        "kind": incident.kind,
        "name": incident.name,
        "summary": incident.summary,
        "occurred_on": incident.occurred_on,
        "location": incident.location,
        "reported_at": incident.created_at,
        "status": incident.status,
        "closed_at": incident.closed_at,
        "messages": [
            {
                "from_reporter": row.from_reporter,
                "by": "You" if row.from_reporter else "Those handling it",
                "at": row.created_at,
                "body": row.body,
            }
            for row in said
        ],
        "can_write": incident.status in reports.LIVE,
    }


def add(session: Session, code: str, body: Any) -> dict[str, Any]:
    incident = find(session, code)
    reports.written_by_reporter(session, incident, body)
    return follow_up(session, code)
