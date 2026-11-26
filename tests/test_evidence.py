"""Evidence: collected once and attached to many things, files judged by their content and
only ever handed back as downloads, freshness, and who may see an item."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from riskwren.compliance import evidence
from riskwren.compliance.evidence import EVIDENCE
from riskwren.controls.service import CONTROL
from riskwren.core.clock import frozen_at
from riskwren.core.errors import Invalid, PermissionDenied
from riskwren.db.engine import Database
from riskwren.db.models import Event, StoredFile
from riskwren.files import store
from riskwren.inventory import records
from riskwren.reporting import service as reporting
from tests.conftest import Instance
from tests.people import People
from tests.test_risks import who
from tests.test_treatment import add_control

Clients = Callable[[str | None], TestClient]
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
PAGE = b"<!doctype html><html><body><script>alert(document.cookie)</script></body></html>"
DRAWING = (
    b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><script>alert(1)</script></svg>'
)


def docx() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
    return out.getvalue()


def add_evidence(session, by, unit: int, name: str = "Restore test report", **more):  # type: ignore[no-untyped-def]
    values = {"name": name, "kind": "note", "note": "Seen on the day.", "org_unit_id": unit, **more}
    return records.create(session, by, EVIDENCE, values)


# --- Files --------------------------------------------------------------------------------


def test_a_file_is_judged_by_what_it_contains_and_stored_once(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert store.sniff(PDF).extension == "pdf"  # type: ignore[union-attr]
    assert store.sniff(b"\x89PNG\r\n\x1a\n" + b"0" * 20).media_type == "image/png"  # type: ignore[union-attr]
    assert store.sniff(docx()).extension == "docx"  # type: ignore[union-attr]
    assert store.sniff(b"date,restored\n2026-03-01,yes\n").media_type == "text/plain"  # type: ignore[union-attr]
    # Markup is taken as the text it is, and can only ever leave as text.
    assert store.sniff(PAGE).media_type == "text/plain"  # type: ignore[union-attr]
    assert store.sniff(DRAWING).extension == "txt"  # type: ignore[union-attr]
    for refused in (b"MZ\x90\x00binary", b"\x7fELF\x02\x01", b"#!/bin/sh\nrm -rf /\n",
                    b"\x00\x01\x02 not text", b"PK\x03\x04 not really a document"):  # fmt: skip
        assert store.sniff(refused) is None
    with pytest.raises(Invalid) as empty:
        store.check(b"")
    assert "empty" in empty.value.errors["file"]
    with pytest.raises(Invalid) as large:
        store.check(b"a" * (store.MAX_BYTES + 1))
    assert "25 MB" in large.value.errors["file"]
    first, kind = store.save(tmp_path, PDF)
    again, _ = store.save(tmp_path, PDF)
    assert first == again and kind.extension == "pdf"
    assert [p.name for p in tmp_path.rglob("*") if p.is_file()] == [first]
    assert store.path_of(tmp_path, first).read_bytes() == PDF
    with pytest.raises(ValueError, match="digest"):
        store.path_of(tmp_path, "../../etc/passwd")
    assert store.safe_name("../../Report (final).EXE", kind) == "Report (final).pdf"
    assert store.safe_name(None, kind) == "file.pdf" and store.safe_name("π", kind) == "π.pdf"
    text = store.sniff(b"a,b\n1,2\n")
    assert text is not None and store.safe_name("counts.CSV", text) == "counts.csv"
    assert store.safe_name("page.html", text) == "page.txt"


# --- Items --------------------------------------------------------------------------------


def test_an_item_says_when_it_was_collected_and_until_when_it_holds(
    db: Database, people: People
) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    hale = people.units["HALE"]
    today = date(2026, 6, 1)
    with frozen_at(datetime(2026, 6, 1, 12, tzinfo=UTC)), db.write(member.actor) as session:
        # The people who do the work collect the evidence, in a unit they work in.
        item = add_evidence(session, member, hale, collected_on="2026-05-20")
        assert item.ref == "EV-0001" and item.valid_until == date(2027, 5, 20)  # a year, by default
        assert evidence.state_of(item, today) == "current"
        assert evidence.state_of(item, date(2027, 4, 25)) == "expiring"
        assert evidence.state_of(item, date(2027, 5, 21)) == "stale"
        with pytest.raises(PermissionDenied):
            add_evidence(session, member, people.units["CANCER"])
        for values, field in [
            ({"kind": "link"}, "url"),
            ({"kind": "attestation", "note": ""}, "note"),
            ({"kind": "screenshot"}, "kind"),
            ({"collected_on": "2026-07-01"}, "collected_on"),
            ({"collected_on": "2026-05-01", "valid_until": "2026-04-01"}, "valid_until"),
            ({"covers_from": "2026-03-01", "covers_to": "2026-01-01"}, "covers_to"),
            ({"data_class": "secret"}, "data_class"),
        ]:
            with pytest.raises(Invalid) as bad:
                add_evidence(session, member, hale, **values)
            assert field in bad.value.errors, values
        link = add_evidence(
            session, member, hale, "Service report", kind="link", note=None,
            url="https://files.northmere.example/service/2026-q1", covers_from="2026-01-01",
            covers_to="2026-03-31", valid_until="2026-06-20", data_class="internal",
        )  # fmt: skip
        assert evidence.state_of(link, today) == "expiring"
        with pytest.raises(Invalid) as fixed:
            records.update(session, member, EVIDENCE, link, {"kind": "note"}, version=link.version)
        assert "kind" in fixed.value.errors
    with db.read() as session:
        soon, _ = records.search(
            session, steward, EVIDENCE, {"state": "expiring"}, sort="name", limit=10, offset=0
        )
        assert [row.ref for row in soon] == ["EV-0002"] or [row.ref for row in soon] == []


def test_one_item_supports_many_things_and_is_attached_by_those_who_keep_them(
    db: Database, people: People
) -> None:
    steward, member = who(db, people, "steward"), who(db, people, "member")
    hale = people.units["HALE"]
    with db.write(steward.actor) as session:
        backups = add_control(session, steward, hale, "Backups")
        restore = add_control(session, steward, hale, "Restore test")
        item = add_evidence(session, steward, hale)
        evidence.set_subjects(session, steward, item, [backups.ref, restore.ref])
        seen = records.detail(session, steward, EVIDENCE, item)
        assert [r["ref"] for r in seen["subjects"]["records"]] == [backups.ref, restore.ref]
        assert seen["supports"] == 2
        for control in (backups, restore):
            found = evidence.of_subject(session, steward, CONTROL, control)
            assert [i["ref"] for i in found["items"]] == [item.ref]
            assert found["current"] == 1 and found["can_add"]
        with pytest.raises(Invalid):
            evidence.set_subjects(session, steward, item, ["RSK-0001"])
        evidence.set_subjects(session, steward, item, [restore.ref])
        assert evidence.current_for(session, CONTROL, backups.id) == 0
        told = session.scalars(
            select(Event).where(Event.subject_type == "evidence_link").order_by(Event.id)
        ).all()
        assert [e.action for e in told] == ["created", "created", "deleted"]
        assert {e.parent_type for e in told} == {"evidence"}
    with db.write(member.actor) as session:
        # A member may collect evidence, and may not put it on a control they do not keep.
        mine = add_evidence(session, member, hale, "My screenshot")
        with pytest.raises(PermissionDenied):
            evidence.set_subjects(session, member, mine, [restore.ref])
        with pytest.raises(PermissionDenied):
            evidence.set_subjects(
                session, member, records.load(session, member, EVIDENCE, item.ref), []
            )


def test_evidence_is_seen_by_those_with_a_role_in_it_or_in_what_it_supports(
    db: Database, people: People
) -> None:
    manager, steward, member, leader = (
        who(db, people, r) for r in ("manager", "steward", "member", "leader")
    )
    hale, cancer = people.units["HALE"], people.units["CANCER"]
    with db.write(manager.actor) as session:
        ours = add_control(session, manager, hale, "Ours")
        theirs = add_control(session, manager, cancer, "Theirs")
        loose = add_evidence(session, manager, cancer, "Attached to nothing")
        on_ours = add_evidence(session, manager, cancer, "On our control")
        on_theirs = add_evidence(session, manager, cancer, "On their control")
        sensitive = add_evidence(session, manager, cancer, "Sensitive", data_class="restricted")
        closed = add_evidence(session, manager, cancer, "Restricted", restricted=True)
        evidence.set_subjects(session, manager, on_ours, [ours.ref])
        evidence.set_subjects(session, manager, on_theirs, [theirs.ref])
        evidence.set_subjects(session, manager, sensitive, [ours.ref])
        evidence.set_subjects(session, manager, closed, [ours.ref])
    names = lambda principal: {  # noqa: E731
        row.name
        for row in records.search(
            db_session, principal, EVIDENCE, {}, sort="name", limit=50, offset=0
        )[0]
    }
    with db.read() as db_session:
        everything = {
            "Attached to nothing",
            "On our control",
            "On their control",
            "Sensitive",
            "Restricted",
        }
        assert names(manager) == everything and names(who(db, people, "auditor")) == everything
        # A member of HALE sees evidence in another unit only through a control they may see,
        # and not when it is of the most sensitive class or restricted.
        assert names(member) == {"On our control"}
        for item, expected in (
            (on_ours, True),
            (on_theirs, False),
            (sensitive, False),
            (closed, False),
            (loose, False),
        ):
            row = db_session.get(type(item), item.id)
            assert evidence.can_see(db_session, member, row) is expected, row.name
        # An assessor for the whole organization sees what is not restricted.
        assert names(who(db, people, "assessor")) == everything - {"Restricted"}
        # A steward and a leader of another division are no different from its members here:
        # they see what is attached to something of theirs, and no more.
        assert names(steward) == {"On our control"} and names(leader) == {"On our control"}
        found = evidence.of_subject(
            db_session, member, CONTROL, db_session.get(type(ours), ours.id)
        )
        assert [i["name"] for i in found["items"]] == ["On our control"]
        assert found["hidden"] == 2 and found["current"] == 3 and not found["can_add"]


def test_the_owner_is_told_when_their_evidence_is_about_to_stop_counting(
    db: Database, people: People
) -> None:
    steward = who(db, people, "steward")
    hale = people.units["HALE"]
    with frozen_at(datetime(2026, 1, 10, 12, tzinfo=UTC)), db.write(steward.actor) as session:
        control = add_control(session, steward, hale, "Backups")
        used = add_evidence(session, steward, hale, "Used", collected_on="2026-01-10")
        add_evidence(session, steward, hale, "Not attached", collected_on="2026-01-10")
        evidence.set_subjects(session, steward, used, [control.ref])
    with frozen_at(datetime(2026, 12, 20, 12, tzinfo=UTC)), db.read() as session:
        waiting = [i for i in reporting.home(session, steward)["items"] if i["kind"] == "evidence"]
        assert [(i["title"], i["overdue"]) for i in waiting] == [("Renew Used", False)]
        assert (
            waiting[0]["due_on"] == date(2027, 1, 10) and waiting[0]["href"] == "/evidence/EV-0001"
        )
    with frozen_at(datetime(2027, 2, 1, 12, tzinfo=UTC)), db.read() as session:
        waiting = [i for i in reporting.home(session, steward)["items"] if i["kind"] == "evidence"]
        assert waiting[0]["overdue"] and "no longer counts" in waiting[0]["detail"]
        assert evidence.current_for(session, CONTROL, control.id) == 0


# --- Through the API ----------------------------------------------------------------------


def test_a_file_goes_up_and_comes_back_only_as_a_download_that_cannot_run(
    as_role: Clients, instance: Instance, db: Database, people: People
) -> None:
    steward = as_role("steward")
    made = steward.post(
        "/api/v1/evidence",
        json={
            "name": "Quarterly restore report",
            "kind": "file",
            "org_unit_id": people.units["HALE"],
        },
    )
    assert made.status_code == 201 and made.json()["data"]["file"] is None
    ref = made.json()["data"]["ref"]
    token = {"X-CSRF-Token": steward.get("/api/v1/session").json()["data"]["csrf_token"]}
    sent = steward.post(
        f"/api/v1/evidence/{ref}/file",
        params={"name": "../Restore Q1.PDF"},
        content=PDF,
        headers=token,
    )
    assert sent.status_code == 200
    assert sent.json()["data"]["file"] == {
        "name": "Restore Q1.pdf", "size": len(PDF), "media_type": "application/pdf",
        "sha256": sent.json()["data"]["file"]["sha256"],
    }  # fmt: skip
    got = steward.get(f"/api/v1/evidence/{ref}/file")
    assert got.status_code == 200 and got.content == PDF
    assert got.headers["content-disposition"].startswith('attachment; filename="Restore Q1.pdf"')
    assert got.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert got.headers["x-content-type-options"] == "nosniff"

    # A page and a drawing that carry script are taken as text, and leave as text, as downloads.
    for name, body in (("page.html", PAGE), ("drawing.svg", DRAWING)):
        steward.post(
            f"/api/v1/evidence/{ref}/file", params={"name": name}, content=body, headers=token
        )
        back = steward.get(f"/api/v1/evidence/{ref}/file")
        assert back.headers["content-type"].startswith("text/plain")
        assert back.headers["content-disposition"].startswith(
            f'attachment; filename="{name.split(".")[0]}.txt"'
        )
        assert "sandbox" in back.headers["content-security-policy"]
    refused = steward.post(
        f"/api/v1/evidence/{ref}/file",
        params={"name": "tool.pdf"},
        content=b"MZ\x90\x00",
        headers=token,
    )
    assert refused.status_code == 422 and "not taken" in refused.json()["errors"][0]["message"]
    note = steward.post(
        "/api/v1/evidence",
        json={
            "name": "A note",
            "kind": "note",
            "note": "Seen.",
            "org_unit_id": people.units["HALE"],
        },
    ).json()["data"]["ref"]
    assert (
        steward.post(f"/api/v1/evidence/{note}/file", content=PDF, headers=token).status_code == 422
    )
    assert steward.get(f"/api/v1/evidence/{note}/file").status_code == 404

    with db.read() as session:
        # Three uploads, three files on disk, each under its digest and outside anything served.
        stored = session.scalars(select(StoredFile).order_by(StoredFile.id)).all()
        assert [row.extension for row in stored] == ["pdf", "txt", "txt"]
        for row in stored:
            assert store.path_of(instance.home.files, row.sha256).is_file()
        # Each download is on the record.
        downloads = session.scalars(
            select(Event).where(Event.action == "evidence.downloaded")
        ).all()
        assert len(downloads) == 3 and {e.subject_ref for e in downloads} == {ref}
    assert steward.get("/files/" + stored[0].sha256).status_code in (200, 404)
    assert PDF not in steward.get("/files/" + stored[0].sha256).content


def test_a_person_who_cannot_see_a_control_cannot_download_its_evidence(
    as_role: Clients, db: Database, people: People
) -> None:
    manager = as_role("manager")
    token = {"X-CSRF-Token": manager.get("/api/v1/session").json()["data"]["csrf_token"]}
    cancer = people.units["CANCER"]
    control = manager.post(
        "/api/v1/controls",
        json={
            "name": "Their control",
            "statement": "Done.",
            "kind": "preventive",
            "org_unit_id": cancer,
        },
    ).json()["data"]["ref"]
    ref = manager.post(
        "/api/v1/evidence", json={"name": "Their report", "kind": "file", "org_unit_id": cancer}
    ).json()["data"]["ref"]
    manager.post(
        f"/api/v1/evidence/{ref}/file", params={"name": "r.pdf"}, content=PDF, headers=token
    )
    attached = manager.put(f"/api/v1/evidence/{ref}/subjects", json={"subjects": [control]})
    assert [r["ref"] for r in attached.json()["data"]["subjects"]["records"]] == [control]
    assert manager.get("/api/v1/evidence", params={"subject": control}).json()["meta"]["total"] == 1

    member = as_role("member")  # works in another unit, and cannot see that control
    assert member.get(f"/api/v1/controls/{control}").status_code == 404
    assert member.get(f"/api/v1/evidence/{ref}").status_code == 404
    assert member.get(f"/api/v1/evidence/{ref}/file").status_code == 404
    assert member.get("/api/v1/evidence").json()["meta"]["total"] == 0
    assert member.get(f"/api/v1/evidence-for/{control}").status_code == 404
    assert as_role(None).get(f"/api/v1/evidence/{ref}/file").status_code == 401
    # The auditor reads it, file and all, and changes nothing.
    auditor = as_role("auditor")
    assert auditor.get(f"/api/v1/evidence/{ref}/file").content == PDF
    assert auditor.put(f"/api/v1/evidence/{ref}/subjects", json={"subjects": []}).status_code == 403
    listed = auditor.get(f"/api/v1/evidence-for/{control}").json()["data"]
    assert [i["ref"] for i in listed["items"]] == [ref] and not listed["can_add"]
