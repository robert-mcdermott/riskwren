"""Outside auditors (AUD-08): read-only access for a person outside the organization to one
reported engagement or one scope, until a date, through a link, with every view recorded.

An external auditor, a regulator, or a sponsor's monitor is not given an account. An auditor
gives them a link to exactly one thing: a reported engagement (its report, workpapers,
findings, and requests), or a scope (what it is, each framework's statement, how each control
is done there, its evidence, and its plan of action). The link is a token of 256 random bits,
of which only the digest is kept; it is shown once, it follows a ``#`` so it is in nobody's
logs, and it comes back in a header of its own. It ends on its date, or when an auditor
withdraws it. Every time it is used, the history records who looked at what.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.compliance import issues, scopes
from riskwren.compliance.evidence import EVIDENCE
from riskwren.compliance.scopes import SCOPE
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, RiskWrenError
from riskwren.db.models import Engagement, Evidence, EvidenceLink, Implementation, OutsideAccess
from riskwren.events import audit
from riskwren.events.actor import Actor
from riskwren.internal_audit import engagements, universe
from riskwren.inventory import records

HEADER = "X-RiskWren-Access"
OUTSIDE = "outside"  # the kind of actor a link's holder is, in the history
MOST_DAYS = 90


class AccessRefused(RiskWrenError):
    def __init__(self, reason: str | None) -> None:
        self.reason = reason
        super().__init__(
            {
                None: "This link does not lead anywhere. Check that the whole address was "
                "copied, or ask whoever sent it for a new one.",
                "expired": "This link has expired. Ask whoever sent it for a new one.",
                "withdrawn": "This link was withdrawn. Ask whoever sent it for a new one.",
            }[reason]
        )


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _subject(session: Session, kind: str, ref: str) -> Any:
    if kind == "engagement":
        found = session.scalars(
            select(Engagement).where(Engagement.ref == ref.strip().upper())
        ).first()
        if found is None:
            raise NotFound(f"There is no engagement {ref}.")
        if found.status != "reported":
            raise Conflict("An engagement is opened to outside auditors once it is reported.")
        return found
    if kind == "scope":
        found = session.scalars(
            select(SCOPE.model).where(SCOPE.model.ref == ref.strip().upper())
        ).first()
        if found is None or found.status != "active":
            raise NotFound(f"There is no scope in use {ref}.")
        return found
    raise Invalid("Nothing was opened.", {"kind": "An engagement or a scope."})


def grant(
    session: Session, principal: Principal, values: Mapping[str, Any]
) -> tuple[OutsideAccess, str]:
    """Open one engagement or scope to a named person outside the organization, until a date.
    Returns the access and its token, which is shown this once."""
    universe.require_work(principal)
    errors = records.Errors()
    name = records.text(values.get("name"))
    organization = records.text(values.get("organization"))
    if not name:
        errors.add("name", "Name the person it is for.")
    if not organization:
        errors.add("organization", "Say whom they are with.")
    try:
        days = int(values.get("days") or 0)
    except (TypeError, ValueError):
        days = 0
    if not 1 <= days <= MOST_DAYS:
        errors.add("days", f"From 1 to {MOST_DAYS} days.")
    if errors:
        raise Invalid("Nothing was opened.", errors)
    kind = str(values.get("kind") or "")
    subject = _subject(session, kind, str(values.get("ref") or ""))
    token = secrets.token_urlsafe(32)
    now = utc_now()
    with audit.operation(session, "outside.grant"):
        access = OutsideAccess(
            token_hash=digest(token),
            name=str(name),
            organization=str(organization),
            email=records.text(values.get("email")),
            purpose=records.text(values.get("purpose")),
            subject_type=kind,
            subject_id=subject.id,
            granted_by=principal.account_id,
            granted_by_name=principal.name,
            granted_at=now,
            expires_at=now + timedelta(days=days),
            views=0,
        )
        session.add(access)
        session.flush()
    return access, token


def revoke(session: Session, principal: Principal, access_id: int) -> OutsideAccess:
    universe.require_work(principal)
    access = session.get(OutsideAccess, access_id)
    if access is None:
        raise NotFound(f"There is no outside access {access_id}.")
    if access.revoked_at is not None:
        raise Conflict("It was withdrawn already.")
    with audit.operation(session, "outside.revoke"):
        access.revoked_at = utc_now()
    return access


def find(session: Session, token: str | None) -> OutsideAccess:
    if not token or len(token) > 200:
        raise AccessRefused(None)
    access = session.scalars(
        select(OutsideAccess).where(OutsideAccess.token_hash == digest(token.strip()))
    ).first()
    if access is None:
        raise AccessRefused(None)
    if access.revoked_at is not None:
        raise AccessRefused("withdrawn")
    if access.expires_at <= utc_now():
        raise AccessRefused("expired")
    return access


def actor_for(access: OutsideAccess) -> Actor:
    return Actor(OUTSIDE, None, f"{access.name} ({access.organization}), outside, by link")


def _scope_package(session: Session, scope: Any) -> dict[str, Any]:
    everyone = Principal.for_command("Outside access")
    frameworks = []
    for held in scopes.held_to(session, scope):
        found = scopes.statement(session, everyone, scope, held["key"])
        frameworks.append(
            {
                "title": found["framework"]["title"],
                "counts": found["counts"],
                "applicable": found["applicable"],
                "requirements": [
                    {
                        "code": r["code"],
                        "title": r["title"],
                        "state": r["state"],
                        "reason": r["reason"],
                        "controls": [f"{c['ref']} {c['name']}" for c in r["controls"]],
                    }
                    for r in found["requirements"]
                ],
            }
        )
    used = scopes.implementations(session, everyone, scope)["controls"]
    controls = [
        row.control_id
        for row in session.scalars(
            select(Implementation).where(Implementation.scope_id == scope.id)
        )
    ]
    rows = session.scalars(
        select(Evidence)
        .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
        .where(
            ((EvidenceLink.subject_type == "scope") & (EvidenceLink.subject_id == scope.id))
            | (
                (EvidenceLink.subject_type == "control")
                & EvidenceLink.subject_id.in_(controls or [0])
            ),
            Evidence.status == "active",
        )
        .distinct()
        .order_by(Evidence.ref)
    ).all()
    cards = records.cards(session, EVIDENCE, list(rows))
    plan = issues.plan_of_action(session, everyone, scope)
    return {
        "scope": {
            "ref": scope.ref,
            "name": scope.name,
            "summary": scope.summary,
            "boundary": scope.boundary,
        },
        "frameworks": frameworks,
        "controls": [
            {
                "ref": v["control"]["ref"],
                "name": v["control"]["name"],
                "status": v["status"],
                "standing": v["standing"],
                "responsibility": v["responsibility"],
                "statement": v["statement"]
                or (v["provider"] or {}).get("statement")
                or v["control"]["statement"],
            }
            for v in used
        ],
        "evidence": [
            {
                "ref": c["ref"],
                "name": c["name"],
                "kind": c.get("kind"),
                "collected_on": c.get("collected_on"),
                "valid_until": c.get("valid_until"),
                "state": c.get("state"),
                "file": c.get("file"),
            }
            for c in cards
        ],
        "plan_of_action": [
            {
                "ref": c["ref"],
                "name": c["name"],
                "severity": c["severity"],
                "due_on": c["due_on"],
                "status": c["status"],
                "overdue": c["overdue"],
            }
            for c in plan["issues"]
        ],
    }


def package(session: Session, access: OutsideAccess) -> dict[str, Any]:
    """What the link opens, read-only."""
    about = {
        "name": access.name,
        "organization": access.organization,
        "expires_at": access.expires_at,
        "granted_by": access.granted_by_name,
        "kind": access.subject_type,
    }
    if access.subject_type == "engagement":
        engagement = session.get(Engagement, access.subject_id)
        if engagement is None:
            raise AccessRefused(None)
        shown = engagements.view(session, Principal.for_command("Outside access"), engagement)
        for key in ("can", "role", "next", "waiting"):
            shown.pop(key, None)
        return {"about": about, "engagement": shown}
    scope = session.get(SCOPE.model, access.subject_id)
    if scope is None:
        raise AccessRefused(None)
    return {"about": about, **_scope_package(session, scope)}


def record_view(session: Session, access: OutsideAccess) -> None:
    """Each use of the link is an event in the history, on the thing it opened."""
    model: Any = Engagement if access.subject_type == "engagement" else SCOPE.model
    subject = session.get(model, access.subject_id)
    audit.record(
        session,
        "outside.viewed",
        subject,
        changes={"viewed_by": [None, f"{access.name} ({access.organization})"]},
    )
    access.views += 1
    access.last_viewed_at = utc_now()


def listing(session: Session, principal: Principal) -> dict[str, Any]:
    universe.require_read(principal)
    rows = session.scalars(select(OutsideAccess).order_by(OutsideAccess.granted_at.desc())).all()
    out = []
    now = utc_now()
    for row in rows:
        model: Any = Engagement if row.subject_type == "engagement" else SCOPE.model
        subject = session.get(model, row.subject_id)
        state = "withdrawn" if row.revoked_at else "expired" if row.expires_at <= now else "open"
        out.append(
            {
                "id": row.id,
                "name": row.name,
                "organization": row.organization,
                "email": row.email,
                "purpose": row.purpose,
                "kind": row.subject_type,
                "subject": {"ref": subject.ref, "name": subject.name} if subject else None,
                "granted_by": row.granted_by_name,
                "granted_at": row.granted_at,
                "expires_at": row.expires_at,
                "revoked_at": row.revoked_at,
                "state": state,
                "views": row.views,
                "last_viewed_at": row.last_viewed_at,
            }
        )
    reported = session.scalars(
        select(Engagement).where(Engagement.status == "reported").order_by(Engagement.ref)
    ).all()
    in_use = session.scalars(
        select(SCOPE.model).where(SCOPE.model.status == "active").order_by(SCOPE.model.ref)
    ).all()
    return {
        "grants": out,
        "can_grant": universe.may_work(principal),
        "choices": {
            "engagement": [{"ref": e.ref, "name": e.name} for e in reported],
            "scope": [{"ref": s.ref, "name": s.name} for s in in_use],
        },
        "most_days": MOST_DAYS,
    }
