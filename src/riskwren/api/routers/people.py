"""Accounts, roles, units, and importing them."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from riskwren.access import roles
from riskwren.access.policy import current
from riskwren.access.principal import Grant
from riskwren.api.common import envelope, reading, writing
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.people import accounts, imports, units

router = APIRouter(prefix="/api/v1", tags=["people"])
MAX_IMPORT_BYTES = 5_000_000


class GrantBody(BaseModel):
    role: str
    org_unit_id: int | None = None
    accept_limit: str | None = Field(default=None, max_length=40)

    def to_grant(self) -> Grant:
        return Grant(self.role, self.org_unit_id, self.accept_limit)


class NewAccount(BaseModel):
    email: str = Field(max_length=254)
    display_name: str = Field(max_length=200)
    title: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, max_length=1024)
    roles: list[GrantBody] = []
    unit_ids: list[int] = []


class AccountChanges(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    time_zone: str | None = Field(default=None, max_length=64)
    status: str | None = None


class Roles(BaseModel):
    roles: list[GrantBody]


class Units(BaseModel):
    unit_ids: list[int]


class NewPassword(BaseModel):
    new_password: str = Field(max_length=1024)


class NewUnit(BaseModel):
    name: str = Field(max_length=200)
    kind: str = Field(max_length=40)
    code: str | None = Field(default=None, max_length=60)
    parent_id: int | None = None


class UnitChanges(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    kind: str | None = Field(default=None, max_length=40)
    code: str | None = Field(default=None, max_length=60)
    parent_id: int | None = None
    status: str | None = None


def _card(account: Any) -> dict[str, Any]:
    """What anyone signed in may know about another person: enough to pick them."""
    return {
        "id": account.id,
        "display_name": account.display_name,
        "email": account.email,
        "title": account.title,
        "status": account.status,
    }


@router.get("/roles", summary="The roles and what each allows")
def list_roles() -> dict[str, Any]:
    return envelope(
        [
            {
                "role": role,
                "description": roles.DESCRIPTIONS[role],
                "grantable": role in roles.GRANTABLE,
            }
            for role in roles.ROLES
        ]
    )


@router.get("/accounts", summary="Find people")
def list_accounts(
    request: Request, q: str = Query("", max_length=100), status: str | None = None
) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        found = accounts.search(session, query=q, status=status)
        if principal.is_admin or principal.reads_all:
            return envelope([accounts.view(session, a) for a in found], count=len(found))
        return envelope([_card(a) for a in found if a.status != "disabled"])


@router.post("/accounts", status_code=201, summary="Add a person")
def create_account(request: Request, body: NewAccount) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        account = accounts.create(
            session,
            principal,
            email=body.email,
            display_name=body.display_name,
            title=body.title,
            password=body.password,
            grants=[g.to_grant() for g in body.roles],
        )
        if body.unit_ids:
            accounts.set_memberships(session, principal, account, body.unit_ids)
        return envelope(accounts.view(session, account))


@router.get("/accounts/{account_id}", summary="One person")
def show_account(request: Request, account_id: int) -> dict[str, Any]:
    principal = current(request)
    with reading(request) as session:
        account = accounts.get(session, account_id)
        if principal.is_admin or principal.reads_all or principal.account_id == account_id:
            return envelope(accounts.view(session, account))
        return envelope(_card(account))


@router.patch("/accounts/{account_id}", summary="Change a person's details")
def update_account(request: Request, account_id: int, body: AccountChanges) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        account = accounts.get(session, account_id)
        if principal.account_id != account_id and not principal.is_admin:
            raise PermissionDenied("You can change only your own details.")
        accounts.update(session, principal, account, body.model_dump(exclude_unset=True))
        return envelope(accounts.view(session, account))


@router.put("/accounts/{account_id}/roles", summary="Set a person's roles")
def set_roles(request: Request, account_id: int, body: Roles) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        account = accounts.get(session, account_id)
        accounts.set_grants(session, principal, account, [g.to_grant() for g in body.roles])
        return envelope(accounts.view(session, account))


@router.put("/accounts/{account_id}/units", summary="Set the units a person works in")
def set_units(request: Request, account_id: int, body: Units) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        account = accounts.get(session, account_id)
        accounts.set_memberships(session, principal, account, body.unit_ids)
        return envelope(accounts.view(session, account))


@router.post("/accounts/{account_id}/password", summary="Give a person a new password")
def reset_password(request: Request, account_id: int, body: NewPassword) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        account = accounts.get(session, account_id)
        if principal.account_id == account_id:
            raise Invalid(
                "Change your own password from your account menu.",
                {"new_password": "Use the change-password form, which asks for your current one."},
            )
        accounts.set_password(session, principal, account, body.new_password)
        return envelope({"changed": True})


@router.get("/units", summary="The organization's units, as a list and as a tree")
def list_units(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(
            {
                "units": [units.view(u) for u in units.all_units(session)],
                "tree": units.tree(session),
            }
        )


@router.post("/units", status_code=201, summary="Add a unit")
def create_unit(request: Request, body: NewUnit) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        unit = units.create(
            session,
            principal,
            name=body.name,
            kind=body.kind,
            code=body.code,
            parent_id=body.parent_id,
        )
        return envelope(units.view(unit))


@router.get("/units/{unit_id}", summary="One unit, with the units above it")
def show_unit(request: Request, unit_id: int) -> dict[str, Any]:
    with reading(request) as session:
        unit = units.get(session, unit_id)
        above = [units.view(u) for u in units.ancestors(session, unit_id)]
        return envelope({**units.view(unit), "ancestors": above})


@router.patch("/units/{unit_id}", summary="Rename, move, or close a unit")
def update_unit(request: Request, unit_id: int, body: UnitChanges) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        unit = units.get(session, unit_id)
        units.update(session, principal, unit, body.model_dump(exclude_unset=True))
        return envelope(units.view(unit))


async def _csv(request: Request) -> str:
    body = await request.body()
    if len(body) > MAX_IMPORT_BYTES:
        raise Invalid("The file is too large.", {"file": "Import at most 5 MB at a time."})
    try:
        return body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Invalid("The file cannot be read.", {"file": "Save it as CSV in UTF-8."}) from exc


def _import(request: Request, text: str, kind: str, dry_run: bool) -> dict[str, Any]:
    principal = current(request)
    run = imports.import_units if kind == "units" else imports.import_people
    with writing(request, principal.actor) as session:
        report = run(session, principal, text, dry_run=dry_run)
        if not report.applied:
            session.rollback()  # a dry run, or a file with problems, changes nothing
        return envelope(report.to_json())


@router.post("/imports/units", summary="Import units from CSV")
async def import_units(request: Request, dry_run: bool = True) -> dict[str, Any]:
    """Send the CSV as the request body. With ``dry_run`` (the default) nothing is changed."""
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(_import, request, await _csv(request), "units", dry_run)


@router.post("/imports/people", summary="Import people from CSV")
async def import_people(request: Request, dry_run: bool = True) -> dict[str, Any]:
    """Send the CSV as the request body. With ``dry_run`` (the default) nothing is changed."""
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(_import, request, await _csv(request), "people", dry_run)
