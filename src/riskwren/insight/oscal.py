"""A scope in the Open Security Controls Assessment Language (OSCAL): its control
implementations as a system security plan, and its open issues as a plan of action and
milestones (OSCAL 1.1.2).

Every identifier is a name-based UUID made from the installation's references, so exporting
the same scope twice gives the same identifiers, and a tool that reads both can tell what
changed. A requirement's OSCAL control id is its code as the catalog labels it, lowercased,
with an enhancement's number after a dot (``AC-2(1)`` is ``ac-2.1``), which is how the
published catalogs name them; the code as written is kept beside it as its label.

What is RiskWren's own and has no place in the model (a severity, a due date, a state of
readiness) is carried as a property in RiskWren's namespace, which a reader may ignore.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from riskwren import __version__
from riskwren.access.principal import Principal
from riskwren.compliance import issues, scopes
from riskwren.core.clock import isoformat, utc_now
from riskwren.db.models import Scope
from riskwren.inventory import records

VERSION = "1.1.2"
NS = "urn:riskwren:oscal"
SPACE = uuid.UUID("6f1c7f0e-5d0a-4c8e-9a3b-2f0f2b7a9c11")
STATUS = {  # readiness here → OSCAL implementation status
    "verified": "implemented",
    "in_place": "implemented",
    "failing": "partial",
    "planned": "planned",
    "gap": "planned",
    "excepted": "alternative",
    "excluded": "not-applicable",
}


def uid(*parts: str) -> str:
    return str(uuid.uuid5(SPACE, "/".join(parts)))


def control_id(code: str) -> str:
    """``AC-2(1)`` → ``ac-2.1``; an id must start with a letter or an underscore."""
    found = re.sub(r"\((\w+)\)", r".\1", code.strip()).lower()
    found = re.sub(r"[^\w.\-]", "_", found)
    return found if re.match(r"^[^\W\d]", found) else f"_{found}"


def _prop(name: str, value: Any, *, ours: bool = True) -> dict[str, Any]:
    prop: dict[str, Any] = {"name": name, "value": str(value)}
    if ours:
        prop["ns"] = NS
    return prop


def _metadata(session: Session, scope: Scope, title: str) -> dict[str, Any]:
    owners = records.owners_of(session, scopes.SCOPE, [scope.id]).get(scope.id, [])
    parties = [
        {"uuid": uid("party", str(owner["account_id"])), "type": "person", "name": owner["name"]}
        for owner in owners
    ]
    metadata: dict[str, Any] = {
        "title": title,
        "last-modified": isoformat(utc_now()),
        "version": str(scope.version),
        "oscal-version": VERSION,
        "props": [_prop("generator", f"RiskWren {__version__}")],
        "roles": [{"id": "system-owner", "title": "System Owner"}],
    }
    if parties:
        metadata["parties"] = parties
        metadata["responsible-parties"] = [
            {"role-id": "system-owner", "party-uuids": [party["uuid"] for party in parties]}
        ]
    return metadata


def _statement_text(control: dict[str, Any]) -> str:
    return f"{control['ref']} {control['name']}"


def ssp(session: Session, principal: Principal, scope: Scope, framework_key: str) -> dict[str, Any]:
    """The scope's system security plan against one framework it is held to."""
    statement = scopes.statement(session, principal, scope, framework_key)
    framework = statement["framework"]
    used = {
        view["control"]["ref"]: view
        for view in scopes.implementations(session, principal, scope)["controls"]
    }
    members = scopes.members_of(session, principal, scope)
    this_system = uid("scope", scope.ref, "this-system")
    information = [
        {
            "uuid": uid("information", chip["ref"]),
            "title": chip["name"],
            "description": f"{chip['ref']} {chip['name']}, as recorded in RiskWren.",
        }
        for chip in members["records"]
        if chip.get("type") == "information"
    ] or [
        {
            "uuid": uid("information", scope.ref, "unrecorded"),
            "title": "Information in the scope",
            "description": "No information asset is recorded as part of this scope.",
        }
    ]
    implemented = []
    for row in statement["requirements"]:
        state = row["state"]
        by_components = []
        for control in row["controls"]:
            view = used.get(control["ref"], {})
            provider = view.get("provider") or {}
            words = (
                view.get("statement")
                or provider.get("statement")
                or (view.get("control") or {}).get("statement")
                or "No implementation statement is recorded."
            )
            entry: dict[str, Any] = {
                "component-uuid": this_system,
                "uuid": uid("by", scope.ref, framework["key"], row["code"], control["ref"]),
                "description": f"{_statement_text(control)}: {words}",
                "props": [
                    _prop("control", control["ref"]),
                    _prop("readiness", control["readiness"]),
                    _prop(
                        "control-origination",
                        "inherited" if control["inheritance"] != "none" else "sp-system",
                        ours=False,
                    ),
                ],
                "implementation-status": {"state": STATUS.get(control["readiness"], "planned")},
            }
            if view.get("responsibility"):
                entry["props"].append(_prop("responsibility", view["responsibility"]))
            if control.get("provider"):
                entry["props"].append(_prop("provided-by", control["provider"]["ref"]))
            by_components.append(entry)
        if not by_components:
            remark = (
                f"Not applicable here: {row['reason']}"
                if state == "excluded" and row.get("reason")
                else "Not applicable here."
                if state == "excluded"
                else "No control used in this scope answers this requirement."
            )
            by_components.append(
                {
                    "component-uuid": this_system,
                    "uuid": uid("by", scope.ref, framework["key"], row["code"], "none"),
                    "description": remark,
                    "implementation-status": {"state": STATUS.get(state, "planned")},
                }
            )
        implemented.append(
            {
                "uuid": uid("requirement", scope.ref, framework["key"], row["code"]),
                "control-id": control_id(row["code"]),
                "props": [_prop("label", row["code"], ours=False), _prop("readiness", state)],
                "by-components": by_components,
            }
        )
    baseline = statement["baseline"]
    resource = uid("framework", framework["key"], baseline["key"] if baseline else "")
    profile = framework["title"] + (f", {baseline['title']} baseline" if baseline else "")
    return {
        "system-security-plan": {
            "uuid": uid("ssp", scope.ref, framework["key"]),
            "metadata": _metadata(
                session, scope, f"System security plan: {scope.name} against {framework['title']}"
            ),
            "import-profile": {"href": f"#{resource}"},
            "system-characteristics": {
                "system-ids": [
                    {
                        "identifier-type": "https://ietf.org/rfc/rfc4122",
                        "id": uid("scope", scope.ref),
                    }
                ],
                "system-name": scope.name,
                "system-name-short": scope.ref,
                "description": scope.summary or scope.name,
                "system-information": {"information-types": information},
                "status": {"state": "operational" if scope.status == "active" else "disposition"},
                "authorization-boundary": {
                    "description": scope.boundary or "The boundary is not described."
                },
            },
            "system-implementation": {
                "users": [
                    {
                        "uuid": uid("user", scope.ref, "system-owner"),
                        "title": "System Owner",
                        "role-ids": ["system-owner"],
                    }
                ],
                "components": [
                    {
                        "uuid": this_system,
                        "type": "this-system",
                        "title": scope.name,
                        "description": scope.summary or scope.name,
                        "status": {"state": "operational"},
                    }
                ],
            },
            "control-implementation": {
                "description": (
                    f"How {scope.name} meets {profile}: each requirement that applies, the "
                    "controls that answer it here, and where each stands; and each left out, "
                    "with the reason."
                ),
                "implemented-requirements": implemented,
            },
            "back-matter": {
                "resources": [
                    {
                        "uuid": resource,
                        "title": profile,
                        "props": [
                            _prop("framework", framework["key"]),
                            _prop("framework-version", framework.get("version") or ""),
                        ],
                    }
                ]
            },
        }
    }


def poam(session: Session, principal: Principal, scope: Scope) -> dict[str, Any]:
    """The open issues that bear on the scope, as a plan of action and milestones."""
    plan = issues.plan_of_action(session, principal, scope)
    items = []
    for card in plan["issues"]:
        props = [
            _prop("issue", card["ref"]),
            _prop("severity", card["severity"]),
            _prop("due-on", card["due_on"]),
            _prop("status", card["status"]),
        ]
        steps = [
            f"{action['title']} (due {action['due_on']}, {action['status']})"
            for action in card.get("actions", [])
        ]
        description = card.get("summary") or card["name"]
        if steps:
            description += " Milestones: " + "; ".join(steps) + "."
        items.append(
            {
                "uuid": uid("poam-item", scope.ref, card["ref"]),
                "title": f"{card['ref']} {card['name']}",
                "description": description,
                "props": props,
            }
        )
    return {
        "plan-of-action-and-milestones": {
            "uuid": uid("poam", scope.ref),
            "metadata": _metadata(session, scope, f"Plan of action and milestones: {scope.name}"),
            "system-id": {
                "identifier-type": "https://ietf.org/rfc/rfc4122",
                "id": uid("scope", scope.ref),
            },
            "poam-items": items,
        }
    }
