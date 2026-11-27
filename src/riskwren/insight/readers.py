"""Who reads the leadership reports.

Those who read everything (managers for the whole organization, administrators, and
auditors) and those who lead the whole organization always do. How much further the reports
reach is the program's to choose: in a large organization they may be for its executives
alone; in a smaller one the security leader may be the most senior person who uses the
system, and in a smaller one still, the people who run the program day to day. Named people
may read them whatever the reach.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.models import Account
from riskwren.events import audit
from riskwren.program import settings

SETTING = "leadership_reports.readers"
REACHES = {
    "executives": "Nobody else",
    "organization": (
        "Anyone whose role covers the whole organization, such as a security leader who "
        "assesses everywhere"
    ),
    "leaders": "Every leader and every manager, of any unit",
}
DEFAULT_REACH = "organization"
MOST_PEOPLE = 50


def current(session: Session) -> dict[str, Any]:
    """The setting in force: how far the reports reach, and who is named."""
    stored = settings.get(session, SETTING, None) or {}
    reach = stored.get("reach")
    people = stored.get("people") or []
    return {
        "reach": reach if reach in REACHES else DEFAULT_REACH,
        "people": [person for person in people if isinstance(person, int)],
    }


def reaches(principal: Principal, setting: dict[str, Any]) -> bool:
    """Whether the setting makes this person a reader, beyond those who always are."""
    if principal.account_id is not None and principal.account_id in setting["people"]:
        return True
    reach = setting["reach"]
    if reach == "executives":
        return False
    if any(principal.everywhere(role) for role in roles.SCOPED):
        return True
    return reach == "leaders" and (principal.leads or principal.manages_somewhere)


def view(session: Session) -> dict[str, Any]:
    setting = current(session)
    named = _accounts(session, setting["people"])
    return {
        "reach": setting["reach"],
        "choices": REACHES,
        "people": [
            {"account_id": account.id, "name": account.display_name, "email": account.email}
            for account in named
        ],
    }


def save(
    session: Session, principal: Principal, reach: str, people: Iterable[int]
) -> dict[str, Any]:
    if not principal.configures:
        raise PermissionDenied("Only those who run the program choose who reads the reports.")
    errors: dict[str, str] = {}
    if reach not in REACHES:
        errors["reach"] = f"Use one of: {', '.join(REACHES)}."
    chosen = list(dict.fromkeys(people))
    if len(chosen) > MOST_PEOPLE:
        errors["people"] = f"Name at most {MOST_PEOPLE} people."
    named = _accounts(session, chosen)
    if len(named) != len(chosen):
        errors["people"] = "Name only people who have an account here."
    elif any(account.status == "disabled" for account in named):
        errors["people"] = "An account that is turned off cannot be named."
    if errors:
        raise Invalid("Who reads the reports was not changed.", errors)
    with audit.operation(session, "leadership_readers.edit"):
        settings.put(session, SETTING, {"reach": reach, "people": sorted(chosen)})
    return view(session)


def _accounts(session: Session, ids: Iterable[int]) -> list[Account]:
    ids = list(ids)
    if not ids:
        return []
    return list(
        session.scalars(select(Account).where(Account.id.in_(ids)).order_by(Account.display_name))
    )
