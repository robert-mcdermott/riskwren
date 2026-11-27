"""The library, and acknowledgment (POL-05, POL-06).

A document applies to everyone, or to the people who work in chosen units (and the units
beneath them) and those who hold chosen roles. The library is the published documents that
apply to the reader. A document can ask the people it applies to to say they have read it:
each says so for the version in force. A new version says whether they must say so again;
if it does not, what they said of the earlier version still counts.

Who has and has not is always worked out from the people the document applies to now, so a
person who joins a unit is asked, and one who leaves it is not counted.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import (
    Account,
    Campaign,
    CampaignItem,
    Membership,
    OrgUnit,
    PolicyAcknowledgment,
    PolicyAudience,
    PolicyDocument,
    PolicyVersion,
    RoleGrant,
)
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.people import notices, units
from riskwren.policy import documents
from riskwren.policy.documents import DOCUMENT, RANK

ROLES = roles.GRANTABLE  # "member" is everyone, so it is not a role to choose


# --- Who a document applies to ----------------------------------------------------------------


def audience_of(session: Session, document: PolicyDocument) -> dict[str, Any]:
    rows = session.scalars(
        select(PolicyAudience)
        .where(PolicyAudience.document_id == document.id)
        .order_by(PolicyAudience.id)
    ).all()
    names = dict(
        session.execute(
            select(OrgUnit.id, OrgUnit.name).where(
                OrgUnit.id.in_([row.org_unit_id for row in rows if row.org_unit_id] or [0])
            )
        ).all()
    )
    return {
        "everyone": document.for_everyone,
        "units": [
            {"id": row.org_unit_id, "name": names.get(row.org_unit_id, "")}
            for row in rows
            if row.org_unit_id
        ],
        "roles": [row.role for row in rows if row.role],
    }


def set_audience(
    session: Session, principal: Principal, document: PolicyDocument, everyone: bool,
    unit_ids: Iterable[int], chosen_roles: Iterable[str],
) -> None:  # fmt: skip
    """Say who a document applies to: everyone, or the units and roles named."""
    if not documents.can_edit(session, principal, document):
        raise PermissionDenied(
            "Who a document applies to is said by its owners, or by those over its unit."
        )
    wanted_units = list(dict.fromkeys(int(each) for each in unit_ids))
    wanted_roles = list(dict.fromkeys(str(each) for each in chosen_roles))
    errors: dict[str, str] = {}
    if any(session.get(OrgUnit, each) is None for each in wanted_units):
        errors["units"] = "There is no such unit."
    unknown = [each for each in wanted_roles if each not in ROLES]
    if unknown:
        errors["roles"] = f"{unknown[0]!r} is not a role. Use: {', '.join(ROLES)}."
    if not everyone and not wanted_units and not wanted_roles and not errors:
        errors["units"] = "Choose the units or roles it applies to, or say it is for everyone."
    if errors:
        raise Invalid("Who it applies to was not saved.", errors)
    have = session.scalars(
        select(PolicyAudience).where(PolicyAudience.document_id == document.id)
    ).all()
    keep = (
        set()
        if everyone
        else {("unit", each) for each in wanted_units} | {("role", each) for each in wanted_roles}
    )
    with audit.operation(session, "document.audience"):
        for row in have:
            key = ("unit", row.org_unit_id) if row.org_unit_id else ("role", row.role)
            if key in keep:
                keep.discard(key)
            else:
                session.delete(row)
        for kind, value in sorted(keep, key=str):
            session.add(
                PolicyAudience(
                    document_id=document.id,
                    org_unit_id=value if kind == "unit" else None,
                    role=value if kind == "role" else None,
                )
            )
        document.for_everyone = bool(everyone)
        document.updated_at = utc_now()
        session.flush()


def _chosen(session: Session, document: PolicyDocument) -> tuple[frozenset[int], set[str]]:
    rows = session.scalars(
        select(PolicyAudience).where(PolicyAudience.document_id == document.id)
    ).all()
    within = units.with_descendants(session, [row.org_unit_id for row in rows if row.org_unit_id])
    return within, {row.role for row in rows if row.role}


def people(session: Session, document: PolicyDocument) -> list[Account]:
    """Everyone the document applies to who can sign in, by name."""
    query = select(Account).where(Account.status != "disabled").order_by(Account.display_name)
    if not document.for_everyone:
        within, chosen = _chosen(session, document)
        in_units = select(Membership.account_id).where(Membership.org_unit_id.in_(within or {0}))
        in_roles = select(RoleGrant.account_id).where(RoleGrant.role.in_(chosen or {""}))
        query = query.where(or_(Account.id.in_(in_units), Account.id.in_(in_roles)))
    return list(session.scalars(query))


def applies(session: Session, document: PolicyDocument, principal: Principal) -> bool:
    if document.for_everyone:
        return True
    within, chosen = _chosen(session, document)
    return bool(principal.member_units & within) or any(principal.has(each) for each in chosen)


def home_units(session: Session, account_ids: Iterable[int]) -> dict[int, int]:
    """Each person's own unit: the one marked as theirs, or the first they were put in."""
    first: dict[int, int] = {}
    marked: dict[int, int] = {}
    for account, unit, primary in session.execute(
        select(Membership.account_id, Membership.org_unit_id, Membership.is_primary)
        .where(Membership.account_id.in_(list(account_ids) or [0]))
        .order_by(Membership.id)
    ):
        first.setdefault(account, unit)
        if primary:
            marked.setdefault(account, unit)
    return {**first, **marked}


# --- Acknowledgment -------------------------------------------------------------------------------


def required(session: Session, document: PolicyDocument) -> PolicyVersion | None:
    """The version people must have acknowledged, or a later one: the newest published that
    asked them to say so again. None if the document asks nobody."""
    if not document.acknowledge or document.published_version_id is None:
        return None
    for version in session.scalars(
        select(PolicyVersion)
        .where(
            PolicyVersion.document_id == document.id,
            PolicyVersion.status.in_(documents.SHOWN),
        )
        .order_by(PolicyVersion.number.desc())
    ):
        if version.ask_again or version.number == 1:
            return version
    return None


def acknowledged(
    session: Session, document: PolicyDocument, account_ids: Iterable[int]
) -> dict[int, tuple[int, datetime]]:
    """For each person, the newest version they acknowledged and when."""
    found: dict[int, tuple[int, datetime]] = {}
    for account, number, when in session.execute(
        select(PolicyAcknowledgment.account_id, PolicyVersion.number,
               PolicyAcknowledgment.acknowledged_at)
        .join(PolicyVersion, PolicyVersion.id == PolicyAcknowledgment.version_id)
        .where(PolicyAcknowledgment.document_id == document.id,
               PolicyAcknowledgment.account_id.in_(list(account_ids) or [0]))
        .order_by(PolicyVersion.number)
    ):  # fmt: skip
        found[account] = (number, when)
    return found


def counts_for(required_version: PolicyVersion | None, seen: tuple[int, datetime] | None) -> bool:
    """Whether what a person acknowledged still counts."""
    return bool(required_version and seen and seen[0] >= (required_version.number or 0))


def acknowledge(session: Session, principal: Principal, document: PolicyDocument) -> None:
    """Say you have read the version in force."""
    if not access.can_see(session, principal, DOCUMENT, document) or principal.account_id is None:
        raise NotFound(f"There is no document {document.ref}.")
    version = documents.published(session, document)
    if version is None or document.status != "active":
        raise Conflict("Nothing of this document is in force to acknowledge.")
    if not document.acknowledge:
        raise Conflict("This document does not ask anyone to acknowledge it.")
    if not applies(session, document, principal):
        raise Conflict("This document does not apply to you.")
    already = session.scalars(
        select(PolicyAcknowledgment.id).where(
            PolicyAcknowledgment.version_id == version.id,
            PolicyAcknowledgment.account_id == principal.account_id,
        )
    ).first()
    now = utc_now()
    with audit.operation(session, "document.acknowledge"):
        if already is None:
            session.add(
                PolicyAcknowledgment(
                    document_id=document.id, version_id=version.id,
                    account_id=principal.account_id, account_name=principal.name,
                    acknowledged_at=now,
                )
            )  # fmt: skip
        # Anything a campaign was waiting on them for is answered.
        for item in session.scalars(
            select(CampaignItem)
            .join(Campaign, Campaign.id == CampaignItem.campaign_id)
            .where(
                Campaign.kind == "acknowledgment",
                Campaign.status == "open",
                CampaignItem.subject_type == "document",
                CampaignItem.subject_id == document.id,
                CampaignItem.account_id == principal.account_id,
                CampaignItem.status == "pending",
            )
        ):
            item.status, item.outcome = "done", "acknowledged"
            item.completed_at, item.completed_by_name = now, principal.name
        session.flush()


def tell_to_acknowledge(
    session: Session, principal: Principal, document: PolicyDocument, version: PolicyVersion
) -> int:
    """When a version that must be acknowledged is published, everyone it applies to is told."""
    if not document.acknowledge or not (version.ask_again or version.number == 1):
        return 0
    asked = [person.id for person in people(session, document)]
    again = " again" if (version.number or 0) > 1 else ""
    return notices.tell_all(
        session, asked, "document",
        f"Version {version.number} of {document.name} is published. Please read it and "
        f"say you have{again}.",
        f"/library/{document.ref}", by=principal,
    )  # fmt: skip


def standing(session: Session, document: PolicyDocument) -> dict[str, Any]:
    """Who the document applies to, split by whether they have acknowledged it, and by unit."""
    version = required(session, document)
    everyone = people(session, document)
    seen = acknowledged(session, document, [person.id for person in everyone])
    homes = home_units(session, [person.id for person in everyone])
    names = dict(session.execute(select(OrgUnit.id, OrgUnit.name)).all())
    rows = []
    by_unit: dict[int | None, dict[str, int]] = {}
    for person in everyone:
        done = counts_for(version, seen.get(person.id))
        unit = homes.get(person.id)
        tally = by_unit.setdefault(unit, {"people": 0, "acknowledged": 0})
        tally["people"] += 1
        tally["acknowledged"] += done
        rows.append({
            "account_id": person.id, "name": person.display_name, "unit_id": unit,
            "unit": names.get(unit, "No unit"), "acknowledged": done,
            "version": seen[person.id][0] if person.id in seen else None,
            "at": seen[person.id][1] if person.id in seen else None,
        })  # fmt: skip
    rows.sort(key=lambda row: (row["acknowledged"], row["unit"], row["name"]))
    total = len(rows)
    done_count = sum(1 for row in rows if row["acknowledged"])
    return {
        "required": {"id": version.id, "number": version.number} if version else None,
        "people": total,
        "acknowledged": done_count,
        "outstanding": total - done_count,
        "by_unit": sorted(
            (
                {
                    "unit": {"id": unit, "name": names.get(unit, "No unit")},
                    **tally,
                    "share": round(100 * tally["acknowledged"] / tally["people"]),
                }
                for unit, tally in by_unit.items()
            ),
            # Where the most are still to say they have read it comes first.
            key=lambda row: (
                row["acknowledged"] - row["people"],
                row["share"],
                row["unit"]["name"],
            ),
        ),
        "rows": rows,
    }


def may_see_standing(session: Session, principal: Principal, document: PolicyDocument) -> bool:
    return (
        principal.reads_all
        or documents.can_edit(session, principal, document)
        or principal.assesses_unit(document.org_unit_id)
    )


# --- The library -------------------------------------------------------------------------------


def _mine(session: Session, principal: Principal, rows: list[PolicyDocument]) -> dict[int, Any]:
    if principal.account_id is None:
        return {}
    return {
        document.id: acknowledged(session, document, [principal.account_id]).get(
            principal.account_id
        )
        for document in rows
        if document.acknowledge
    }


def entry(
    session: Session, principal: Principal, document: PolicyDocument, seen: Any
) -> dict[str, Any]:
    version = documents.published(session, document)
    must = required(session, document)
    applying = applies(session, document, principal)
    return {
        "ref": document.ref,
        "name": document.name,
        "kind": document.kind,
        "summary": document.summary,
        "org_unit_id": document.org_unit_id,
        "number": version.number if version else None,
        "published_at": version.published_at if version else None,
        "form": version.form if version else None,
        "applies": applying,
        "acknowledge": document.acknowledge and applying,
        "acknowledged": counts_for(must, seen) if document.acknowledge else None,
        "acknowledged_at": seen[1] if seen else None,
        "acknowledged_version": seen[0] if seen else None,
    }


def library(
    session: Session, principal: Principal, *, words: str | None = None, everything: bool = False
) -> list[dict[str, Any]]:
    """The published documents that apply to the reader (or all they may see), those still to
    acknowledge first, then broadest first. Words are looked for in the title, the summary,
    and the text in force."""
    query = (
        select(PolicyDocument)
        .join(PolicyVersion, PolicyVersion.id == PolicyDocument.published_version_id)
        .where(PolicyDocument.status == "active")
    )
    seen_rule = access.visible(session, principal, DOCUMENT)
    if seen_rule is not None:
        query = query.where(seen_rule)
    for word in (records.text(words) or "").lower().split()[:8]:
        like = f"%{word}%"
        query = query.where(
            or_(
                func.lower(PolicyDocument.name).like(like),
                func.lower(PolicyDocument.ref).like(like),
                func.lower(func.coalesce(PolicyDocument.summary, "")).like(like),
                and_(PolicyVersion.form == "text", func.lower(PolicyVersion.body).like(like)),
            )
        )
    rows = list(session.scalars(query))
    if not everything:
        rows = [row for row in rows if applies(session, row, principal)]
    mine = _mine(session, principal, rows)
    found = [entry(session, principal, row, mine.get(row.id)) for row in rows]
    found.sort(key=lambda each: (
        not (each["acknowledge"] and not each["acknowledged"]), RANK[each["kind"]], each["name"]
    ))  # fmt: skip
    return found


def reading(session: Session, principal: Principal, document: PolicyDocument) -> dict[str, Any]:
    """A document as it is read in the library."""
    version = documents.published(session, document)
    if version is None or document.status != "active":
        raise NotFound(f"Nothing of {document.ref} is published.")
    seen = _mine(session, principal, [document]).get(document.id)
    parent = session.get(PolicyDocument, document.parent_id) if document.parent_id else None
    beneath = session.scalars(
        select(PolicyDocument)
        .where(
            PolicyDocument.parent_id == document.id,
            PolicyDocument.status == "active",
            PolicyDocument.published_version_id.is_not(None),
        )
        .order_by(PolicyDocument.kind, PolicyDocument.name)
    ).all()
    must = required(session, document)
    return {
        **entry(session, principal, document, seen),
        "version": documents.version_view(session, principal, document, version),
        "required": {"number": must.number} if must else None,
        "next_review_on": document.next_review_on,
        "parent": documents._chip(parent)
        if parent and parent.published_version_id
        and access.can_see(session, principal, DOCUMENT, parent) else None,
        "children": [documents._chip(row) for row in beneath
                     if access.can_see(session, principal, DOCUMENT, row)],
        "can_manage": documents.can_edit(session, principal, document),
    }  # fmt: skip


def outstanding(session: Session, principal: Principal) -> list[PolicyDocument]:
    """Documents the person must acknowledge and has not."""
    if principal.account_id is None:
        return []
    rows = session.scalars(
        select(PolicyDocument).where(
            PolicyDocument.acknowledge.is_(True),
            PolicyDocument.status == "active",
            PolicyDocument.published_version_id.is_not(None),
        )
    ).all()
    found = []
    for document in rows:
        if not applies(session, document, principal):
            continue
        if not access.can_see(session, principal, DOCUMENT, document):
            continue
        seen = acknowledged(session, document, [principal.account_id]).get(principal.account_id)
        if not counts_for(required(session, document), seen):
            found.append(document)
    return sorted(found, key=lambda row: (RANK[row.kind], row.name))


def asked_by_campaign(session: Session, principal: Principal) -> set[int]:
    """Documents an open campaign is already asking this person to acknowledge."""
    return set(
        session.scalars(
            select(CampaignItem.subject_id)
            .join(Campaign, Campaign.id == CampaignItem.campaign_id)
            .where(
                Campaign.kind == "acknowledgment",
                Campaign.status == "open",
                CampaignItem.account_id == principal.account_id,
                CampaignItem.status == "pending",
            )
        )
    )
