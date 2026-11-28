"""The tools an assistant may use (INT-06, INT-07): the same set for the tool server another
assistant talks to and for RiskWren's own assistant.

Every tool calls RiskWren's own API, as whoever is asking: with their token for the tool
server, with their session for the assistant in the app. So a tool sees only what the asker
may, and the ordinary rules decide everything. The tools read, or draft; a draft is kept for a
person to open in the ordinary form, and makes nothing by itself.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

LIMIT = 24_000  # characters of a tool's answer, so one record cannot fill a conversation


class ToolError(Exception):
    """Something the asker should be told, such as a record that is not found."""


class Api(Protocol):
    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any: ...

    async def post(self, path: str, body: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    schema: dict[str, Any]
    run: Callable[[Api, dict[str, Any]], Awaitable[Any]]
    drafts: bool = False  # proposes a draft, rather than only reading
    required: tuple[str, ...] = field(default=())

    def listed(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {"type": "object", "properties": self.schema,
                            "required": list(self.required), "additionalProperties": False},
            "annotations": {"readOnlyHint": not self.drafts, "openWorldHint": False},
        }  # fmt: skip


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"Give {name} as text.")
    return value.strip()


def _ref(args: dict[str, Any]) -> str:
    ref = _text(args.get("ref"), "the reference").upper()
    if len(ref) > 32 or not all(ch.isalnum() or ch == "-" for ch in ref):
        raise ToolError("A reference looks like RSK-0042.")
    return ref


async def _search(api: Api, args: dict[str, Any]) -> Any:
    params: dict[str, Any] = {"q": _text(args.get("query"), "what to look for"), "limit": 8}
    if args.get("type"):
        params["type"] = _text(args["type"], "the kind")
    found = await api.get("/api/v1/search", params)
    return [
        {"type": group["type"], "ref": item["ref"], "name": item["name"],
         "status": item.get("status"), "summary": item.get("summary")}
        for group in found.get("groups", []) for item in group["items"]
    ]  # fmt: skip


async def _where(api: Api, ref: str) -> str:
    found = await api.get("/api/v1/search", {"q": ref, "limit": 1})
    for group in found.get("groups", []):
        if any(item["ref"] == ref for item in group["items"]):
            return str(group["path"])
    raise ToolError(f"There is no {ref} that you may see.")


async def _record(api: Api, args: dict[str, Any]) -> Any:
    ref = _ref(args)
    return await api.get(f"/api/v1/{await _where(api, ref)}/{ref}")


async def _risk(api: Api, args: dict[str, Any]) -> Any:
    ref = _ref(args)
    risk = await api.get(f"/api/v1/risks/{ref}")
    controls = await api.get(f"/api/v1/risks/{ref}/controls")
    return {"risk": risk, "controls": controls}


async def _scope(api: Api, args: dict[str, Any]) -> Any:
    ref = _ref(args)
    scope = await api.get(f"/api/v1/scopes/{ref}")
    plan = await api.get(f"/api/v1/scopes/{ref}/plan-of-action")
    issues = plan.get("issues", []) if isinstance(plan, dict) else []
    return {"scope": scope, "open_issues": [
        {"ref": each.get("ref"), "name": each.get("name"), "severity": each.get("severity"),
         "due_on": each.get("due_on")} for each in issues]}  # fmt: skip


OVERDUE = {
    "risks": ("/api/v1/risks", {"overdue": "true"}),
    "issues": ("/api/v1/issues", {"overdue": "true"}),
    "controls": ("/api/v1/controls", {"stale": "true"}),
}


async def _overdue(api: Api, args: dict[str, Any]) -> Any:
    kinds = [args["kind"]] if args.get("kind") else list(OVERDUE)
    out: dict[str, Any] = {}
    for kind in kinds:
        if kind not in OVERDUE:
            raise ToolError(f"Ask about one of: {', '.join(OVERDUE)}.")
        path, params = OVERDUE[kind]
        rows = await api.get(path, {**params, "limit": 50})
        out[kind] = [{"ref": row.get("ref"), "name": row.get("name"),
                      "status": row.get("status"), "unit": row.get("org_unit_id")}
                     for row in rows]  # fmt: skip
    return out


def _drafter(kind: str, fields: tuple[str, ...]) -> Callable[[Api, dict[str, Any]], Awaitable[Any]]:
    async def run(api: Api, args: dict[str, Any]) -> Any:
        values = {key: args[key] for key in fields if args.get(key) not in (None, "")}
        if args.get("org_unit_id") is not None:
            values["org_unit_id"] = args["org_unit_id"]
        made = await api.post("/api/v1/drafts", {"kind": kind, "values": values,
                                                 "why": args.get("why")})  # fmt: skip
        return {"draft": made.get("id"), "kind": kind, "status": made.get("status"),
                "told": "Kept as a draft. Nothing is made until a person opens it in RiskWren, "
                        "changes what they like, and saves it."}  # fmt: skip

    return run


_STR = {"type": "string"}
_UNIT = {"type": "integer", "description": "The unit it belongs to, by id, if known"}
_WHY = {"type": "string", "description": "What the draft rests on: who said what, where"}

TOOLS: tuple[Tool, ...] = (
    Tool("search", "Search every kind of record you may see, by words or a reference.",
         {"query": _STR, "type": {"type": "string",
                                  "description": "Only this kind, such as risk or control"}},
         _search, required=("query",)),
    Tool("get_record", "One record in full, by its reference, such as RSK-0042 or CTL-0007.",
         {"ref": _STR}, _record, required=("ref",)),
    Tool("risk_with_controls", "A risk, with its ratings and the controls that bear on it.",
         {"ref": _STR}, _risk, required=("ref",)),
    Tool("scope_readiness", "A scope: what it is held to, how far it meets it, and the open "
         "issues that bear on it.", {"ref": _STR}, _scope, required=("ref",)),
    Tool("whats_overdue", "Risks whose review is overdue, issues past their date, and controls "
         "whose rating has gone stale.",
         {"kind": {"type": "string", "enum": list(OVERDUE)}}, _overdue),
    Tool("draft_risk", "Draft a risk for a person to open, change, and save. Write it as a "
         "cause, an event, and a consequence.",
         {"name": _STR, "cause": _STR, "event": _STR, "consequence": _STR,
          "category": {"type": "string", "description": "A risk category's key, if known"},
          "org_unit_id": _UNIT, "why": _WHY},
         _drafter("risk", ("name", "cause", "event", "consequence", "category")),
         drafts=True, required=("name",)),
    Tool("draft_issue", "Draft an issue, something wrong that must be put right, for a person "
         "to open, change, and save.",
         {"name": _STR, "summary": _STR,
          "severity": {"type": "string",
                       "description": "The program's severity, such as high or moderate"},
          "org_unit_id": _UNIT, "why": _WHY},
         _drafter("issue", ("name", "summary", "severity")), drafts=True, required=("name",)),
    Tool("draft_control", "Draft a control for a person to open, change, and save: one "
         "sentence of who does what, and how often.",
         {"name": _STR, "statement": _STR, "objective": _STR,
          "kind": {"type": "string",
                   "description": "The program's kind of control, such as preventive"},
          "org_unit_id": _UNIT, "why": _WHY},
         _drafter("control", ("name", "statement", "objective", "kind")),
         drafts=True, required=("name",)),
)  # fmt: skip
BY_NAME = {tool.name: tool for tool in TOOLS}


def offered(*, drafting: bool = True) -> tuple[Tool, ...]:
    return tuple(tool for tool in TOOLS if drafting or not tool.drafts)


async def call(api: Api, name: str, args: dict[str, Any] | None, *, drafting: bool = True) -> str:
    """Run a tool and give its answer as text, cut to ``LIMIT``. Raises ToolError."""
    tool = BY_NAME.get(name)
    if tool is None or (tool.drafts and not drafting):
        raise ToolError(f"There is no tool {name}.")
    if args is not None and not isinstance(args, dict):
        raise ToolError("Give the tool's arguments by name.")
    answer = await tool.run(api, args or {})
    text = json.dumps(answer, default=str, separators=(",", ":"))
    return text if len(text) <= LIMIT else text[:LIMIT] + "… (cut short)"
