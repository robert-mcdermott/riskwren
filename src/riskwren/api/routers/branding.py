"""The organization's name, logo, and colors: what everyone sees, and where an admin sets it."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from riskwren.access.policy import current
from riskwren.api.common import envelope, reading, writing
from riskwren.api.problems import problem
from riskwren.core import color
from riskwren.core.errors import Invalid
from riskwren.program import branding

router = APIRouter(prefix="/api/v1/admin/branding", tags=["branding"])

# An uploaded image is shown, never run: nothing in it may load or execute anything.
IMAGE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "public, max-age=3600",
}


class BrandingBody(BaseModel):
    product_name: str = Field(max_length=200)
    organization_name: str = Field(default="", max_length=400)
    palette: str = Field(max_length=40)
    accent: str = Field(default="", max_length=20)
    accent_dark: str | None = Field(default=None, max_length=20)
    rating_ramp: str | None = Field(default=None, max_length=20)
    show_powered_by: bool = True
    sign_in_message: str | None = Field(default=None, max_length=2000)
    footer_links: list[dict[str, str]] | None = None
    email_footer: str | None = Field(default=None, max_length=1000)
    terms: dict[str, dict[str, str]] | None = Field(
        default=None, description="The organization's own words: key → {one, many}"
    )


class AccentBody(BaseModel):
    accent: str = Field(max_length=20)
    accent_dark: str = Field(default="", max_length=20)


def _editor_view(current_branding: branding.Branding) -> dict[str, Any]:
    accent = current_branding.accent
    return {
        **branding.public_view(current_branding),
        "accent": accent,
        "accent_dark": current_branding.accent_dark,
        "email_footer": current_branding.email_footer,
        "palettes": [{"key": key, "description": text} for key, text in branding.PALETTES.items()],
        "ramps": [{"key": key, "description": text} for key, text in branding.RAMPS.items()],
        "term_choices": [
            {"key": key, "one": one, "many": many} for key, (one, many) in branding.TERMS.items()
        ],
        "images": [
            {
                "kind": kind,
                "label": label,
                "set": kind in current_branding.images or kind in current_branding.files,
                "from_file": kind in current_branding.files,
            }
            for kind, label in branding.IMAGES.items()
        ],
        # What the configuration file has fixed, and the colors it sets, for showing.
        "pinned": list(current_branding.pinned),
        "colors": current_branding.colors,
        "checks": [
            c.to_json()
            for c in branding.derive_accent(accent, current_branding.accent_dark).checks()
        ]
        if accent
        else [],
    }


@router.get("", summary="The branding, for editing")
def show(request: Request) -> dict[str, Any]:
    with reading(request) as session:
        return envelope(_editor_view(branding.load(session)))


@router.put("", summary="Change the product name, palette, and accent")
def save(request: Request, body: BrandingBody) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        saved = branding.save(session, principal, body.model_dump(exclude_none=True))
        return envelope(_editor_view(saved))


@router.post("/check", summary="How an accent color would read, before saving it")
def check(body: AccentBody) -> dict[str, Any]:
    accent = body.accent.strip()
    if not color.is_hex(accent):
        raise Invalid("That is not a color.", {"accent": "Write it as a hex color, like #1f6f5c."})
    dark = body.accent_dark.strip()
    if dark and not color.is_hex(dark):
        raise Invalid("That is not a color.", {"accent_dark": "Write it as hex, like #7fd1bd."})
    derived = branding.derive_accent(accent, dark)
    checks = derived.checks()
    return envelope(
        {
            "day": derived.day,
            "night": derived.night,
            "on_day": derived.on_day,
            "on_night": derived.on_night,
            "checks": [c.to_json() for c in checks],
            "ok": all(c.ok for c in checks),
        }
    )


@router.post("/images/{kind}", summary="Upload a logo or tab icon")
async def upload(request: Request, kind: str) -> dict[str, Any]:
    """Send the image as the request body: PNG, JPEG, WebP, or SVG, up to 2 MB."""
    from starlette.concurrency import run_in_threadpool

    data = await request.body()

    def store() -> dict[str, Any]:
        principal = current(request)
        with writing(request, principal.actor) as session:
            saved = branding.store_image(
                session, principal, request.app.state.home.brand, kind, data
            )
            return envelope(_editor_view(saved))

    return await run_in_threadpool(store)


@router.delete("/images/{kind}", summary="Remove a logo or tab icon")
def remove(request: Request, kind: str) -> dict[str, Any]:
    principal = current(request)
    with writing(request, principal.actor) as session:
        return envelope(_editor_view(branding.remove_image(session, principal, kind)))


def install_branding(app: FastAPI) -> None:
    """The stylesheet and images the web app loads. They are public: the sign-in page is
    branded too."""

    @app.get("/theme.css", include_in_schema=False)
    def theme(request: Request) -> Response:
        with reading(request) as session:
            css = branding.theme_css(branding.load(session))
        return Response(css, media_type="text/css", headers={"Cache-Control": "no-cache"})

    @app.get("/branding/{kind}", include_in_schema=False)
    def image(request: Request, kind: str) -> Response:
        with reading(request) as session:
            found = branding.image_file(branding.load(session), request.app.state.home.brand, kind)
        if found is None:
            return problem(404, instance=request.url.path)
        path, media = found
        if media == "image/svg+xml":
            # An SVG named in the configuration file is read as it is on disk, so it is
            # reduced to drawing here, as an uploaded one is when it is stored.
            data = branding.sanitize_svg(path.read_bytes())
            return Response(data, media_type=media, headers=IMAGE_HEADERS)
        return FileResponse(path, media_type=media, headers=IMAGE_HEADERS)
