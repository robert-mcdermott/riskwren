"""The optional assistant (INT-07): off and absent by default; when on, it reads through the
API as the asker, is sent no data class the configuration keeps back, drafts only what a person
then makes, keeps to a daily limit and a time limit, and every exchange is in the history.

No provider is called: each test scripts one, in the protocol named in the configuration."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import replace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.api.app import create_app
from riskwren.assistant import providers, service
from riskwren.config import AssistantConfig, parse_config
from riskwren.core.errors import ConfigError
from riskwren.db.models import Event
from tests.conftest import Instance
from tests.people import People, email_of, sign_in

Clients = Callable[[str | None], TestClient]


class Script:
    """A provider that answers from a list, in the Chat Completions protocol, and keeps what
    it was sent."""

    def __init__(self, *answers: dict[str, Any]) -> None:
        self.answers = list(answers)
        self.sent: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(json.loads(request.content))
        if not self.answers:
            return httpx.Response(500, text="nothing more scripted")
        return httpx.Response(200, json=self.answers.pop(0))


def calls(*wanted: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"c{i}",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)},
                        }
                        for i, (name, args) in enumerate(wanted)
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 10},
    }


def says(text: str) -> dict[str, Any]:
    return {
        "choices": [{"finish_reason": "stop", "message": {"content": text}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
    }


ON = AssistantConfig(enabled=True, model="test-model", url="http://127.0.0.1:9/v1", daily_limit=3)


@pytest.fixture
def assisted(instance: Instance, people: People) -> Iterator[Callable[..., TestClient]]:
    """Clients of an app with the assistant on, each signed in as a role, answering from the
    script given."""
    with ExitStack() as stack:
        apps: dict[int, Any] = {}

        def make(role: str | None, script: Script | None = None, **settings: Any) -> TestClient:
            key = id(settings.get("config", ON))
            if key not in apps:
                config = replace(instance.config, assistant=settings.get("config", ON))
                apps[key] = create_app(config)
            app = apps[key]
            if script is not None:
                app.state.assistant_transport = httpx.MockTransport(script)
            client = stack.enter_context(TestClient(app, base_url="http://localhost"))
            return sign_in(client, email_of(role)) if role else client

        yield make


def test_while_off_the_assistant_is_not_there(as_role: Clients) -> None:
    manager = as_role("manager")
    assert manager.get("/api/v1/session").json()["data"]["assistant"] is False
    assert manager.post("/api/v1/assistant/summary", json={"ref": "RSK-0001"}).status_code in (
        404,
        405,
    )
    assert as_role("admin").get("/api/v1/admin/assistant").status_code == 404
    paths = manager.get("/api/openapi.json").json()["paths"]
    assert not [path for path in paths if "assistant" in path]


def test_a_key_in_the_file_is_refused(tmp_path: Any) -> None:
    with pytest.raises(ConfigError) as found:
        parse_config(
            {"assistant": {"enabled": True, "model": "m", "api_key": "sk-x"}}, base_dir=tmp_path
        )
    assert "never written in this file" in str(found.value.args)
    with pytest.raises(ConfigError):
        parse_config(
            {"assistant": {"enabled": True, "model": "m", "url": "http://models.example.org/v1"}},
            base_dir=tmp_path,
        )


def test_a_summary_reads_as_the_asker_and_is_recorded(
    assisted: Callable[..., TestClient], people: People, instance: Instance
) -> None:
    manager = assisted("manager")
    assert manager.get("/api/v1/session").json()["data"]["assistant"] is True
    risk = manager.post(
        "/api/v1/risks",
        json={
            "name": "Freezer failure in the biorepository",
            "category": "operations",
            "cause": "Aging compressors",
            "org_unit_id": people.units["HALE"],
        },
    ).json()["data"]
    sealed = manager.post(
        "/api/v1/systems",
        json={
            "name": "Sample tracking",
            "kind": "application",
            "org_unit_id": people.units["HALE"],
            "data_class": "confidential",
        },
    ).json()["data"]
    script = Script(
        calls(("get_record", {"ref": risk["ref"]}), ("get_record", {"ref": sealed["ref"]})),
        says(f"{risk['ref']} is a risk of losing specimens; it has no controls yet."),
    )
    asker = assisted("manager", script)
    done = asker.post("/api/v1/assistant/summary", json={"ref": risk["ref"]})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["answer"].startswith(risk["ref"])
    # What the tools gave the provider: the risk, read as the asker, and the confidential
    # system withheld, by its data class.
    told = [m["content"] for m in script.sent[1]["messages"] if m["role"] == "tool"]
    assert "Aging compressors" in told[0]
    assert "withheld" in told[1] and "Sample tracking" not in told[1]
    assert script.sent[0]["model"] == "test-model" and "tools" in script.sent[0]

    shown = assisted("admin").get("/api/v1/admin/assistant").json()["data"]
    entry = shown["log"][0]
    assert entry["status"] == "answered" and entry["task"] == "summarize"
    assert [used["name"] for used in entry["tools_used"]] == ["get_record", "get_record"]
    assert (entry["input_tokens"], entry["output_tokens"]) == (150, 30)
    assert shown["send"] == ["internal", "public"]
    with instance.db.read() as session:
        kept = session.scalars(
            select(Event).where(Event.subject_type == "assistant_exchange")
        ).all()
        assert {"assistant.ask", "assistant.answer"} <= {(e.context or {}).get("op") for e in kept}


def test_a_drafted_risk_waits_for_a_person(
    assisted: Callable[..., TestClient], people: People
) -> None:
    script = Script(
        calls(("search", {"query": "laptops lab"})),
        calls(
            (
                "draft_risk",
                {
                    "name": "Unmanaged laptops on the lab network",
                    "cause": "Visitors connect their own laptops",
                    "event": "Malware reaches the instruments",
                    "consequence": "Instrument time is lost",
                    "org_unit_id": people.units["HALE"],
                },
            )
        ),
        says("I drafted a risk about unmanaged laptops; open it to check and save it."),
    )
    steward = assisted("steward", script)
    short = steward.post("/api/v1/assistant/draft-risk", json={"description": "laptops"})
    assert short.status_code == 422
    done = steward.post(
        "/api/v1/assistant/draft-risk",
        json={
            "description": "Visiting researchers plug their own laptops into the lab network, and "
            "nothing checks them first.",
            "org_unit_id": people.units["HALE"],
        },
    )
    assert done.status_code == 200, done.text
    draft_id = done.json()["data"]["draft_id"]
    draft = steward.get(f"/api/v1/drafts/{draft_id}").json()["data"]
    assert draft["status"] == "waiting" and draft["source"] == "The assistant, for Steward Person"
    assert draft["values"]["name"] == "Unmanaged laptops on the lab network"
    # Only the tools for drafting a risk were offered.
    offered = {tool["function"]["name"] for tool in script.sent[0]["tools"]}
    assert offered == {"search", "get_record", "draft_risk"}


def test_the_daily_limit_and_a_failing_provider(
    assisted: Callable[..., TestClient], people: People
) -> None:
    risk = (
        assisted("manager")
        .post(
            "/api/v1/risks",
            json={"name": "A risk", "category": "operations", "org_unit_id": people.units["HALE"]},
        )
        .json()["data"]
    )
    script = Script(says("One."), says("Two."))
    member = assisted("manager", script)
    for _ in range(2):
        assert (
            member.post("/api/v1/assistant/summary", json={"ref": risk["ref"]}).status_code == 200
        )
    failed = member.post("/api/v1/assistant/summary", json={"ref": risk["ref"]})
    assert failed.status_code == 502 and "500" in failed.json()["detail"]
    refused = member.post("/api/v1/assistant/summary", json={"ref": risk["ref"]})
    assert refused.status_code == 429  # three asked today, the most this configuration allows
    log = assisted("admin").get("/api/v1/admin/assistant").json()["data"]["log"]
    assert [entry["status"] for entry in log[:4]] == ["refused", "failed", "answered", "answered"]


def test_the_time_limit(instance: Instance, people: People) -> None:
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return httpx.Response(200, json=says("Too late."))

    config = replace(instance.config, assistant=replace(ON, time_limit_seconds=1))
    app = create_app(config)
    app.state.assistant_transport = httpx.MockTransport(slow)
    with TestClient(app, base_url="http://localhost") as client:
        sign_in(client, email_of("manager"))
        risk = client.post(
            "/api/v1/risks",
            json={"name": "A risk", "category": "operations", "org_unit_id": people.units["HALE"]},
        ).json()["data"]
        late = client.post("/api/v1/assistant/summary", json={"ref": risk["ref"]})
        assert late.status_code == 502 and "longer than 1 seconds" in late.json()["detail"]


def test_a_token_asks_as_itself(assisted: Callable[..., TestClient], people: People) -> None:
    made = (
        assisted("admin")
        .post("/api/v1/admin/tokens", json={"name": "Ticket bot", "role": "auditor", "days": 30})
        .json()["meta"]["token"]
    )
    risk = (
        assisted("manager")
        .post(
            "/api/v1/risks",
            json={
                "name": "A risk the bot may read",
                "category": "operations",
                "org_unit_id": people.units["HALE"],
            },
        )
        .json()["data"]
    )
    script = Script(calls(("get_record", {"ref": risk["ref"]})), says("Read."))
    bot = assisted(None, script)
    bot.cookies.clear()
    bot.headers["Authorization"] = f"Bearer {made}"
    done = bot.post("/api/v1/assistant/summary", json={"ref": risk["ref"]})
    assert done.status_code == 200, done.text
    told = [m["content"] for m in script.sent[1]["messages"] if m["role"] == "tool"]
    assert "A risk the bot may read" in told[0]
    log = assisted("admin").get("/api/v1/admin/assistant").json()["data"]["log"]
    assert log[0]["asked_by"] == "API token Ticket bot"


def test_the_three_protocols() -> None:
    """Each provider is sent its own protocol and gives back the same reply."""
    seen: list[httpx.Request] = []

    def anthropic(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "stop_reason": "tool_use",
                "content": [
                    {"type": "text", "text": "Looking."},
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "search",
                        "input": {"query": "freezer"},
                    },
                ],
                "usage": {"input_tokens": 7, "output_tokens": 3},
            },
        )

    def bedrock(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "stopReason": "end_turn",
                "output": {"message": {"role": "assistant", "content": [{"text": "Done."}]}},
                "usage": {"inputTokens": 5, "outputTokens": 2},
            },
        )

    async def go() -> tuple[providers.Reply, providers.Reply, providers.Reply]:
        one = providers.make(
            replace(ON, provider="anthropic", url="https://api.example.org", key_env="TEST_KEY"),
            env={"TEST_KEY": "k1"},
            transport=httpx.MockTransport(anthropic),
        )
        two = providers.make(
            replace(ON, provider="bedrock", url=""),
            env={"AWS_ACCESS_KEY_ID": "AKIDEXAMPLE", "AWS_SECRET_ACCESS_KEY": "s"},
            transport=httpx.MockTransport(bedrock),
        )
        three = providers.make(
            replace(ON, provider="bedrock", url=""),
            env={"AWS_BEARER_TOKEN_BEDROCK": "b1"},
            transport=httpx.MockTransport(bedrock),
        )
        history = [
            {"role": "user", "text": "Hi"},
            {
                "role": "assistant",
                "text": "",
                "tool_calls": [{"id": "t0", "name": "search", "arguments": {"query": "x"}}],
            },
            {"role": "tool", "id": "t0", "name": "search", "content": "[]"},
        ]
        tool = [{"name": "search", "description": "d", "parameters": {"type": "object"}}]
        replies = (
            await one.complete("sys", history, tool),
            await two.complete("sys", history, tool),
            await three.complete("sys", history, None),
        )
        for each in (one, two, three):
            await each.close()
        return replies

    first, second, third = asyncio.run(go())
    assert first.text == "Looking." and first.tool_calls == [
        {"id": "t1", "name": "search", "arguments": {"query": "freezer"}}
    ]
    assert first.usage == {"input": 7, "output": 3}
    sent = json.loads(seen[0].content)
    assert seen[0].url == "https://api.example.org/v1/messages"
    assert seen[0].headers["x-api-key"] == "k1" and sent["system"] == "sys"
    assert sent["messages"][2]["content"][0]["type"] == "tool_result"
    assert second.text == "Done." and second.usage == {"input": 5, "output": 2}
    assert str(seen[1].url) == (
        "https://bedrock-runtime.us-east-1.amazonaws.com/model/test-model/converse"
    )
    assert seen[1].headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/")
    assert seen[2].headers["Authorization"] == "Bearer b1"
    assert "toolConfig" not in json.loads(seen[2].content) and third.text == "Done."


def test_withholding_reaches_inside_what_is_sent() -> None:
    kept = service.withhold(
        {
            "ref": "RSK-1",
            "name": "A",
            "systems": [
                {"ref": "SYS-1", "name": "Open", "data_class": "internal"},
                {"ref": "SYS-2", "name": "Shut", "data_class": "restricted"},
                {"ref": "SYS-3", "name": "Hidden", "restricted": True},
            ],
        },
        frozenset({"public", "internal"}),
    )
    assert [each.get("name") for each in kept["systems"]] == ["Open", None, None]
    assert "Shut" not in json.dumps(kept) and "Hidden" not in json.dumps(kept)
