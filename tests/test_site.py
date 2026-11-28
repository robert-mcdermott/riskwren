"""The documentation site is built from the guides. The build checks every link, anchor, and
picture, so running it here means a guide cannot be merged with a broken one."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
IMAGES = DOCS / "img"
HOME = ROOT / "scripts" / "site" / "pages" / "index.html"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="needs Node to build the site")


def _used() -> set[str]:
    """The pictures the guides and the home page name, without -light or -dark."""
    names: set[str] = set()
    for guide in DOCS.glob("*.md"):
        names.update(re.findall(r"\]\(img/([\w-]+)-light\.webp", guide.read_text(encoding="utf-8")))
    names.update(re.findall(r"\{\{shot:([\w-]+)\|", HOME.read_text(encoding="utf-8")))
    return names


@needs_node
def test_the_site_builds_with_no_broken_links(tmp_path: Path) -> None:
    out = tmp_path / "site"
    result = subprocess.run(
        ["node", "scripts/site/build.mjs", "--out", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-3000:]
    # Every guide is a page: a new guide that is not in the menu would never be published.
    for guide in DOCS.glob("*.md"):
        page = "guides" if guide.stem == "README" else guide.stem
        assert (out / f"{page}.html").is_file(), f"{guide.name} is not in the site's menu"
    for page in ("api-reference", "changelog"):
        assert (out / f"{page}.html").is_file()
    home = (out / "index.html").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M)
    assert version and f"Describes RiskWren {version.group(1)}." in home
    assert "{{" not in home
    assert (out / "assets" / "search.json").stat().st_size > 10_000
    assert (out / ".nojekyll").is_file()


def test_every_picture_is_used_and_has_both_themes() -> None:
    """The pictures are committed, so one nothing uses is weight for nothing, and a guide that
    names one in light only would show a bright picture on a dark page."""
    used = _used()
    assert used, "the guides and the home page use no pictures"
    present = {path.name for path in IMAGES.glob("*.webp")}
    for name in sorted(used):
        for mode in ("light", "dark"):
            assert f"{name}-{mode}.webp" in present, f"docs/img/{name}-{mode}.webp is missing"
    extra = present - {f"{name}-{mode}.webp" for name in used for mode in ("light", "dark")}
    assert not extra, f"nothing uses {sorted(extra)}"
    assert {path.name for path in IMAGES.iterdir()} == present, "docs/img holds only .webp pictures"


def test_pictures_in_the_guides_say_what_they_show() -> None:
    for guide in DOCS.glob("*.md"):
        for alt, src in re.findall(r"!\[([^\]]*)\]\(([^)\s]+)", guide.read_text(encoding="utf-8")):
            assert len(alt) >= 20, f"{guide.name}: the picture {src} needs a description"
            assert src.startswith("img/") and src.endswith("-light.webp"), f"{guide.name}: {src}"
