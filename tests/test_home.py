from __future__ import annotations

from pathlib import Path

import pytest

from riskwren.core.errors import DataHomeError
from riskwren.home import DataHome


def test_create_is_safe_to_repeat(tmp_path: Path) -> None:
    home = DataHome(tmp_path / "var")
    assert not home.is_initialized()
    home.create()
    home.create()
    assert home.is_initialized()
    for path in (home.files, home.brand, home.exports, home.logs):
        assert path.is_dir()
    assert "Back it up" in home.marker.read_text(encoding="utf-8")


def test_require_says_what_to_run(tmp_path: Path) -> None:
    with pytest.raises(DataHomeError, match="riskwren init"):
        DataHome(tmp_path / "missing").require()
