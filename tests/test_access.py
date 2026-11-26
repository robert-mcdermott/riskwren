"""Signing in, sessions, requests from other sites, and what each role may reach."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.access.policy import POLICIES, Needs
from riskwren.api.app import create_app
from riskwren.auth import sessions
from riskwren.core.clock import frozen_at, utc_now
from riskwren.db.models import Event
from tests.conftest import Instance
from tests.people import ME, PASSWORD, ROLES, People, email_of, sign_in

Clients = Callable[[str | None], TestClient]


def test_nobody_is_signed_in_at_first(as_role: Clients) -> None:
    client = as_role(None)
    assert client.get("/api/v1/session").status_code == 401
    assert client.get("/api/v1/units").status_code == 401
    assert client.get("/api/v1/meta").status_code == 200  # the sign-in page needs this


def test_signing_in_gives_a_session_the_page_cannot_read(as_role: Clients) -> None:
    client = as_role(None)
    response = client.post(
        "/api/v1/session", json={"email": " Steward@northmere.example", "password": PASSWORD}
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/" in cookie
    data = response.json()["data"]
    assert data["account"]["email"] == email_of("steward")
    assert data["roles"] == ["steward", "member"]
    assert data["permissions"]["steward"] and not data["permissions"]["admin"]
    assert len(data["csrf_token"]) > 20
    assert client.get("/api/v1/session").json()["data"]["account"]["name"] == "Steward Person"


def test_the_cookie_is_secure_behind_tls(as_role: Clients) -> None:
    client = as_role(None)
    response = client.post(
        "/api/v1/session",
        json={"email": email_of("member"), "password": PASSWORD},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert "secure" in response.headers["set-cookie"].lower()


def test_a_wrong_password_and_an_unknown_account_look_the_same(as_role: Clients) -> None:
    client = as_role(None)
    wrong = client.post(
        "/api/v1/session", json={"email": email_of("member"), "password": "not it at all"}
    )
    unknown = client.post(
        "/api/v1/session", json={"email": "ghost@northmere.example", "password": PASSWORD}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]
    assert "set-cookie" not in wrong.headers


def test_guessing_is_slowed_down(as_role: Clients) -> None:
    client = as_role(None)
    for _ in range(sessions.THROTTLE_LIMIT):
        assert (
            client.post(
                "/api/v1/session",
                json={"email": email_of("member"), "password": "guess guess guess"},
            ).status_code
            == 401
        )
    blocked = client.post(
        "/api/v1/session", json={"email": email_of("member"), "password": PASSWORD}
    )
    assert blocked.status_code == 429
    # Another account is unaffected, and the block passes with time.
    assert (
        client.post(
            "/api/v1/session", json={"email": email_of("auditor"), "password": PASSWORD}
        ).status_code
        == 200
    )
    with frozen_at(utc_now() + sessions.THROTTLE_WINDOW + timedelta(seconds=1)):
        assert (
            as_role(None)
            .post("/api/v1/session", json={"email": email_of("member"), "password": PASSWORD})
            .status_code
            == 200
        )


def test_signing_in_is_recorded(as_role: Clients, instance: Instance, people: People) -> None:
    as_role("auditor")
    with instance.db.read() as session:
        event = session.scalars(select(Event).order_by(Event.id.desc())).first()
    assert event is not None
    assert (event.action, event.subject_type, event.subject_id) == (
        "signed_in",
        "account",
        people.accounts["auditor"],
    )
    assert event.context == {"method": "password"} and event.actor_id == people.accounts["auditor"]


def test_changes_need_the_csrf_token(as_role: Clients, people: People) -> None:
    client = as_role("admin")
    body = {"name": "Imaging Core", "kind": "core", "parent_id": people.units["NMI"]}
    token = client.headers.pop(sessions.CSRF_HEADER)
    assert client.post("/api/v1/units", json=body).status_code == 403
    assert (
        client.post("/api/v1/units", json=body, headers={sessions.CSRF_HEADER: "wrong"}).status_code
        == 403
    )
    refused = client.post("/api/v1/units", json=body)
    assert refused.headers["content-type"] == "application/problem+json"
    assert "content-security-policy" in refused.headers
    assert (
        client.post("/api/v1/units", json=body, headers={sessions.CSRF_HEADER: token}).status_code
        == 201
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://elsewhere.example"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Origin": "http://localhost.elsewhere.example"},
    ],
)
def test_requests_from_other_sites_are_refused(
    as_role: Clients, people: People, headers: dict[str, str]
) -> None:
    client = as_role("admin")
    body = {"name": "Imaging Core", "kind": "core", "parent_id": people.units["NMI"]}
    assert client.post("/api/v1/units", json=body, headers=headers).status_code == 403
    signing_in = as_role(None).post(
        "/api/v1/session", json={"email": email_of("member"), "password": PASSWORD}, headers=headers
    )
    assert signing_in.status_code == 403


def test_requests_from_its_own_pages_are_accepted(as_role: Clients, people: People) -> None:
    client = as_role("admin")
    body = {"name": "Imaging Core", "kind": "core", "parent_id": people.units["NMI"]}
    assert (
        client.post("/api/v1/units", json=body, headers={"Origin": "http://localhost"}).status_code
        == 201
    )
    proxied = {
        "Origin": "https://riskwren.northmere.example",
        "X-Forwarded-Host": "riskwren.northmere.example",
    }
    body["name"] = "Proteomics Core"
    assert client.post("/api/v1/units", json=body, headers=proxied).status_code == 201


def test_signing_out_ends_the_session_for_good(as_role: Clients) -> None:
    client = as_role("member")
    cookie = client.cookies.get(sessions.COOKIE)
    assert client.delete("/api/v1/session").json()["data"] == {"signed_out": True}
    assert client.get("/api/v1/session").status_code == 401
    client.cookies.set(sessions.COOKIE, cookie)  # a copy of the old cookie is no use
    assert client.get("/api/v1/session").status_code == 401


def test_sessions_expire_when_idle_and_at_their_limit(as_role: Clients, instance: Instance) -> None:
    client = as_role("member")
    idle = instance.config.server.session_idle_hours
    with frozen_at(utc_now() + timedelta(hours=idle - 1)):
        assert client.get("/api/v1/session").status_code == 200  # and slides the expiry
    with frozen_at(utc_now() + timedelta(hours=2 * idle - 2)):
        assert client.get("/api/v1/session").status_code == 200
    with frozen_at(utc_now() + timedelta(hours=4 * idle)):
        assert client.get("/api/v1/session").status_code == 401
    fresh = as_role("auditor")
    limit = instance.config.server.session_max_days
    moment = utc_now()
    for _ in range(limit * 24 // (idle - 1)):  # used constantly, it still ends at the limit
        moment += timedelta(hours=idle - 1)
        with frozen_at(moment):
            fresh.get("/api/v1/session")
    with frozen_at(utc_now() + timedelta(days=limit, minutes=1)):
        assert fresh.get("/api/v1/session").status_code == 401


def test_disabling_an_account_ends_its_sessions(as_role: Clients, people: People) -> None:
    member, admin = as_role("member"), as_role("admin")
    response = admin.patch(
        f"/api/v1/accounts/{people.accounts['member']}", json={"status": "disabled"}
    )
    assert response.status_code == 200
    assert member.get("/api/v1/session").status_code == 401
    again = as_role(None).post(
        "/api/v1/session", json={"email": email_of("member"), "password": PASSWORD}
    )
    assert again.status_code == 401


def test_changing_a_password_through_the_api(as_role: Clients) -> None:
    here, elsewhere = as_role("member"), as_role("member")
    new = "an even longer passphrase"
    wrong = here.post(
        "/api/v1/session/password", json={"current_password": "no", "new_password": new}
    )
    assert wrong.status_code == 422 and wrong.json()["errors"][0]["location"] == [
        "current_password"
    ]
    weak = here.post(
        "/api/v1/session/password", json={"current_password": PASSWORD, "new_password": "short"}
    )
    assert weak.status_code == 422
    assert (
        here.post(
            "/api/v1/session/password", json={"current_password": PASSWORD, "new_password": new}
        ).status_code
        == 200
    )
    assert here.get("/api/v1/session").status_code == 200
    assert elsewhere.get("/api/v1/session").status_code == 401
    assert sign_in(as_role(None), email_of("member"), new)


# What each role may reach. This is written out, not derived from the policy table, so that
# a mistake in the table is caught here. Record-level rules are tested with the services.
EVERYONE = set(ROLES)
REACH: dict[tuple[str, str], set[str]] = {
    ("GET", "/api/v1/health/live"): EVERYONE | {"nobody"},
    ("GET", "/api/v1/health/ready"): EVERYONE | {"nobody"},
    ("GET", "/api/v1/meta"): EVERYONE | {"nobody"},
    ("GET", "/api/v1/session"): EVERYONE,
    ("POST", "/api/v1/session"): EVERYONE | {"nobody"},
    ("DELETE", "/api/v1/session"): EVERYONE | {"nobody"},
    ("POST", "/api/v1/session/password"): EVERYONE,
    ("GET", "/api/v1/accounts"): EVERYONE,
    ("POST", "/api/v1/accounts"): {"admin"},
    ("GET", "/api/v1/accounts/{account_id}"): EVERYONE,
    ("PATCH", "/api/v1/accounts/{account_id}"): EVERYONE,
    ("PUT", "/api/v1/accounts/{account_id}/roles"): {"admin"},
    ("PUT", "/api/v1/accounts/{account_id}/units"): {"admin"},
    ("POST", "/api/v1/accounts/{account_id}/password"): {"admin"},
    ("GET", "/api/v1/roles"): EVERYONE,
    ("GET", "/api/v1/units"): EVERYONE,
    ("POST", "/api/v1/units"): {"admin"},
    ("GET", "/api/v1/units/{unit_id}"): EVERYONE,
    ("PATCH", "/api/v1/units/{unit_id}"): {"admin"},
    ("GET", "/api/v1/admin/branding"): {"admin"},
    ("PUT", "/api/v1/admin/branding"): {"admin"},
    ("POST", "/api/v1/admin/branding/check"): {"admin"},
    ("POST", "/api/v1/admin/branding/images/{kind}"): {"admin"},
    ("DELETE", "/api/v1/admin/branding/images/{kind}"): {"admin"},
    ("POST", "/api/v1/imports/units"): {"admin"},
    ("POST", "/api/v1/imports/people"): {"admin"},
}


def api_routes(instance: Instance) -> set[tuple[str, str]]:
    """Every API route, read from the document the app publishes about itself."""
    paths = create_app(instance.config).openapi()["paths"]
    return {(method.upper(), path) for path, methods in paths.items() for method in methods}


def test_every_route_has_a_policy_and_every_policy_a_route(instance: Instance) -> None:
    routes = api_routes(instance)
    assert routes - set(POLICIES) == set(), "routes with no access policy"
    assert set(POLICIES) - routes == set(), "policies for routes that do not exist"
    assert set(REACH) == routes, "the matrix below must cover every route"


def test_a_route_without_a_policy_is_refused(instance: Instance, people: People) -> None:
    extra = APIRouter(prefix="/api/v1")

    @extra.get("/forgotten")
    def forgotten() -> dict[str, bool]:
        return {"reached": True}

    app = create_app(instance.config)
    app.include_router(extra)
    app.router.routes.insert(0, app.router.routes.pop())  # ahead of the web app's catch-all
    with TestClient(app, base_url="http://localhost") as client:
        sign_in(client, email_of("admin"))
        response = client.get("/api/v1/forgotten")
    assert response.status_code == 403 and "no access policy" in response.json()["detail"]


def test_each_role_reaches_exactly_what_it_should(as_role: Clients, people: People) -> None:
    for role in [*ROLES, "nobody"]:
        own = people.accounts.get(role, people.accounts["member"])
        for (method, template), may in sorted(REACH.items()):
            if (method, template) in {("DELETE", "/api/v1/session"), ("POST", "/api/v1/session")}:
                continue  # exercised above; they would end or replace the session under test
            client = as_role(None if role == "nobody" else role)
            path = template.replace("{account_id}", str(own)).replace(
                "{unit_id}", str(people.units["HALE"])
            )
            path = path.replace("{kind}", "favicon")
            if template.endswith("/password") and "{account_id}" in template:
                path = template.replace(
                    "{account_id}",
                    str(people.accounts["auditor" if role != "auditor" else "member"]),
                )
            body: dict[str, object] | None = {}
            if template == "/api/v1/accounts" and method == "POST":
                body = {"email": f"new-{role}@northmere.example", "display_name": "New"}
            elif template.endswith("/roles"):
                body = {"roles": [{"role": "admin"}] if role == "admin" else []}
            elif template.endswith("/units") and method == "PUT":
                body = {"unit_ids": []}
            elif template.endswith("/password"):
                body = {
                    "new_password": "short",
                    "current_password": "wrong",
                }  # reached, and refused
            elif template == "/api/v1/admin/branding":
                body = {"product_name": "RiskWren", "palette": "wren"}
            elif template.endswith("/branding/check"):
                body = {"accent": "#1f6f5c"}
            elif template == "/api/v1/units" and method == "POST":
                body = {"name": f"Unit by {role}", "kind": "lab", "parent_id": people.units["NMI"]}
            kwargs = (
                {"content": "code,name,kind\n"}
                if "imports" in template
                else ({"json": body} if method != "GET" else {})
            )
            status = client.request(method, path, **kwargs).status_code
            where = f"{role}: {method} {template} → {status}"
            if role in may:
                assert status not in (401, 403), where
            elif role == "nobody":
                assert status == 401, where
            else:
                assert status == 403, where


def test_policies_name_real_needs() -> None:
    assert all(isinstance(needs, Needs) for needs in POLICIES.values())


def test_members_see_only_enough_of_other_people_to_pick_them(
    as_role: Clients, people: People
) -> None:
    member, auditor = as_role("member"), as_role("auditor")
    listing = member.get("/api/v1/accounts", params={"q": "steward"}).json()["data"]
    assert listing == [
        {"id": people.accounts["steward"], "display_name": "Steward Person",
         "email": email_of("steward"), "title": None, "status": "active"}
    ]  # fmt: skip
    other = member.get(f"/api/v1/accounts/{people.accounts['steward']}").json()["data"]
    assert "roles" not in other
    assert "roles" in member.get(f"/api/v1/accounts/{people.accounts['member']}").json()["data"]
    assert "roles" in auditor.get(f"/api/v1/accounts/{people.accounts['steward']}").json()["data"]
    assert (
        member.patch(
            f"/api/v1/accounts/{people.accounts['steward']}", json={"title": "x"}
        ).status_code
        == 403
    )
    assert (
        member.patch(
            f"/api/v1/accounts/{people.accounts['member']}", json={"title": "Analyst"}
        ).status_code
        == 200
    )
    assert ME.is_admin


def test_a_body_that_is_too_large_is_refused_before_it_is_read(
    as_role: Callable[[str | None], TestClient],
) -> None:
    from riskwren.access.middleware import MAX_BODY

    response = as_role("admin").post(
        "/api/v1/imports/units", content=b"x", headers={"Content-Length": str(MAX_BODY + 1)}
    )
    assert response.status_code == 413
