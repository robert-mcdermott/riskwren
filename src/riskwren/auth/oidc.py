"""The OpenID Connect client: what RiskWren says to an identity provider, and what it accepts
back. The authorization code flow with PKCE, and nothing else.

The provider's addresses are read from its discovery document, its signing keys from the key
set that document names, and both are remembered for an hour. A token signed by a key
RiskWren has not seen makes it fetch the keys again once, because providers rotate them.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

from riskwren.auth import tokens
from riskwren.config import SsoConfig
from riskwren.core.errors import RiskWrenError

REMEMBER = 3600.0
TIMEOUT = 10.0


class SignInFailed(RiskWrenError):
    """Single sign-on did not complete. The message is for the log; the person is told only
    that it did not work."""


@dataclass(frozen=True)
class Challenge:
    state: str
    nonce: str
    verifier: str

    @property
    def code_challenge(self) -> str:
        digest = hashlib.sha256(self.verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def new_challenge() -> Challenge:
    return Challenge(
        secrets.token_urlsafe(32), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    )


class Client:
    def __init__(self, config: SsoConfig, *, transport: httpx.BaseTransport | None = None) -> None:
        self.config = config
        self.issuer = config.issuer.rstrip("/")
        self._transport = transport
        self._lock = threading.Lock()
        self._metadata: tuple[float, dict[str, Any]] | None = None
        self._keys: tuple[float, list[tokens.Key]] | None = None

    def _http(self) -> httpx.Client:
        return httpx.Client(transport=self._transport, timeout=TIMEOUT, follow_redirects=False)

    def _get(self, url: str) -> dict[str, Any]:
        try:
            with self._http() as http:
                response = http.get(url, headers={"accept": "application/json"})
            response.raise_for_status()
            document = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SignInFailed(f"the identity provider could not be read at {url}: {exc}") from exc
        if not isinstance(document, dict):
            raise SignInFailed(f"the identity provider sent something unexpected from {url}")
        return document

    def _same_site(self, url: str) -> bool:
        """An endpoint must be https (or on this machine, for development)."""
        parts = urlsplit(url)
        return parts.scheme == "https" or (
            parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1")
        )

    def metadata(self) -> dict[str, Any]:
        with self._lock:
            if self._metadata and time.monotonic() - self._metadata[0] < REMEMBER:
                return self._metadata[1]
        document = self._get(f"{self.issuer}/.well-known/openid-configuration")
        if str(document.get("issuer", "")).rstrip("/") != self.issuer:
            raise SignInFailed(
                "the identity provider describes a different issuer than the one configured"
            )
        for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            if not isinstance(document.get(name), str) or not self._same_site(document[name]):
                raise SignInFailed(f"the identity provider's {name} is missing or not https")
        with self._lock:
            self._metadata = (time.monotonic(), document)
        return document

    def keys(self, *, fresh: bool = False) -> list[tokens.Key]:
        with self._lock:
            if not fresh and self._keys and time.monotonic() - self._keys[0] < REMEMBER:
                return self._keys[1]
        found = tokens.keys_from_jwks(self._get(self.metadata()["jwks_uri"]))
        if not found:
            raise SignInFailed("the identity provider publishes no usable signing keys")
        with self._lock:
            self._keys = (time.monotonic(), found)
        return found

    def secret(self) -> str:
        value = os.environ.get(self.config.client_secret_env, "")
        if not value:
            raise SignInFailed(
                f"the client secret is not set: put it in the {self.config.client_secret_env} "
                "environment variable"
            )
        return value

    def authorization_url(self, challenge: Challenge, redirect_uri: str) -> str:
        query = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.config.scopes,
            "state": challenge.state,
            "nonce": challenge.nonce,
            "code_challenge": challenge.code_challenge,
            "code_challenge_method": "S256",
        }
        endpoint = self.metadata()["authorization_endpoint"]
        return f"{endpoint}{'&' if '?' in endpoint else '?'}{urlencode(query)}"

    def redeem(self, code: str, *, verifier: str, nonce: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange the code for an ID token and return its claims, once every check passes."""
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.config.client_id,
            "client_secret": self.secret(),
            "code_verifier": verifier,
        }
        try:
            with self._http() as http:
                response = http.post(
                    self.metadata()["token_endpoint"], data=form,
                    headers={"accept": "application/json"},
                )  # fmt: skip
            answer = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SignInFailed(
                f"the identity provider did not answer the token request: {exc}"
            ) from exc
        if response.status_code != 200 or not isinstance(answer, dict) or "id_token" not in answer:
            reason = (
                answer.get("error_description") or answer.get("error")
                if isinstance(answer, dict)
                else None
            )
            raise SignInFailed(
                f"the identity provider refused the code: {reason or response.status_code}"
            )
        check = {
            "issuer": self.issuer,
            "audience": self.config.client_id,
            "now": time.time(),
            "nonce": nonce,
        }
        try:
            try:
                return tokens.verify(answer["id_token"], self.keys(), **check)
            except tokens.TokenError:
                return tokens.verify(answer["id_token"], self.keys(fresh=True), **check)
        except tokens.TokenError as exc:
            raise SignInFailed(f"the ID token was not accepted: {exc}") from exc
