"""Coverage (TPR-05, TPR-06): whether the paper covers what is shared.

Information is shared with a third party when it is linked as shared with it, or when one of
the third party's services handles it. The program says, as rules in the condition language,
which kinds of agreement information of each kind needs when it is shared with a third party
of each kind: identifiable health information handled for the organization needs a business
associate agreement; data held under another party's terms needs a data use agreement.

Where a rule applies and no agreement of one of its kinds is open, in force, with that third
party, and covers the information, the service, or a scope that holds the information, the
gap is a **stop**, shown on the information, the third party, and the service, and gathered
in one list. It goes as soon as such an agreement covers it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core import conditions
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, PermissionDenied
from riskwren.db.models import (
    Agreement,
    AgreementCoverage,
    AgreementParty,
    Information,
    RecordLink,
    ScopeMember,
    Service,
    ThirdParty,
)
from riskwren.events import audit
from riskwren.inventory import access, records
from riskwren.inventory.registry import INFORMATION, THIRD_PARTY
from riskwren.program import rules, vocab
from riskwren.thirdparty.services import SERVICE


@dataclass(frozen=True)
class Sharing:
    """Information that a third party holds, receives, or can see, and how."""

    information: Information
    third_party: ThirdParty
    service: Service | None  # None: shared with the third party directly


# --- The program's rules --------------------------------------------------------------------


def requirements(session: Session) -> list[dict[str, Any]]:
    return list(rules.get(session, "sharing").get("rules") or [])


def problems(value: Any) -> list[str]:
    """What is wrong with the table of sharing rules, before it is saved or loaded."""
    from riskwren.db.models.agreements import AGREEMENT_KINDS

    if not isinstance(value, Mapping) or not isinstance(value.get("rules"), list):
        return ["The sharing rules need a list of rules."]
    found: list[str] = []
    keys: set[str] = set()
    for index, rule in enumerate(value["rules"]):
        where = f"Rule {index + 1}"
        if not isinstance(rule, Mapping):
            found.append(f"{where}: must be an object.")
            continue
        key = rule.get("key")
        if not isinstance(key, str) or not vocab.KEY.fullmatch(key) or key in keys:
            found.append(f"{where}: needs a key of its own.")
        else:
            keys.add(key)
        if not str(rule.get("reason") or "").strip():
            found.append(f"{where}: says why, in words.")
        if not isinstance(rule.get("when"), Mapping) or not rule["when"]:
            found.append(f"{where}: needs a condition.")
        kinds = rule.get("kinds")
        if not isinstance(kinds, list) or not kinds or any(k not in AGREEMENT_KINDS for k in kinds):
            found.append(f"{where}: names the kinds of agreement that meet it.")
    return found


def _context(sharing: Sharing) -> dict[str, Any]:
    info, party, service = sharing.information, sharing.third_party, sharing.service
    return {
        "information": {"kind": info.kind, "data_class": info.data_class},
        "third_party": {"kind": party.kind, "tier": party.tier},
        "service": {"kind": service.kind} if service is not None else {},
    }


# --- What is shared, and what covers it ---------------------------------------------------


def shared(session: Session) -> list[Sharing]:
    """Every piece of information in use shared with a third party in use, directly or
    through one of its services."""
    infos = {row.id: row for row in session.scalars(
        select(Information).where(Information.status == "active"))}  # fmt: skip
    parties = {row.id: row for row in session.scalars(
        select(ThirdParty).where(ThirdParty.status == "active"))}  # fmt: skip
    services = {row.id: row for row in session.scalars(
        select(Service).where(Service.status == "active"))}  # fmt: skip
    found: dict[tuple[int, int, int | None], Sharing] = {}
    for link in session.scalars(
        select(RecordLink).where(
            or_(
                and_(RecordLink.from_type == "information", RecordLink.relation == "shared_with",
                     RecordLink.to_type == "third_party"),
                and_(RecordLink.from_type == "service", RecordLink.relation == "handles",
                     RecordLink.to_type == "information"),
            )
        )
    ):  # fmt: skip
        if link.from_type == "information":
            info, party, service = infos.get(link.from_id), parties.get(link.to_id), None
        else:
            service = services.get(link.from_id)
            info = infos.get(link.to_id)
            party = parties.get(service.third_party_id) if service else None
            if service is None:
                continue
        if info is None or party is None:
            continue
        key = (info.id, party.id, service.id if service else None)
        found[key] = Sharing(info, party, service)
    return sorted(found.values(), key=lambda s: (s.information.ref, s.third_party.ref,
                                                 s.service.ref if s.service else ""))  # fmt: skip


def in_force(agreement: Agreement, today: date) -> bool:
    return (
        agreement.status == "active"
        and (agreement.starts_on is None or agreement.starts_on <= today)
        and (agreement.ends_on is None or agreement.ends_on >= today)
    )


def _agreements(session: Session) -> list[tuple[Agreement, set[int], set[tuple[str, int]]]]:
    """Every open agreement with the third parties it is with and what it covers."""
    rows = session.scalars(select(Agreement).where(Agreement.status == "active")).all()
    ids = [row.id for row in rows] or [0]
    parties: dict[int, set[int]] = {}
    for row in session.scalars(select(AgreementParty).where(AgreementParty.agreement_id.in_(ids))):
        parties.setdefault(row.agreement_id, set()).add(row.third_party_id)
    covers: dict[int, set[tuple[str, int]]] = {}
    for row in session.scalars(
        select(AgreementCoverage).where(AgreementCoverage.agreement_id.in_(ids))
    ):
        covers.setdefault(row.agreement_id, set()).add((row.subject_type, row.subject_id))
    return [(row, parties.get(row.id, set()), covers.get(row.id, set())) for row in rows]


def stops(session: Session) -> list[dict[str, Any]]:
    """Every sharing that a rule says needs an agreement and that none covers: the records,
    each rule it fails, and what agreements there are with the third party that do not meet
    them."""
    today = utc_now().date()
    listed = requirements(session)
    if not listed:
        return []
    agreements = _agreements(session)
    holding: dict[int, set[int]] = {}
    for scope_id, info_id in session.execute(
        select(ScopeMember.scope_id, ScopeMember.subject_id).where(
            ScopeMember.subject_type == "information"
        )
    ):
        holding.setdefault(info_id, set()).add(scope_id)
    found = []
    for sharing in shared(session):
        context = _context(sharing)
        wanted = {("information", sharing.information.id)}
        wanted |= {("scope", scope) for scope in holding.get(sharing.information.id, set())}
        if sharing.service is not None:
            wanted.add(("service", sharing.service.id))
        with_party = [
            (row, covered) for row, parties, covered in agreements
            if sharing.third_party.id in parties
        ]  # fmt: skip
        failed = []
        for rule in listed:
            if not conditions.evaluate(rule.get("when"), context):
                continue
            kinds = set(rule["kinds"])
            met = any(
                row.kind in kinds and in_force(row, today) and covered & wanted
                for row, covered in with_party
            )
            if not met:
                failed.append(rule)
        if failed:
            found.append({"sharing": sharing, "rules": failed,
                          "short": [row for row, _ in with_party]})  # fmt: skip
    return found


ARTICLED = {
    "award": "an award's terms", "data_use": "a data use agreement",
    "business_associate": "a business associate agreement", "contract": "a contract",
    "confidentiality": "a confidentiality agreement",
    "memorandum": "a memorandum of understanding", "other": "an agreement",
}  # fmt: skip


def _kinds_in_words(kinds: list[str]) -> str:
    words = [ARTICLED.get(kind, kind) for kind in kinds]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + ", or " + words[-1]


def view(session: Session, principal: Principal, found: dict[str, Any]) -> dict[str, Any] | None:
    """A stop as the person may see it: None if they may see neither side of it."""
    from riskwren.compliance.agreements import AGREEMENT, state_of

    sharing: Sharing = found["sharing"]
    seen_info = access.can_see(session, principal, INFORMATION, sharing.information)
    seen_party = access.can_see(session, principal, THIRD_PARTY, sharing.third_party)
    if not (seen_info and seen_party):
        return None
    service = sharing.service
    today = utc_now().date()
    return {
        "information": records.chip(INFORMATION, sharing.information),
        "third_party": records.chip(THIRD_PARTY, sharing.third_party),
        "service": records.chip(SERVICE, service)
        if service is not None and access.can_see(session, principal, SERVICE, service)
        else None,
        "needs": [
            {
                "rule": rule["key"],
                "reason": rule["reason"],
                "kinds": rule["kinds"],
                "kinds_words": _kinds_in_words(rule["kinds"]),
            }
            for rule in found["rules"]
        ],
        "agreements": [
            {**records.chip(AGREEMENT, row), "kind": row.kind, "state": state_of(row, today)}
            for row in found["short"]
            if access.can_see(session, principal, AGREEMENT, row)
        ],
    }


def stops_for(session: Session, principal: Principal, record_type: str, record_id: int
              ) -> list[dict[str, Any]]:  # fmt: skip
    """The stops a record is part of, as the person may see them."""
    out = []
    for found in stops(session):
        sharing: Sharing = found["sharing"]
        involved = {
            "information": sharing.information.id,
            "third_party": sharing.third_party.id,
            "service": sharing.service.id if sharing.service else None,
        }
        if involved.get(record_type) != record_id:
            continue
        shown = view(session, principal, found)
        if shown is not None:
            out.append(shown)
    return out


def all_stops(session: Session, principal: Principal) -> list[dict[str, Any]]:
    return [shown for found in stops(session) if (shown := view(session, principal, found))]


# --- Who an agreement is with -------------------------------------------------------------


def parties_of(session: Session, principal: Principal, agreement: Agreement) -> list[Any]:
    rows = session.scalars(
        select(ThirdParty)
        .join(AgreementParty, AgreementParty.third_party_id == ThirdParty.id)
        .where(AgreementParty.agreement_id == agreement.id)
        .order_by(ThirdParty.name)
    ).all()
    return [records.chip(THIRD_PARTY, row) for row in rows
            if access.can_see(session, principal, THIRD_PARTY, row)]  # fmt: skip


def set_parties(
    session: Session, principal: Principal, agreement: Agreement, refs: list[str]
) -> None:
    """Say which third parties an agreement is with."""
    from riskwren.compliance import agreements

    if not agreements.can_edit(session, principal, agreement):
        raise PermissionDenied("An agreement is changed by its owners, or its unit's keepers.")
    if agreement.status != "active":
        raise Conflict("A closed agreement is with nobody. Open it again first.")
    wanted: dict[int, ThirdParty] = {}
    for ref in dict.fromkeys(refs):
        found = session.scalars(
            select(ThirdParty).where(ThirdParty.ref == str(ref).strip().upper())
        ).first()
        if found is None or not access.can_see(session, principal, THIRD_PARTY, found):
            raise Invalid("Who it is with was not changed.",
                          {"parties": f"There is no third party {ref}."})  # fmt: skip
        wanted[found.id] = found
    have = {row.third_party_id: row for row in session.scalars(
        select(AgreementParty).where(AgreementParty.agreement_id == agreement.id))}  # fmt: skip
    for party_id, row in have.items():
        if party_id not in wanted:
            party = session.get(ThirdParty, party_id)
            who = f"{party.ref} {party.name}" if party else "a third party"
            with audit.operation(session, "agreement.parties", who=who):
                session.delete(row)
                session.flush()
    for party_id, party in wanted.items():
        if party_id not in have:
            with audit.operation(session, "agreement.parties", who=f"{party.ref} {party.name}"):
                session.add(AgreementParty(agreement_id=agreement.id, third_party_id=party_id))
                session.flush()
    records.touch(session, agreement)


def agreements_with(session: Session, principal: Principal, third_party: ThirdParty
                    ) -> list[dict[str, Any]]:  # fmt: skip
    """The agreements a third party is party to, open ones first."""
    from riskwren.compliance.agreements import AGREEMENT, state_of

    rows = session.scalars(
        select(Agreement)
        .join(AgreementParty, AgreementParty.agreement_id == Agreement.id)
        .where(AgreementParty.third_party_id == third_party.id)
        .order_by(Agreement.status, Agreement.ends_on, Agreement.name)
    ).all()
    today = utc_now().date()
    return [
        {**records.chip(AGREEMENT, row), "kind": row.kind, "state": state_of(row, today),
         "ends_on": row.ends_on}
        for row in rows
        if access.can_see(session, principal, AGREEMENT, row)
    ]  # fmt: skip


# --- On the records involved ----------------------------------------------------------------


def _with_stops(key: str, earlier: Any) -> Any:
    def detail(session: Session, principal: Principal, record: Any) -> dict[str, Any]:
        out = dict(earlier(session, principal, record)) if earlier else {}
        out["stops"] = stops_for(session, principal, key, record.id)
        return out

    return detail


def _agreement_detail(earlier: Any) -> Any:
    def detail(session: Session, principal: Principal, agreement: Agreement) -> dict[str, Any]:
        out = dict(earlier(session, principal, agreement)) if earlier else {}
        out["with"] = parties_of(session, principal, agreement)
        return out

    return detail


def install() -> None:
    """Give each record involved in sharing its stops, and agreements who they are with."""
    from riskwren.compliance.agreements import AGREEMENT

    for record_type in (INFORMATION, THIRD_PARTY, SERVICE):
        record_type.extra["detail"] = _with_stops(record_type.key, record_type.extra.get("detail"))
    AGREEMENT.extra["detail"] = _agreement_detail(AGREEMENT.extra.get("detail"))
