"""Drafts and the tool server (INT-06): an assistant reads what its token may and drafts what a
person then makes, through the ordinary form, in the app."""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import Callable
from typing import Any

import httpx
from fastapi.testclient import TestClient

from riskwren.integration import mcp, tools
from tests.people import People

Clients = Callable[[str | None], TestClient]


def _token(as_role: Clients, role: str, **more: object) -> tuple[TestClient, str]:
    made = as_role("admin").post("/api/v1/admin/tokens", json={
        "name": f"Assistant as {role}", "role": role, "days": 30, **more})  # fmt: skip
    assert made.status_code == 201, made.text
    raw = made.json()["meta"]["token"]
    client = as_role(None)
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    client.headers["Authorization"] = f"Bearer {raw}"
    return client, raw


def test_a_draft_is_made_only_by_a_person_in_the_ordinary_form(
    as_role: Clients, people: People
) -> None:
    reader, _ = _token(as_role, "auditor")  # may only read, and may still draft
    hale = people.units["HALE"]
    assert reader.post("/api/v1/risks", json={"name": "x"}).status_code == 403
    wrong = reader.post("/api/v1/drafts", json={"kind": "risk", "values": {
        "cause": "c", "owner_id": 3}})  # fmt: skip
    assert wrong.status_code == 422
    assert {e["location"][0] for e in wrong.json()["errors"]} == {"values.owner_id", "values.name"}
    assert reader.post("/api/v1/drafts", json={"kind": "budget", "values": {}}).status_code == 422
    made = reader.post("/api/v1/drafts", json={"kind": "risk", "why": "From INC-0004's notes.",
        "values": {"name": "Unpatched imaging workstations", "cause": "Vendor-locked builds",
                   "event": "Ransomware spreads", "consequence": "Imaging stops",
                   "org_unit_id": hale}})  # fmt: skip
    assert made.status_code == 201, made.text
    draft = made.json()["data"]
    assert draft["status"] == "waiting" and draft["source"] == "Assistant as auditor"
    assert draft["can"]["use"] is False

    # Those who may add a risk in the unit see it; a member does not.
    steward = as_role("steward")
    shown = steward.get("/api/v1/drafts").json()["data"]
    assert [row["id"] for row in shown] == [draft["id"]] and shown[0]["can"]["use"]
    owed = steward.get("/api/v1/home").json()["data"]["items"]
    assert [item["href"] for item in owed if item["kind"] == "drafts"] == ["/drafts"]
    assert not [i for i in as_role("member").get("/api/v1/home").json()["data"]["items"]
                if i["kind"] == "drafts"]  # fmt: skip
    assert as_role("member").get(f"/api/v1/drafts/{draft['id']}").status_code == 404
    # A token never decides one; a record someone else made does not use it.
    assert (
        reader.post(f"/api/v1/drafts/{draft['id']}/use", json={"ref": "RSK-0001"}).status_code
        == 403
    )
    other = as_role("manager").post("/api/v1/risks", json={
        "name": "Someone else's", "category": "operations", "org_unit_id": hale})  # fmt: skip
    other = other.json()["data"]
    refused = steward.post(f"/api/v1/drafts/{draft['id']}/use", json={"ref": other["ref"]})
    assert refused.status_code == 422
    # The steward opens it in the ordinary form, changes it, and saves it.
    changed = {**draft["values"], "name": "Imaging workstations unpatched",
               "org_unit_id": hale, "category": "operations"}  # fmt: skip
    risk = steward.post("/api/v1/risks", json=changed)
    assert risk.status_code == 201, risk.text
    ref = risk.json()["data"]["ref"]
    used = steward.post(f"/api/v1/drafts/{draft['id']}/use", json={"ref": ref})
    assert used.status_code == 200, used.text
    assert used.json()["data"]["status"] == "used" and used.json()["data"]["record_ref"] == ref
    assert steward.post(f"/api/v1/drafts/{draft['id']}/use", json={"ref": ref}).status_code == 409
    assert steward.get("/api/v1/drafts").json()["data"] == []

    noise = reader.post("/api/v1/drafts", json={"kind": "control", "values": {
        "name": "Patch weekly", "org_unit_id": hale}}).json()["data"]  # fmt: skip
    assert steward.post(f"/api/v1/drafts/{noise['id']}/set-aside", json={}).status_code == 422
    aside = steward.post(f"/api/v1/drafts/{noise['id']}/set-aside",
                         json={"note": "We have one already."})  # fmt: skip
    assert aside.status_code == 200 and aside.json()["data"]["status"] == "set_aside"


class _Sync:
    """The tools' API, over a test client: the same calls the tool server makes."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        answer = self.client.get(path, params=params)
        if answer.status_code >= 400:
            raise tools.ToolError(answer.json().get("detail") or answer.json().get("title"))
        return answer.json()["data"]

    async def post(self, path: str, body: dict[str, Any]) -> Any:
        answer = self.client.post(path, json=body)
        if answer.status_code >= 400:
            raise tools.ToolError(answer.json().get("detail") or answer.json().get("title"))
        return answer.json()["data"]


def _ask(api: Any, method: str, params: dict[str, Any] | None = None, **kw: Any) -> Any:
    message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return asyncio.run(mcp.answer(api, message, **kw))


def test_the_tool_server_speaks_the_protocol(as_role: Clients, people: People) -> None:
    client, _ = _token(as_role, "auditor")
    api = _Sync(client)
    hello = _ask(api, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "test", "version": "1"}})  # fmt: skip
    assert hello["result"]["protocolVersion"] == "2025-06-18"
    assert hello["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert (
        asyncio.run(mcp.answer(api, {"jsonrpc": "2.0", "method": "notifications/initialized"}))
        is None
    )
    names = [tool["name"] for tool in _ask(api, "tools/list")["result"]["tools"]]
    assert names[:5] == ["search", "get_record", "risk_with_controls", "scope_readiness",
                         "whats_overdue"] and "draft_risk" in names  # fmt: skip
    reading = [tool["name"] for tool in _ask(api, "tools/list", drafting=False)["result"]["tools"]]
    assert not any(name.startswith("draft_") for name in reading)
    assert _ask(api, "nothing/here")["error"]["code"] == -32601

    made = as_role("manager").post("/api/v1/risks", json={
        "name": "Freezer failure in the biorepository", "category": "operations",
        "org_unit_id": people.units["HALE"]}).json()["data"]  # fmt: skip
    found = _ask(api, "tools/call", {"name": "search", "arguments": {"query": "freezer"}})
    assert not found["result"]["isError"]
    assert made["ref"] in found["result"]["content"][0]["text"]
    record = _ask(api, "tools/call", {"name": "get_record", "arguments": {"ref": made["ref"]}})
    assert json.loads(record["result"]["content"][0]["text"])["ref"] == made["ref"]
    both = _ask(
        api, "tools/call", {"name": "risk_with_controls", "arguments": {"ref": made["ref"]}}
    )
    assert set(json.loads(both["result"]["content"][0]["text"])) == {"risk", "controls"}
    missing = _ask(api, "tools/call", {"name": "get_record", "arguments": {"ref": "RSK-9999"}})
    assert missing["result"]["isError"]
    late = _ask(api, "tools/call", {"name": "whats_overdue", "arguments": {}})
    assert set(json.loads(late["result"]["content"][0]["text"])) == {"risks", "issues", "controls"}
    drafted = _ask(api, "tools/call", {"name": "draft_issue", "arguments": {
        "name": "Freezer alarms not tested", "summary": "No test since spring.",
        "why": "From the risk's notes."}})  # fmt: skip
    assert not drafted["result"]["isError"], drafted
    assert json.loads(drafted["result"]["content"][0]["text"])["kind"] == "issue"
    refused = _ask(api, "tools/call", {"name": "draft_issue", "arguments": {"name": "x"}},
                   drafting=False)  # fmt: skip
    assert refused["result"]["isError"]


def test_the_tool_server_over_lines_and_http(as_role: Clients) -> None:
    client, raw = _token(as_role, "auditor")
    api = mcp.HttpApi("https://testserver", raw, transport=httpx.ASGITransport(app=client.app))
    lines = io.StringIO("\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
        "not json",
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "whats_overdue", "arguments": {"kind": "issues"}}}),
    ]) + "\n")  # fmt: skip
    out = io.StringIO()

    async def go() -> None:
        await mcp.serve(api, lines, out)
        await api.close()

    asyncio.run(go())
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert replies[0] == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert replies[1]["error"]["code"] == -32700
    assert replies[2]["result"]["isError"] is False
    assert json.loads(replies[2]["result"]["content"][0]["text"]) == {"issues": []}
    bad = mcp.HttpApi(
        "https://testserver", "rwt_nothing", transport=httpx.ASGITransport(app=client.app)
    )
    refused = asyncio.run(mcp.answer(bad, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                           "params": {"name": "search", "arguments": {
                                               "query": "anything"}}}))  # fmt: skip
    assert refused["result"]["isError"] and "token" in refused["result"]["content"][0]["text"]


def test_the_tool_server_wants_a_token_from_the_environment(monkeypatch: Any, capsys: Any) -> None:
    from riskwren.cli import main

    monkeypatch.delenv("RISKWREN_TOKEN", raising=False)
    monkeypatch.delenv("RISKWREN_URL", raising=False)
    assert main(["tools"]) == 1
    assert "--url" in capsys.readouterr().err
    assert main(["tools", "--url", "https://grc.example.org"]) == 1
    assert "RISKWREN_TOKEN" in capsys.readouterr().err
    monkeypatch.setenv("RISKWREN_TOKEN", "rwt_example")
    assert main(["tools", "--url", "http://grc.example.org"]) == 1
    assert "https://" in capsys.readouterr().err
    called: list[tuple[str, bool]] = []
    monkeypatch.setattr(mcp, "run", lambda url, token, drafting: called.append((url, drafting)))
    assert main(["tools", "--url", "http://localhost:8000", "--no-drafts"]) == 0
    assert called == [("http://localhost:8000", False)]
