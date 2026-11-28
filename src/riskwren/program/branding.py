"""An organization's own name, logo, and colors (PLT-08).

Branding is a program setting: edited in the app, stored in the database, and applied at
once. The server writes a small stylesheet from it, which the web app loads after the
built-in palettes.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field, replace
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
          "favicon": "Browser tab icon", "sign-in": "Picture on the sign-in page"}  # fmt: skip
# Each palette's accent by day, as a plain color for email, where stylesheets do not reach.
EMAIL_ACCENTS = {"wren": "#0f5876", "slate": "#2d57b4", "garnet": "#9b2c3c"}
MAX_LINKS = 5
# The words an organization may replace with its own, as (one, many): the kinds of record
# whose names differ most between organizations, and units.
TERMS = {
    "unit": ("Unit", "Units"),
    "process": ("Process", "Processes"),
    "system": ("System", "Systems"),
    "third_party": ("Third party", "Third parties"),
    "service": ("Service", "Services"),
    "information": ("Information asset", "Information assets"),
    "site": ("Site", "Sites"),
    "issue": ("Issue", "Issues"),
    "exception": ("Exception", "Exceptions"),
    "incident": ("Incident", "Incidents"),
}
_LINK = re.compile(r"^(https://|http://|mailto:)\S+$", re.I)
MAX_IMAGE_BYTES = 2_000_000
# What the app stores. The rest of a Branding comes from the configuration file.
STORED = (
    "product_name", "organization_name", "palette", "accent", "accent_dark", "sign_in_message",
    "footer_links", "email_footer", "terms", "rating_ramp", "show_powered_by", "images",
)  # fmt: skip
TEXT_MIN = 4.5  # WCAG AA for ordinary text


@dataclass(frozen=True)
class Branding:
    product_name: str = PRODUCT_NAME
    organization_name: str = ""
    palette: str = "wren"
    accent: str = ""  # a hex color, or empty to use the palette's own
    accent_dark: str = ""  # the accent after dark, or empty to work it out from ``accent``
    sign_in_message: str = ""
    footer_links: list[dict[str, str]] = field(default_factory=list)  # label and url
    email_footer: str = ""
    terms: dict[str, dict[str, str]] = field(default_factory=dict)  # key → one and many
    rating_ramp: str = "ordinal"
    show_powered_by: bool = True
    images: dict[str, str] = field(default_factory=dict)  # kind → stored file name
    # What only the configuration file can set. None of it is ever stored.
    colors: dict[str, dict[str, str]] = field(default_factory=dict)  # day and night, by name
    files: dict[str, str] = field(default_factory=dict)  # kind → an image file's full path
    fonts: dict[str, list[str]] = field(default_factory=dict)  # body and headings → families
    logo_height: int = 0  # the logo's height in the sidebar, in pixels, or 0 for the usual
    pinned: tuple[str, ...] = ()  # the settings the configuration file has fixed

    def to_json(self) -> dict[str, Any]:
        """What is stored. The configuration file's part is left out."""
        kept = asdict(self)
        for name in ("colors", "files", "fonts", "logo_height", "pinned"):
            del kept[name]
        return kept


def _stored(session: Session) -> Branding:
    """The branding as the app stores it, before the configuration file has its say."""
    stored = settings.get(session, KEY, {}) or {}
    known = {name: stored[name] for name in STORED if name in stored}
    return Branding(**known)


def load(session: Session) -> Branding:
    """The branding in effect: what the app stores, with whatever the configuration file
    sets laid over it."""
    stored = _stored(session)
    file = _pinned
    if file is None:
        return stored
    return replace(
        stored,
        **file.values,
        colors=file.colors,
        files={kind: str(path) for kind, path in file.files.items()},
        fonts=file.fonts,
        logo_height=file.logo_height,
        pinned=file.names,
    )


# --- Branding from the configuration file ---------------------------------------------------

# The colors a [branding.colors.day] or [branding.colors.night] table may set. The first
# six are needed; the rest are worked out from them when they are left out.
COLOR_NAMES = (
    "bg", "surface", "text", "muted", "accent", "on_accent", "border", "border_strong",
    "surface_2", "surface_3", "subtle", "accent_hover", "accent_soft", "stripe",
)  # fmt: skip
COLORS_NEEDED = ("bg", "surface", "text", "muted", "accent")
FILE_IMAGES = {"logo_light": "logo-light", "logo_dark": "logo-dark", "favicon": "favicon",
               "sign_in_image": "sign-in"}  # fmt: skip
# Fonts are named, never shipped: a name works on a machine that has the font installed, and
# the next name is tried on one that does not.
FILE_FONTS = {"font": "body", "font_headings": "headings"}
_FONT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,39}$")
GENERIC = ("serif", "sans-serif", "system-ui", "monospace")
FILE_TEXT = ("product_name", "organization_name", "palette", "accent", "accent_dark",
             "sign_in_message", "email_footer", "rating_ramp")  # fmt: skip


@dataclass(frozen=True)
class FileBranding:
    """The [branding] section of the configuration file, checked."""

    values: dict[str, Any] = field(default_factory=dict)
    colors: dict[str, dict[str, str]] = field(default_factory=dict)
    files: dict[str, Path] = field(default_factory=dict)
    fonts: dict[str, list[str]] = field(default_factory=dict)
    logo_height: int = 0

    @property
    def names(self) -> tuple[str, ...]:
        fixed = list(self.values)
        if self.colors:
            fixed += ["colors", "palette", "accent", "accent_dark"]
        fixed += [f"image:{kind}" for kind in self.files]
        fixed += [f"font:{role}" for role in self.fonts]
        return tuple(dict.fromkeys(fixed))

    def __bool__(self) -> bool:
        return bool(self.values or self.colors or self.files or self.fonts or self.logo_height)


_pinned: FileBranding | None = None


def pin(file: FileBranding | None) -> None:
    """Lay the configuration file's branding over what the app stores, from now on. Called
    once when the server or a command starts."""
    global _pinned
    _pinned = file if file else None


def _mode_problems(mode: str, table: dict[str, str]) -> list[str]:
    """Whether a day or night set of colors can be read."""
    where = f"[branding.colors.{mode}]"
    pairs = [
        ("text", "bg", TEXT_MIN), ("text", "surface", TEXT_MIN), ("muted", "surface", TEXT_MIN),
        ("muted", "bg", TEXT_MIN), ("accent", "surface", TEXT_MIN),
        ("on_accent", "accent", TEXT_MIN), ("accent", "accent_soft", TEXT_MIN),
        ("accent", "surface_2", TEXT_MIN), ("text", "surface_2", TEXT_MIN),
    ]  # fmt: skip
    found = []
    for front, back, least in pairs:
        ratio = color.contrast(table[front], table[back])
        if ratio < least:
            found.append(
                f"{where} {front} on {back} has a contrast of {ratio:.1f}:1, and {least}:1 is "
                "needed for it to be read"
            )
    return found


def _complete(mode: str, given: dict[str, str]) -> dict[str, str]:
    """A day or night set of colors with every name filled in. What was not given is worked
    out from what was, a step lighter or darker on the same hue."""
    out = dict(given)
    day = mode == "day"
    step = -1.0 if day else 1.0
    surface_l, _, _ = color.rgb_to_oklch(color.parse(out["surface"]))

    def shade(base: str, by: float) -> str:
        lightness, _, _ = color.rgb_to_oklch(color.parse(base))
        return color.with_lightness(base, max(0.0, min(1.0, lightness + step * by)))

    def readable(by: float, fronts: tuple[str, ...]) -> str:
        """A shade of the surface that the given colors can still be read on: the full step
        if they can, and a smaller one if not."""
        for part in (1.0, 0.75, 0.5, 0.3, 0.15, 0.0):
            made = shade(out["surface"], by * part)
            if all(color.contrast(out[front], made) >= TEXT_MIN + 0.1 for front in fronts):
                break
        return made

    out.setdefault("on_accent", color.readable_on(out["accent"]))
    out.setdefault("surface_2", readable(0.032 if day else 0.037, ("text", "muted", "accent")))
    out.setdefault("surface_3", readable(0.06 if day else 0.08, ("text", "muted", "accent")))
    out.setdefault("border", shade(out["surface"], 0.095 if day else 0.11))
    out.setdefault("border_strong", shade(out["border"], 0.105 if day else 0.125))
    out.setdefault("subtle", out["muted"])
    out.setdefault("accent_hover", shade(out["accent"], 0.06 if day else 0.05))
    if "accent_soft" not in out:
        # Behind the selected page and accent labels, where the accent itself is the text:
        # as tinted as it can be while that text can still be read.
        target = 0.95 if day else min(0.42, surface_l + 0.08)
        for _ in range(12):
            soft = color.with_lightness(out["accent"], target, max_chroma=0.035 if day else 0.05)
            if color.contrast(out["accent"], soft) >= TEXT_MIN + 0.1:
                break
            target = min(1.0, target + 0.01) if day else max(0.0, target - 0.02)
        out["accent_soft"] = soft
    out.setdefault("stripe", out["accent"])
    # The edge of a field or a checkbox has to be seen against the surface it sits on.
    edge = 0.60 if day else 0.62
    if abs(edge - surface_l) < 0.3:
        edge = surface_l + (0.36 if surface_l < 0.5 else -0.36)
    out["control_border"] = color.with_lightness(out["border"], max(0.0, min(1.0, edge)))
    return out


def from_file(table: Any, base_dir: Path) -> tuple[FileBranding | None, list[str]]:
    """Read and check a [branding] table. Returns what it sets and everything wrong with it."""
    found: list[str] = []
    if not isinstance(table, dict):
        return None, ["[branding] must be a table"]
    known = {
        *FILE_TEXT, "show_powered_by", "footer_links", "terms", "colors", *FILE_IMAGES, *FILE_FONTS,
        "logo_height",
    }  # fmt: skip
    for key in table:
        if key not in known:
            found.append(f"[branding] {key} is not a setting RiskWren knows")
    values: dict[str, Any] = {}
    for key in FILE_TEXT:
        if key in table:
            if not isinstance(table[key], str):
                found.append(f"[branding] {key}: must be text in quotes")
            else:
                values[key] = table[key].strip()
    for key in ("accent", "accent_dark"):
        if key in values:
            values[key] = values[key].lower()
    if "show_powered_by" in table:
        if not isinstance(table["show_powered_by"], bool):
            found.append("[branding] show_powered_by: must be true or false")
        else:
            values["show_powered_by"] = table["show_powered_by"]
    for key in ("footer_links", "terms"):
        if key in table:
            values[key] = table[key]
    shaped = dict(values)
    if isinstance(shaped.get("footer_links"), list) and all(
        isinstance(link, dict) for link in shaped["footer_links"]
    ):
        _tidy_lists(shaped)
        values.update({k: shaped[k] for k in ("footer_links", "terms") if k in values})
    elif "footer_links" in shaped:
        found.append("[branding] footer_links: give a list of { label, url } tables")
        shaped.pop("footer_links"), values.pop("footer_links")
    if "terms" in shaped and not (
        isinstance(shaped["terms"], dict)
        and all(isinstance(words, dict) for words in shaped["terms"].values())
    ):
        found.append("[branding] terms: give a table for each word, with one and many")
        shaped.pop("terms"), values.pop("terms")
    elif "terms" in shaped and "footer_links" not in shaped:
        _tidy_lists(shaped)
        values["terms"] = shaped["terms"]
    # Check what was given by the same rules the app applies when someone saves.
    probe = {**Branding().to_json(), **shaped}
    if "accent_dark" in shaped and "accent" not in shaped:
        probe["accent"] = "#1f6f5c"  # the app may hold the day accent
    for name, message in problems(probe).items():
        if name in shaped:
            found.append(f"[branding] {name}: {message}")

    colors: dict[str, dict[str, str]] = {}
    given = table.get("colors", {})
    if not isinstance(given, dict) or set(given) - {"day", "night"}:
        found.append("[branding.colors] holds two tables, day and night")
    elif given:
        if set(given) != {"day", "night"}:
            found.append("[branding.colors] needs both day and night, or neither")
        for mode, entries in given.items():
            where = f"[branding.colors.{mode}]"
            if not isinstance(entries, dict):
                found.append(f"{where} must be a table")
                continue
            bad = False
            for name, value in entries.items():
                if name not in COLOR_NAMES:
                    found.append(f"{where} {name} is not a color RiskWren knows")
                    bad = True
                elif not isinstance(value, str) or not color.is_hex(value.strip()):
                    found.append(f"{where} {name}: write the color as hex, like #1f6f5c")
                    bad = True
            missing = [name for name in COLORS_NEEDED if name not in entries]
            if missing:
                found.append(f"{where} also needs: {', '.join(missing)}")
            if bad or missing:
                continue
            full = _complete(mode, {k: v.strip().lower() for k, v in entries.items()})
            found.extend(_mode_problems(mode, full))
            colors[mode] = full
        if len(colors) != 2:
            colors = {}

    files: dict[str, Path] = {}
    for key, kind in FILE_IMAGES.items():
        if key not in table:
            continue
        if not isinstance(table[key], str) or not table[key].strip():
            found.append(f"[branding] {key}: must be the path of an image file")
            continue
        path = Path(table[key].strip()).expanduser()
        path = path if path.is_absolute() else (base_dir / path).resolve()
        if not path.is_file():
            found.append(f"[branding] {key}: there is no file at {path}")
        elif path.stat().st_size > MAX_IMAGE_BYTES:
            found.append(f"[branding] {key}: use an image smaller than 2 MB")
        elif (form := sniff(path.read_bytes())) is None:
            found.append(f"[branding] {key}: use a PNG, JPEG, WebP, or SVG image")
        else:
            if form == "svg":
                try:
                    sanitize_svg(path.read_bytes())
                except Invalid:
                    found.append(f"[branding] {key}: the SVG cannot be used. Save it as UTF-8, "
                                 "with no DOCTYPE")  # fmt: skip
                    continue
            files[kind] = path
    fonts: dict[str, list[str]] = {}
    for key, role in FILE_FONTS.items():
        if key not in table:
            continue
        names = table[key]
        if (
            not isinstance(names, list)
            or not 1 <= len(names) <= 6
            or not all(isinstance(name, str) and _FONT.match(name.strip()) for name in names)
        ):
            found.append(
                f"[branding] {key}: give up to six font names in order of preference, "
                'such as ["Inter", "Arial"]. Letters, digits, spaces, and hyphens only'
            )
        else:
            fonts[role] = [name.strip() for name in names]
    height = table.get("logo_height", 0)
    if (
        isinstance(height, bool)
        or not isinstance(height, int)
        or (height and not 20 <= height <= 48)
    ):
        found.append("[branding] logo_height: a whole number of pixels from 20 to 48")
        height = 0
    made = FileBranding(values=values, colors=colors, files=files, fonts=fonts, logo_height=height)
    return (made if made else None), found


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


def derive_accent(accent: str, dark: str = "") -> Accent:
    """From one chosen color: the same hue lifted for dark mode, and readable text for each.
    A color chosen for dark mode is used as it is."""
    lightness, _, _ = color.rgb_to_oklch(color.parse(accent))
    night = (
        dark.lower()
        if dark and color.is_hex(dark)
        else color.with_lightness(accent, max(lightness, 0.76), max_chroma=0.15)
    )
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
    dark = str(values.get("accent_dark", "")).strip()
    if dark:
        if not accent:
            errors["accent_dark"] = "Choose an accent color first."
        elif not color.is_hex(dark):
            errors["accent_dark"] = "Write the color as hex, like #7fd1bd."
        elif "accent" not in errors:
            failed = [c for c in derive_accent(accent, dark).checks()[2:] if not c.ok]
            if failed:
                worst = failed[0]
                errors["accent_dark"] = (
                    f"This color is hard to read: {worst.pair.lower()} would have a contrast "
                    f"of {worst.ratio:.1f}:1, and {worst.minimum}:1 is needed. Try a lighter shade."
                )
    if len(str(values.get("sign_in_message", ""))) > 600:
        errors["sign_in_message"] = "Keep the message to 600 characters."
    if len(str(values.get("email_footer", ""))) > 300:
        errors["email_footer"] = "Keep the line to 300 characters."
    links = values.get("footer_links") or []
    if not isinstance(links, list) or len(links) > MAX_LINKS:
        errors["footer_links"] = f"Give no more than {MAX_LINKS} links."
    else:
        for link in links:
            label, url = str(link.get("label", "")).strip(), str(link.get("url", "")).strip()
            if not label or len(label) > 40:
                errors["footer_links"] = "Give each link a label of up to 40 characters."
            elif not _LINK.match(url) or len(url) > 300:
                errors["footer_links"] = (
                    f"“{label}” needs an address that starts with https://, http://, or mailto:."
                )
    terms = values.get("terms") or {}
    if not isinstance(terms, dict) or set(terms) - set(TERMS):
        errors["terms"] = f"Words can be set for: {', '.join(TERMS)}."
    else:
        for key, words in terms.items():
            one, many = str(words.get("one", "")).strip(), str(words.get("many", "")).strip()
            if bool(one) != bool(many):
                errors["terms"] = f"Give both words for {TERMS[key][0].lower()}, or neither."
            elif len(one) > 30 or len(many) > 30:
                errors["terms"] = "Keep each word to 30 characters."
    return errors


def _tidy(values: dict[str, Any]) -> None:
    """Trim what was typed, and drop what was left empty."""
    for name in ("sign_in_message", "email_footer", "accent_dark"):
        values[name] = str(values.get(name) or "").strip()
    values["accent_dark"] = values["accent_dark"].lower()
    _tidy_lists(values)


def _tidy_lists(values: dict[str, Any]) -> None:
    links = values.get("footer_links")
    if isinstance(links, list):
        values["footer_links"] = [
            {"label": str(link.get("label", "")).strip(), "url": str(link.get("url", "")).strip()}
            for link in links
            if isinstance(link, dict) and (link.get("label") or link.get("url"))
        ]
    terms = values.get("terms")
    if isinstance(terms, dict):
        values["terms"] = {
            key: {
                "one": str(words.get("one", "")).strip(),
                "many": str(words.get("many", "")).strip(),
            }
            for key, words in terms.items()
            if isinstance(words, dict) and (words.get("one") or words.get("many"))
        }


def save(session: Session, principal: Principal, values: dict[str, Any]) -> Branding:
    """Change the name, palette, and accent. Images are changed with ``store_image``."""
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator can change the branding.")
    current = _stored(session)
    fixed = set(_pinned.names) if _pinned else set()
    merged = {
        **current.to_json(),
        **{k: v for k, v in values.items() if k != "images" and k not in fixed},
    }
    for name in ("product_name", "organization_name", "accent"):
        merged[name] = str(merged.get(name, "")).strip()
    merged["accent"] = merged["accent"].lower()
    merged["show_powered_by"] = bool(merged.get("show_powered_by", True))
    _tidy(merged)
    errors = problems(merged)
    if errors:
        raise Invalid("The branding was not saved.", errors)
    with audit.operation(session, "branding.save"):
        settings.put(session, KEY, merged)
    return load(session)


def theme_css(branding: Branding) -> str:
    """The stylesheet that applies an organization's colors. Empty when none are set.

    Every value written here has passed ``problems`` or ``from_file``: a hex color and
    nothing else.
    """
    fonts = _fonts_css(branding.fonts)
    if branding.logo_height:
        # The bar the logo sits in is 56 pixels high, and the sidebar 244 wide.
        fonts += (
            f":root {{\n  --brand-logo-height: {branding.logo_height}px;\n"
            "  --brand-logo-width: 212px;\n}\n"
        )
    if branding.colors:
        return _colors_css(branding.colors["day"], branding.colors["night"]) + fonts
    if fonts and not (branding.accent and color.is_hex(branding.accent)):
        return fonts
    if not branding.accent or not color.is_hex(branding.accent):
        return "/* No custom accent: the palette's own is used. */\n"
    accent = derive_accent(branding.accent, branding.accent_dark)
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
    ) + fonts


def _family(names: list[str], last: str) -> str:
    """A CSS font list from checked names, ending in a kind of font every machine has."""
    listed = [name if name in GENERIC else f'"{name}"' for name in names]
    return ", ".join([*listed, *([] if names[-1] in GENERIC else [last])])


def _fonts_css(fonts: dict[str, list[str]]) -> str:
    out = ""
    if fonts.get("body"):
        out += f":root {{\n  --font: {_family(fonts['body'], 'sans-serif')};\n}}\n"
    if fonts.get("headings"):
        out += f"h1, h2 {{\n  font-family: {_family(fonts['headings'], 'serif')};\n}}\n"
    return out


# Each token of the stylesheet, and the color of the configuration file that fills it.
_TOKENS = (
    ("--bg", "bg"), ("--surface-1", "surface"), ("--surface-2", "surface_2"),
    ("--surface-3", "surface_3"), ("--border", "border"), ("--border-strong", "border_strong"),
    ("--control-border", "control_border"), ("--text", "text"), ("--text-muted", "muted"),
    ("--text-subtle", "subtle"), ("--brand-accent", "accent"),
    ("--brand-accent-hover", "accent_hover"), ("--brand-accent-soft", "accent_soft"),
    ("--brand-on-accent", "on_accent"), ("--signature", "stripe"),
)  # fmt: skip


def _colors_css(day: dict[str, str], night: dict[str, str]) -> str:
    """The whole look from the configuration file. It is written for the page itself, over
    whichever built-in palette is named there, so a palette shown as a sample elsewhere on
    a page keeps its own colors."""
    lines = [f"  {token}: light-dark({day[name]}, {night[name]});" for token, name in _TOKENS]
    # Text set on the opposite of the page: light by day, dark at night.
    lines.append(f"  --text-inverse: light-dark({day['surface']}, {night['bg']});")
    return ":root, :root[data-palette] {\n" + "\n".join(lines) + "\n}\n"


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
    if _pinned and kind in _pinned.files:
        raise Invalid(
            "The image was not changed.",
            {"file": "This image is set in the configuration file. Change it there."},
        )
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
    current = _stored(session)
    images = {**current.images, kind: name}
    with audit.operation(session, "branding.image", kind=kind):
        settings.put(session, KEY, {**current.to_json(), "images": images})
    return load(session)


def remove_image(session: Session, principal: Principal, kind: str) -> Branding:
    if not principal.is_admin:
        raise PermissionDenied("Only an administrator can change the branding.")
    current = _stored(session)
    images = {k: v for k, v in current.images.items() if k != kind}
    with audit.operation(session, "branding.image", kind=kind):
        settings.put(session, KEY, {**current.to_json(), "images": images})
    return load(session)


def _named(branding: Branding, kind: str) -> str | None:
    """The image the configuration file names for a place, if it names one. The logo for
    dark backgrounds falls back to the one for light, unless the app holds its own."""
    if branding.files.get(kind):
        return branding.files[kind]
    if kind == "logo-dark" and not branding.images.get(kind):
        return branding.files.get("logo-light")
    return None


def image_file(branding: Branding, brand_dir: Path, kind: str) -> tuple[Path, str] | None:
    """The file for an image and its media type, if there is one: the one the configuration
    file names, or else the one stored in the app."""
    named = _named(branding, kind)
    if named:
        file = Path(named)
        form = sniff(file.read_bytes()) if file.is_file() else None
        return (file, MEDIA_TYPES[form]) if form else None
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


def email_accent(branding: Branding) -> str:
    """The accent email is written in: the configuration file's, the one chosen, or the
    palette's. Every one of them reads on white, which is where email is shown."""
    day = branding.colors.get("day", {}) if branding.colors else {}
    return day.get("accent") or branding.accent or EMAIL_ACCENTS.get(branding.palette, "#0f5876")


def public_view(branding: Branding) -> dict[str, Any]:
    """What the web app needs before anyone signs in."""

    def url(kind: str) -> str | None:
        named = _named(branding, kind)
        if named:  # the address changes when the file does, so a browser fetches it again
            file = Path(named)
            return f"/branding/{kind}?v=f{int(file.stat().st_mtime) if file.is_file() else 0}"
        name = branding.images.get(kind) or (
            branding.images.get("logo-light") if kind == "logo-dark" else None
        )
        return f"/branding/{kind}?v={name.rsplit('-', 1)[-1].split('.')[0]}" if name else None

    return {
        "product_name": branding.product_name,
        "organization_name": branding.organization_name,
        "palette": branding.palette,
        "accent": branding.accent or None,
        "colors_fixed": bool(branding.colors),
        "rating_ramp": branding.rating_ramp,
        "show_powered_by": branding.show_powered_by,
        "logo_light": url("logo-light"),
        "logo_dark": url("logo-dark"),
        "favicon": url("favicon"),
        "sign_in_image": url("sign-in"),
        "sign_in_message": branding.sign_in_message,
        "footer_links": branding.footer_links,
        "terms": {
            key: {"one": words["one"], "many": words["many"]}
            for key, words in branding.terms.items()
            if key in TERMS and words.get("one") and words.get("many")
        },
    }
