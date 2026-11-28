"""The three protocols the assistant can speak, over plain HTTP, with no vendor library.

* ``openai``: any endpoint that speaks the Chat Completions API: the official service,
  gateways, and servers on the organization's own machines, such as Ollama or vLLM. ``url`` is
  the API's root, such as ``http://127.0.0.1:11434/v1``.
* ``anthropic``: any endpoint that speaks the Messages API. ``url`` is its root.
* ``bedrock``: Amazon Bedrock's Converse API, with an Amazon Bedrock API key in
  ``AWS_BEARER_TOKEN_BEDROCK`` (or the variable ``key_env`` names), or with access keys from the
  environment, signed with Signature Version 4.

Each takes the same conversation and tools and gives the same reply, so nothing else knows which
is in use. A message is ``{"role": "user", "text"}``, ``{"role": "assistant", "text",
"tool_calls"}``, or ``{"role": "tool", "id", "name", "content"}``; a tool is ``{"name",
"description", "parameters"}``. Keys are read from the environment when a call is made, never
from the configuration file.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

from riskwren.assistant.sigv4 import sign
from riskwren.config import AssistantConfig
from riskwren.core.errors import RiskWrenError


class ProviderError(RiskWrenError):
    """The provider could not be reached, refused, or answered something unreadable."""


@dataclass
class Reply:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stop: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


def _arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        found = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProviderError("The model sent tool arguments that are not JSON.") from exc
    return found if isinstance(found, dict) else {}


class Provider:
    name = ""

    def __init__(
        self,
        config: AssistantConfig,
        env: Mapping[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.env = os.environ if env is None else env
        self.client = httpx.AsyncClient(timeout=config.time_limit_seconds, transport=transport)

    async def close(self) -> None:
        await self.client.aclose()

    def _key(self) -> str | None:
        return self.env.get(self.config.key_env) if self.config.key_env else None

    async def _post(self, url: str, body: dict[str, Any], headers: dict[str, str]) -> Any:
        try:
            request = self.client.build_request("POST", url, json=body, headers=headers)
            response = await self.client.send(self._sign(request))
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"{self.name}: could not reach {url}: {type(exc).__name__}"
            ) from exc
        if response.status_code >= 400:
            said = response.text[:300].replace("\n", " ")
            raise ProviderError(f"{self.name}: {response.status_code} from {url}: {said}")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError(f"{self.name}: an answer that is not JSON") from exc

    def _sign(self, request: httpx.Request) -> httpx.Request:
        return request

    async def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> Reply:
        raise NotImplementedError


class OpenAIProvider(Provider):
    """The Chat Completions API."""

    name = "openai"

    @staticmethod
    def _messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["id"], "content": m["content"]})
            elif m["role"] == "assistant" and m.get("tool_calls"):
                out.append({"role": "assistant", "content": m.get("text") or None,
                            "tool_calls": [{"id": c["id"], "type": "function",
                                            "function": {"name": c["name"],
                                                         "arguments": json.dumps(c["arguments"])}}
                                           for c in m["tool_calls"]]})  # fmt: skip
            else:
                out.append({"role": m["role"], "content": m.get("text") or ""})
        return out

    async def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> Reply:
        body: dict[str, Any] = {
            "model": self.config.model, "messages": self._messages(system, messages),
            "max_tokens": self.config.max_tokens, "temperature": self.config.temperature,
        }  # fmt: skip
        if tools:
            body["tools"] = [{"type": "function", "function": tool} for tool in tools]
        headers = {"Authorization": f"Bearer {key}"} if (key := self._key()) else {}
        said = await self._post(f"{self.config.base_url}/chat/completions", body, headers)
        try:
            choice = said["choices"][0]
            message = choice.get("message") or {}
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("openai: an answer with no choice in it") from exc
        usage = said.get("usage") or {}
        return Reply(
            text=message.get("content") or "",
            tool_calls=[{"id": call.get("id") or f"call_{i}",
                         "name": (call.get("function") or {}).get("name", ""),
                         "arguments": _arguments((call.get("function") or {}).get("arguments"))}
                        for i, call in enumerate(message.get("tool_calls") or [])],
            stop=choice.get("finish_reason"),
            usage={"input": usage.get("prompt_tokens", 0),
                   "output": usage.get("completion_tokens", 0)},
        )  # fmt: skip


class AnthropicProvider(Provider):
    """The Messages API."""

    name = "anthropic"

    @staticmethod
    def _messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if m["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": m["id"], "content": m["content"]}
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                    out[-1]["content"].append(block)  # the results of one turn go together
                else:
                    out.append({"role": "user", "content": [block]})
            elif m["role"] == "assistant":
                content: list[dict[str, Any]] = []
                if m.get("text"):
                    content.append({"type": "text", "text": m["text"]})
                for c in m.get("tool_calls") or []:
                    content.append({"type": "tool_use", "id": c["id"], "name": c["name"],
                                    "input": c["arguments"]})  # fmt: skip
                out.append({"role": "assistant", "content": content or ""})
            else:
                out.append({"role": "user", "content": m.get("text") or ""})
        return out

    async def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> Reply:
        body: dict[str, Any] = {
            "model": self.config.model, "messages": self._messages(messages),
            "max_tokens": self.config.max_tokens, "temperature": self.config.temperature,
        }  # fmt: skip
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [{"name": t["name"], "description": t["description"],
                              "input_schema": t["parameters"]} for t in tools]  # fmt: skip
        headers = {"anthropic-version": "2023-06-01"}
        if key := self._key():
            headers["x-api-key"] = key
        said = await self._post(f"{self.config.base_url}/v1/messages", body, headers)
        reply = Reply(stop=said.get("stop_reason"))
        for block in said.get("content") or []:
            if block.get("type") == "text":
                reply.text += block.get("text", "")
            elif block.get("type") == "tool_use":
                reply.tool_calls.append({"id": block.get("id"), "name": block.get("name"),
                                         "arguments": _arguments(block.get("input"))})  # fmt: skip
        usage = said.get("usage") or {}
        reply.usage = {
            "input": usage.get("input_tokens", 0),
            "output": usage.get("output_tokens", 0),
        }
        return reply


class BedrockProvider(Provider):
    """Amazon Bedrock's Converse API."""

    name = "bedrock"

    @staticmethod
    def _messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if m["role"] == "tool":
                block = {"toolResult": {"toolUseId": m["id"], "content": [{"text": m["content"]}]}}
                if out and out[-1]["role"] == "user" and "toolResult" in out[-1]["content"][0]:
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
            elif m["role"] == "assistant":
                content: list[dict[str, Any]] = [{"text": m["text"]}] if m.get("text") else []
                for c in m.get("tool_calls") or []:
                    content.append({"toolUse": {"toolUseId": c["id"], "name": c["name"],
                                                "input": c["arguments"]}})  # fmt: skip
                out.append({"role": "assistant", "content": content or [{"text": ""}]})
            else:
                out.append({"role": "user", "content": [{"text": m.get("text") or ""}]})
        return out

    def _sign(self, request: httpx.Request) -> httpx.Request:
        token = self.env.get(self.config.key_env or "AWS_BEARER_TOKEN_BEDROCK")
        if token:
            request.headers["Authorization"] = f"Bearer {token}"
            return request
        access, secret = self.env.get("AWS_ACCESS_KEY_ID"), self.env.get("AWS_SECRET_ACCESS_KEY")
        if not (access and secret):
            raise ProviderError("bedrock: set AWS_BEARER_TOKEN_BEDROCK (an Amazon Bedrock API "
                                "key), or AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")  # fmt: skip
        body = request.read()
        headers = {"content-type": request.headers.get("content-type", "application/json"),
                   "host": request.url.netloc.decode()}  # fmt: skip
        signed = sign("POST", str(request.url), headers, body, access_key=access, secret_key=secret,
                      session_token=self.env.get("AWS_SESSION_TOKEN"), region=self.config.region,
                      service="bedrock")  # fmt: skip
        for name, value in signed.items():
            request.headers[name] = value
        return request

    async def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> Reply:
        body: dict[str, Any] = {
            "messages": self._messages(messages),
            "inferenceConfig": {"maxTokens": self.config.max_tokens,
                                "temperature": self.config.temperature},
        }  # fmt: skip
        if system:
            body["system"] = [{"text": system}]
        if tools:
            body["toolConfig"] = {"tools": [{"toolSpec": {
                "name": t["name"], "description": t["description"],
                "inputSchema": {"json": t["parameters"]}}} for t in tools]}  # fmt: skip
        url = f"{self.config.base_url}/model/{quote(self.config.model, safe='')}/converse"
        said = await self._post(url, body, {})
        reply = Reply(stop=said.get("stopReason"))
        for block in ((said.get("output") or {}).get("message") or {}).get("content") or []:
            if "text" in block:
                reply.text += block["text"]
            elif "toolUse" in block:
                use = block["toolUse"]
                reply.tool_calls.append({"id": use.get("toolUseId"), "name": use.get("name"),
                                         "arguments": _arguments(use.get("input"))})  # fmt: skip
        usage = said.get("usage") or {}
        reply.usage = {"input": usage.get("inputTokens", 0), "output": usage.get("outputTokens", 0)}
        return reply


PROVIDERS: dict[str, type[Provider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "bedrock": BedrockProvider,
}


def make(
    config: AssistantConfig,
    env: Mapping[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Provider:
    if not config.enabled:
        raise ProviderError("The assistant is not turned on.")
    return PROVIDERS[config.provider](config, env, transport)
