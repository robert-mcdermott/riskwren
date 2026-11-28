"""Sign-in sessions: an opaque random token in an HttpOnly cookie, stored only as a hash.

A session lasts ``idle_hours`` past its last use and never longer than ``max_days`` from
sign-in. Each has its own CSRF token, which the web app sends back in a header with every
change it asks for.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from riskwren.core.clock import utc_now
from riskwren.db.models import Account, FailedSignIn, SessionToken

COOKIE = "riskwren_session"
CSRF_HEADER = "X-CSRF-Token"
TOUCH_EVERY = timedelta(minutes=1)  # write the sliding expiry at most this often
THROTTLE_LIMIT = 5  # for one account from one address
THROTTLE_WIDE = 25  # for one account from anywhere, or one address at any account: 100 an hour
THROTTLE_WINDOW = timedelta(minutes=15)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create(
    session: Session, account_id: int, *, idle_hours: float, max_days: float, user_agent: str | None
) -> tuple[str, SessionToken]:
    """Start a session for an account that has just proved who it is. Returns the token,
    which is given to the browser and never stored, and the session's row."""
    token = secrets.token_urlsafe(32)
    now = utc_now()
    row = SessionToken(
        token_hash=token_hash(token),
        account_id=account_id,
        csrf_token=secrets.token_urlsafe(24),
        created_at=now,
        last_seen_at=now,
        expires_at=min(now + timedelta(hours=idle_hours), now + timedelta(days=max_days)),
        user_agent=(user_agent or "")[:300] or None,
    )
    session.add(row)
    session.flush()
    return token, row


def load(
    session: Session, token: str | None, *, idle_hours: float, max_days: float
) -> tuple[SessionToken, Account] | None:
    """The live session for a token and its account, sliding the expiry; None if there is none."""
    if not token or len(token) > 200:
        return None
    found = session.execute(
        select(SessionToken, Account)
        .join(Account, Account.id == SessionToken.account_id)
        .where(SessionToken.token_hash == token_hash(token))
    ).first()
    if found is None:
        return None
    row, account = found
    now = utc_now()
    if row.revoked_at is not None or row.expires_at <= now or account.status != "active":
        return None
    if now - row.last_seen_at >= TOUCH_EVERY:
        row.last_seen_at = now
        row.expires_at = min(
            now + timedelta(hours=idle_hours), row.created_at + timedelta(days=max_days)
        )
    return row, account


def revoke(session: Session, token: str | None) -> None:
    if token:
        session.execute(
            update(SessionToken)
            .where(SessionToken.token_hash == token_hash(token), SessionToken.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )


def revoke_all(session: Session, account_id: int, *, keep: int | None = None) -> None:
    """End every session of an account, as when its password changes or it is disabled."""
    statement = (
        update(SessionToken)
        .where(SessionToken.account_id == account_id, SessionToken.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    if keep is not None:
        statement = statement.where(SessionToken.id != keep)
    session.execute(statement)


def throttled(session: Session, *keys: str, limit: int = THROTTLE_LIMIT) -> bool:
    """Too many recent failures for any of these keys (an account, an address)?"""
    if not keys:
        return False
    cutoff = utc_now() - THROTTLE_WINDOW
    counts = session.execute(
        select(func.count())
        .select_from(FailedSignIn)
        .where(
            FailedSignIn.key_hash.in_([token_hash(k) for k in keys]),
            FailedSignIn.failed_at >= cutoff,
        )
        .group_by(FailedSignIn.key_hash)
    ).scalars()
    return any(count >= limit for count in counts)


def note_failure(session: Session, *keys: str) -> None:
    now = utc_now()
    session.execute(delete(FailedSignIn).where(FailedSignIn.failed_at < now - THROTTLE_WINDOW))
    if keys:
        session.execute(
            insert(FailedSignIn), [{"key_hash": token_hash(k), "failed_at": now} for k in keys]
        )


def note_success(session: Session, *keys: str) -> None:
    if keys:
        session.execute(
            delete(FailedSignIn).where(FailedSignIn.key_hash.in_([token_hash(k) for k in keys]))
        )
