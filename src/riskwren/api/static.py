"""Serve the web app: a static shell, its files, and a fallback for client-side routes."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response

from riskwren.api.problems import problem

WEB_ROOT = Path(str(resources.files("riskwren.web").joinpath("static")))
NO_CACHE = {"Cache-Control": "no-cache"}


def resolve_static(path: str, root: Path = WEB_ROOT) -> Path | None:
    """The file a request path names, or None. Never anything outside the web root."""
    if not path or "\x00" in path:
        return None
    base = root.resolve()
    candidate = (base / path).resolve()
    if not candidate.is_relative_to(base) or not candidate.is_file():
        return None
    return candidate


def install_static(app: FastAPI) -> None:
    """Register the catch-all. It must be installed last, or it would shadow the API."""

    @app.get("/{path:path}", include_in_schema=False)
    def web_app(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            return problem(404, "No such API route.", instance=f"/{path}")
        file = resolve_static(path)
        if file is not None:
            return FileResponse(file, headers=NO_CACHE)
        if "." in path.rsplit("/", 1)[-1]:  # asked for a file that is not there
            return problem(404, instance=f"/{path}")
        return FileResponse(WEB_ROOT / "index.html", headers=NO_CACHE)
