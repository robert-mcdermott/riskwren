"""The seven roles (PLT-04). ``member`` is held by everyone who can sign in and is never granted.

The roles follow the three lines: owners, stewards, and leaders are the first line and act on
their own unit's records; managers and assessors are the second and run the program; auditors
are the third and read everything.
"""

from __future__ import annotations

ADMIN = "admin"
MANAGER = "manager"
ASSESSOR = "assessor"
AUDITOR = "auditor"
LEADER = "leader"
STEWARD = "steward"
MEMBER = "member"

GRANTABLE = (ADMIN, MANAGER, ASSESSOR, AUDITOR, LEADER, STEWARD)
ROLES = (*GRANTABLE, MEMBER)

# Roles that must name the unit they are for, and roles that may be limited to one.
UNIT_REQUIRED = (LEADER, STEWARD)
UNIT_OPTIONAL = (MANAGER, ASSESSOR)
SCOPED = (*UNIT_REQUIRED, *UNIT_OPTIONAL)

DESCRIPTIONS = {
    ADMIN: "Manage accounts, sign-in settings, branding, and system configuration",
    MANAGER: "Run the program: edit any record, and manage the taxonomy, scoring, and libraries",
    ASSESSOR: "Assess risks and rate controls, across the organization or within a unit",
    AUDITOR: "Read every record and the full history; change nothing",
    LEADER: "See a unit and everything beneath it, and accept its risks up to a limit",
    STEWARD: "Keep the records of a unit and those beneath it complete and current",
    MEMBER: "See and do what is assigned to them, and manage the records they own",
}
