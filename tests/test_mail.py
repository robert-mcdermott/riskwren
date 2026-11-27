"""Email: notices to an outbox, immediate or as a daily summary, sent over real SMTP to a
server that runs inside the test."""

from __future__ import annotations

import socketserver
import threading
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from email import message_from_string
from email.message import EmailMessage, Message

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren import mail
from riskwren.config import Config, ConfigError, load_config
from riskwren.core.clock import frozen_at
from riskwren.db.engine import Database
from riskwren.db.models import Notice, OutboxMessage
from riskwren.people import accounts, notices
from tests.conftest import Instance
from tests.people import ME, People

Clients = Callable[[str | None], TestClient]
NINE = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)


class Inbox:
    """A mail server that takes one message at a time and keeps what it is given."""

    def __init__(self) -> None:
        self.messages: list[Message] = []
        self.refuse = False
        inbox = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                def say(line: str) -> None:
                    self.wfile.write(f"{line}\r\n".encode())

                say("220 inbox.test ESMTP")
                while True:
                    line = self.rfile.readline().decode("utf-8", "replace").strip()
                    word = line[:4].upper()
                    if not line or word == "QUIT":
                        say("221 bye")
                        return
                    if word in ("EHLO", "HELO"):
                        say("250 inbox.test")
                    elif word == "MAIL" and inbox.refuse:
                        say("451 try again later")
                    elif word == "DATA":
                        say("354 go on")
                        body = []
                        while (part := self.rfile.readline().decode("utf-8", "replace")) != ".\r\n":
                            body.append(part[1:] if part.startswith("..") else part)
                        inbox.messages.append(message_from_string("".join(body)))
                        say("250 kept")
                    else:
                        say("250 ok")

        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def inbox() -> Iterator[Inbox]:
    box = Inbox()
    yield box
    box.close()


@pytest.fixture
def config(instance: Instance, inbox: Inbox) -> Config:
    mailing = replace(
        instance.config.mail, host="127.0.0.1", port=inbox.port, security="none",
        from_address="riskwren@northmere.example", digest_hour=7,
    )  # fmt: skip
    server = replace(instance.config.server, base_url="https://riskwren.northmere.example")
    return replace(instance.config, mail=mailing, server=server)


def tell(db: Database, account_id: int, title: str, href: str = "/risks/RSK-0001") -> None:
    with db.bookkeeping() as session:
        notices.tell_all(session, [account_id], "decision", title, href)


def text_of(message: Message) -> str:
    part = message.get_payload()[0] if message.is_multipart() else message  # type: ignore[index]
    return part.get_payload(decode=True).decode()  # type: ignore[union-attr]


def test_a_notice_is_sent_once_with_a_link_back(
    db: Database, people: People, config: Config, inbox: Inbox
) -> None:
    tell(db, people.accounts["member"], "RSK-0001 was accepted by Leader Person until 2027-05-01")
    with frozen_at(NINE):
        assert mail.run_once(db, config) == {"queued": 1, "digests": 0, "sent": 1, "failed": 0}
        assert mail.run_once(db, config) == {"queued": 0, "digests": 0, "sent": 0, "failed": 0}
    (message,) = inbox.messages
    assert message["To"] == "member@northmere.example"
    assert message["From"] == "RiskWren <riskwren@northmere.example>"
    assert message["Subject"] == "RSK-0001 was accepted by Leader Person until 2027-05-01"
    assert message["Auto-Submitted"] == "auto-generated" and message.is_multipart()
    plain = text_of(message)
    assert plain.startswith("Hello Member Person,")
    assert "https://riskwren.northmere.example/risks/RSK-0001" in plain
    assert "https://riskwren.northmere.example/account" in plain
    page = message.get_payload()[1].get_payload(decode=True).decode()  # type: ignore[index, union-attr]
    assert 'href="https://riskwren.northmere.example/risks/RSK-0001"' in page
    with db.read() as session:
        assert session.scalars(select(Notice.mail_state)).all() == ["queued"]
        assert session.scalars(select(OutboxMessage.status)).all() == ["sent"]


def test_each_person_chooses_how_notices_reach_them(
    db: Database, people: People, config: Config, inbox: Inbox
) -> None:
    with db.write(ME.actor) as session:
        for role, choice in (("member", "digest"), ("steward", "none")):
            accounts.set_email_notices(
                session, accounts.get(session, people.accounts[role]), choice
            )
        with pytest.raises(Exception, match="not saved"):
            accounts.set_email_notices(
                session, accounts.get(session, people.accounts["member"]), "hourly"
            )
    for title in ("First thing", "Second thing"):
        tell(db, people.accounts["member"], title)
    tell(db, people.accounts["steward"], "Not wanted")
    tell(db, people.accounts["assessor"], "Sent at once")
    early = NINE.replace(hour=5)
    with frozen_at(early):
        done = mail.run_once(db, config)
    assert (done["queued"], done["digests"], done["sent"]) == (1, 0, 1)  # too early for summaries
    assert [m["To"] for m in inbox.messages] == ["assessor@northmere.example"]
    with db.bookkeeping() as session:  # one of the two is read in the app before the summary goes
        first = session.scalars(select(Notice).where(Notice.text == "First thing")).one()
        first.read_at = early
    with frozen_at(NINE):
        assert mail.run_once(db, config)["digests"] == 1
        tell(db, people.accounts["member"], "Arrived after today's summary")
        assert mail.run_once(db, config)["digests"] == 0  # one summary a day
    digest = inbox.messages[-1]
    assert digest["Subject"] == "RiskWren: 1 thing for you"
    assert "- Second thing" in text_of(digest) and "First thing" not in text_of(digest)
    with frozen_at(NINE + timedelta(days=1)):
        assert mail.run_once(db, config)["digests"] == 1
    assert "Arrived after today's summary" in text_of(inbox.messages[-1])
    assert "steward@northmere.example" not in [m["To"] for m in inbox.messages]


def test_a_server_that_is_down_is_tried_again_and_then_given_up_on(
    db: Database, people: People, config: Config, inbox: Inbox
) -> None:
    tell(db, people.accounts["member"], "Held up")
    inbox.refuse = True
    with frozen_at(NINE):
        assert mail.run_once(db, config)["failed"] == 1
        assert mail.run_once(db, config) == {
            "queued": 0,
            "digests": 0,
            "sent": 0,
            "failed": 0,
        }  # not yet
    with db.read() as session:
        row = session.scalars(select(OutboxMessage)).one()
        assert (row.status, row.attempts) == ("queued", 1) and "451" in (row.last_error or "")
        assert row.send_after == NINE + timedelta(minutes=5)
    inbox.refuse = False
    with frozen_at(NINE + timedelta(minutes=6)):
        assert mail.run_once(db, config)["sent"] == 1
    assert len(inbox.messages) == 1
    tell(db, people.accounts["member"], "Never arrives")
    inbox.refuse = True
    moment = NINE + timedelta(hours=1)
    for _ in range(mail.MAX_ATTEMPTS):
        with frozen_at(moment):
            mail.run_once(db, config)
        moment += timedelta(days=1)
    with db.read() as session:
        last = session.scalars(select(OutboxMessage).order_by(OutboxMessage.id.desc())).first()
        assert last is not None and (last.status, last.attempts) == ("failed", mail.MAX_ATTEMPTS)
        assert mail.status(session, config)["failed"] == 1


def test_a_message_claimed_by_a_process_that_died_is_taken_up_again(
    db: Database, people: People, config: Config, inbox: Inbox
) -> None:
    tell(db, people.accounts["member"], "Half sent")
    with frozen_at(NINE), db.bookkeeping() as session:
        mail.queue_notices(session, config)
    with frozen_at(NINE):
        assert len(mail._claim(db)) == 1  # and then the process stops
        assert mail._claim(db) == []
    with frozen_at(NINE + timedelta(minutes=11)):
        assert mail.run_once(db, config)["sent"] == 1


def test_without_settings_nothing_is_queued_or_sent(
    instance: Instance, db: Database, people: People
) -> None:
    tell(db, people.accounts["member"], "Nobody is told by email")
    assert mail.run_once(db, instance.config) == {"queued": 0, "digests": 0, "sent": 0, "failed": 0}
    with db.read() as session:
        # And it never will be: turning email on later does not send people their history.
        assert session.scalars(select(Notice.mail_state)).all() == ["skipped"]
        assert session.scalars(select(OutboxMessage)).all() == []


def test_turning_email_on_does_not_send_what_came_before(
    instance: Instance, db: Database, people: People, config: Config, inbox: Inbox
) -> None:
    tell(db, people.accounts["member"], "From before there was email")
    mail.run_once(db, instance.config)  # the mailer's turn, with no mail server named
    tell(db, people.accounts["member"], "From after")
    with frozen_at(NINE):
        assert mail.run_once(db, config)["sent"] == 1
    assert [m["Subject"] for m in inbox.messages] == ["From after"]


def test_the_api_shows_how_email_is_doing_and_sends_a_test(
    instance: Instance, people: People, config: Config, inbox: Inbox
) -> None:
    from riskwren.api.app import create_app
    from tests.people import email_of, sign_in

    plain = create_app(instance.config)
    with TestClient(plain, base_url="http://localhost") as client:
        assert client.get("/api/v1/meta").json()["data"]["mail"] is False
        admin = sign_in(client, email_of("admin"))
        assert admin.post("/api/v1/mail/test").status_code == 502
    app = create_app(config)
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/v1/meta").json()["data"]["mail"] is True
        member = sign_in(client, email_of("member"))
        assert member.get("/api/v1/mail").status_code == 403
        mine = member.get("/api/v1/session/preferences").json()["data"]
        assert mine["email_notices"] == "immediate" and mine["email"] is True
        assert mine["choices"] == ["immediate", "digest", "none"]
        saved = member.put("/api/v1/session/preferences", json={"email_notices": "digest"})
        assert saved.json()["data"]["email_notices"] == "digest"
        refused = member.put("/api/v1/session/preferences", json={"email_notices": "weekly"})
        assert refused.status_code == 422
    with TestClient(app, base_url="http://localhost") as client:
        admin = sign_in(client, email_of("admin"))
        seen = admin.get("/api/v1/mail").json()["data"]
        assert (
            seen["enabled"]
            and seen["from_address"] == "riskwren@northmere.example"
            and seen["links"]
        )
        assert admin.post("/api/v1/mail/test").json()["data"] == {
            "sent_to": "admin@northmere.example"
        }
        assert "This is a test message from RiskWren" in text_of(inbox.messages[-1])
        inbox.refuse = True
        failed = admin.post("/api/v1/mail/test")
        assert failed.status_code == 502 and "451" in failed.json()["detail"]


@pytest.mark.parametrize(
    ("section", "message"),
    [
        ('host = "smtp.example.org"', "host and from_address go together"),
        ('host = "smtp.example.org"\nfrom_address = "nobody"', "must be an email address"),
        ('host = "h"\nfrom_address = "a@b.example"\nsecurity = "maybe"', "starttls"),
        ('host = "h"\nfrom_address = "a@b.example"\ndigest_hour = 30', "digest_hour"),
        ('host = "h"\nfrom_address = "a@b.example"\npassword = "hunter2"', "never"),
    ],
)
def test_settings_are_checked(tmp_path, section: str, message: str) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "riskwren.toml"
    path.write_text(f"[mail]\n{section}\n", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        load_config(path, env={})
    assert message in " ".join(caught.value.problems)


def test_a_message_is_safe_whatever_a_notice_says() -> None:
    how = mail.Look("RiskWren", "Northmere", "https://riskwren.northmere.example")
    text, page = mail.compose(
        how, "Hello <b>You</b>", [('A "title" <script>alert(1)</script>', "/x?a=1&b=2")]
    )
    assert "<script>" not in page and "&lt;script&gt;" in page and "&amp;b=2" in page
    assert "<script>" in text  # plain text is plain text
    bare = mail.compose(mail.Look("RiskWren", "", ""), "Hello", [("Something", "/x")])[0]
    signed = mail.compose(
        mail.Look("RiskWren", "", "", "Security Office <ask us>"), "Hello", [("Something", "/x")]
    )
    assert (
        signed[0].rstrip().endswith("Security Office <ask us>")
        and "Security Office &lt;ask us&gt;" in signed[1]
    )
    assert "http" not in bare and "Open RiskWren to see more." in bare
    _ = EmailMessage


def test_a_link_to_a_questionnaire_is_sent_to_the_contact_and_not_kept(
    db: Database, people: People, config: Config, inbox: Inbox
) -> None:
    from riskwren.inventory import records
    from riskwren.inventory.registry import THIRD_PARTY
    from riskwren.thirdparty import contacts, reviews, tiering
    from tests.test_risks import who

    steward = who(db, people, "steward")
    with frozen_at(NINE), db.write(steward.actor) as session:
        party = records.create(session, steward, THIRD_PARTY, {
            "name": "Tallyfield Surveys", "kind": "service_provider",
            "org_unit_id": people.units["IMM"]})  # fmt: skip
        tiering.record(session, steward, party, {"information": "internal",
                       "access": ["on_site"], "dependency": "little"}, None, None)  # fmt: skip
        contact = contacts.add(session, steward, party,
                               {"name": "Ana Ruiz", "email": "ana@tallyfield.example"})  # fmt: skip
        review = reviews.start(session, steward, party, {})
        token = reviews.send(session, steward, review, contact_id=contact.id)
        url = f"https://riskwren.northmere.example/respond#{token}"
        assert mail.queue_link(session, config, review, url)
    with frozen_at(NINE):
        assert mail.run_once(db, config)["sent"] == 1
    (message,) = inbox.messages
    assert message["To"] == "ana@tallyfield.example"
    assert "Tallyfield Surveys" in message["Subject"]
    assert url in text_of(message)
    with db.read() as session:
        kept = session.scalars(select(OutboxMessage)).one()
        assert kept.status == "sent" and token not in kept.body_text
        assert kept.body_html is None and kept.body_text == mail.CLEARED
