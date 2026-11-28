"""The person, or the command, on whose behalf something is being done."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from riskwren.access import roles
from riskwren.events.actor import Actor

EVERYWHERE = None  # a scoped role held with no unit covers the whole organization


@dataclass(frozen=True)
class Grant:
    role: str
    org_unit_id: int | None = None
    # For a leader: the key of the highest rating they may accept.
    accept_limit: str | None = None


@dataclass(frozen=True)
class Principal:
    account_id: int | None
    name: str
    email: str = ""
    grants: tuple[Grant, ...] = ()
    # For each scoped role held: the units it covers, with every unit beneath them, worked
    # out at sign-in. ``None`` means the whole organization.
    coverage: Mapping[str, frozenset[int] | None] = field(default_factory=dict, hash=False)
    # Units the person works in, with every unit beneath them (for what a member may see).
    member_units: frozenset[int] = frozenset()
    csrf_token: str = ""
    has_password: bool = True
    session_id: int | None = None
    command: bool = field(default=False)
    # Leads every unit there is, as the head of the organization does: worked out at sign-in.
    leads_all: bool = False
    # Reads the leadership reports by the program's choice of who does: worked out at sign-in.
    report_reader: bool = False
    signed_in_at: datetime | None = None  # when this session began
    token_id: int | None = None  # an API token acting as a role, not a person
    read_only: bool = False  # a token that may only read

    @classmethod
    def for_command(cls, label: str = "Command line") -> Principal:
        """Someone at the server's own command line: trusted with everything."""
        return cls(
            None,
            label,
            grants=(Grant(roles.ADMIN), Grant(roles.MANAGER)),
            coverage={roles.MANAGER: EVERYWHERE},
            command=True,
        )

    @property
    def person(self) -> int | None:
        """The account of the person acting, or None for a command or a token."""
        return self.account_id if self.account_id is not None and self.account_id > 0 else None

    @property
    def actor(self) -> Actor:
        if self.token_id is not None:
            return Actor("token", None, self.name)
        if self.command or self.account_id is None:
            return Actor.command(self.name)
        return Actor.account(self.account_id, self.name)

    def has(self, role: str) -> bool:
        return role == roles.MEMBER or any(grant.role == role for grant in self.grants)

    @property
    def role_names(self) -> list[str]:
        held = {grant.role for grant in self.grants}
        return [role for role in roles.ROLES if role in held or role == roles.MEMBER]

    def covers(self, role: str, org_unit_id: int | None) -> bool:
        """Whether this person holds ``role`` for the unit, directly or from above."""
        if role not in self.coverage:
            return False
        units = self.coverage[role]
        return units is EVERYWHERE or (org_unit_id is not None and org_unit_id in units)

    def everywhere(self, role: str) -> bool:
        return role in self.coverage and self.coverage[role] is EVERYWHERE

    def units_for(self, *held: str) -> frozenset[int] | None:
        """The units these roles cover between them. ``None`` means every unit."""
        covered: set[int] = set()
        for role in held:
            if role in self.coverage:
                units = self.coverage[role]
                if units is EVERYWHERE:
                    return None
                covered |= units
        return frozenset(covered)

    @property
    def is_admin(self) -> bool:
        return self.has(roles.ADMIN)

    @property
    def manages(self) -> bool:
        """Runs the program for the whole organization."""
        return self.everywhere(roles.MANAGER)

    @property
    def manages_somewhere(self) -> bool:
        return roles.MANAGER in self.coverage

    @property
    def configures(self) -> bool:
        """May shape the program: taxonomy, scoring method, appetite, vocabularies."""
        return self.manages or self.is_admin

    @property
    def reads_all(self) -> bool:
        return self.manages or self.is_admin or self.has(roles.AUDITOR)

    @property
    def reads_oversight(self) -> bool:
        """May read internal audit's universe and plans: they are the organization's, so
        those who read everything, and those who lead all of it."""
        return self.reads_all or self.leads_all or self.everywhere(roles.LEADER)

    @property
    def reads_leadership(self) -> bool:
        """May read the leadership reports: those who read everything and those who lead all
        of it, and whomever else the program has chosen."""
        return self.reads_oversight or self.report_reader

    @property
    def edits_all(self) -> bool:
        """Administration is not judgment: only a manager for the whole organization."""
        return self.manages

    @property
    def assesses(self) -> bool:
        return self.manages_somewhere or roles.ASSESSOR in self.coverage

    @property
    def stewards(self) -> bool:
        return roles.STEWARD in self.coverage

    @property
    def leads(self) -> bool:
        return roles.LEADER in self.coverage

    def manages_unit(self, org_unit_id: int | None) -> bool:
        return self.covers(roles.MANAGER, org_unit_id)

    def stewards_unit(self, org_unit_id: int | None) -> bool:
        return self.covers(roles.STEWARD, org_unit_id)

    def leads_unit(self, org_unit_id: int | None) -> bool:
        return self.covers(roles.LEADER, org_unit_id)

    def assesses_unit(self, org_unit_id: int | None) -> bool:
        return self.covers(roles.ASSESSOR, org_unit_id) or self.manages_unit(org_unit_id)

    def permissions(self) -> dict[str, bool]:
        """What the web app needs to decide which parts of itself to show."""
        return {
            "admin": self.is_admin,
            "manage": self.manages,
            "configure": self.configures,
            "read_all": self.reads_all,
            "edit_all": self.edits_all,
            "assess": self.assesses,
            "steward": self.stewards or self.manages_somewhere,
            "lead": self.leads,
            "oversight": self.reads_oversight,
            "leadership": self.reads_leadership,
            "audit": self.has(roles.AUDITOR),
        }

    def to_json(self) -> dict[str, Any]:
        return {
            "account": {"id": self.account_id, "name": self.name, "email": self.email},
            "roles": self.role_names,
            "permissions": self.permissions(),
            "units": {
                role: None if units is EVERYWHERE else sorted(units)
                for role, units in self.coverage.items()
            },
            "member_units": sorted(self.member_units),
            "has_password": self.has_password,
            "csrf_token": self.csrf_token,
        }
