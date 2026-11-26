from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.access.principal import Principal
from riskwren.core import color
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Event
from riskwren.program import branding, settings
from tests.conftest import Instance
from tests.people import ME, People

Clients = Callable[[str | None], TestClient]
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
SVG = b"""<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 10 10" onload="alert(1)">
  <script>alert(1)</script>
  <style>@import url(https://elsewhere.example/x.css);</style>
  <foreignObject><body xmlns="http://www.w3.org/1999/xhtml"><iframe src="https://elsewhere.example"/></body></foreignObject>
  <a xlink:href="javascript:alert(1)"><circle cx="5" cy="5" r="4" fill="#1f6f5c" onclick="alert(2)" style="fill:url(https://elsewhere.example/a)"/></a>
  <image href="https://elsewhere.example/track.png"/>
  <use href="#shape"/><use xlink:href="https://elsewhere.example/sprite.svg#x"/>
  <rect id="shape" width="2" height="2" fill="url(#gradient)"/>
  <path d="M0 0h10" stroke="url(javascript:alert(3))"/>
</svg>"""


def test_color_arithmetic() -> None:
    assert color.contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert color.contrast("#fff", "#ffffff") == pytest.approx(1.0)
    assert color.contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)
    assert color.to_hex(color.parse("oklch(1 0 0)")) == "#ffffff"
    assert color.to_hex(color.parse("oklch(0.5 0 0)")) in {"#636363", "#646464"}
    lightness, chroma, hue = color.rgb_to_oklch(color.parse("#1f6f5c"))
    assert color.to_hex(color.oklch_to_rgb(lightness, chroma, hue)) == "#1f6f5c"
    assert color.readable_on("#1f6f5c") == "#ffffff" and color.readable_on("#f5d76e") == "#111111"
    with pytest.raises(ValueError, match="not a color"):
        color.parse("teal")


def test_settings_are_copies_and_changes_are_history(db: Database) -> None:
    with db.write(ME.actor) as session:
        assert settings.get(session, "example", {"a": 1}) == {"a": 1}
        assert settings.put(session, "example", {"list": [1, 2]})
        assert not settings.put(session, "example", {"list": [1, 2]})
        value = settings.get(session, "example")
        value["list"].append(3)  # changing the copy changes nothing
        assert settings.get(session, "example") == {"list": [1, 2]}
        assert settings.put(session, "example", {"list": [1, 2, 3]})
    with db.read() as session:
        events = session.scalars(select(Event).where(Event.subject_type == "setting")).all()
    assert [event.action for event in events] == ["created", "updated"]
    assert events[1].changes["value"] == [{"list": [1, 2]}, {"list": [1, 2, 3]}]


def test_defaults_and_saving(db: Database) -> None:
    with db.write(ME.actor) as session:
        assert branding.load(session) == branding.Branding()
        saved = branding.save(
            session, ME,
            {"product_name": " Risk Register ", "organization_name": "Northmere Institute",
             "palette": "slate", "accent": "#7A1F2B", "show_powered_by": False},
        )  # fmt: skip
    assert (saved.product_name, saved.palette, saved.accent) == (
        "Risk Register",
        "slate",
        "#7a1f2b",
    )
    with db.read() as session:
        view = branding.public_view(branding.load(session))
        last = session.scalars(select(Event).order_by(Event.id.desc())).first()
    assert view["product_name"] == "Risk Register" and view["logo_light"] is None
    assert last is not None and last.context == {"op": "branding.save"}


@pytest.mark.parametrize(
    ("values", "field"),
    [
        ({"product_name": ""}, "product_name"),
        ({"product_name": "x" * 41}, "product_name"),
        ({"palette": "neon"}, "palette"),
        ({"accent": "teal"}, "accent"),
        ({"accent": "#1f6f5c; } body { display: none"}, "accent"),
        ({"accent": "#ffe98a"}, "accent"),  # far too pale to read on white
    ],
)
def test_branding_that_cannot_be_used_is_refused(
    db: Database, values: dict[str, str], field: str
) -> None:
    with db.write(ME.actor) as session, pytest.raises(Invalid) as caught:
        branding.save(session, ME, {"product_name": "RiskWren", "palette": "wren", **values})
    assert field in caught.value.errors


def test_a_pale_accent_is_explained_in_plain_words() -> None:
    message = branding.problems({"product_name": "X", "palette": "wren", "accent": "#ffe98a"})[
        "accent"
    ]
    assert "hard to read" in message and "4.5:1" in message


def test_an_accent_is_lifted_for_dark_mode_and_stays_readable() -> None:
    for accent in ("#7a1f2b", "#1f6f5c", "#1a3a8f", "#4a2a7a", "#333333", "#b3261e"):
        derived = branding.derive_accent(accent)
        assert derived.day == accent
        assert all(check.ok for check in derived.checks()), accent
        assert color.contrast(derived.night, branding.NIGHT_SURFACE) > color.contrast(
            accent, branding.NIGHT_SURFACE
        )


def test_the_theme_stylesheet(db: Database) -> None:
    assert "--brand-accent" not in branding.theme_css(branding.Branding())
    css = branding.theme_css(branding.Branding(accent="#7a1f2b"))
    assert css.startswith(":root {") and "--brand-accent: light-dark(#7a1f2b, #" in css
    assert "--brand-on-accent: light-dark(#ffffff, #111111)" in css
    assert set(css) <= set("abcdefghijklmnopqrstuvwxyz0123456789#:;(){}-, \n")
    # A stored value that is not a color (edited by hand in the database) writes nothing.
    assert "--brand" not in branding.theme_css(branding.Branding(accent="red; } * { display:none"))


def test_only_administrators_change_the_branding(
    db: Database, people: People, tmp_path: Path
) -> None:
    manager = Principal(account_id=people.accounts["manager"], name="G")
    with db.write(manager.actor) as session:
        with pytest.raises(PermissionDenied):
            branding.save(session, manager, {"product_name": "Mine"})
        with pytest.raises(PermissionDenied):
            branding.store_image(session, manager, tmp_path, "favicon", PNG)


def test_images_are_judged_by_their_content() -> None:
    assert branding.sniff(PNG) == "png"
    assert branding.sniff(b"\xff\xd8\xff\xe0" + b"0" * 20) == "jpg"
    assert branding.sniff(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert branding.sniff(SVG) == "svg" and branding.sniff(b"  <svg xmlns='x'/>") == "svg"
    assert branding.sniff(b"<html><script>alert(1)</script></html>") is None
    assert branding.sniff(b"GIF89a") is None and branding.sniff(b"MZ\x90\x00") is None


def test_an_svg_is_reduced_to_drawing() -> None:
    clean = branding.sanitize_svg(SVG).decode()
    for gone in ("script", "onload", "onclick", "javascript", "elsewhere.example", "foreignObject",
                 "iframe", "style", "@import", "<image", "<a "):  # fmt: skip
        assert gone not in clean, gone
    assert "<circle" not in clean  # it was inside a link, which is not drawing
    assert 'href="#shape"' in clean and 'fill="url(#gradient)"' in clean  # references within stay
    assert clean.startswith("<svg") and 'viewBox="0 0 10 10"' in clean


@pytest.mark.parametrize(
    "data",
    [
        b'<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg">&a;</svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><unclosed></svg>',
        b"<svg><rect/></svg>",  # no namespace: not an SVG image
        b"\xff\xfe<svg",
    ],
)
def test_svgs_that_cannot_be_trusted_are_refused(data: bytes) -> None:
    with pytest.raises(Invalid):
        branding.sanitize_svg(data)


def test_branding_through_the_api(as_role: Clients, instance: Instance) -> None:
    admin, nobody = as_role("admin"), as_role(None)
    meta = nobody.get("/api/v1/meta").json()["data"]
    assert meta["branding"]["product_name"] == "RiskWren" and meta["palettes"] == [
        "wren",
        "slate",
        "garnet",
    ]
    assert nobody.get("/theme.css").headers["content-type"].startswith("text/css")

    check = admin.post("/api/v1/admin/branding/check", json={"accent": "#7a1f2b"}).json()["data"]
    assert check["ok"] and len(check["checks"]) == 4
    assert (
        admin.post("/api/v1/admin/branding/check", json={"accent": "#fff7c2"}).json()["data"]["ok"]
        is False
    )
    assert (
        admin.post("/api/v1/admin/branding/check", json={"accent": "burgundy"}).status_code == 422
    )

    body = {"product_name": "Risk Register", "organization_name": "Northmere Institute",
            "palette": "garnet", "accent": "#7a1f2b", "show_powered_by": True}  # fmt: skip
    saved = admin.put("/api/v1/admin/branding", json=body)
    assert saved.status_code == 200 and saved.json()["data"]["checks"]
    refused = admin.put("/api/v1/admin/branding", json={**body, "accent": "#fff7c2"})
    assert refused.status_code == 422 and refused.json()["errors"][0]["location"] == ["accent"]

    meta = nobody.get("/api/v1/meta").json()["data"]  # the sign-in page is branded too
    assert meta["product"]["name"] == "Risk Register" and meta["branding"]["palette"] == "garnet"
    assert "--brand-accent: light-dark(#7a1f2b" in nobody.get("/theme.css").text


def test_logos_through_the_api(as_role: Clients, instance: Instance) -> None:
    admin, nobody = as_role("admin"), as_role(None)
    assert nobody.get("/branding/logo-light").status_code == 404
    uploaded = admin.post("/api/v1/admin/branding/images/logo-light", content=SVG)
    assert uploaded.status_code == 200
    url = nobody.get("/api/v1/meta").json()["data"]["branding"]["logo_light"]
    assert url.startswith("/branding/logo-light?v=")
    served = nobody.get(url)
    assert served.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in served.headers["content-security-policy"]
    assert "default-src 'none'" in served.headers["content-security-policy"]
    assert served.headers["x-content-type-options"] == "nosniff"
    assert b"script" not in served.content and b"<svg" in served.content
    # With no logo for dark backgrounds, the light one is used.
    assert nobody.get("/branding/logo-dark").content == served.content
    assert admin.post("/api/v1/admin/branding/images/favicon", content=PNG).status_code == 200
    assert nobody.get("/branding/favicon").headers["content-type"] == "image/png"

    assert admin.post("/api/v1/admin/branding/images/banner", content=PNG).status_code == 422
    assert (
        admin.post("/api/v1/admin/branding/images/favicon", content=b"GIF89a....").status_code
        == 422
    )
    assert (
        admin.post(
            "/api/v1/admin/branding/images/favicon", content=PNG + b"0" * 2_000_001
        ).status_code
        == 422
    )
    assert nobody.get("/branding/..%2f..%2friskwren.db").status_code == 404
    assert len(list(instance.home.brand.iterdir())) == 2

    assert admin.delete("/api/v1/admin/branding/images/logo-light").status_code == 200
    assert nobody.get("/branding/logo-light").status_code == 404
    assert (
        as_role("manager").post("/api/v1/admin/branding/images/favicon", content=PNG).status_code
        == 403
    )


def test_the_rating_ramp_is_the_organizations_choice(
    as_role: Callable[[str | None], TestClient],
) -> None:
    admin = as_role("admin")
    editor = admin.get("/api/v1/admin/branding").json()["data"]
    assert editor["rating_ramp"] == "ordinal"
    assert [ramp["key"] for ramp in editor["ramps"]] == ["ordinal", "signal"]
    body = {"product_name": "RiskWren", "palette": "wren", "rating_ramp": "signal"}
    assert admin.put("/api/v1/admin/branding", json=body).status_code == 200
    assert as_role(None).get("/api/v1/meta").json()["data"]["branding"]["rating_ramp"] == "signal"
    refused = admin.put("/api/v1/admin/branding", json={**body, "rating_ramp": "rainbow"})
    assert refused.status_code == 422
    assert [e["location"] for e in refused.json()["errors"]] == [["rating_ramp"]]
