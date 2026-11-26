from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from riskwren import __version__
from riskwren.api.common import clamp_limit, decode_cursor, encode_cursor
from riskwren.api.security import CONTENT_SECURITY_POLICY
from riskwren.api.static import resolve_static
from riskwren.core.errors import Invalid
from riskwren.db import migrate
from tests.conftest import Instance


def test_live(client: TestClient) -> None:
    assert client.get("/api/v1/health/live").json() == {"data": {"status": "ok"}, "meta": {}}


def test_ready_when_the_schema_is_current(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok", "database": "ok", "version": __version__}


def test_ready_reports_a_schema_that_is_behind(client: TestClient, instance: Instance) -> None:
    migrate.downgrade(instance.db.engine, "base")
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["data"]["database"] == "outdated"


def test_meta(client: TestClient) -> None:
    data = client.get("/api/v1/meta").json()["data"]
    assert data["product"]["name"] == "RiskWren" and data["version"] == __version__


def test_every_response_carries_the_security_headers(client: TestClient) -> None:
    for path in ("/", "/api/v1/meta", "/api/v1/nothing", "/css/base.css"):
        headers = client.get(path).headers
        assert headers["content-security-policy"] == CONTENT_SECURITY_POLICY, path
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
    assert client.get("/api/v1/meta").headers["cache-control"] == "no-store"


def test_the_policy_allows_nothing_inline_and_nothing_from_elsewhere() -> None:
    assert "unsafe" not in CONTENT_SECURITY_POLICY
    assert "http" not in CONTENT_SECURITY_POLICY and "*" not in CONTENT_SECURITY_POLICY


def test_unknown_api_routes_answer_with_a_problem(client: TestClient) -> None:
    response = client.get("/api/v1/nothing")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not Found"


def test_wrong_methods_answer_with_a_problem(client: TestClient) -> None:
    response = client.post("/api/v1/meta")
    assert response.status_code == 405
    assert response.headers["content-type"] == "application/problem+json"


def test_the_shell_is_served_for_the_app_and_its_routes(client: TestClient) -> None:
    shell = client.get("/").text
    assert '<div id="app"' in shell or '<main id="app"' in shell
    for route in ("/use-cases", "/use-cases/UC-0001", "/admin/appearance"):
        response = client.get(route)
        assert response.status_code == 200 and response.text == shell
        assert response.headers["cache-control"] == "no-cache"


def test_static_files_are_served_and_missing_ones_are_not_the_shell(client: TestClient) -> None:
    assert client.get("/js/app.js").status_code == 200
    assert "javascript" in client.get("/js/app.js").headers["content-type"]
    missing = client.get("/js/absent.js")
    assert missing.status_code == 404
    assert missing.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize(
    "path", ["../config.py", "js/../../config.py", "/etc/passwd", "js/\x00app.js", "", "js"]
)
def test_nothing_outside_the_web_root_is_served(path: str) -> None:
    assert resolve_static(path) is None


def test_traversal_through_the_server(client: TestClient) -> None:
    response = client.get("/%2e%2e/%2e%2e/config.py")
    assert response.status_code == 404


def test_the_openapi_document_is_served(client: TestClient) -> None:
    document = client.get("/api/openapi.json").json()
    assert document["info"]["title"] == "RiskWren"
    assert "/api/v1/health/ready" in document["paths"]
    assert client.get("/docs").text == client.get("/").text  # no bundled docs page


def test_cursors_round_trip_and_bad_ones_are_refused() -> None:
    position = {"after": 41, "sort": "name"}
    assert decode_cursor(encode_cursor(position)) == position
    assert decode_cursor(None) is None and decode_cursor("") is None
    for bad in ("not-base64!", encode_cursor({})[:-2] + "@@", "WzFd"):
        with pytest.raises(Invalid):
            decode_cursor(bad)


def test_limits_are_kept_within_bounds() -> None:
    assert (clamp_limit(None), clamp_limit(0), clamp_limit(10), clamp_limit(10_000)) == (
        50,
        1,
        10,
        200,
    )
