"""Signing in, sessions, requests from other sites, and what each role may reach."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.access.policy import POLICIES, Needs, record_policies
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
    ("POST", "/api/v1/session/demo"): EVERYONE | {"nobody"},
    ("POST", "/api/v1/session/password"): EVERYONE,
    # Single sign-on. The round trip is open to all, and answers 404 unless it is set up.
    ("GET", "/api/v1/sso/start"): EVERYONE | {"nobody"},
    ("GET", "/api/v1/sso/callback"): EVERYONE | {"nobody"},
    ("GET", "/api/v1/sso"): {"admin"},
    ("POST", "/api/v1/sso/check"): {"admin"},
    ("PUT", "/api/v1/sso/mappings"): {"admin"},
    ("GET", "/api/v1/jobs"): {"admin"},
    ("POST", "/api/v1/jobs/{key}/run"): {"admin"},
    ("PUT", "/api/v1/jobs/{key}"): {"admin"},
    ("GET", "/api/v1/mail"): {"admin"},
    ("POST", "/api/v1/mail/test"): {"admin"},
    ("GET", "/api/v1/session/preferences"): EVERYONE,
    ("PUT", "/api/v1/session/preferences"): EVERYONE,
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

EVERYONE = set(ROLES)
RECORD_PATHS = {
    "processes": "PRC",
    "systems": "SYS",
    "third-parties": "TP",
    "information": "INF",
    "services": "SVC",
    "risks": "RSK",
    "controls": "CTL",
    "scopes": "SCP",
}
REACH[("GET", "/api/v1/vocabularies")] = EVERYONE
REACH[("GET", "/api/v1/admin/visibility")] = {"admin", "manager"}
REACH[("GET", "/api/v1/questionnaires")] = EVERYONE
REACH[("POST", "/api/v1/questionnaires")] = {"admin", "manager"}
REACH[("POST", "/api/v1/questionnaires/check")] = {"admin", "manager"}
REACH[("GET", "/api/v1/questionnaires/{key}")] = EVERYONE
REACH[("PATCH", "/api/v1/questionnaires/{key}")] = {"admin", "manager"}
REACH[("POST", "/api/v1/questionnaires/{key}/responses")] = EVERYONE
REACH[("GET", "/api/v1/responses/{response_id}")] = EVERYONE
for _route in (
    ("GET", "/api/v1/indicators"), ("POST", "/api/v1/indicators"),
    ("GET", "/api/v1/indicators/{ref}"), ("PATCH", "/api/v1/indicators/{ref}"),
    ("PUT", "/api/v1/indicators/{ref}/owners"), ("GET", "/api/v1/indicators/{ref}/history"),
    ("POST", "/api/v1/indicators/{ref}/readings"), ("PUT", "/api/v1/indicators/{ref}/risks"),
    ("GET", "/api/v1/risks/{ref}/indicators"),
    ("GET", "/api/v1/search"), ("GET", "/api/v1/views"), ("POST", "/api/v1/views"),
    ("PATCH", "/api/v1/views/{view_id}"), ("DELETE", "/api/v1/views/{view_id}"),
    ("GET", "/api/v1/tidy"), ("GET", "/api/v1/similar"),
    ("POST", "/api/v1/tidy/not-duplicates"),
    ("GET", "/api/v1/accounts/{account_id}/holdings"),
    ("POST", "/api/v1/accounts/{account_id}/handover"),
):  # fmt: skip
    REACH[_route] = EVERYONE
for _route in (
    ("GET", "/api/v1/risk-analyses"),
    ("POST", "/api/v1/risk-analyses"),
    ("POST", "/api/v1/risk-analyses/preview"),
    ("GET", "/api/v1/risk-analyses/{ref}"),
    ("PATCH", "/api/v1/risk-analyses/{ref}"),
    ("PUT", "/api/v1/risk-analyses/{ref}/owners"),
    ("GET", "/api/v1/risk-analyses/{ref}/history"),
    ("GET", "/api/v1/risk-analyses/{ref}/assets/{subject}"),
    ("POST", "/api/v1/risk-analyses/{ref}/items/{item_id}"),
    ("POST", "/api/v1/risk-analyses/{ref}/assets/{subject}/rest"),
    ("POST", "/api/v1/risk-analyses/{ref}/close"),
    ("POST", "/api/v1/risk-analyses/{ref}/reopen"),
):
    REACH[_route] = EVERYONE
for _route in (
    ("GET", "/api/v1/documents"),
    ("POST", "/api/v1/documents"),
    ("GET", "/api/v1/documents/{ref}"),
    ("PATCH", "/api/v1/documents/{ref}"),
    ("PUT", "/api/v1/documents/{ref}/owners"),
    ("GET", "/api/v1/documents/{ref}/history"),
    ("POST", "/api/v1/documents/{ref}/draft"),
    ("PATCH", "/api/v1/documents/{ref}/draft"),
    ("DELETE", "/api/v1/documents/{ref}/draft"),
    ("POST", "/api/v1/documents/{ref}/draft/file"),
    ("POST", "/api/v1/documents/{ref}/draft/submit"),
    ("POST", "/api/v1/documents/{ref}/draft/decision"),
    ("POST", "/api/v1/documents/{ref}/draft/withdraw"),
    ("POST", "/api/v1/documents/{ref}/draft/publish"),
    ("POST", "/api/v1/documents/{ref}/review"),
    ("POST", "/api/v1/documents/{ref}/retire"),
    ("POST", "/api/v1/documents/{ref}/reinstate"),
    ("GET", "/api/v1/documents/{ref}/versions/{version_id}"),
    ("GET", "/api/v1/documents/{ref}/compare"),
    ("GET", "/api/v1/documents/{ref}/versions/{version_id}/file"),
    ("PUT", "/api/v1/documents/{ref}/audience"),
    ("GET", "/api/v1/documents/{ref}/acknowledgments"),
    ("GET", "/api/v1/documents/{ref}/governs"),
    ("GET", "/api/v1/agreements"),
    ("POST", "/api/v1/agreements"),
    ("GET", "/api/v1/agreements/{ref}"),
    ("PATCH", "/api/v1/agreements/{ref}"),
    ("PUT", "/api/v1/agreements/{ref}/owners"),
    ("GET", "/api/v1/agreements/{ref}/history"),
    ("PUT", "/api/v1/agreements/{ref}/covers"),
    ("POST", "/api/v1/agreements/{ref}/close"),
    ("POST", "/api/v1/agreements/{ref}/reopen"),
    ("GET", "/api/v1/framework-packs"),
    ("GET", "/api/v1/objectives"),
    ("POST", "/api/v1/objectives"),
    ("GET", "/api/v1/objectives/{ref}"),
    ("PATCH", "/api/v1/objectives/{ref}"),
    ("PUT", "/api/v1/objectives/{ref}/owners"),
    ("GET", "/api/v1/objectives/{ref}/history"),
    ("PUT", "/api/v1/risks/{ref}/objectives"),
    ("GET", "/api/v1/sessions"),
    ("POST", "/api/v1/sessions"),
    ("GET", "/api/v1/sessions/{ref}"),
    ("PATCH", "/api/v1/sessions/{ref}"),
    ("PUT", "/api/v1/sessions/{ref}/owners"),
    ("GET", "/api/v1/sessions/{ref}/history"),
    ("POST", "/api/v1/sessions/{ref}/items"),
    ("PATCH", "/api/v1/sessions/{ref}/items/{item_id}"),
    ("DELETE", "/api/v1/sessions/{ref}/items/{item_id}"),
    ("POST", "/api/v1/sessions/{ref}/items/{item_id}/move"),
    ("POST", "/api/v1/sessions/{ref}/items/{item_id}/decision"),
    ("POST", "/api/v1/sessions/{ref}/held"),
    ("POST", "/api/v1/sessions/{ref}/cancel"),
    ("PUT", "/api/v1/documents/{ref}/controls"),
    ("DELETE", "/api/v1/documents/{ref}/controls/{link_id}"),
    ("PUT", "/api/v1/documents/{ref}/requirements"),
    ("DELETE", "/api/v1/documents/{ref}/requirements/{link_id}"),
    ("GET", "/api/v1/library"),
    ("GET", "/api/v1/library/{ref}"),
    ("POST", "/api/v1/library/{ref}/acknowledge"),
    ("GET", "/api/v1/tiers"),
    ("GET", "/api/v1/third-parties/{ref}/tiering"),
    ("POST", "/api/v1/third-parties/{ref}/tiering"),
    ("POST", "/api/v1/third-parties/{ref}/contacts"),
    ("PATCH", "/api/v1/contacts/{contact_id}"),
    ("GET", "/api/v1/reviews"),
    ("POST", "/api/v1/third-parties/{ref}/reviews"),
    ("GET", "/api/v1/reviews/{ref}"),
    ("PATCH", "/api/v1/reviews/{ref}"),
    ("PUT", "/api/v1/reviews/{ref}/owners"),
    ("GET", "/api/v1/reviews/{ref}/history"),
    ("POST", "/api/v1/reviews/{ref}/send"),
    ("POST", "/api/v1/reviews/{ref}/withdraw"),
    ("POST", "/api/v1/reviews/{ref}/conclude"),
    ("POST", "/api/v1/reviews/{ref}/cancel"),
):
    REACH[_route] = EVERYONE
# Through a link, without an account: reached by anyone, and answered by the link.
for _route in (("GET", "/api/v1/respond"), ("PUT", "/api/v1/respond"),
               ("POST", "/api/v1/respond/submit"), ("POST", "/api/v1/respond/files")):  # fmt: skip
    REACH[_route] = EVERYONE | {"nobody"}
for _route in (
    ("GET", "/api/v1/coverage"), ("PUT", "/api/v1/agreements/{ref}/parties"),
    ("POST", "/api/v1/third-parties/{ref}/call-review"),
    ("POST", "/api/v1/third-parties/{ref}/offboarding"),
    ("POST", "/api/v1/third-parties/{ref}/offboarding/steps/{step}"),
    ("POST", "/api/v1/third-parties/{ref}/offboarding/cancel"),
    ("POST", "/api/v1/reviews/{ref}/findings"),
    ("GET", "/api/v1/assurance-kinds"), ("GET", "/api/v1/third-parties/{ref}/assurance"),
    ("POST", "/api/v1/third-parties/{ref}/assurance"),
    ("POST", "/api/v1/third-parties/{ref}/assurance/{document}/reviews"),
):  # fmt: skip
    REACH[_route] = EVERYONE
RUNNERS = {"manager", "assessor"}
REACH[("GET", "/api/v1/campaigns")] = EVERYONE
REACH[("POST", "/api/v1/campaigns")] = RUNNERS
REACH[("POST", "/api/v1/campaigns/preview")] = RUNNERS
REACH[("GET", "/api/v1/campaigns/{ref}")] = EVERYONE
REACH[("POST", "/api/v1/campaigns/{ref}/remind")] = RUNNERS
REACH[("POST", "/api/v1/campaigns/{ref}/close")] = RUNNERS
REACH[("POST", "/api/v1/campaigns/{ref}/cancel")] = RUNNERS
REACH[("GET", "/api/v1/campaign-items/{item_id}")] = EVERYONE
REACH[("POST", "/api/v1/campaign-items/{item_id}/answer")] = EVERYONE
REACH[("POST", "/api/v1/campaign-items/{item_id}/excuse")] = RUNNERS
REACH[("PUT", "/api/v1/admin/visibility")] = {"admin", "manager"}
for _route in (
    ("GET", "/api/v1/admin/vocabularies"), ("PUT", "/api/v1/vocabularies/{name}"),
    ("POST", "/api/v1/risk-categories"), ("POST", "/api/v1/program/preview"),
    ("POST", "/api/v1/program/publish"),
):  # fmt: skip
    REACH[_route] = {"admin", "manager"}
REACH[("GET", "/api/v1/program")] = EVERYONE
for _report in ("home", "heat-map", "dashboard", "compliance", "graph/{ref}"):
    REACH[("GET", f"/api/v1/{_report}")] = EVERYONE
REACH[("GET", "/api/v1/history")] = {"admin", "manager", "auditor"}
REACH[("GET", "/api/v1/measures")] = {"admin", "manager", "auditor"}
REACH[("POST", "/api/v1/framework-packs")] = {"admin", "manager"}
REACH[("GET", "/api/v1/risk-library")] = EVERYONE
for (_method, _template), _needs in POLICIES.items():
    if _template.startswith("/api/v1/frameworks"):
        REACH[(_method, _template)] = (
            {"admin", "manager"} if _needs is Needs.CONFIGURE else EVERYONE
        )
REACH[("PATCH", "/api/v1/risk-categories/{key}")] = {"admin", "manager"}
for _action in ("assessments", "subjects", "escalation"):
    for _method in ("GET", "POST", "PUT"):
        if (_method, f"/api/v1/risks/{{ref}}/{_action}") in POLICIES:
            REACH[(_method, f"/api/v1/risks/{{ref}}/{_action}")] = EVERYONE
for _key, _needs in POLICIES.items():
    # Everything about controls and treatment is reached by anyone and decided by the
    # record, except accepting a risk, which is a leader's alone.
    parts = ("control", "/treatment", "/response", "/plans", "/acceptances", "/actions")
    if any(part in _key[1] for part in parts) and _key not in REACH:
        REACH[_key] = {"leader"} if _needs is Needs.LEAD else EVERYONE
for _key in POLICIES:
    # Everything about a scope is reached by anyone and decided by the scope.
    if _key[1].startswith("/api/v1/scopes/{ref}/") and _key not in REACH:
        REACH[_key] = EVERYONE
for _key, _needs in POLICIES.items():
    # Assessing is for assessors and managers; the rest is decided by the assessment.
    mine = _key[1].startswith(("/api/v1/assessments", "/api/v1/tests", "/api/v1/results"))
    if mine and _key not in REACH:
        REACH[_key] = {"assessor", "manager"} if _needs is Needs.ASSESS else EVERYONE
for _key, _needs in POLICIES.items():
    # Issues, exceptions, and notices are reached by anyone and decided by the record.
    # Confirming a closure, withdrawing an issue, and reopening one are the second line's.
    mine = _key[1].startswith(("/api/v1/issues", "/api/v1/exceptions", "/api/v1/notices"))
    if mine and _key not in REACH:
        REACH[_key] = {"assessor", "manager"} if _needs is Needs.ASSESS else EVERYONE
REACH[("GET", "/api/v1/exports/{kind}")] = EVERYONE
for _step in ("", "/columns"):
    REACH[("POST", f"/api/v1/imports/records/{{path}}{_step}")] = {"manager", "steward"}
    REACH[("POST", f"/api/v1/imports/requirements/{{key}}{_step}")] = {"admin", "manager"}
for _key in POLICIES:
    # Evidence is reached by anyone and decided by the item.
    if _key[1].startswith("/api/v1/evidence") and _key not in REACH:
        REACH[_key] = EVERYONE
for _path in RECORD_PATHS:
    for _method, _template in record_policies(
        _path, links=_path not in ("risks", "controls", "scopes")
    ):
        # Anyone may ask about a record, and the service decides what they may see and do.
        # Adding one is for a unit's steward or a manager.
        adding = _method == "POST" and _template == f"/api/v1/{_path}"
        REACH[(_method, _template)] = {"manager", "steward"} if adding else EVERYONE


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
            if template.startswith("/api/v1/graph"):
                path = path.replace("{ref}", "SYS-9999")
            if template.startswith("/api/v1/exports"):
                path = path.replace("{kind}", "processes")
            if template.startswith("/api/v1/imports/records"):
                path = path.replace("{path}", "processes")
            path = path.replace("{kind}", "favicon").replace("{key}", "technology")
            path = path.replace("{control_ref}", "CTL-9999").replace("{acceptance_id}", "9999")
            path = path.replace("{mapping_id}", "9999").replace("{implementation_id}", "9999")
            if template.startswith("/api/v1/plans/"):
                path = path.replace("{ref}", "PLN-9999")
            if template.startswith("/api/v1/actions/"):
                path = path.replace("{ref}", "ACT-9999")
            path = path.replace("{test_id}", "9999").replace("{result_id}", "9999")
            if template.startswith("/api/v1/assessments"):
                path = path.replace("{ref}", "ASM-9999")
            if template.startswith("/api/v1/evidence"):
                path = path.replace("{ref}", "EV-9999")
            if template.startswith("/api/v1/issues"):
                path = path.replace("{ref}", "ISS-9999")
            if template.startswith("/api/v1/exceptions"):
                path = path.replace("{ref}", "EXC-9999")
            if template.startswith("/api/v1/reviews"):
                path = path.replace("{ref}", "DDR-9999")
            path = path.replace("{contact_id}", "9999").replace("{document}", "EV-9999")
            for record_path, prefix in RECORD_PATHS.items():
                if template.startswith(f"/api/v1/{record_path}"):
                    # A record that is not there: reached, and answered with "not found".
                    path = path.replace("{ref}", f"{prefix}-9999").replace("{link_id}", "1")
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
            elif template.endswith("/controls/{ref}/requirements"):
                body = {"framework": "nist-csf", "code": "GV.OC-01", "coverage": "full"}
            elif template.endswith("/scopes/{ref}/frameworks"):
                body = {"framework": "nist-csf"}
            elif template.endswith("/scopes/{ref}/requirements"):
                body = {"framework": "nist-csf", "code": "GV.OC-01", "applicable": True}
            elif template.endswith("/scopes/{ref}/controls"):
                body = {"control": "CTL-9999", "status": "planned"}
            elif template.endswith("/controls/inherited"):
                body = {"implementation": 9999, "inheritance": "inherited"}
            elif template.endswith("/issues/{ref}/actions"):
                body = {"title": "x", "owner_id": 1, "due_on": "2030-01-01"}
            elif template.endswith("/due-date"):
                body = {"due_on": "2030-01-01", "reason": "x"}
            elif template.endswith("/closure"):
                body = {"note": "x", "root_cause": "other"}
            elif template.endswith("/validation"):
                body = {"confirm": True}
            elif template.endswith("/decision"):
                body = {"approve": True}
            elif template.endswith("/results"):
                body = {"design": "effective", "operation": "effective", "note": "x"}
            elif template.endswith("/review"):
                body = {"confirm": True}
            elif template.endswith("/assessments/{ref}/tests"):
                body = {"control": "CTL-9999"}
            elif template.endswith("/ratings"):
                body = {"design": "effective", "operation": "effective", "note": "x"}
            elif template.endswith("/risks/{ref}/controls"):
                body = {"control": "CTL-9999", "reduces": "likelihood", "reliance": "primary"}
            elif template.endswith("/response"):
                body = {"response": "reduce", "rationale": "x"}
            elif template.endswith("/plans"):
                body = {"objective": "x", "owner_id": 1, "due_on": "2030-01-01"}
            elif template.endswith("/plans/{ref}/actions"):
                body = {"title": "x", "owner_id": 1, "due_on": "2030-01-01"}
            elif template.endswith(("/cancellation", "/withdrawal")):
                body = {"reason": "x"}
            elif template.endswith("/acceptances") and method == "POST":
                body = {"rationale": "x", "expires_on": "2030-01-01"}
            elif template.endswith("/assessments"):
                body = {"kind": "inherent", "likelihood": 3, "impact_levels": {}, "rationale": ""}
            elif template.endswith("/subjects"):
                body = {"subjects": []}
            elif template.endswith("/escalation"):
                body = {"unit_id": None}
            elif template == "/api/v1/admin/visibility":
                body = {"visibility": "unit"}
            elif template.endswith("/owners"):
                body = {"owners": []}
            elif template.endswith("/links"):
                body = {"relation": "relies_on", "to": "SYS-9999"}
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
