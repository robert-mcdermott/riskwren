"""What a person answered for, when they leave (OVS-08).

Disabling an account leaves nothing without an owner. Whatever the person alone answered
for passes at once to the steward of its unit, who is told, and it stays listed as theirs
to pass on. An administrator, or a steward for their own units, then names who takes each
thing for good, in one step.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren.access import roles
from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.models import (
    Account,
    Action,
    Campaign,
    CampaignItem,
    Handover,
    RecordOwner,
    Risk,
    RoleGrant,
    TreatmentPlan,
)
from riskwren.events import audit
from riskwren.inventory import access
from riskwren.inventory.registry import TYPES
from riskwren.people import notices, units

ACTION, ITEM, PLAN = "action", "campaign_item", "plan"
OPEN_ACTIONS = ("open", "in_progress")


def _active(session: Session, account_ids: Iterable[int], *, but: int) -> list[int]:
    ids = [each for each in dict.fromkeys(account_ids) if each != but]
    if not ids:
        return []
    live = set(
        session.scalars(select(Account.id).where(Account.id.in_(ids), Account.status != "disabled"))
    )
    return [each for each in ids if each in live]


def stand_in(
    session: Session, org_unit_id: int | None, leaving: int, fallback: int | None
) -> int | None:
    """Who answers for something in this unit until an owner is named: the nearest steward,
    then the nearest leader, then someone who runs the program, then whoever is disabling
    the account."""
    if org_unit_id is not None:
        line = [org_unit_id, *(unit.id for unit in units.ancestors(session, org_unit_id))]
        for role in (roles.STEWARD, roles.LEADER):
            grants = session.execute(
                select(RoleGrant.account_id, RoleGrant.org_unit_id).where(
                    RoleGrant.role == role, RoleGrant.org_unit_id.in_(line)
                )
            ).all()
            # The nearest unit first.
            grants = sorted(grants, key=lambda grant: line.index(grant[1]))
            found = _active(session, (account for account, _ in grants), but=leaving)
            if found:
                return found[0]
    managers = session.scalars(
        select(RoleGrant.account_id)
        .where(RoleGrant.role == roles.MANAGER, RoleGrant.org_unit_id.is_(None))
        .order_by(RoleGrant.account_id)
    )
    found = _active(session, managers, but=leaving)
    if found:
        return found[0]
    return fallback if fallback != leaving else None


def _action_unit(session: Session, action: Action) -> int | None:
    from riskwren.reminders import _action_unit as unit_of

    return unit_of(session, action)


def _plan_unit(session: Session, plan: TreatmentPlan) -> int | None:
    risk = session.get(Risk, plan.risk_id)
    return risk.org_unit_id if risk else None


def _log(session: Session, leaving: int, subject_type: str, subject_id: int, kind: str,
         held_by: int) -> None:  # fmt: skip
    row = session.scalars(
        select(Handover).where(
            Handover.from_account_id == leaving,
            Handover.subject_type == subject_type,
            Handover.subject_id == subject_id,
            Handover.kind == kind,
        )
    ).first()
    if row is None:
        session.add(
            Handover(from_account_id=leaving, subject_type=subject_type, subject_id=subject_id,
                     kind=kind, held_by=held_by, created_at=utc_now())
        )  # fmt: skip
    else:
        row.held_by = held_by


def cover(session: Session, principal: Principal, account: Account) -> dict[str, Any]:
    """Pass on whatever this person alone answered for, so that nothing is left without
    someone who can sign in. Called as the account is disabled."""
    taken: Counter[int] = Counter()
    left = 0
    with audit.operation(session, "account.handover"):
        rows = session.scalars(
            select(RecordOwner).where(
                RecordOwner.account_id == account.id, RecordOwner.kind == "owner"
            )
        ).all()
        for row in rows:
            record_type = TYPES.get(row.record_type)
            record = session.get(record_type.model, row.record_id) if record_type else None
            if record is None:
                continue
            others = session.scalars(
                select(RecordOwner.account_id).where(
                    RecordOwner.record_type == row.record_type,
                    RecordOwner.record_id == row.record_id,
                    RecordOwner.kind == "owner",
                )
            ).all()
            if _active(session, others, but=account.id):
                continue  # someone else already answers for it
            own = record_type.extra.get("stand_in")
            default = lambda record=record: stand_in(  # noqa: E731
                session, record.org_unit_id, account.id, principal.account_id
            )
            to = own(session, record, account.id, default) if own is not None else default()
            if to is None:
                left += 1
                continue
            row.account_id = to
            _log(session, account.id, row.record_type, row.record_id, "owner", to)
            taken[to] += 1
        for action in session.scalars(
            select(Action).where(Action.owner_id == account.id, Action.status.in_(OPEN_ACTIONS))
        ).all():
            to = stand_in(session, _action_unit(session, action), account.id, principal.account_id)
            if to is None:
                left += 1
                continue
            action.owner_id = to
            _log(session, account.id, ACTION, action.id, "owner", to)
            taken[to] += 1
        for plan in session.scalars(
            select(TreatmentPlan).where(
                TreatmentPlan.owner_id == account.id, TreatmentPlan.status == "active"
            )
        ).all():
            to = stand_in(session, _plan_unit(session, plan), account.id, principal.account_id)
            if to is None:
                left += 1
                continue
            plan.owner_id = to
            _log(session, account.id, PLAN, plan.id, "owner", to)
            taken[to] += 1
        items = session.execute(
            select(CampaignItem)
            .join(Campaign, Campaign.id == CampaignItem.campaign_id)
            .where(
                CampaignItem.account_id == account.id,
                CampaignItem.status == "pending",
                Campaign.status == "open",
            )
        ).scalars().all()  # fmt: skip
        for item in items:
            to = stand_in(session, item.org_unit_id, account.id, principal.account_id)
            if to is None:
                left += 1
                continue
            item.account_id = to
            holder = session.get(Account, to)
            item.account_name = holder.display_name if holder else item.account_name
            _log(session, account.id, ITEM, item.id, "asked", to)
            taken[to] += 1
        session.flush()
    names = {
        row.id: row.display_name
        for row in session.scalars(select(Account).where(Account.id.in_(list(taken) or [0])))
    }
    for to, count in taken.items():
        things = "1 thing" if count == 1 else f"{count} things"
        notices.tell(
            session, to, "handover",
            f"{account.display_name}'s account was disabled. You now answer for {things} "
            "they owned, until someone is named for good.",
            f"/handover/{account.id}", by=principal,
        )  # fmt: skip
    return {
        "passed_on": sum(taken.values()),
        "to": [{"account_id": to, "name": names.get(to, ""), "count": count}
               for to, count in taken.most_common()],
        "left": left,
    }  # fmt: skip


def _may_pass_on(session: Session, principal: Principal, unit_id: int | None) -> bool:
    return principal.is_admin or principal.manages_unit(unit_id) or principal.stewards_unit(unit_id)


def holdings(session: Session, principal: Principal, account: Account) -> dict[str, Any]:
    """Everything the person is still named on, and everything passed on when they left,
    cut to what the asker may see. Each carries whether the asker may pass it on."""
    held: list[dict[str, Any]] = []
    names: dict[int, str] = {}

    def name_of(account_id: int) -> str:
        if account_id not in names:
            found = session.get(Account, account_id)
            names[account_id] = found.display_name if found else ""
        return names[account_id]

    seen: set[tuple[str, int, str]] = set()

    def record(subject_type: str, subject_id: int, kind: str, holder: int | None) -> None:
        if (subject_type, subject_id, kind) in seen:
            return
        seen.add((subject_type, subject_id, kind))
        if subject_type == ACTION:
            action = session.get(Action, subject_id)
            if action is None or action.status not in OPEN_ACTIONS:
                return
            unit = _action_unit(session, action)
            if not (_may_pass_on(session, principal, unit) or principal.reads_all):
                return
            held.append({"type": ACTION, "id": action.id, "ref": action.ref, "name": action.title,
                         "kind": "owner", "org_unit_id": unit, "href": "/actions?q=" + action.ref,
                         "held_by": holder and name_of(holder),
                         "can_pass_on": _may_pass_on(session, principal, unit)})  # fmt: skip
            return
        if subject_type == PLAN:
            plan = session.get(TreatmentPlan, subject_id)
            risk = session.get(Risk, plan.risk_id) if plan is not None else None
            if plan is None or risk is None or plan.status != "active":
                return
            unit = risk.org_unit_id
            if not (_may_pass_on(session, principal, unit) or principal.reads_all):
                return
            held.append({"type": PLAN, "id": plan.id, "ref": plan.ref,
                         "name": f"Treatment plan for {risk.name}", "kind": "owner",
                         "org_unit_id": unit, "href": f"/risks/{risk.ref}?tab=treatment",
                         "held_by": holder and name_of(holder),
                         "can_pass_on": _may_pass_on(session, principal, unit)})  # fmt: skip
            return
        if subject_type == ITEM:
            item = session.get(CampaignItem, subject_id)
            if item is None or item.status != "pending":
                return
            if not (_may_pass_on(session, principal, item.org_unit_id) or principal.reads_all):
                return
            about = f"{item.subject_ref or ''} {item.subject_name}".strip()
            held.append({"type": ITEM, "id": item.id, "ref": None, "name": f"Asked about {about}",
                         "kind": "asked", "org_unit_id": item.org_unit_id,
                         "href": f"/campaign-items/{item.id}",
                         "held_by": holder and name_of(holder),
                         "can_pass_on": _may_pass_on(session, principal,
                                                     item.org_unit_id)})  # fmt: skip
            return
        record_type = TYPES.get(subject_type)
        row = session.get(record_type.model, subject_id) if record_type else None
        if row is None or record_type is None:
            return
        if not access.can_see(session, principal, record_type, row):
            return
        held.append({"type": subject_type, "id": row.id, "ref": row.ref, "name": row.name,
                     "kind": kind, "org_unit_id": row.org_unit_id,
                     "href": f"/{record_type.path}/{row.ref}",
                     "held_by": holder and name_of(holder),
                     "can_pass_on": _may_pass_on(session, principal, row.org_unit_id)})  # fmt: skip

    for log in session.scalars(
        select(Handover).where(Handover.from_account_id == account.id).order_by(Handover.id)
    ):
        record(log.subject_type, log.subject_id, log.kind, log.held_by)
    for owner in session.scalars(
        select(RecordOwner).where(RecordOwner.account_id == account.id).order_by(RecordOwner.id)
    ):
        record(owner.record_type, owner.record_id, owner.kind, None)
    for action in session.scalars(
        select(Action).where(Action.owner_id == account.id, Action.status.in_(OPEN_ACTIONS))
    ):
        record(ACTION, action.id, "owner", None)
    for plan in session.scalars(
        select(TreatmentPlan).where(
            TreatmentPlan.owner_id == account.id, TreatmentPlan.status == "active"
        )
    ):
        record(PLAN, plan.id, "owner", None)
    for item in session.scalars(
        select(CampaignItem).where(
            CampaignItem.account_id == account.id, CampaignItem.status == "pending"
        )
    ):
        record(ITEM, item.id, "asked", None)
    return {
        "account": {"id": account.id, "name": account.display_name, "status": account.status},
        "items": held,
        "can_pass_on": sum(1 for each in held if each["can_pass_on"]),
    }


def waiting(session: Session, principal: Principal) -> list[dict[str, Any]]:
    """People who have left with things still to pass on that the asker may pass on."""
    ids = set(session.scalars(select(Handover.from_account_id).distinct()))
    ids |= set(
        session.scalars(
            select(RecordOwner.account_id)
            .join(Account, Account.id == RecordOwner.account_id)
            .where(Account.status == "disabled")
            .distinct()
        )
    )
    out = []
    for account in session.scalars(
        select(Account).where(Account.id.in_(ids or {0})).order_by(Account.display_name)
    ):
        found = holdings(session, principal, account)
        if found["can_pass_on"]:
            out.append({**found["account"], "count": found["can_pass_on"]})
    return out


def pass_on(
    session: Session,
    principal: Principal,
    account: Account,
    to: Account,
    *,
    only: Iterable[tuple[str, int]] | None = None,
) -> int:
    """Name who takes what this person held, for good: everything the asker may pass on,
    or only the things named. Returns how many things changed hands."""
    if to.status == "disabled" or to.id == account.id:
        raise Invalid(
            "Nothing was passed on.", {"to": "Choose someone whose account is not disabled."}
        )
    wanted = set(only) if only is not None else None
    found = holdings(session, principal, account)
    chosen = [
        each for each in found["items"]
        if each["can_pass_on"] and (wanted is None or (each["type"], each["id"]) in wanted)
    ]  # fmt: skip
    if not chosen:
        if found["items"]:
            raise PermissionDenied(
                "What a person held is passed on by an administrator, or by a steward or "
                "manager for their own units."
            )
        return 0
    with audit.operation(session, "account.handover"):
        for each in chosen:
            log = session.scalars(
                select(Handover).where(
                    Handover.from_account_id == account.id,
                    Handover.subject_type == each["type"],
                    Handover.subject_id == each["id"],
                    Handover.kind == each["kind"],
                )
            ).first()
            holder = log.held_by if log is not None else account.id
            if holder == to.id:
                pass  # the stand-in keeps it for good: only the note of it goes
            elif each["type"] == ACTION:
                action = session.get(Action, each["id"])
                assert action is not None
                action.owner_id = to.id
            elif each["type"] == PLAN:
                plan = session.get(TreatmentPlan, each["id"])
                assert plan is not None
                plan.owner_id = to.id
            elif each["type"] == ITEM:
                item = session.get(CampaignItem, each["id"])
                assert item is not None
                item.account_id, item.account_name = to.id, to.display_name
            else:
                rows = session.scalars(
                    select(RecordOwner).where(
                        RecordOwner.record_type == each["type"],
                        RecordOwner.record_id == each["id"],
                        RecordOwner.kind == each["kind"],
                    )
                ).all()
                has = any(row.account_id == to.id for row in rows)
                for row in rows:
                    if row.account_id != holder:
                        continue
                    if has:
                        session.delete(row)
                    else:
                        row.account_id = to.id
                        has = True
            if log is not None:
                session.delete(log)
        session.flush()
    things = "1 thing" if len(chosen) == 1 else f"{len(chosen)} things"
    notices.tell(
        session, to.id, "handover",
        f"You now answer for {things} that {account.display_name} held, for good.",
        "/", by=principal,
    )  # fmt: skip
    return len(chosen)
