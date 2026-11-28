"""Password hashing with the standard library's scrypt (ADR-0008).

Stored as ``scrypt$N$r$p$salt$hash`` (base64), so the cost can rise later without breaking
existing hashes: verification always uses the parameters stored with the hash.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from riskwren.core.errors import Invalid

SCRYPT_N = 2**15  # about 32 MiB and a few tens of milliseconds per check
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LENGTH = 32
MIN_LENGTH = 12
MAX_LENGTH = 128  # ASVS 2.1.2: at least 64 allowed, more than 128 refused


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=max(64 * 1024 * 1024, 129 * n * r * p),
        dklen=KEY_LENGTH,
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = _derive(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(key)
        actual = _derive(password, base64.b64decode(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


_DUMMY: list[str] = []


def burn_time(password: str) -> None:
    """Spend the same effort as a real check, so unknown accounts take as long as known ones."""
    if not _DUMMY:
        _DUMMY.append(hash_password(secrets.token_urlsafe(16)))
    verify_password(password, _DUMMY[0])


def check_rules(password: str, *, email: str = "") -> None:
    """Length over complexity: long, any characters, no composition rules, no forced rotation."""
    problem = None
    if len(password) < MIN_LENGTH:
        problem = f"Use at least {MIN_LENGTH} characters."
    elif len(password) > MAX_LENGTH:
        problem = f"Use at most {MAX_LENGTH} characters."
    elif len(set(password)) < 4:
        problem = "Use more varied characters."
    else:
        name = email.split("@")[0].lower()
        if len(name) >= 4 and name in password.lower():
            problem = "Do not include your email name in the password."
    if problem:
        raise Invalid("That password cannot be used.", {"password": problem})
