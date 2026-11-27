#!/usr/bin/env python3
"""A stand-in OpenID Connect provider, for tests and for trying single sign-on on a laptop.

It speaks the real protocol: discovery, the authorization endpoint (with PKCE), the token
endpoint, and a published key set, and it signs ID tokens with RS256. It has a fixed list of
people and no passwords: whoever reaches its sign-in page chooses who to be.

ITS SIGNING KEY IS PUBLISHED BELOW, so a token from it proves nothing. It listens only on
this machine and must never stand in for a real identity provider.

    uv run python scripts/dev_identity_provider.py            # http://127.0.0.1:8099

Then, in riskwren.toml:

    [sso]
    issuer = "http://127.0.0.1:8099"
    client_id = "riskwren-dev"
    trust_email = true

and start RiskWren with RISKWREN_SSO_CLIENT_SECRET=dev-secret in its environment.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")

# A 2048-bit RSA key made for this file. It is public, on purpose.
DEV_N = int(
    "c1b0b3ce71e3245de2f950acb30b515a55e6dadb00521b302ac517986d43fc76694e7799c64f728dea88d0a9"
    "d1cb7dc409aa2453ad00241794118bd82b13366756dc042f7d09800164166e361b1fec0d5958df53667778da"
    "ed72301ee0a13465c415ca0374ebe0bfd7aeb1f16490193c4a130399e305c21148f5254bae55a4f61726869a"
    "a2fae63d016f9197597bc97da69ab0ffce2018fca416a9249b46d3b6c32959991cbecf4fcdfe3eb817c7a31f"
    "453acfa6b0f97dbbaaf8330be333650a654c9d165f7a296db251954bd0beb4aad025f19535fe5a8c0c5d31ac"
    "51c7978bf426db1b091dfdedf853c40272f015cc73bfefdf71f3fc5fb91f51a0446d33b1",
    16,
)
DEV_D = int(
    "1139514e0010e8ba9c1cdb549631e114c14b8f85f6d1f656bad0eec39860d9b61e7072c08712e8cf0fae85ae"
    "ba4828198b19f913c3503e4565fe86f2ecc6af39728f0b64bd2fdf75103551ece80dd7480b1c54f4b5c99542"
    "d3a76a39ceb42b248b12bc7580fbda4f3902f1123424ffc77d97520448dcc9d88f66346035e32a116c11c358"
    "9ab902f3d2ebc90f20e5cdffd1c72dc3ec4bf6a10fca22b22b3deed1329a1cba5f0db81a33f903788d8bcf72"
    "0e754de0a7bee0e9202d42c4f6b4bb12dca40e7c6a8d4bd5c9365bfcdda8f87ceac900e95b1fd9b539f29543"
    "9741f2a2540f6d40d8b67a9381d588d542baf7e4fb51b98f6396e307960ad3914fe0e799",
    16,
)
CLIENT_ID = "riskwren-dev"
CLIENT_SECRET = "dev-secret"  # noqa: S105 (published on purpose)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@dataclass
class Person:
    subject: str
    name: str
    email: str
    groups: list[str] = field(default_factory=list)


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    @classmethod
    def json(cls, value: Any, status: int = 200) -> Response:
        return cls(
            status,
            {"content-type": "application/json", "cache-control": "no-store"},
            json.dumps(value).encode(),
        )

    @classmethod
    def redirect(cls, location: str) -> Response:
        return cls(302, {"location": location}, b"")

    @classmethod
    def html(cls, text: str, status: int = 200) -> Response:
        return cls(status, {"content-type": "text/html; charset=utf-8"}, text.encode())


class Provider:
    """The provider's whole behavior, independent of how requests reach it."""

    def __init__(
        self,
        issuer: str,
        *,
        n: int,
        d: int,
        client_id: str,
        client_secret: str,
        people: list[Person],
        groups_claim: str = "roles",
        kid: str = "dev-key-1",
    ) -> None:
        self.issuer = issuer.rstrip("/")
        self.n, self.d, self.kid = n, d, kid
        self.client_id, self.client_secret = client_id, client_secret
        self.people = {person.subject: person for person in people}
        self.groups_claim = groups_claim
        self.codes: dict[str, dict[str, Any]] = {}
        self.now = time.time  # tests may replace it
        self.tamper: str | None = None  # tests set this to make the next token wrong
        self.email_verified = True
        self.send_groups = True  # a provider leaves the claim out when there are too many
        self.overflow = False  # and says so, pointing elsewhere for the list

    # --- Signing ---

    def sign(self, claims: dict[str, Any], *, alg: str = "RS256") -> str:
        header = {"alg": alg, "typ": "JWT", "kid": self.kid}
        first = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
        size = (self.n.bit_length() + 7) // 8
        digest = hashlib.sha256(first.encode()).digest()
        padded = (
            b"\x00\x01"
            + b"\xff" * (size - len(_PREFIX) - len(digest) - 3)
            + b"\x00"
            + _PREFIX
            + digest
        )
        signature = pow(int.from_bytes(padded, "big"), self.d, self.n).to_bytes(size, "big")
        return f"{first}.{_b64(signature)}"

    def jwks(self) -> dict[str, Any]:
        size = (self.n.bit_length() + 7) // 8
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self.kid,
                    "n": _b64(self.n.to_bytes(size, "big")),
                    "e": _b64((65537).to_bytes(3, "big")),
                }
            ]
        }

    def id_token(self, person: Person, nonce: str | None) -> str:
        now = int(self.now())
        claims: dict[str, Any] = {
            "iss": self.issuer,
            "aud": self.client_id,
            "sub": person.subject,
            "iat": now,
            "nbf": now,
            "exp": now + 300,
            "name": person.name,
            "email": person.email,
            "email_verified": self.email_verified,
            "preferred_username": person.email,
        }
        if self.send_groups:
            claims[self.groups_claim] = list(person.groups)
        elif self.overflow:
            claims["_claim_names"] = {self.groups_claim: "src1"}
        if nonce:
            claims["nonce"] = nonce
        tamper, self.tamper = self.tamper, None
        if tamper == "expired":
            claims["exp"] = now - 3600
        elif tamper == "audience":
            claims["aud"] = "another-application"
        elif tamper == "issuer":
            claims["iss"] = "https://someone-else.example"
        elif tamper == "nonce":
            claims["nonce"] = "not-the-one-sent"
        token = self.sign(claims, alg="none" if tamper == "unsigned" else "RS256")
        if tamper == "signature":
            head, body, signature = token.split(".")
            body = _b64(json.dumps({**claims, "sub": "someone-else"}).encode())
            token = f"{head}.{body}.{signature}"
        elif tamper == "unsigned":
            token = token.rsplit(".", 1)[0] + "."
        return token

    # --- Endpoints ---

    def handle(
        self, method: str, url: str, body: bytes = b"", headers: dict[str, str] | None = None
    ) -> Response:
        parts = urlsplit(url)
        path = parts.path
        query = {k: v[0] for k, v in parse_qs(parts.query).items()}
        base = urlsplit(self.issuer).path.rstrip("/")
        if base and path.startswith(base):
            path = path[len(base) :]
        if path == "/.well-known/openid-configuration":
            return Response.json(
                {
                    "issuer": self.issuer,
                    "authorization_endpoint": f"{self.issuer}/authorize",
                    "token_endpoint": f"{self.issuer}/token",
                    "jwks_uri": f"{self.issuer}/keys",
                    "response_types_supported": ["code"],
                    "subject_types_supported": ["public"],
                    "id_token_signing_alg_values_supported": ["RS256"],
                    "code_challenge_methods_supported": ["S256"],
                }
            )
        if path == "/keys":
            return Response.json(self.jwks())
        if path == "/authorize":
            return self._authorize(query)
        if path == "/token" and method == "POST":
            form = {k: v[0] for k, v in parse_qs(body.decode()).items()}
            return self._token(form, headers or {})
        return Response.json({"error": "not_found"}, 404)

    def _authorize(self, query: dict[str, str]) -> Response:
        if query.get("client_id") != self.client_id or query.get("response_type") != "code":
            return Response.html("<h1>Unknown application</h1>", 400)
        if "openid" not in query.get("scope", "").split() or not query.get("redirect_uri"):
            return Response.html("<h1>Bad request</h1>", 400)
        if query.get("code_challenge_method") != "S256" or not query.get("code_challenge"):
            return Response.html("<h1>PKCE is required</h1>", 400)
        chosen = query.get("login_hint") or query.get("as")
        if chosen not in self.people:
            links = "".join(
                f'<li><a href="?{urlencode({**query, "as": p.subject})}">{p.name}</a> '
                f"<small>{p.email} · {', '.join(p.groups) or 'no groups'}</small></li>"
                for p in self.people.values()
            )
            return Response.html(
                "<!doctype html><title>Development sign-in</title>"
                "<body style='font:16px system-ui;max-width:40rem;margin:3rem auto'>"
                "<h1>Development sign-in</h1><p>This is a stand-in identity provider for "
                f"trying single sign-on. Choose who to be.</p><ul>{links}</ul>"
            )
        code = secrets.token_urlsafe(24)
        self.codes[code] = {
            "subject": chosen,
            "nonce": query.get("nonce"),
            "challenge": query["code_challenge"],
            "redirect_uri": query["redirect_uri"],
            "made": self.now(),
        }
        joiner = "&" if "?" in query["redirect_uri"] else "?"
        answer = urlencode({"code": code, "state": query.get("state", "")})
        return Response.redirect(f"{query['redirect_uri']}{joiner}{answer}")

    def _token(self, form: dict[str, str], headers: dict[str, str]) -> Response:
        client_id, secret = form.get("client_id"), form.get("client_secret")
        basic = headers.get("authorization", "")
        if basic.lower().startswith("basic "):
            client_id, _, secret = base64.b64decode(basic[6:]).decode().partition(":")
        if client_id != self.client_id or secret != self.client_secret:
            return Response.json({"error": "invalid_client"}, 401)
        grant = self.codes.pop(form.get("code", ""), None)  # a code works once
        if form.get("grant_type") != "authorization_code" or grant is None:
            return Response.json({"error": "invalid_grant"}, 400)
        if self.now() - grant["made"] > 300 or form.get("redirect_uri") != grant["redirect_uri"]:
            return Response.json({"error": "invalid_grant"}, 400)
        challenge = _b64(hashlib.sha256(form.get("code_verifier", "").encode()).digest())
        if challenge != grant["challenge"]:
            return Response.json({"error": "invalid_grant", "error_description": "PKCE"}, 400)
        person = self.people[grant["subject"]]
        return Response.json(
            {
                "access_token": secrets.token_urlsafe(16),
                "token_type": "Bearer",
                "expires_in": 300,
                "id_token": self.id_token(person, grant["nonce"]),
            }
        )


# Some of the demo organization's sample people, with the application roles a provider might
# send for them, and one person RiskWren has not met. Map the roles under Admin, Single sign-on.
PEOPLE = [
    Person("u-tobias", "Tobias Larsen", "tobias.larsen@northmere.example", ["riskwren-admins"]),
    Person("u-goran", "Goran Dimitrov", "goran.dimitrov@northmere.example", ["security-leaders"]),
    Person("u-keiko", "Keiko Nakashima", "keiko.nakashima@northmere.example", ["assessors"]),
    Person("u-greta", "Greta Bergstrom", "greta.bergstrom@northmere.example", ["internal-audit"]),
    Person("u-dalia", "Dalia Ferreira", "dalia.ferreira@northmere.example", []),
    Person("u-new", "Noor Valdivia", "noor.valdivia@northmere.example", ["assessors"]),
]


def serve(port: int) -> None:
    provider = Provider(
        f"http://127.0.0.1:{port}", n=DEV_N, d=DEV_D, client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET, people=PEOPLE,
    )  # fmt: skip

    class Handler(BaseHTTPRequestHandler):
        def _answer(self, body: bytes = b"") -> None:
            headers = {key.lower(): value for key, value in self.headers.items()}
            response = provider.handle(self.command, self.path, body, headers)
            self.send_response(response.status)
            for name, value in response.headers.items():
                self.send_header(name, value)
            self.send_header("content-length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

        def do_GET(self) -> None:
            self._answer()

        def do_POST(self) -> None:
            self._answer(self.rfile.read(int(self.headers.get("content-length", "0"))))

    print(f"Development identity provider on http://127.0.0.1:{port} (not for real use)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8099)
    serve(parser.parse_args().port)
