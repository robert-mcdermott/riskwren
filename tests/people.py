"""A small organization with one person in each role, for tests that need people."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from riskwren.access.principal import Grant, Principal
from riskwren.auth.sessions import CSRF_HEADER
from riskwren.db.engine import Database
from riskwren.people import accounts, units

PASSWORD = "a long enough passphrase"
ME = Principal.for_command("Tester")
ROLES = ("admin", "manager", "assessor", "auditor", "leader", "steward", "member")


def email_of(role: str) -> str:
    return f"{role}@northmere.example"


@dataclass
class People:
    units: dict[str, int] = field(default_factory=dict)
    accounts: dict[str, int] = field(default_factory=dict)


def seed(db: Database) -> People:
    """Northmere → Immunology → Hale Lab, and Cancer Biology beside Immunology.
    The steward and the leader are for Immunology; the member works in the Hale Lab."""
    people = People()
    with db.write(ME.actor) as session:
        org = units.create(session, ME, name="Northmere Institute", kind="organization", code="NMI")
        immuno = units.create(
            session, ME, name="Immunology", kind="division", code="IMM", parent_id=org.id
        )
        hale = units.create(
            session, ME, name="Hale Lab", kind="lab", code="HALE", parent_id=immuno.id
        )
        cancer = units.create(
            session, ME, name="Cancer Biology", kind="division", code="CANCER", parent_id=org.id
        )
        people.units = {"NMI": org.id, "IMM": immuno.id, "HALE": hale.id, "CANCER": cancer.id}
        grants = {
            "admin": [Grant("admin")],
            "manager": [Grant("manager")],
            "assessor": [Grant("assessor")],
            "auditor": [Grant("auditor")],
            "leader": [Grant("leader", org_unit_id=immuno.id, accept_limit="high")],
            "steward": [Grant("steward", org_unit_id=immuno.id)],
            "member": [],
        }
        for role in ROLES:
            account = accounts.create(
                session, ME, email=email_of(role), display_name=f"{role.title()} Person",
                password=PASSWORD, grants=grants[role],
            )  # fmt: skip
            people.accounts[role] = account.id
        accounts.set_memberships(
            session, ME, accounts.get(session, people.accounts["member"]), [hale.id]
        )
    return people


def sign_in(client: TestClient, email: str, password: str = PASSWORD) -> TestClient:
    response = client.post("/api/v1/session", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    client.headers[CSRF_HEADER] = response.json()["data"]["csrf_token"]
    return client
