"""Rules the web app is held to (ADR-0004): what it may load, how big it may be, and whether
its colors can be read."""

from __future__ import annotations

import gzip
import itertools
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from riskwren.api.static import WEB_ROOT
from riskwren.core import color

JS = WEB_ROOT / "js"
CSS = WEB_ROOT / "css"
SHELL_BUDGET = 100_000
PART_BUDGET = 40_000


def test_no_inline_script_or_style() -> None:
    for page in WEB_ROOT.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), f"inline script in {page.name}"
        assert "<style" not in html, f"inline style in {page.name}"
        assert not re.search(r"\sstyle\s*=", html), f"style attribute in {page.name}"
        assert not re.search(r"\son[a-z]+\s*=", html), f"inline handler in {page.name}"


def test_nothing_is_loaded_from_another_origin() -> None:
    for file in WEB_ROOT.rglob("*"):
        if file.suffix in {".html", ".css", ".js"}:
            text = file.read_text(encoding="utf-8")
            assert not re.search(r"""\bsrc\s*=\s*["'](https?:)?//""", text), file.name
            assert not re.search(r"""<link[^>]+href\s*=\s*["'](https?:)?//""", text), file.name
            assert not re.search(r"""(import|from)\s+["']https?://""", text), file.name
            assert "url(http" not in text and "@import" not in text, file.name


def test_scripts_never_parse_data_as_html_or_set_inline_styles() -> None:
    forbidden = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(",
                 "new Function", 'setAttribute("style"', ".cssText")  # fmt: skip
    for script in JS.rglob("*.js"):
        text = script.read_text(encoding="utf-8")
        for word in forbidden:
            assert word not in text, f"{word} in {script.name}"


def _imports(file: Path) -> set[Path]:
    text = file.read_text(encoding="utf-8")
    found = re.findall(r"""(?:import|export)\s[^;]*?from\s+["'](\.{1,2}/[^"']+)["']""", text)
    return {(file.parent / name).resolve() for name in found}


def test_every_import_resolves() -> None:
    for script in JS.rglob("*.js"):
        for target in _imports(script):
            assert target.is_file(), f"{script.name} imports {target.name}, which does not exist"
    app = (JS / "app.js").read_text(encoding="utf-8")
    for page in re.findall(r"""page\("([\w-]+)",\s*"(\w+)\"""", app):
        file = JS / "pages" / f"{page[0]}.js"
        assert file.is_file(), f"app.js routes to pages/{page[0]}.js, which does not exist"
        assert re.search(rf"export (async )?function {page[1]}\b", file.read_text()), page
    index = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    for href in re.findall(r"""(?:href|src)="(/(?:css|js|img)/[^"]+)\"""", index):
        assert (WEB_ROOT / href.lstrip("/")).is_file(), f"index.html loads {href}"


def _gz(paths: set[Path]) -> int:
    return sum(len(gzip.compress(path.read_bytes(), 9)) for path in paths)


def _shell() -> set[Path]:
    """What every visit loads: the stylesheets, and app.js with everything it imports."""
    seen: set[Path] = set()
    stack = [(JS / "app.js").resolve()]
    while stack:
        file = stack.pop()
        if file not in seen:
            seen.add(file)
            stack.extend(_imports(file))
    return seen | set(CSS.glob("*.css")) | {WEB_ROOT / "index.html"}


def test_the_app_stays_within_its_size_budgets() -> None:
    shell = _shell()
    assert _gz(shell) <= SHELL_BUDGET, f"the app shell is {_gz(shell)} bytes gzipped"
    for page in (JS / "pages").glob("*.js"):
        extra = {page.resolve(), *_imports(page)} - shell
        assert _gz(extra) <= PART_BUDGET, f"{page.name} adds {_gz(extra)} bytes gzipped"


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node to check syntax")
def test_every_script_parses() -> None:
    for script in JS.rglob("*.js"):
        result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


# --- Contrast -----------------------------------------------------------------------------


def _block(css: str, selector: str) -> dict[str, str]:
    """The custom properties declared in the first rule whose selector list includes this one."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selectors = [s.strip() for s in match.group(1).split(",")]
        if selector in selectors:
            return {
                name: " ".join(value.split())
                for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", match.group(2))
            }
    raise AssertionError(f"no rule for {selector}")


def _split(value: str) -> tuple[str, str]:
    inner = value[len("light-dark(") : -1]
    depth = 0
    for position, char in enumerate(inner):
        depth += char == "("
        depth -= char == ")"
        if char == "," and depth == 0:
            return inner[:position].strip(), inner[position + 1 :].strip()
    raise AssertionError(f"not a light-dark pair: {value}")


def _resolve(tokens: dict[str, str], name: str, night: bool) -> str:
    value = tokens[name]
    for _ in range(8):
        if value.startswith("light-dark("):
            value = _split(value)[1 if night else 0]
        elif value.startswith("var("):
            inner = value[4:-1]
            first, _, fallback = inner.partition(",")
            value = tokens.get(first.strip()) or fallback.strip()
        else:
            return value
    raise AssertionError(f"could not resolve {name}")


def palettes() -> dict[str, dict[str, str]]:
    base = _block((CSS / "tokens.css").read_text(encoding="utf-8"), ":root")
    others = (CSS / "palettes.css").read_text(encoding="utf-8")
    return {
        "wren": base,
        "slate": {**base, **_block(others, ':root[data-palette="slate"]')},
        "garnet": {**base, **_block(others, ':root[data-palette="garnet"]')},
    }


TEXT, LARGE = 4.5, 3.0
SURFACES = ("--bg", "--surface-1", "--surface-2")
PAIRS: list[tuple[str, str, float]] = [
    *[("--text", surface, TEXT) for surface in (*SURFACES, "--surface-3")],
    *[("--text-muted", surface, TEXT) for surface in (*SURFACES, "--surface-3")],
    *[("--text-subtle", surface, TEXT) for surface in SURFACES],
    *[("--accent", surface, TEXT) for surface in (*SURFACES, "--accent-soft")],
    ("--on-accent", "--accent", TEXT),
    ("--on-accent", "--accent-hover", TEXT),
    ("--text-inverse", "--text", TEXT),
    *[(f"--{tone}", f"--{tone}-soft", TEXT) for tone in ("ok", "warn", "danger", "info")],
    *[(f"--{tone}", "--surface-1", TEXT) for tone in ("ok", "warn", "danger", "info")],
    *[(f"--rating-{level}", "--rating-soft", TEXT) for level in (1, 2, 3, 4, 5)],
    *[(f"--rating-{level}-on", f"--rating-{level}-fill", TEXT) for level in (1, 2, 3, 4, 5)],
    *[
        (f"--rec-{kind}", "--surface-1", TEXT)
        for kind in ("risk", "control", "process", "system", "party")
    ],
    ("--control-border", "--surface-1", LARGE),
    ("--control-border", "--bg", LARGE),
    ("--focus", "--surface-1", LARGE),
    ("--focus", "--bg", LARGE),
]


@pytest.mark.parametrize("palette", ["wren", "slate", "garnet"])
@pytest.mark.parametrize("night", [False, True], ids=["day", "night"])
def test_every_palette_can_be_read_in_both_modes(palette: str, night: bool) -> None:
    tokens = palettes()[palette]
    failures = []
    for foreground, background, minimum in PAIRS:
        ratio = color.contrast(
            _resolve(tokens, foreground, night), _resolve(tokens, background, night)
        )
        if ratio < minimum:
            failures.append(f"{foreground} on {background}: {ratio:.2f} (needs {minimum})")
    assert failures == []


def test_ratings_never_borrow_the_standing_colors() -> None:
    """A rating says how much is at stake; green, amber, and red say whether things are in
    order. On the default ramp their hues are kept well apart, in every palette."""
    for tokens in palettes().values():
        for night in (False, True):
            for level in (1, 3, 5):
                rating = color.rgb_to_oklch(
                    color.parse(_resolve(tokens, f"--rating-{level}", night))
                )[2]
                for tone in ("ok", "warn", "danger"):
                    hue = color.rgb_to_oklch(color.parse(_resolve(tokens, f"--{tone}", night)))[2]
                    apart = min(abs(rating - hue), 360 - abs(rating - hue))
                    assert apart >= 40, f"rating {level} and {tone} are {apart:.0f}° apart"


def test_the_ordinal_ramp_runs_from_pale_to_deep() -> None:
    """Each step of the default ramp's fill is darker by day, and lighter after dark, than
    the one before, so order can be read without color."""
    for tokens in palettes().values():
        for night in (False, True):
            lightness = [
                color.rgb_to_oklch(color.parse(_resolve(tokens, f"--rating-{n}-fill", night)))[0]
                for n in (1, 2, 3, 4, 5)
            ]
            steps = [b - a for a, b in itertools.pairwise(lightness)]
            assert (
                all(step > 0.04 for step in steps) if night else all(step < -0.04 for step in steps)
            )


@pytest.mark.parametrize("night", [False, True], ids=["day", "night"])
def test_the_signal_ramp_can_be_read_too(night: bool) -> None:
    ramp = _block((CSS / "palettes.css").read_text(encoding="utf-8"), ':root[data-ramp="signal"]')
    for tokens in palettes().values():
        signal = {**tokens, **ramp}
        for level in (1, 2, 3, 4, 5):
            for fore, back in (
                (f"--rating-{level}", "--rating-soft"),
                (f"--rating-{level}-on", f"--rating-{level}-fill"),
            ):
                ratio = color.contrast(_resolve(signal, fore, night), _resolve(signal, back, night))
                assert ratio >= TEXT, f"{fore} on {back}: {ratio:.2f}"


def test_the_palettes_the_server_offers_are_the_ones_the_stylesheets_define() -> None:
    from riskwren.program import branding

    assert set(palettes()) == set(branding.PALETTES)
