"""Reading and checking the signed tokens an identity provider issues.

Only what RiskWren needs: compact JSON Web Tokens signed with RS256, checked against the
provider's published keys. Verifying an RSA signature uses only the public key, so it is
done here with integer arithmetic and the standard library's SHA-256, and no cryptography
package is needed. Anything else (another algorithm, an unsigned token, a token that is
encrypted) is refused.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

# The fixed bytes that precede a SHA-256 digest inside an RSA PKCS #1 v1.5 signature.
_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")
LEEWAY = 120  # seconds of clock difference tolerated between RiskWren and the provider


class TokenError(Exception):
    """The token cannot be trusted. The message says why, for the log and never for the page."""


@dataclass(frozen=True)
class Key:
    kid: str | None
    n: int
    e: int


def b64url_decode(text: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError) as exc:
        raise TokenError("not base64url") from exc


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def keys_from_jwks(document: Mapping[str, Any]) -> list[Key]:
    """The RSA signing keys in a provider's published key set."""
    keys = []
    for entry in document.get("keys", []):
        if entry.get("kty") != "RSA" or entry.get("use", "sig") != "sig":
            continue
        try:
            n = int.from_bytes(b64url_decode(entry["n"]), "big")
            e = int.from_bytes(b64url_decode(entry["e"]), "big")
        except (KeyError, TokenError):
            continue
        if n.bit_length() >= 2048 and e >= 3:
            keys.append(Key(entry.get("kid"), n, e))
    return keys


def _verify_rs256(key: Key, message: bytes, signature: bytes) -> bool:
    size = (key.n.bit_length() + 7) // 8
    if len(signature) != size:
        return False
    number = int.from_bytes(signature, "big")
    if number >= key.n:
        return False
    recovered = pow(number, key.e, key.n).to_bytes(size, "big")
    digest = hashlib.sha256(message).digest()
    padding = size - len(_SHA256_PREFIX) - len(digest) - 3
    if padding < 8:
        return False
    expected = b"\x00\x01" + b"\xff" * padding + b"\x00" + _SHA256_PREFIX + digest
    return hmac.compare_digest(recovered, expected)


def verify(
    token: str,
    keys: Iterable[Key],
    *,
    issuer: str,
    audience: str,
    now: float,
    nonce: str | None = None,
) -> dict[str, Any]:
    """The claims of a token, once its signature, issuer, audience, and times all check."""
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("not a signed token")
    try:
        header = json.loads(b64url_decode(parts[0]))
        claims = json.loads(b64url_decode(parts[1]))
    except (ValueError, UnicodeDecodeError) as exc:
        raise TokenError("not JSON") from exc
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise TokenError("not JSON objects")
    if header.get("alg") != "RS256":
        raise TokenError(f"signed with {header.get('alg')!r}, and only RS256 is accepted")
    kid = header.get("kid")
    candidates = [key for key in keys if kid is None or key.kid is None or key.kid == kid]
    message = f"{parts[0]}.{parts[1]}".encode("ascii")
    signature = b64url_decode(parts[2])
    if not any(_verify_rs256(key, message, signature) for key in candidates):
        raise TokenError("the signature does not match any of the provider's keys")

    if claims.get("iss") != issuer:
        raise TokenError("issued by someone else")
    audiences = claims.get("aud")
    audiences = [audiences] if isinstance(audiences, str) else list(audiences or [])
    if audience not in audiences:
        raise TokenError("meant for another application")
    if len(audiences) > 1 and claims.get("azp") != audience:
        raise TokenError("meant for several applications, and not authorized for this one")
    expires = claims.get("exp")
    if not isinstance(expires, (int, float)) or now > expires + LEEWAY:
        raise TokenError("expired")
    not_before = claims.get("nbf")
    if isinstance(not_before, (int, float)) and now < not_before - LEEWAY:
        raise TokenError("not valid yet")
    issued = claims.get("iat")
    if isinstance(issued, (int, float)) and issued > now + LEEWAY:
        raise TokenError("issued in the future")
    if nonce is not None and not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise TokenError("not the answer to this sign-in")
    if not claims.get("sub"):
        raise TokenError("names nobody")
    return claims
