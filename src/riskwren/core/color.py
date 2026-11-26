"""Just enough color science to check contrast and derive a dark-mode accent.

Colors are hex (``#1f6f5c``) or ``oklch(L C H)``, the two forms RiskWren's stylesheets use.
"""

from __future__ import annotations

import math
import re

RGB = tuple[float, float, float]

_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_OKLCH = re.compile(r"^oklch\(\s*([\d.]+)(%?)\s+([\d.]+)\s+([\d.]+)(?:deg)?\s*\)$")


def is_hex(text: str) -> bool:
    return bool(_HEX.match(text.strip()))


def parse(text: str) -> RGB:
    """A color as red, green, and blue between 0 and 1."""
    text = text.strip()
    match = _HEX.match(text)
    if match:
        digits = match.group(1)
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        return tuple(int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    match = _OKLCH.match(text)
    if match:
        lightness = float(match.group(1)) / (100 if match.group(2) else 1)
        return oklch_to_rgb(lightness, float(match.group(3)), float(match.group(4)))
    raise ValueError(f"not a color RiskWren can read: {text!r}")


def to_hex(rgb: RGB) -> str:
    return "#" + "".join(f"{round(min(1.0, max(0.0, c)) * 255):02x}" for c in rgb)


def _to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _from_linear(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def oklch_to_rgb(lightness: float, chroma: float, hue: float) -> RGB:
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        _from_linear(4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_),
        _from_linear(-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_),
        _from_linear(-0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_),
    )


def rgb_to_oklch(rgb: RGB) -> tuple[float, float, float]:
    r, g, b = (_to_linear(c) for c in rgb)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return lightness, math.hypot(a, b2), math.degrees(math.atan2(b2, a)) % 360


def luminance(rgb: RGB) -> float:
    r, g, b = (_to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(first: RGB | str, second: RGB | str) -> float:
    """The WCAG contrast ratio between two colors, from 1 to 21."""
    one = luminance(parse(first) if isinstance(first, str) else first)
    two = luminance(parse(second) if isinstance(second, str) else second)
    lighter, darker = max(one, two), min(one, two)
    return (lighter + 0.05) / (darker + 0.05)


def readable_on(background: RGB | str) -> str:
    """Black or white, whichever reads better on this background."""
    return (
        "#ffffff"
        if contrast(background, "#ffffff") >= contrast(background, "#111111")
        else "#111111"
    )


def with_lightness(color: str, lightness: float, *, max_chroma: float | None = None) -> str:
    """The same hue at another lightness, as hex."""
    _, chroma, hue = rgb_to_oklch(parse(color))
    if max_chroma is not None:
        chroma = min(chroma, max_chroma)
    return to_hex(oklch_to_rgb(lightness, chroma, hue))
