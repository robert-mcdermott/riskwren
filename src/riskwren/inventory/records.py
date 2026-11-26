"""Creating, changing, finding, and showing records.

Written once for every record type: what differs between them is data, in the registry.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.core.clock import utc_now
from riskwren.core.errors import Conflict, Invalid, NotFound, PermissionDenied
from riskwren.db.models import Account, OrgUnit, RecordOwner
from riskwren.db.models.inventory import RECORD_STATUSES
from riskwren.db.refs import next_ref
from riskwren.events import audit
from riskwren.inventory import access
from riskwren.inventory.registry import RecordType
from riskwren.people import units
from riskwren.program import vocab

DEFAULT_CRITICALITY = "moderate"
OWNER = "owner"


class Errors(dict[str, str]):
    def add(self, field: str, message: str) -> None:
        self.setdefault(field, message)


def text(value: Any) -> str | None:
    cleaned = str(value).strip() if value is not None else ""
    return cleaned or None


def url(value: Any, field: str, errors: Errors, *, max_length: int = 300) -> str | None:
    cleaned = text(value)
    if cleaned and not cleaned.lower().startswith(("https://", "http://")):
        errors.add(field, "Start the address with https://")
        return None
    if cleaned and len(cleaned) > max_length:
        errors.add(field, f"Keep the address to {max_length} characters.")
        return None
    return cleaned


def choice(
    session: Session, name: str, value: Any, field: str, errors: Errors, *, required: bool = False
) -> str | None:
    key = text(value)
    if key is None:
        if required:
            errors.add(field, "Choose a value.")
        return None
    if key not in vocab.keys(session, name):
        errors.add(field, f"{key!r} is not one of the choices.")
        return None
    return key


def tags(values: Any, errors: Errors) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list | tuple):
        errors.add("tags", "Give a list of tags.")
        return []
    cleaned = list(dict.fromkeys(t for t in (str(v).strip().lower() for v in values) if t))
    if len(cleaned) > 20 or any(len(tag) > 40 for tag in cleaned):
        errors.add("tags", "Use at most 20 tags of up to 40 characters each.")
    return cleaned


def unit(session: Session, value: Any, errors: Errors) -> int | None:
    if value in (None, ""):
        errors.add("org_unit_id", "Say which unit this belongs to.")
        return None
    found = session.get(OrgUnit, int(value)) if str(value).isdigit() else None
    if found is None or found.status != "active":
        errors.add("org_unit_id", "Choose a unit that is active.")
        return None
    return found.id


def apply_header(
    session: Session, record: Any, values: Mapping[str, Any], errors: Errors, *, creating: bool
) -> None:
    """The facts every record has: a name, a summary, a unit, tags, and whether it is restricted."""
    if "name" in values or creating:
        name = text(values.get("name"))
        if not name:
            errors.add("name", "Give it a name.")
        elif len(name) > 200:
            errors.add("name", "Keep the name to 200 characters.")
        else:
            record.name = name
    if "summary" in values:
        record.summary = text(values["summary"])
    if "tags" in values:
        record.tags = tags(values["tags"], errors)
    if "restricted" in values and values["restricted"] is not None:
        record.restricted = bool(values["restricted"])
    if "org_unit_id" in values or creating:
        unit_id = unit(session, values.get("org_unit_id"), errors)
        if unit_id is not None:
            record.org_unit_id = unit_id


def apply_fields(
    session: Session,
    record_type: RecordType,
    record: Any,
    values: Mapping[str, Any],
    errors: Errors,
    *,
    creating: bool,
) -> None:
    """The facts particular to a record type, as its registry entry describes them."""
    for field in record_type.fields:
        if field.name not in values and not creating:
            continue
        given = values.get(field.name)
        if given in (None, "") and creating and field.default is not None:
            given = field.default
        if field.kind == "choice":
            assert field.vocab is not None
            chosen = choice(
                session, field.vocab, given, field.name, errors, required=field.required
            )
            if chosen is not None or not field.required:
                setattr(record, field.name, chosen)
        elif field.kind == "url":
            setattr(record, field.name, url(given, field.name, errors, max_length=field.max_length))
        else:
            cleaned = text(given)
            if field.required and not cleaned:
                errors.add(field.name, "This is needed.")
            elif cleaned and field.kind == "text" and len(cleaned) > field.max_length:
                errors.add(field.name, f"Keep this to {field.max_length} characters.")
            else:
                setattr(record, field.name, cleaned)


def _apply(
    session: Session,
    record_type: RecordType,
    record: Any,
    values: Mapping[str, Any],
    *,
    creating: bool,
) -> Errors:
    errors = Errors()
    apply_header(session, record, values, errors, creating=creating)
    if record_type.is_thing:
        if "criticality" in values or creating:
            given = values.get("criticality") or (DEFAULT_CRITICALITY if creating else None)
            chosen = choice(session, "criticalities", given, "criticality", errors, required=True)
            if chosen:
                record.criticality = chosen
        if "data_class" in values:
            record.data_class = choice(
                session, "data_classes", values["data_class"], "data_class", errors
            )
        if "status" in values and values["status"] is not None:
            if values["status"] not in RECORD_STATUSES:
                errors.add("status", "Use active or retired.")
            else:
                record.status = values["status"]
    apply_fields(session, record_type, record, values, errors, creating=creating)
    hook = record_type.extra.get("apply")
    if hook is not None:
        hook(session, record, values, errors, creating)
    return errors


def create(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    values: Mapping[str, Any],
) -> Any:
    """Add a record. Whoever adds it becomes its owner until they name someone else."""
    now = utc_now()
    record: Any = record_type.model(created_by=principal.account_id, created_at=now, updated_at=now)
    record.tags, record.restricted, record.version = [], False, 1
    if record_type.is_thing:
        record.status = "active"
    starting = record_type.extra.get("new")
    if starting is not None:
        starting(record)
    errors = _apply(session, record_type, record, values, creating=True)
    if errors:
        raise Invalid(f"The {record_type.label} was not saved.", errors)
    may_add = record_type.extra.get("can_add")
    allowed = (
        may_add(principal, record.org_unit_id)
        if may_add is not None
        else access.can_add(principal, record.org_unit_id)
    )
    if not allowed:
        raise PermissionDenied(
            record_type.extra.get("add_refusal")
            or f"Only a steward of the unit, or a manager, can add a {record_type.label} to it."
        )
    with audit.operation(session, f"{record_type.key}.create"):
        record.ref = next_ref(session, record_type.prefix)
        session.add(record)
        session.flush()
        if principal.account_id is not None:
            session.add(
                RecordOwner(
                    record_type=record_type.key,
                    record_id=record.id,
                    account_id=principal.account_id,
                    kind=OWNER,
                )
            )
        created = record_type.extra.get("created")
        if created is not None:
            created(session, principal, record)
    return record


def require_version(record_type: RecordType, record: Any, version: int | None) -> None:
    """Refuse a change made against an older version, so nothing is silently overwritten."""
    if version != record.version:
        raise Conflict(
            f"This {record_type.label} was changed by someone else while you were editing. "
            "Reload it, then make your change again."
        )


def update(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    record: Any,
    values: Mapping[str, Any],
    *,
    version: int | None,
) -> Any:
    """Change a record. ``version`` is the one the editor was looking at."""
    if not access.can_edit(session, principal, record_type, record):
        raise PermissionDenied(f"You cannot edit this {record_type.label}.")
    require_version(record_type, record, version)
    with audit.operation(session, f"{record_type.key}.edit"):
        with session.no_autoflush:
            errors = _apply(session, record_type, record, values, creating=False)
        if errors:
            session.expire(record)  # put back what was there
            raise Invalid(f"The {record_type.label} was not saved.", errors)
        if "org_unit_id" in values and not access.can_add(principal, record.org_unit_id):
            session.expire(record)
            raise PermissionDenied("You can move a record only to a unit you look after.")
        touch(session, record)
    return record


def touch(session: Session, record: Any) -> None:
    """Mark a record as changed, if it was."""
    if session.is_modified(record):
        record.version += 1
        record.updated_at = utc_now()


# --- Owners -------------------------------------------------------------------------------


def owners_of(
    session: Session, record_type: RecordType, ids: Iterable[int]
) -> dict[int, list[dict[str, Any]]]:
    """The people named on each record, owners first."""
    ids = list(ids)
    found: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if not ids:
        return found
    order = {key: position for position, key in enumerate(vocab.keys(session, "owner_kinds"))}
    rows = session.execute(
        select(RecordOwner, Account)
        .join(Account, Account.id == RecordOwner.account_id)
        .where(RecordOwner.record_type == record_type.key, RecordOwner.record_id.in_(ids))
        .order_by(Account.display_name)
    )
    for owner, account in rows:
        found[owner.record_id].append(
            {
                "account_id": account.id,
                "name": account.display_name,
                "email": account.email,
                "kind": owner.kind,
                "active": account.status != "disabled",
            }
        )
    for people in found.values():
        people.sort(key=lambda person: order.get(person["kind"], 99))
    return found


def accountable(owners: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [owner for owner in owners if owner["kind"] == OWNER]


def orphaned(owners: list[dict[str, Any]]) -> bool:
    """Nobody who can sign in answers for this record."""
    return not any(owner["active"] for owner in accountable(owners))


def set_owners(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    record: Any,
    owners: list[Mapping[str, Any]],
) -> None:
    if not access.can_edit(session, principal, record_type, record):
        raise PermissionDenied(f"You cannot edit this {record_type.label}.")
    kinds = vocab.keys(session, "owner_kinds")
    wanted: set[tuple[int, str]] = set()
    for owner in owners:
        identifier = owner.get("account_id")
        account = session.get(Account, int(identifier)) if str(identifier).isdigit() else None
        kind = str(owner.get("kind", ""))
        if account is None or account.status == "disabled":
            raise Invalid(
                "The owners were not saved.",
                {"owners": "Choose people whose accounts are not disabled."},
            )
        if kind not in kinds:
            raise Invalid(
                "The owners were not saved.", {"owners": f"{kind!r} is not a kind of owner."}
            )
        wanted.add((account.id, kind))
    if not any(kind == OWNER for _, kind in wanted):
        raise Invalid("The owners were not saved.", {"owners": "Every record needs an owner."})
    existing = session.scalars(
        select(RecordOwner).where(
            RecordOwner.record_type == record_type.key, RecordOwner.record_id == record.id
        )
    ).all()
    have = {(row.account_id, row.kind): row for row in existing}
    with audit.operation(session, f"{record_type.key}.owners"):
        for key, row in have.items():
            if key not in wanted:
                session.delete(row)
        for account_id, kind in sorted(wanted - set(have)):
            session.add(
                RecordOwner(
                    record_type=record_type.key,
                    record_id=record.id,
                    account_id=account_id,
                    kind=kind,
                )
            )


# --- Finding ------------------------------------------------------------------------------


def conditions_for(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    filters: Mapping[str, Any],
) -> list[Any]:
    """What narrows a list: what the person may see, and what they asked for."""
    model: Any = record_type.model
    conditions: list[Any] = []
    seen = access.visible(session, principal, record_type)
    if seen is not None:
        conditions.append(seen)
    query = text(filters.get("q"))
    if query:
        like = f"%{query.lower()}%"
        conditions.append(
            or_(
                func.lower(model.name).like(like),
                func.lower(model.ref).like(like),
                func.lower(func.coalesce(model.summary, "")).like(like),
            )
        )
    if filters.get("unit"):
        conditions.append(
            model.org_unit_id.in_(units.with_descendants(session, [int(filters["unit"])]))
        )
    for name in record_type.filters:
        value = filters.get(name)
        if value not in (None, ""):
            conditions.append(getattr(model, name) == value)
    more = record_type.extra.get("conditions")
    if more is not None:
        conditions += more(session, principal, filters)
    owner = filters.get("owner")
    if filters.get("mine"):
        owner = principal.account_id
    if owner:
        owned = select(RecordOwner.record_id).where(
            RecordOwner.record_type == record_type.key, RecordOwner.account_id == int(owner)
        )
        conditions.append(model.id.in_(owned))
    return conditions


def ordering(session: Session, record_type: RecordType, sort: str) -> list[Any]:
    model: Any = record_type.model
    descending = sort.startswith("-")
    name = sort.lstrip("-")
    if name not in record_type.sorts:
        raise Invalid(
            "The list could not be sorted.",
            {"sort": f"Sort by one of: {', '.join(record_type.sorts)}."},
        )
    column = getattr(model, name)
    special = record_type.extra.get("sort_columns", {}).get(name)
    if special is not None:
        column = special(session, model)
    elif name == "criticality":
        # An ordered vocabulary sorts by its order, not by its spelling.
        from sqlalchemy import case

        ranks = {key: rank for rank, key in enumerate(vocab.keys(session, "criticalities"))}
        column = case(ranks, value=model.criticality, else_=-1)
    return [
        column.desc().nulls_last() if descending else column.asc().nulls_last(),
        model.id.desc(),
    ]


def search(
    session: Session,
    principal: Principal,
    record_type: RecordType,
    filters: Mapping[str, Any],
    *,
    sort: str = "-updated_at",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Any], int]:
    """Records the person may see that match the filters, and how many there are in all."""
    model: Any = record_type.model
    conditions = conditions_for(session, principal, record_type, filters)
    order = ordering(session, record_type, sort)
    total = session.execute(select(func.count()).select_from(model).where(*conditions)).scalar_one()
    rows = list(
        session.scalars(
            select(model).where(*conditions).order_by(*order).limit(limit).offset(offset)
        )
    )
    return rows, total


# --- Showing ------------------------------------------------------------------------------


def chip(record_type: RecordType, record: Any) -> dict[str, Any]:
    """A record as it appears wherever another record refers to it."""
    out = {"type": record_type.key, "ref": record.ref, "name": record.name}
    if record_type.is_thing:
        out.update(status=record.status, criticality=record.criticality)
    return out


def card(record_type: RecordType, record: Any, owners: list[dict[str, Any]]) -> dict[str, Any]:
    """A record as a row of a list."""
    out: dict[str, Any] = {
        "type": record_type.key,
        "ref": record.ref,
        "name": record.name,
        "summary": record.summary,
        "org_unit_id": record.org_unit_id,
        "restricted": record.restricted,
        "updated_at": record.updated_at,
        "owners": accountable(owners),
        "orphaned": orphaned(owners),
    }
    if record_type.is_thing:
        out.update(
            status=record.status, criticality=record.criticality, data_class=record.data_class
        )
    for field in record_type.fields:
        if field.kind in ("choice", "text"):
            out[field.name] = getattr(record, field.name)
    return out


def cards(session: Session, record_type: RecordType, rows: list[Any]) -> list[dict[str, Any]]:
    owners = owners_of(session, record_type, [row.id for row in rows])
    out = [card(record_type, row, owners.get(row.id, [])) for row in rows]
    more = record_type.extra.get("cards")
    if more is not None:
        for item, extra in zip(out, more(session, rows), strict=True):
            item.update(extra)
    return out


def detail(
    session: Session, principal: Principal, record_type: RecordType, record: Any
) -> dict[str, Any]:
    """One record in full. Raises NotFound if the person may not see it: a record they may
    not see does not exist, as far as they can tell."""
    if not access.can_see(session, principal, record_type, record):
        raise NotFound(f"There is no {record_type.label} {record.ref}.")
    owners = owners_of(session, record_type, [record.id]).get(record.id, [])
    out = cards(session, record_type, [record])[0]
    out["owners"] = owners
    for field in record_type.fields:
        out[field.name] = getattr(record, field.name)
    editable = access.can_edit(session, principal, record_type, record)
    out.update(
        tags=record.tags,
        version=record.version,
        created_at=record.created_at,
        can={
            "edit": editable,
            "assess": access.can_assess(session, principal, record_type, record),
        },
    )
    more = record_type.extra.get("detail")
    if more is not None:
        out.update(more(session, principal, record))
    return out


def load(session: Session, principal: Principal, record_type: RecordType, ref: str) -> Any:
    """Find a record the person may see, or raise NotFound."""
    from riskwren.inventory.registry import find

    record = find(session, record_type, ref)
    if not access.can_see(session, principal, record_type, record):
        raise NotFound(f"There is no {record_type.label} {ref}.")
    return record
