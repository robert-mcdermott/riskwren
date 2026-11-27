"""Email: notices sent as they happen, or gathered into a daily summary, as each person
chooses. Optional: with no mail server named, nothing here is attempted and notices are read
in the app.

Nothing is sent straight from the request that caused it. A notice is written to the
database; the mailer picks it up, writes the message to an outbox in the same database, and
sends from there. A restart loses nothing, a mail server that is down is tried again later,
and several server processes never send the same message twice.
"""

from __future__ import annotations

import html
import logging
import os
import smtplib
import ssl
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any, Protocol

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from riskwren import PRODUCT_NAME
from riskwren.config import Config, MailConfig
from riskwren.core.clock import utc_now
from riskwren.core.errors import RiskWrenError
from riskwren.db.engine import Database
from riskwren.db.models import Account, Notice, OutboxMessage
from riskwren.program import branding

log = logging.getLogger("riskwren.mail")
PREFERENCES = ("immediate", "digest", "none")
MAX_ATTEMPTS = 6
BATCH = 50
EVERY_SECONDS = 30


class MailError(RiskWrenError):
    """The message could not be handed to the mail server."""


class Sender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class SmtpSender:
    def __init__(self, config: MailConfig) -> None:
        self.config = config

    def _connect(self) -> smtplib.SMTP:
        config = self.config
        if config.security == "tls":
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                config.host, config.port, timeout=20, context=ssl.create_default_context()
            )
        else:
            server = smtplib.SMTP(config.host, config.port, timeout=20)
            if config.security == "starttls":
                server.starttls(context=ssl.create_default_context())
        if config.username:
            server.login(config.username, os.environ.get(config.password_env, ""))
        return server

    def check(self) -> None:
        """Connect and sign in, sending nothing."""
        try:
            with self._connect() as server:
                server.noop()
        except (OSError, smtplib.SMTPException) as exc:
            raise MailError(f"the mail server cannot be used: {exc}") from exc

    def send(self, message: EmailMessage) -> None:
        try:
            with self._connect() as server:
                server.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise MailError(str(exc)) from exc


# --- Writing messages ---------------------------------------------------------------------


@dataclass(frozen=True)
class Look:
    product: str
    organization: str
    base_url: str
    footer: str = ""

    def link(self, href: str | None) -> str | None:
        return f"{self.base_url}{href}" if self.base_url and href else None


def look(session: Session, config: Config) -> Look:
    brand = branding.load(session)
    return Look(
        brand.product_name or PRODUCT_NAME,
        brand.organization_name,
        config.server.base_url,
        brand.email_footer,
    )


def compose(
    how: Look, greeting: str, items: Sequence[tuple[str, str | None]], *, digest: bool = False
) -> tuple[str, str]:
    """A message as plain text and as HTML. ``items`` are (what happened, where to see it)."""
    intro = (
        "Here is what happened since your last summary."
        if digest
        else "Something needs you, or has changed."
    )
    account = how.link("/account")
    footer = [
        f"Sent by {how.product}" + (f" at {how.organization}" if how.organization else "") + ".",
        "To get these as a daily summary, or not at all, change Email under Your account"
        + (f": {account}" if account else "."),
    ]
    if how.footer:
        footer.append(how.footer)
    lines = [f"{greeting},", "", intro, ""]
    for title, href in items:
        lines.append(f"- {title}")
        if how.link(href):
            lines.append(f"  {how.link(href)}")
    if not how.base_url:
        lines += ["", f"Open {how.product} to see more."]
    lines += ["", "--", *footer]
    escape = html.escape
    rows = "".join(
        '<li style="margin:0 0 12px 0">'
        + (
            f'<a href="{escape(how.link(href) or "", quote=True)}" '
            f'style="color:#0f5876;font-weight:600">{escape(title)}</a>'
            if how.link(href)
            else f"<strong>{escape(title)}</strong>"
        )
        + "</li>"
        for title, href in items
    )
    page = (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;font-size:15px;'
        'line-height:1.5;color:#1c1b19;max-width:36em">'
        f"<p>{escape(greeting)},</p><p>{escape(intro)}</p>"
        f'<ul style="padding-left:20px">{rows}</ul>'
        f'<p style="color:#6b6862;font-size:13px;border-top:1px solid #e3e0da;padding-top:12px">'
        f"{'<br>'.join(escape(line) for line in footer)}</p></div>"
    )
    return "\n".join(lines), page


def _queue(
    session: Session, account: Account, subject: str, text: str, page: str, *, kind: str = "notice",
    digest_on: Any = None,
) -> OutboxMessage:  # fmt: skip
    now = utc_now()
    # A subject is one line. A line break in it, from a name someone typed, would stop the
    # message being built at all.
    subject = " ".join(subject.split())
    message = OutboxMessage(
        account_id=account.id, to_address=account.email, subject=subject[:300], body_text=text,
        body_html=page, kind=kind, digest_on=digest_on, status="queued", attempts=0,
        created_at=now, send_after=now,
    )  # fmt: skip
    session.add(message)
    return message


# --- From notices to the outbox -----------------------------------------------------------


def queue_notices(session: Session, config: Config) -> int:
    """Turn notices nobody has looked at yet into messages, for people who want each one."""
    rows = session.execute(
        select(Notice, Account)
        .join(Account, Account.id == Notice.account_id)
        .where(Notice.mail_state.is_(None))
        .order_by(Notice.id)
        .limit(500)
        .with_for_update(skip_locked=True, of=Notice)
    ).all()
    how = look(session, config) if rows else None
    queued = 0
    for notice, account in rows:
        if account.status != "active" or account.email_notices == "none":
            notice.mail_state = "skipped"
        elif account.email_notices == "digest":
            notice.mail_state = "digest"
        else:
            assert how is not None
            text, page = compose(how, f"Hello {account.display_name}", [(notice.text, notice.href)])
            _queue(session, account, notice.text, text, page)
            notice.mail_state = "queued"
            queued += 1
    session.flush()
    return queued


def queue_digests(session: Session, config: Config) -> int:
    """Once a day, after the hour set, gather each person's waiting notices into one message."""
    now = utc_now()
    if now.hour < config.mail.digest_hour:
        return 0
    today = now.date()
    rows = session.execute(
        select(Notice, Account)
        .join(Account, Account.id == Notice.account_id)
        .where(Notice.mail_state == "digest")
        .order_by(Notice.account_id, Notice.id)
        .with_for_update(skip_locked=True, of=Notice)
    ).all()
    by_account: dict[int, tuple[Account, list[Notice]]] = {}
    for notice, account in rows:
        by_account.setdefault(account.id, (account, []))[1].append(notice)
    if not by_account:
        return 0
    already = set(
        session.scalars(
            select(OutboxMessage.account_id).where(
                OutboxMessage.digest_on == today, OutboxMessage.account_id.in_(by_account)
            )
        )
    )
    how = look(session, config)
    made = 0
    for account_id, (account, notices) in by_account.items():
        if account_id in already:
            continue  # today's summary has gone; these wait for tomorrow's
        unread = [n for n in notices if n.read_at is None]
        for notice in notices:
            notice.mail_state = "queued" if unread else "skipped"
        if not unread or account.status != "active":
            continue
        count = len(unread)
        subject = f"{how.product}: {count} thing{'s' if count != 1 else ''} for you"
        text, page = compose(
            how, f"Hello {account.display_name}", [(n.text, n.href) for n in unread], digest=True
        )
        _queue(session, account, subject, text, page, kind="digest", digest_on=today)
        made += 1
    session.flush()
    return made


# --- Sending ------------------------------------------------------------------------------


def _claim(db: Database) -> list[int]:
    """Take a batch of messages to send, so that no other process takes the same ones."""
    now = utc_now()
    with db.bookkeeping() as session:
        rows = session.scalars(
            select(OutboxMessage)
            .where(OutboxMessage.status.in_(("queued", "sending")), OutboxMessage.send_after <= now)
            .order_by(OutboxMessage.id)
            .limit(BATCH)
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.status = "sending"
            row.send_after = now + timedelta(minutes=10)  # taken up again if this process dies
        return [row.id for row in rows]


def _message(row: OutboxMessage, config: MailConfig, product: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((config.from_name or product, config.from_address))
    message["To"] = row.to_address
    message["Subject"] = row.subject
    message["Message-ID"] = make_msgid(domain=config.from_address.rsplit("@", 1)[-1])
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(row.body_text)
    if row.body_html:
        message.add_alternative(row.body_html, subtype="html")
    return message


def send_queued(db: Database, config: Config, sender: Sender) -> tuple[int, int]:
    """Send what is waiting. Returns how many were sent and how many could not be."""
    sent = failed = 0
    with db.read() as session:
        product = look(session, config).product
    for message_id in _claim(db):
        with db.read() as session:
            row = session.get(OutboxMessage, message_id)
            if row is None or row.status != "sending":
                continue
            try:
                message: EmailMessage | ValueError = _message(row, config.mail, product)
            except ValueError as exc:
                message = exc
        # Sent with no database session open: a mail server that is slow to answer must never
        # hold anyone else's work up.
        problem: Exception | None = None
        try:
            if isinstance(message, ValueError):
                raise message
            sender.send(message)
        except (MailError, ValueError) as exc:
            problem = exc
        with db.bookkeeping() as session:
            row = session.get(OutboxMessage, message_id)
            if row is None:
                continue
            if problem is not None:
                exc = problem
                # ValueError: a message that cannot be built, such as a header with a line
                # break in it. It counts against this message alone, never the ones after it.
                row.attempts += 1
                row.last_error = str(exc)[:300]
                if row.attempts >= MAX_ATTEMPTS:
                    row.status = "failed"
                    log.error("giving up on message %s to %s: %s", row.id, row.to_address, exc)
                else:
                    row.status = "queued"
                    row.send_after = utc_now() + timedelta(minutes=5 * 2 ** (row.attempts - 1))
                failed += 1
            else:
                row.status, row.sent_at, row.last_error = "sent", utc_now(), None
                sent += 1
            if row.kind == LINK and row.status in ("sent", "failed"):
                # It carried a link that lets whoever holds it answer as someone: once it has
                # gone, or will not go, its words are not kept.
                row.body_text, row.body_html = CLEARED, None
    return sent, failed


def run_once(db: Database, config: Config, sender: Sender | None = None) -> dict[str, int]:
    """One turn of the mailer: notices to the outbox, summaries if it is time, then send."""
    if not config.mail.enabled:
        # Notices written while there is no mail server are never sent as email later: turning
        # email on must not send everyone their history.
        with db.bookkeeping() as session:
            session.execute(
                update(Notice).where(Notice.mail_state.is_(None)).values(mail_state="skipped")
            )
        return {"queued": 0, "digests": 0, "sent": 0, "failed": 0}
    with db.bookkeeping() as session:
        queued = queue_notices(session, config)
        digests = queue_digests(session, config)
    sent, failed = send_queued(db, config, sender or SmtpSender(config.mail))
    return {"queued": queued, "digests": digests, "sent": sent, "failed": failed}


def status(session: Session, config: Config) -> dict[str, Any]:
    counts = dict(
        session.execute(
            select(OutboxMessage.status, func.count()).group_by(OutboxMessage.status)
        ).all()  # type: ignore[arg-type]
    )
    last = session.scalars(
        select(OutboxMessage)
        .where(OutboxMessage.last_error.is_not(None))
        .order_by(OutboxMessage.id.desc())
    ).first()
    mail = config.mail
    return {
        "enabled": mail.enabled,
        "host": mail.host,
        "port": mail.port,
        "security": mail.security,
        "from_address": mail.from_address,
        "from_name": mail.from_name,
        "digest_hour": mail.digest_hour,
        "links": bool(config.server.base_url),
        "waiting": counts.get("queued", 0) + counts.get("sending", 0),
        "sent": counts.get("sent", 0),
        "failed": counts.get("failed", 0),
        "last_error": last.last_error if last else None,
    }


def send_test(db: Database, config: Config, account: Account, sender: Sender | None = None) -> None:
    """Send one message now, to prove the settings work. Raises ``MailError`` if they do not."""
    if not config.mail.enabled:
        raise MailError("email is not set up: give [mail] a host and a from address")
    with db.read() as session:
        how = look(session, config)
    text, page = compose(
        how, f"Hello {account.display_name}",
        [(f"This is a test message from {how.product}. Email is working.", "/")],
    )  # fmt: skip
    row = OutboxMessage(to_address=account.email, subject=f"{how.product}: test message",
                        body_text=text, body_html=page)  # fmt: skip
    (sender or SmtpSender(config.mail)).send(_message(row, config.mail, how.product))


# --- Links to people without accounts -------------------------------------------------------

LINK = "link"  # the kind of message that carries a respondent link; cleared once sent
CLEARED = "(Cleared once sent: it carried a link to answer a questionnaire.)"


def queue_link(session: Session, config: Config, review: Any, url: str) -> bool:
    """Send a contact the link to a questionnaire. Returns whether a message was queued.
    The message holds the token, so its words are cleared once it has gone (``send_queued``)."""
    from riskwren.db.models import ThirdParty, ThirdPartyContact

    contact = session.get(ThirdPartyContact, review.contact_id)
    party = session.get(ThirdParty, review.third_party_id)
    if contact is None or party is None:
        return False
    how = look(session, config)
    asker = session.get(Account, review.created_by) if review.created_by else None
    who = how.organization or how.product
    due = f"{review.due_on.day} {review.due_on:%B %Y}" if review.due_on else None
    lines = [
        f"Dear {contact.name},",
        "",
        f"{who} asks {party.name} to answer a short set of questions about how it protects the "
        "information and systems it handles for us." + (f" Please answer by {due}." if due else ""),
        "",
        "Open this link to answer. You do not need an account, and you can save your answers "
        "and come back to them with the same link:",
        "",
        url,
        "",
        "The link is for you alone: anyone who has it can answer in your name until it expires.",
    ]
    if asker is not None:
        lines += ["", f"If you have a question, reply to {asker.display_name} at {asker.email}."]
    lines += [
        "",
        "--",
        f"Sent by {how.product}" + (f" for {how.organization}" if how.organization else "") + ".",
    ]
    text = "\n".join(lines)
    escape = html.escape
    page = (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;font-size:15px;'
        'line-height:1.5;color:#1c1b19;max-width:36em">'
        + "".join(
            f'<p><a href="{escape(url, quote=True)}" style="color:#0f5876;font-weight:600">'
            "Open the questionnaire</a></p>"
            if line == url
            else (f"<p>{escape(line)}</p>" if line else "")
            for line in lines
        )
        + "</div>"
    )
    now = utc_now()
    session.add(
        OutboxMessage(
            account_id=None, to_address=contact.email,
            subject=" ".join(f"Questions from {who} for {party.name}".split())[:300],
            body_text=text, body_html=page, kind=LINK, status="queued", attempts=0,
            created_at=now, send_after=now,
        )
    )  # fmt: skip
    session.flush()
    return True
