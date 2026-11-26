"""The scoring method in force, and publishing a new one.

A published version is never changed. A new version is published beside it, and every
assessment keeps the version it was made under.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core import scoring
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, NotFound, PermissionDenied
from riskwren.db.models import ScoringMethod
from riskwren.events import audit


def current_row(session: Session) -> ScoringMethod:
    row = session.scalars(select(ScoringMethod).where(ScoringMethod.status == "current")).first()
    if row is None:
        raise NotFound("No scoring method has been published. Run `riskwren db upgrade`.")
    return row


def current(session: Session) -> dict[str, Any]:
    """The method in force, as the document the scoring functions take."""
    return current_row(session).definition


def by_id(session: Session, method_id: int) -> ScoringMethod:
    row = session.get(ScoringMethod, method_id)
    if row is None:
        raise NotFound("There is no such version of the scoring method.")
    return row


def publish(
    session: Session, principal: Principal | None, definition: dict[str, Any]
) -> ScoringMethod:
    """Publish a new version. The whole document is checked first, and every problem with it
    reported together."""
    if principal is not None and not principal.configures:
        raise PermissionDenied("Only those who run the program can publish a scoring method.")
    found = scoring.problems(definition)
    if found:
        raise Invalid("The scoring method cannot be used.", {"definition": " ".join(found)})
    latest = session.execute(select(func.max(ScoringMethod.version))).scalar_one() or 0
    with audit.operation(session, "scoring_method.publish"):
        for row in session.scalars(select(ScoringMethod).where(ScoringMethod.status == "current")):
            row.status = "superseded"
        new = ScoringMethod(
            version=latest + 1,
            status="current",
            definition=definition,
            published_by=principal.account_id if principal else None,
            published_at=utc_now(),
        )
        session.add(new)
        session.flush()
    return new


def view(row: ScoringMethod) -> dict[str, Any]:
    return {"version": row.version, "published_at": row.published_at, **row.definition}
