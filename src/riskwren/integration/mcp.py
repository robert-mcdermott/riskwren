"""``riskwren tools``: a Model Context Protocol server over standard input and output (INT-06).

An assistant on someone's own computer starts it, and it answers with the tools in
``riskwren.integration.tools``, each calling a RiskWren server's API with a token from the
environment. The token decides what the assistant may see; the tools only read, or draft
what a person then makes in the app. Messages are JSON-RPC 2.0, one to a line; anything the
server has to say for itself goes to standard error.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import IO, Any

import httpx

from riskwren import __version__
from riskwren.integration import tools

PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = (
    "RiskWren is an organization's record of its risks, controls, compliance, and issues. "
    "These tools read what the token may see and draft risks, issues, and controls for a "
    "person to open, change, and save in RiskWren. A draft makes nothing by itself. Cite "
    "records by their reference, such as RSK-0042."
)


class HttpApi:
    """RiskWren's API at an address, with a token."""

    def __init__(self, base_url: str, token: str, *, transport: Any = None) -> None:
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), transport=transport, timeout=30.0,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                     "User-Agent": f"riskwren-tools/{__version__}"},
        )  # fmt: skip

    async def _answer(self, response: httpx.Response) -> Any:
        if response.status_code >= 400:
            try:
                said = response.json()
                told = said.get("detail") or said.get("title")
            except ValueError:
                told = None
            raise tools.ToolError(told or f"RiskWren answered {response.status_code}.")
        return response.json().get("data")

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._answer(await self.client.get(path, params=params))

    async def post(self, path: str, body: dict[str, Any]) -> Any:
        return await self._answer(await self.client.post(path, json=body))

    async def close(self) -> None:
        await self.client.aclose()


def _error(ident: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": message}}


async def answer(api: tools.Api, message: Any, *, drafting: bool = True) -> dict[str, Any] | None:
    """The reply to one message, or None for a notification."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Not a JSON-RPC 2.0 request.")
    ident, method = message.get("id"), message.get("method")
    params = message.get("params") or {}
    if ident is None:
        return None  # a notification, such as notifications/initialized: nothing to say
    if method == "initialize":
        asked = params.get("protocolVersion")
        return {"jsonrpc": "2.0", "id": ident, "result": {
            "protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "riskwren", "title": "RiskWren", "version": __version__},
            "instructions": INSTRUCTIONS}}  # fmt: skip
    if method == "ping":
        return {"jsonrpc": "2.0", "id": ident, "result": {}}
    if method == "tools/list":
        listed = [tool.listed() for tool in tools.offered(drafting=drafting)]
        return {"jsonrpc": "2.0", "id": ident, "result": {"tools": listed}}
    if method == "tools/call":
        name = params.get("name")
        try:
            text = await tools.call(api, str(name), params.get("arguments"), drafting=drafting)
        except tools.ToolError as said:
            return {"jsonrpc": "2.0", "id": ident,
                    "result": {"content": [{"type": "text", "text": str(said)}],
                               "isError": True}}  # fmt: skip
        except httpx.HTTPError as failed:
            told = f"RiskWren could not be reached: {type(failed).__name__}."
            return {"jsonrpc": "2.0", "id": ident,
                    "result": {"content": [{"type": "text", "text": told}],
                               "isError": True}}  # fmt: skip
        said = {"content": [{"type": "text", "text": text}], "isError": False}
        return {"jsonrpc": "2.0", "id": ident, "result": said}
    return _error(ident, -32601, f"There is no method {method}.")


async def serve(api: tools.Api, reader: IO[str], writer: IO[str], *, drafting: bool = True) -> None:
    """Answer each line until the input ends."""
    while True:
        line = await asyncio.to_thread(reader.readline)
        if not line:
            return
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            reply: dict[str, Any] | None = _error(None, -32700, "That is not JSON.")
        else:
            reply = await answer(api, message, drafting=drafting)
        if reply is not None:
            writer.write(json.dumps(reply, separators=(",", ":")) + "\n")
            writer.flush()


def run(base_url: str, token: str, *, drafting: bool = True) -> None:
    async def main() -> None:
        api = HttpApi(base_url, token)
        try:
            await serve(api, sys.stdin, sys.stdout, drafting=drafting)
        finally:
            await api.close()

    asyncio.run(main())
