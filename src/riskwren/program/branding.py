"""An organization's own name, logo, and colors (PLT-08).

Branding is a program setting: edited in the app, stored in the database, and applied at
once. The server writes a small stylesheet from it, which the web app loads after the
built-in palettes.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from riskwren import PRODUCT_NAME
from riskwren.access.principal import Principal
from riskwren.core import color
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.events import audit
from riskwren.program import settings

KEY = "branding"
PALETTES = {
    "wren": "Warm paper neutrals with a harbor-blue accent",
    "slate": "Cool greys with a cobalt accent",
    "garnet": "Neutral greys with a deep red accent",
}
RAMPS = {
    "ordinal": "One hue from pale to deep, kept apart from the colors of standing",
    "signal": "Green through amber to red, as many boards expect",
}
# The surfaces an accent has to read against, by day and after dark, in every palette.
DAY_SURFACE = "#ffffff"
NIGHT_SURFACE = "#1f1e1c"
IMAGES = {"logo-light": "Logo for light backgrounds", "logo-dark": "Logo for dark backgrounds",
          "favicon": "Browser tab icon"}  # fmt: skip
MAX_IMAGE_BYTES = 2_000_000
TEXT_MIN = 4.5  # WCAG AA for ordinary text


@dataclass(frozen=True)
class Branding:
    product_name: str = PRODUCT_NAME
    organization_name: str = ""
    palette: str = "wren"
    accent: str = ""  # a hex color, or empty to use the palette's own
    rating_ramp: str = "ordinal"
    show_powered_by: bool = True
    images: dict[str, str] = field(default_factory=dict)  # kind → stored file name

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def load(session: Session) -> Branding:
    stored = settings.get(session, KEY, {}) or {}
    known = {name: stored[name] for name in Branding.__dataclass_fields__ if name in stored}
    return Branding(**known)


@dataclass(frozen=True)
class Check:
    pair: str
    ratio: float
    minimum: float

    @property
    def ok(self) -> bool:
        return self.ratio >= self.minimum

    def to_json(self) -> dict[str, Any]:
        return {
            "pair": self.pair,
            "ratio": round(self.ratio, 2),
            "minimum": self.minimum,
            "ok": self.ok,
        }


@dataclass(frozen=True)
class Accent:
    """A chosen accent, worked out for both modes."""

    day: str
    night: str
    on_day: str
    on_night: str

    def checks(self) -> list[Check]:
        return [
            Check(
                "Accent text and links on a light page",
                color.contrast(self.day, DAY_SURFACE),
                TEXT_MIN,
            ),
            Check(
                "Button text on the accent, by day", color.contrast(self.on_day, self.day), TEXT_MIN
            ),
            Check(
                "Accent text and links on a dark page",
                color.contrast(self.night, NIGHT_SURFACE),
                TEXT_MIN,
            ),
            Check(
                "Button text on the accent, after dark",
                color.contrast(self.on_night, self.night),
                TEXT_MIN,
            ),
        ]


def derive_accent(accent: str) -> Accent:
    """From one chosen color: the same hue lifted for dark mode, and readable text for each."""
    lightness, _, _ = color.rgb_to_oklch(color.parse(accent))
    night = color.with_lightness(accent, max(lightness, 0.76), max_chroma=0.15)
    return Accent(
        day=accent.lower(),
        night=night,
        on_day=color.readable_on(accent),
        on_night=color.readable_on(night),
    )


def problems(values: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    name = str(values.get("product_name", "")).strip()
    if not name:
        errors["product_name"] = "Give the product a name."
    elif len(name) > 40:
        errors["product_name"] = "Keep the product name to 40 characters."
    if len(str(values.get("organization_name", ""))) > 120:
        errors["organization_name"] = "Keep the organization's name to 120 characters."
    if values.get("palette") not in PALETTES:
        errors["palette"] = f"Choose one of: {', '.join(PALETTES)}."
    if values.get("rating_ramp", "ordinal") not in RAMPS:
        errors["rating_ramp"] = f"Choose one of: {', '.join(RAMPS)}."
    accent = str(values.get("accent", "")).strip()
    if accent:
        if not color.is_hex(accent):
            errors["accent"] = "Write the accent as a hex color, like #1f6f5c."
        else:
            failed = [check for check in derive_accent(accent).checks() if not check.ok]
            if failed:
                worst = failed[0]
                errors["accent"] = (
                    f"This color is hard to read: {worst.pair.lower()} would have a contrast "
                    f"of {worst.ratio:.1f}:1, and {worst.minimum}:1 is needed. Try a darker shade."
                )
    return errors


def save(session: Session, principal: Principal, values: dict[str, Any]) -> Branding:
    """Change the name, palette, and accent. Images are changed with ``store_image``."""
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator can change the branding.")
    current = load(session)
    merged = {**current.to_json(), **{k: v for k, v in values.items() if k != "images"}}
    for name in ("product_name", "organization_name", "accent"):
        merged[name] = str(merged.get(name, "")).strip()
    merged["accent"] = merged["accent"].lower()
    merged["show_powered_by"] = bool(merged.get("show_powered_by", True))
    errors = problems(merged)
    if errors:
        raise Invalid("The branding was not saved.", errors)
    with audit.operation(session, "branding.save"):
        settings.put(session, KEY, merged)
    return load(session)


def theme_css(branding: Branding) -> str:
    """The stylesheet that applies an organization's accent. Empty when none is set.

    Every value written here has passed ``problems``: a hex color and nothing else.
    """
    if not branding.accent or not color.is_hex(branding.accent):
        return "/* No custom accent: the palette's own is used. */\n"
    accent = derive_accent(branding.accent)
    lightness, _, _ = color.rgb_to_oklch(color.parse(accent.day))
    hover = color.with_lightness(accent.day, max(0.0, lightness - 0.06))
    night_l, _, _ = color.rgb_to_oklch(color.parse(accent.night))
    night_hover = color.with_lightness(accent.night, min(1.0, night_l + 0.05))
    soft_day = color.with_lightness(accent.day, 0.95, max_chroma=0.035)
    soft_night = color.with_lightness(accent.day, 0.30, max_chroma=0.05)
    return (
        ":root {\n"
        f"  --brand-accent: light-dark({accent.day}, {accent.night});\n"
        f"  --brand-accent-hover: light-dark({hover}, {night_hover});\n"
        f"  --brand-accent-soft: light-dark({soft_day}, {soft_night});\n"
        f"  --brand-on-accent: light-dark({accent.on_day}, {accent.on_night});\n"
        "}\n"
    )


# --- Images -------------------------------------------------------------------------------

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
SVG_ELEMENTS = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "defs",
    "linearGradient", "radialGradient", "stop", "clipPath", "mask", "title", "desc", "use",
    "symbol", "text", "tspan",
}  # fmt: skip
_DANGEROUS_VALUE = re.compile(r"javascript:|data:|expression\(|@import|url\(\s*['\"]?(?!#)", re.I)
MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "svg": "image/svg+xml",
}


def sniff(data: bytes) -> str | None:
    """What kind of image this is, judged by its content and never by its name."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    head = data[:2000].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head):
        return "svg"
    return None


def _drawable(element: ET.Element) -> bool:
    tag = element.tag
    if not isinstance(tag, str) or not tag.startswith(f"{{{SVG_NS}}}"):
        return False  # comments, processing instructions, and anything from another namespace
    return tag.rsplit("}", 1)[-1] in SVG_ELEMENTS


def sanitize_svg(data: bytes) -> bytes:
    """An SVG reduced to drawing: no scripts, handlers, styles, or references outside itself."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Invalid("The image cannot be used.", {"file": "Save the SVG as UTF-8."}) from exc
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I):
        raise Invalid(
            "The image cannot be used.",
            {"file": "Remove the DOCTYPE declaration from the SVG and try again."},
        )
    try:
        root = ET.fromstring(text)  # noqa: S314 (entities were refused above)
    except ET.ParseError as exc:
        raise Invalid("The image cannot be used.", {"file": "The SVG is not well formed."}) from exc
    if root.tag != f"{{{SVG_NS}}}svg":
        raise Invalid("The image cannot be used.", {"file": "This is not an SVG image."})

    def clean(element: ET.Element) -> None:
        for name in list(element.attrib):
            local = name.rsplit("}", 1)[-1].lower()
            value = element.attrib[name]
            is_link = local == "href"
            if (
                local.startswith("on")
                or local == "style"
                or (is_link and not value.strip().startswith("#"))
                or (not is_link and _DANGEROUS_VALUE.search(value))
            ):
                del element.attrib[name]
        for child in list(element):
            if _drawable(child):
                clean(child)
            else:
                element.remove(child)

    clean(root)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=False)


def store_image(
    session: Session, principal: Principal, brand_dir: Path, kind: str, data: bytes
) -> Branding:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator can change the branding.")
    if kind not in IMAGES:
        raise Invalid("The image cannot be used.", {"kind": f"Choose one of: {', '.join(IMAGES)}."})
    if len(data) > MAX_IMAGE_BYTES:
        raise Invalid("The image cannot be used.", {"file": "Use an image smaller than 2 MB."})
    form = sniff(data)
    if form is None:
        raise Invalid("The image cannot be used.", {"file": "Use a PNG, JPEG, WebP, or SVG image."})
    if form == "svg":
        data = sanitize_svg(data)
    brand_dir.mkdir(parents=True, exist_ok=True)
    name = f"{kind}-{hashlib.sha256(data).hexdigest()[:16]}.{form}"
    (brand_dir / name).write_bytes(data)
    current = load(session)
    images = {**current.images, kind: name}
    with audit.operation(session, "branding.image", kind=kind):
        settings.put(session, KEY, {**current.to_json(), "images": images})
    return load(session)


def remove_image(session: Session, principal: Principal, kind: str) -> Branding:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator can change the branding.")
    current = load(session)
    images = {k: v for k, v in current.images.items() if k != kind}
    with audit.operation(session, "branding.image", kind=kind):
        settings.put(session, KEY, {**current.to_json(), "images": images})
    return load(session)


def image_file(branding: Branding, brand_dir: Path, kind: str) -> tuple[Path, str] | None:
    """The stored file for an image and its media type, if there is one."""
    name = branding.images.get(kind)
    if kind == "logo-dark" and not name:
        name = branding.images.get("logo-light")
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    path = brand_dir / name
    media = MEDIA_TYPES.get(name.rsplit(".", 1)[-1])
    if not path.is_file() or media is None:
        return None
    return path, media


def public_view(branding: Branding) -> dict[str, Any]:
    """What the web app needs before anyone signs in."""

    def url(kind: str) -> str | None:
        name = branding.images.get(kind) or (
            branding.images.get("logo-light") if kind == "logo-dark" else None
        )
        return f"/branding/{kind}?v={name.rsplit('-', 1)[-1].split('.')[0]}" if name else None

    return {
        "product_name": branding.product_name,
        "organization_name": branding.organization_name,
        "palette": branding.palette,
        "accent": branding.accent or None,
        "rating_ramp": branding.rating_ramp,
        "show_powered_by": branding.show_powered_by,
        "logo_light": url("logo-light"),
        "logo_dark": url("logo-dark"),
        "favicon": url("favicon"),
    }
