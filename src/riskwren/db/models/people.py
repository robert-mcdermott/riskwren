"""The organization and its people: units, accounts, credentials, roles, and sign-in sessions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from riskwren.db.base import Base
from riskwren.db.types import UtcDateTime

UNIT_STATUSES = ("active", "closed")
ACCOUNT_STATUSES = ("invited", "active", "disabled")
GRANT_SOURCES = ("local", "provider")


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class OrgUnit(Base):
    """A node in the organization's hierarchy: a division, department, lab, core, or office."""

    __tablename__ = "org_unit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"))
    kind: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(60), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(_one_of("status", UNIT_STATUSES), name="status"),
        Index("ix_org_unit_parent_id", "parent_id"),
    )


class Account(Base):
    """A person who can sign in or be named on a record."""

    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="invited")
    time_zone: Mapped[str | None] = mapped_column(String(64))
    # How notices reach this person by email, where email is set up: as they happen, in a
    # daily summary, or not at all.
    email_notices: Mapped[str] = mapped_column(String(16), default="immediate")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (CheckConstraint(_one_of("status", ACCOUNT_STATUSES), name="status"),)


class Credential(Base):
    """A local password, kept only as a hash."""

    __tablename__ = "credential"
    __audit_redact__ = frozenset({"password_hash"})
    __audit_parent__ = ("account", "account_id")

    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(UtcDateTime)


class Membership(Base):
    """Which units a person works in. It drives defaults and visibility, and grants nothing."""

    __tablename__ = "membership"
    __audit_parent__ = ("account", "account_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    org_unit_id: Mapped[int] = mapped_column(ForeignKey("org_unit.id"))
    title: Mapped[str | None] = mapped_column(String(200))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("account_id", "org_unit_id"),
        Index("ix_membership_org_unit_id", "org_unit_id"),
    )


class RoleGrant(Base):
    """A role held by an account, optionally scoped to a unit; a leader may carry a limit."""

    __tablename__ = "role_grant"
    __audit_parent__ = ("account", "account_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    role: Mapped[str] = mapped_column(String(24))
    org_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"))
    accept_limit: Mapped[str | None] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(16), default="local")
    granted_by: Mapped[int | None] = mapped_column(Integer)
    granted_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        CheckConstraint(_one_of("source", GRANT_SOURCES), name="source"),
        Index("ix_role_grant_account_id", "account_id"),
        Index("ix_role_grant_role", "role"),
    )


class SessionToken(Base):
    """A sign-in session. Only a hash of its token is stored."""

    __tablename__ = "session_token"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    user_agent: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (Index("ix_session_token_account_id", "account_id"),)


class FailedSignIn(Base):
    """A failed sign-in, kept briefly to slow down guessing. Keys are stored hashed."""

    __tablename__ = "failed_sign_in"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64))
    failed_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_failed_sign_in_key_hash", "key_hash", "failed_at"),)


class Identity(Base):
    """Who an account is at the identity provider: the provider's own, stable name for them.
    People are matched by this, never by an email address the provider has not vouched for."""

    __tablename__ = "identity"
    __audit_parent__ = ("account", "account_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    issuer: Mapped[str] = mapped_column(String(300))
    subject: Mapped[str] = mapped_column(String(300))
    email: Mapped[str | None] = mapped_column(String(254))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (
        UniqueConstraint("issuer", "subject"),
        Index("ix_identity_account_id", "account_id"),
    )


class ProviderMapping(Base):
    """A rule that turns an application role or a group from the identity provider into a
    role here: for the whole organization or one unit, with a leader's limit, or into
    membership of a unit."""

    __tablename__ = "provider_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_value: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(24))
    org_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"))
    accept_limit: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (Index("ix_provider_mapping_claim_value", "claim_value"),)


class SignInRequest(Base):
    """A single sign-on round trip that has been started and not yet finished. Kept for a few
    minutes and used once."""

    __tablename__ = "sign_in_request"
    __audit__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True)
    nonce: Mapped[str] = mapped_column(String(64))
    verifier: Mapped[str] = mapped_column(String(128))
    next_path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
