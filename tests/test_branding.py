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


def test_the_brand_kit(db: Database) -> None:
    kit = {
        "accent": "#1f6f5c",
        "accent_dark": "#7FD1BD",
        "sign_in_message": "  Questions? Ask the risk office.  ",
        "footer_links": [
            {"label": "Risk policy", "url": "https://intranet.example.org/risk"},
            {"label": "Help", "url": "mailto:risk-office@example.org"},
            {"label": "", "url": ""},
        ],
        "email_footer": "Risk Office, Building 4.",
    }
    with db.write(ME.actor) as session:
        saved = branding.save(session, ME, kit)
    assert saved.accent_dark == "#7fd1bd"
    assert saved.sign_in_message == "Questions? Ask the risk office."
    assert [link["label"] for link in saved.footer_links] == ["Risk policy", "Help"]
    public = branding.public_view(saved)
    assert public["footer_links"][1]["url"] == "mailto:risk-office@example.org"
    assert public["sign_in_message"].startswith("Questions?") and public["sign_in_image"] is None
    assert "#7fd1bd" in branding.theme_css(saved)
    assert branding.derive_accent("#1f6f5c", "#7fd1bd").night == "#7fd1bd"
    assert "sign-in" in branding.IMAGES


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"accent_dark": "#102030", "accent": "#1f6f5c"}, "accent_dark"),  # too dark to read
        ({"accent_dark": "#7fd1bd", "accent": ""}, "accent_dark"),  # nothing to pair it with
        ({"accent_dark": "teal", "accent": "#1f6f5c"}, "accent_dark"),
        ({"sign_in_message": "x" * 601}, "sign_in_message"),
        ({"email_footer": "x" * 301}, "email_footer"),
        ({"footer_links": [{"label": "Bad", "url": "javascript:alert(1)"}]}, "footer_links"),
        ({"footer_links": [{"label": "", "url": "https://example.org"}]}, "footer_links"),
        ({"footer_links": [{"label": "n", "url": "https://example.org"}] * 6}, "footer_links"),
        ({"rating_ramp": "rainbow"}, "rating_ramp"),
        ({"terms": {"risk": {"one": "Hazard", "many": "Hazards"}}}, "terms"),  # not offered
        ({"terms": {"unit": {"one": "Department", "many": ""}}}, "terms"),  # both or neither
        ({"terms": {"unit": {"one": "D" * 31, "many": "Ds"}}}, "terms"),
    ],
)
def test_a_brand_kit_that_cannot_be_used_is_refused(
    db: Database, change: dict[str, object], field: str
) -> None:
    with db.write(ME.actor) as session, pytest.raises(Invalid) as refused:
        branding.save(session, ME, change)
    assert field in refused.value.errors


def test_the_brand_kit_through_the_api(as_role: Clients) -> None:
    admin = as_role("admin")
    body = {
        "product_name": "Risk Front Door", "palette": "slate", "accent": "#2a4fc7",
        "sign_in_message": "Ask the risk office.", "rating_ramp": "signal",
        "footer_links": [{"label": "Policy", "url": "https://example.org/policy"}],
    }  # fmt: skip
    saved = admin.put("/api/v1/admin/branding", json=body)
    assert saved.status_code == 200, saved.text
    meta = as_role(None).get("/api/v1/meta").json()["data"]["branding"]
    assert meta["sign_in_message"] == "Ask the risk office." and meta["rating_ramp"] == "signal"
    assert meta["footer_links"] == [{"label": "Policy", "url": "https://example.org/policy"}]
    # Saving the names again leaves the kit as it was.
    again = admin.put(
        "/api/v1/admin/branding", json={"product_name": "Risk Front Door", "palette": "slate"}
    )
    assert again.json()["data"]["sign_in_message"] == "Ask the risk office."
    checked = admin.post(
        "/api/v1/admin/branding/check", json={"accent": "#2a4fc7", "accent_dark": "#9db4ff"}
    )
    assert checked.json()["data"]["night"] == "#9db4ff" and checked.json()["data"]["ok"]
    assert admin.post("/api/v1/admin/branding/images/sign-in", content=PNG).status_code == 200
    assert as_role(None).get("/api/v1/meta").json()["data"]["branding"]["sign_in_image"]


# --- Branding from the configuration file ---------------------------------------------------

DAY = {"bg": "#f6f5f2", "surface": "#ffffff", "text": "#1d2733", "muted": "#57606b",
       "accent": "#1f5f8b", "stripe": "#b4501a"}  # fmt: skip
NIGHT = {"bg": "#12171d", "surface": "#1a222b", "text": "#f2f4f6", "muted": "#b9c2cc",
         "accent": "#6cb6e6", "on_accent": "#0f1a24"}  # fmt: skip


def _brand_table(tmp_path: Path) -> dict:  # type: ignore[type-arg]
    (tmp_path / "brand").mkdir(exist_ok=True)
    (tmp_path / "brand" / "logo.png").write_bytes(PNG)
    return {
        "product_name": "Lantern",
        "organization_name": "Northmere Institute",
        "show_powered_by": False,
        "logo_light": "brand/logo.png",
        "logo_height": 40,
        "font": ["Inter", "Arial"],
        "font_headings": ["Source Serif", "serif"],
        "footer_links": [{"label": "Privacy", "url": "https://northmere.example/privacy"}],
        "rating_ramp": "signal",
        "colors": {"day": dict(DAY), "night": dict(NIGHT)},
    }


def test_a_brand_is_read_from_the_configuration_file(tmp_path: Path) -> None:
    from riskwren.config import ConfigError, parse_config

    config = parse_config({"branding": _brand_table(tmp_path)}, base_dir=tmp_path)
    file = config.branding
    assert file.values["product_name"] == "Lantern" and file.logo_height == 40
    assert file.files == {"logo-light": (tmp_path / "brand" / "logo.png").resolve()}
    assert file.fonts == {"body": ["Inter", "Arial"], "headings": ["Source Serif", "serif"]}
    # What was left out is worked out: text to go on the accent, and the quieter surfaces.
    day = file.colors["day"]
    assert day["on_accent"] == "#ffffff" and day["stripe"] == "#b4501a"
    assert color.is_hex(day["surface_2"]) and day["surface_2"] != day["surface"]
    assert color.contrast(day["control_border"], day["surface"]) >= 3
    assert color.contrast(file.colors["night"]["control_border"], NIGHT["surface"]) >= 3
    assert {"product_name", "colors", "palette", "accent", "image:logo-light", "font:body"} <= set(
        file.names
    )
    assert parse_config({}, base_dir=tmp_path).branding is None

    bad = _brand_table(tmp_path)
    bad |= {"logo_light": "brand/missing.png", "product_name": "", "colour": "#fff",
            "font": ["Inter; } body { display: none"], "logo_height": 400}  # fmt: skip
    bad["colors"]["day"]["text"] = "#cccccc"  # cannot be read on white
    bad["colors"]["night"].pop("muted")
    bad["footer_links"] = [{"label": "Privacy", "url": "javascript:alert(1)"}]
    with pytest.raises(ConfigError) as caught:
        parse_config({"branding": bad}, base_dir=tmp_path)
    said = "\n".join(caught.value.problems)
    for expected in (
        "logo_light: there is no file", "product_name: Give the product a name",
        "colour is not a setting", "font: give up to six font names", "logo_height",
        "text on bg has a contrast of", "[branding.colors.night] also needs: muted",
        "footer_links:",
    ):  # fmt: skip
        assert expected in said, expected


def test_the_file_wins_and_the_rest_stays_editable(db: Database, tmp_path: Path) -> None:
    file, found = branding.from_file(_brand_table(tmp_path), tmp_path)
    assert found == [] and file is not None
    try:
        branding.pin(file)
        with db.write(ME.actor) as session:
            saved = branding.save(
                session,
                ME,
                {"product_name": "Something else", "sign_in_message": "Ask the office."},
            )
            # The name is the file's; the message, which the file does not set, was saved.
            assert (saved.product_name, saved.sign_in_message) == ("Lantern", "Ask the office.")
            assert saved.rating_ramp == "signal"
            stored = settings.get(session, branding.KEY)
            assert stored["product_name"] != "Lantern" and "colors" not in stored
            assert "files" not in stored and "pinned" not in stored
            with pytest.raises(Invalid) as refused:
                branding.store_image(session, ME, tmp_path / "kept", "logo-light", PNG)
            assert "configuration file" in refused.value.errors["file"]
            branding.store_image(session, ME, tmp_path / "kept", "favicon", PNG)
            current = branding.load(session)
            path, media = branding.image_file(current, tmp_path / "kept", "logo-light")  # type: ignore[misc]
            assert path == tmp_path / "brand" / "logo.png" and media == "image/png"
            # The dark logo falls back to the file's light one; the favicon is the stored one.
            assert branding.image_file(current, tmp_path / "kept", "logo-dark") is not None
            assert (
                branding.image_file(current, tmp_path / "kept", "favicon")[0].parent.name == "kept"
            )  # type: ignore[index]
            shown = branding.public_view(current)
            assert shown["colors_fixed"] and shown["logo_light"].startswith(
                "/branding/logo-light?v=f"
            )
            css = branding.theme_css(current)
        assert css.startswith(":root, :root[data-palette] {")
        assert "--bg: light-dark(#f6f5f2, #12171d);" in css
        assert "--brand-accent: light-dark(#1f5f8b, #6cb6e6);" in css
        assert "--signature: light-dark(#b4501a, #6cb6e6);" in css
        assert '--font: "Inter", "Arial", sans-serif;' in css
        assert 'h1, h2 {\n  font-family: "Source Serif", serif;' in css
        assert "--brand-logo-height: 40px;" in css
        assert set(css) <= set('abcdefghijklmnopqrstuvwxyzAIS0123456789#:;(){}[]-,." \n')
    finally:
        branding.pin(None)
    with db.read() as session:
        # With the file gone, the app's own name is back: the attempt to change a setting
        # the file had fixed was not stored.
        assert branding.load(session).product_name == "RiskWren"
        assert branding.load(session).sign_in_message == "Ask the office."


def test_file_branding_through_the_api(instance: Instance, people: People, tmp_path: Path) -> None:
    from dataclasses import replace

    from riskwren.api.app import create_app
    from tests.people import email_of, sign_in

    file, _ = branding.from_file(_brand_table(tmp_path), tmp_path)
    try:
        app = create_app(replace(instance.config, branding=file))
        with TestClient(app, base_url="http://localhost") as client:
            assert "--bg: light-dark(#f6f5f2, #12171d)" in client.get("/theme.css").text
            assert client.get("/branding/logo-light").content == PNG
            meta = client.get("/api/v1/meta").json()["data"]["branding"]
            assert meta["product_name"] == "Lantern" and meta["colors_fixed"] is True
            sign_in(client, email_of("admin"))
            editor = client.get("/api/v1/admin/branding").json()["data"]
            assert "product_name" in editor["pinned"] and editor["colors"]["day"]["bg"] == "#f6f5f2"
            assert editor["images"][0] == {
                "kind": "logo-light", "label": "Logo for light backgrounds", "set": True,
                "from_file": True,
            }  # fmt: skip
    finally:
        branding.pin(None)


def test_the_organizations_own_words(db: Database, tmp_path: Path) -> None:
    """Terms rename the kinds of record and units, from the app or from the file."""
    words = {"unit": {"one": " Department ", "many": "Departments"},
             "third_party": {"one": "Vendor", "many": "Vendors"},
             "issue": {"one": "", "many": ""}}  # fmt: skip
    with db.write(ME.actor) as session:
        saved = branding.save(session, ME, {"terms": words})
    assert saved.terms == {"unit": {"one": "Department", "many": "Departments"},
                           "third_party": {"one": "Vendor", "many": "Vendors"}}  # fmt: skip
    assert branding.public_view(saved)["terms"]["third_party"]["many"] == "Vendors"

    pinned, found = branding.from_file(
        {"terms": {"issue": {"one": "Finding", "many": "Findings"}}}, tmp_path
    )
    assert found == [] and pinned is not None and "terms" in pinned.names
    _, wrong = branding.from_file({"terms": {"issue": "Finding"}}, tmp_path)
    assert any("terms" in problem for problem in wrong)


def test_email_carries_the_organizations_header(db: Database) -> None:
    from riskwren import mail

    with db.write(ME.actor) as session:
        saved = branding.save(session, ME, {"accent": "#1f6f5c", "organization_name": "Northmere"})
    assert branding.email_accent(saved) == "#1f6f5c"
    how = mail.Look("Harbor Risk", "Northmere", "", accent=branding.email_accent(saved))
    _, page = mail.compose(how, "Hello", [("Something", None)])
    assert "border-top:4px solid #1f6f5c" in page and "Harbor Risk" in page and "Northmere" in page
    assert branding.email_accent(branding.Branding(palette="garnet")) == "#9b2c3c"
