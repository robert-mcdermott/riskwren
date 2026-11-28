"""What the security review of wave 9 found, kept found (spec/security-review.md)."""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Callable

from fastapi.testclient import TestClient

from riskwren.auth import passwords
from riskwren.insight import dossier
from riskwren.reporting import exports
from tests.people import People

Clients = Callable[[str | None], TestClient]
CONCERN = {"kind": "concern", "name": "Something at the loading dock",
           "summary": "Boxes left open overnight."}  # fmt: skip


def _token(as_role: Clients, role: str, **more: object) -> TestClient:
    made = as_role("admin").post("/api/v1/admin/tokens", json={
        "name": f"{role} token", "role": role, "days": 30, **more})  # fmt: skip
    assert made.status_code == 201, made.text
    client = as_role(None)
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    client.headers["Authorization"] = f"Bearer {made.json()['meta']['token']}"
    return client


def test_a_token_is_nobody_and_owns_nothing(as_role: Clients, people: People) -> None:
    """A token has no account, so a report nobody made is not its own (finding V4-1)."""
    as_role("admin").put("/api/v1/admin/anonymous-reporting", json={"open": True})
    nobody = as_role(None)
    ref = nobody.post("/api/v1/anonymous-reports", json=CONCERN).json()["data"]["ref"]
    member = _token(as_role, "member")
    listed = member.get("/api/v1/incidents").json()["data"]
    assert ref not in {row["ref"] for row in listed}
    assert member.get(f"/api/v1/incidents/{ref}").status_code == 404
    assert ref not in json.dumps(member.get("/api/v1/search", params={"q": "loading"}).json())


def test_a_token_makes_no_judgment(as_role: Clients, people: People) -> None:
    """Deciding, confirming, and approving are a named person's (finding V4-4)."""
    writer = _token(as_role, "manager", read_only=False)
    judgments = (
        "/api/v1/exceptions/EXC-0001/decision",
        "/api/v1/issues/ISS-0001/validation",
        "/api/v1/risks/RSK-0001/acceptances",
        "/api/v1/audit/plans/APL-0001/approve",
    )
    for path in judgments:
        refused = writer.post(path, json={})
        assert refused.status_code == 403 and "named person" in refused.json()["detail"], path


def test_a_dossier_check_reads_within_bounds() -> None:
    """A manifest that would unpack to gigabytes is refused unread (finding V12-1)."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(dossier.MANIFEST, "[" + "0," * (dossier.MAX_MANIFEST // 2 + 10) + "0]")
    found = dossier.verify(out.getvalue())
    assert found["verified"] is False and "too large" in found["problems"][0]


def test_a_list_cell_cannot_be_a_formula() -> None:
    """Tags are written guarded, as any other text is (finding V5-2)."""
    assert exports._cell(["=hyperlink(1)", "b"]).startswith("'=")
    assert exports.unguard(exports._cell(["=x", "b"])) == "=x; b"


def test_a_password_is_at_most_128_characters() -> None:
    """ASVS 2.1.2 (finding V2-11)."""
    assert passwords.MAX_LENGTH == 128
