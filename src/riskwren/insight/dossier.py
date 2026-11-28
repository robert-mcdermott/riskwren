"""Dossiers (RPT-10) and the security plan document (CMP-14).

A **dossier** is everything known about a scope, a risk, or a third party, as one ZIP file
that proves itself: the record, its history, what it is connected to, and the files behind
it, with a page to read and print, and a manifest. The manifest lists every file with its
size and SHA-256, and has a fingerprint of its own: the SHA-256 of the manifest, written
canonically, without the fingerprint. Taking a dossier is recorded in the history with that
fingerprint. Anyone can check one without RiskWren: each file's hash is what
``shasum -a 256`` prints. RiskWren checks all of it at once, and says when and by whom it
was taken.

A person's dossier holds only what they may see: a file they may not open is left out, and
the manifest says so.

The **security plan** is a scope's implementation statements in the customary order of a
system security plan: who it is, what it is and where it ends, what is in it, what it is
held to, and then requirement by requirement how it is met here. It prints by itself.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import zipfile
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren import __version__
from riskwren.access.principal import Principal
from riskwren.compliance import evidence, issues, scopes
from riskwren.compliance.evidence import EVIDENCE
from riskwren.compliance.issues import ISSUE
from riskwren.compliance.scopes import SCOPE
from riskwren.core.clock import isoformat, utc_now
from riskwren.core.errors import Invalid
from riskwren.db.models import Event, Evidence, Implementation, StoredFile
from riskwren.events import audit, chain
from riskwren.files import store
from riskwren.insight import oscal
from riskwren.inventory import history, records
from riskwren.inventory.registry import RecordType, find_any
from riskwren.risk.register import RISK

FORMAT = "riskwren-dossier/1"
MANIFEST = "manifest.json"
KINDS = ("scope", "risk", "third_party")
MAX_FILES_BYTES = 200 * 1024 * 1024  # files beyond this are listed as left out
MAX_READ = 400 * 1024 * 1024  # a dossier larger than this, unpacked, is not checked
MAX_MANIFEST = 4 * 1024 * 1024  # a manifest larger than this is not a dossier's


# --- Writing it down ----------------------------------------------------------------------


def _plain(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return chain.jsonable(value)
    if isinstance(value, set | frozenset | tuple):
        return list(value)
    return str(value)


def as_json(value: Any) -> bytes:
    return json.dumps(value, indent=2, ensure_ascii=False, default=_plain).encode("utf-8")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(manifest: dict[str, Any]) -> str:
    return sha256(canonical({k: v for k, v in manifest.items() if k != "fingerprint"}))


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


STYLE = """
body { font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; color: #1b1f24;
  max-width: 980px; margin: 2rem auto; padding: 0 1.5rem; }
h1 { font-size: 1.7rem; margin: 0 0 .25rem; } h2 { font-size: 1.25rem; margin: 2rem 0 .5rem;
  border-bottom: 1px solid #c9ced6; padding-bottom: .25rem; } h3 { font-size: 1.05rem; }
.muted { color: #555d68; } code { font: 12px ui-monospace, Menlo, monospace; }
table { border-collapse: collapse; width: 100%; margin: .5rem 0 1rem; }
th, td { text-align: left; vertical-align: top; border: 1px solid #d5d9df; padding: .35rem .5rem; }
th { background: #f1f3f5; }
dl { display: grid; grid-template-columns: 12rem 1fr; gap: .25rem 1rem; }
dt { font-weight: 600; } dd { margin: 0; }
@media print { body { margin: 0; max-width: none; } h2 { break-after: avoid; }
  tr { break-inside: avoid; } }
"""


def page(title: str, body: str) -> bytes:
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>{_e(title)}</title><style>{STYLE}</style></head><body>{body}</body></html>\n"
    ).encode()


def _facts(rows: list[tuple[str, Any]]) -> str:
    return (
        "<dl>"
        + "".join(
            f"<dt>{_e(label)}</dt><dd>{_e(value) if value not in (None, '') else '—'}</dd>"
            for label, value in rows
        )
        + "</dl>"
    )


def _table(head: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return '<p class="muted">None.</p>'
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{_e(h)}</th>" for h in head)
        + "</tr></thead><tbody>"
        + "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in row) + "</tr>" for row in rows)
        + "</tbody></table>"
    )


def _owners(detail: dict[str, Any]) -> str:
    return ", ".join(f"{o['name']} ({o['kind']})" for o in detail.get("owners", [])) or "Nobody"


# --- The security plan --------------------------------------------------------------------

STATES = {
    "verified": "Verified",
    "in_place": "In place",
    "failing": "Failing",
    "planned": "Planned",
    "gap": "Gap",
    "excepted": "Excepted",
    "excluded": "Not applicable",
}


def security_plan(session: Session, principal: Principal, scope: Any) -> bytes:
    """The scope's system security plan, as a page that prints by itself."""
    detail = records.detail(session, principal, SCOPE, scope)
    members = scopes.members_of(session, principal, scope)
    held = scopes.held_to(session, scope)
    used = {
        view["control"]["ref"]: view
        for view in scopes.implementations(session, principal, scope)["controls"]
    }
    plan = issues.plan_of_action(session, principal, scope)
    units = {unit["id"]: unit["name"] for unit in members["units"]}
    parts = [
        f'<p class="muted">System security plan · {_e(scope.ref)} · made '
        f"{_e(utc_now().date().isoformat())} by RiskWren {_e(__version__)}</p>",
        f"<h1>{_e(scope.name)}</h1>",
        "<h2>1. System identification</h2>",
        _facts(
            [
                ("Name", scope.name),
                ("Reference", scope.ref),
                ("Status", history.words(scope.status)),
                ("Unit", history.Lookups(session, SCOPE).value("org_unit_id", scope.org_unit_id)),
                ("Owners", _owners(detail)),
            ]
        ),
        "<h2>2. System description</h2>",
        f"<p>{_e(scope.summary or 'No description is recorded.')}</p>",
        "<h3>Authorization boundary</h3>",
        f"<p>{_e(scope.boundary or 'The boundary is not described.')}</p>",
        "<h2>3. What the system includes</h2>",
        _table(
            ["Reference", "Name", "Kind"],
            [
                [chip["ref"], chip["name"], history.words(chip.get("type", ""))]
                for chip in members["records"]
            ],
        ),
        (f"<p>And the units: {_e(', '.join(units.values()))}.</p>" if units else ""),
        (
            f'<p class="muted">{members["hidden"]} more you may not see.</p>'
            if members["hidden"]
            else ""
        ),
        "<h2>4. What it is held to</h2>",
        _table(
            ["Framework", "Baseline"],
            [
                [
                    row["title"],
                    (row.get("baseline") or {}).get("title")
                    if isinstance(row.get("baseline"), dict)
                    else row.get("baseline"),
                ]
                for row in held
            ],
        ),
    ]
    number = 5
    for row in held:
        statement = scopes.statement(session, principal, scope, row["key"])
        counts = ", ".join(
            f"{count} {STATES[key].lower()}" for key, count in statement["counts"].items() if count
        )
        parts += [
            f"<h2>{number}. Control implementation: {_e(statement['framework']['title'])}</h2>",
            f'<p class="muted">{_e(statement["applicable"])} requirements apply: {_e(counts)}.</p>',
        ]
        number += 1
        for requirement in statement["requirements"]:
            parts.append(
                f"<h3>{_e(requirement['code'])} {_e(requirement['title'] or '')} · "
                f"{_e(STATES.get(requirement['state'], requirement['state']))}</h3>"
            )
            if requirement["state"] == "excluded":
                parts.append(
                    f"<p>Not applicable: {_e(requirement.get('reason') or 'no reason')}</p>"
                )
                continue
            if not requirement["controls"]:
                parts.append("<p>No control used in this scope answers this requirement.</p>")
                continue
            for control in requirement["controls"]:
                view = used.get(control["ref"], {})
                provider = view.get("provider") or {}
                words = (
                    view.get("statement")
                    or provider.get("statement")
                    or (view.get("control") or {}).get("statement")
                    or "No implementation statement is recorded."
                )
                said = [STATES.get(control["readiness"], control["readiness"])]
                if view.get("responsibility"):
                    said.append(f"responsibility: {view['responsibility']}")
                if control.get("provider"):
                    said.append(
                        f"inherited from {control['provider']['ref']} {control['provider']['name']}"
                    )
                parts.append(
                    f"<p><strong>{_e(control['ref'])} {_e(control['name'])}</strong> "
                    f'<span class="muted">({_e("; ".join(said))})</span><br>{_e(words)}</p>'
                )
    parts += [
        f"<h2>{number}. Plan of action and milestones</h2>",
        _table(
            ["Issue", "Severity", "Due", "Status"],
            [
                [
                    f"{card['ref']} {card['name']}",
                    plan["severities"].get(card["severity"], card["severity"]),
                    card["due_on"],
                    card["status"],
                ]
                for card in plan["issues"]
            ],
        ),
    ]
    return page(f"System security plan: {scope.name}", "".join(parts))


# --- Dossiers -----------------------------------------------------------------------------


class Package:
    def __init__(self) -> None:
        self.files: dict[str, tuple[bytes, str]] = {}
        self.left_out: list[dict[str, str]] = []

    def add(self, path: str, data: bytes, about: str) -> None:
        self.files[path] = (data, about)

    def json(self, path: str, value: Any, about: str) -> None:
        self.add(path, as_json(value), about)


def _evidence_files(
    session: Session, principal: Principal, package: Package, rows: list[Evidence], root: Path
) -> None:
    budget = MAX_FILES_BYTES
    for item in rows:
        if not item.file_id or not evidence.can_see(session, principal, item):
            continue
        stored = session.get(StoredFile, item.file_id)
        if stored is None:
            continue
        name = f"files/{item.ref}-{item.file_name or 'file.' + stored.extension}"
        if stored.size > budget:
            package.left_out.append({"path": name, "why": "The package would be too large."})
            continue
        path = store.path_of(root, stored.sha256)
        if not path.is_file():
            package.left_out.append(
                {"path": name, "why": "The file is missing from the data home."}
            )
            continue
        data = path.read_bytes()
        budget -= len(data)
        package.add(name, data, f"The file of {item.ref} {item.name}")


def _evidence_of(session: Session, subjects: list[tuple[str, int]]) -> list[Evidence]:
    from riskwren.db.models import EvidenceLink

    found: dict[int, Evidence] = {}
    for kind, identifier in subjects:
        for row in session.scalars(
            select(Evidence)
            .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
            .where(EvidenceLink.subject_type == kind, EvidenceLink.subject_id == identifier)
        ):
            found[row.id] = row
    return sorted(found.values(), key=lambda row: row.ref)


def _scope(
    session: Session, principal: Principal, scope: Any, package: Package, root: Path
) -> None:
    package.json(
        "scope/members.json",
        scopes.members_of(session, principal, scope),
        "What is inside the scope",
    )
    package.json(
        "scope/implementations.json",
        scopes.implementations(session, principal, scope),
        "How each control is done here",
    )
    for held in scopes.held_to(session, scope):
        key = held["key"]
        package.json(
            f"scope/statement-{key}.json",
            scopes.statement(session, principal, scope, key),
            f"Each requirement of {held['title']} and where it stands",
        )
        package.json(
            f"oscal/ssp-{key}.json",
            oscal.ssp(session, principal, scope, key),
            f"The system security plan against {held['title']}, in OSCAL",
        )
    package.json(
        "scope/plan-of-action.json",
        issues.plan_of_action(session, principal, scope),
        "The open issues that bear on the scope, with their milestones",
    )
    package.json(
        "oscal/poam.json",
        oscal.poam(session, principal, scope),
        "The plan of action and milestones, in OSCAL",
    )
    package.add(
        "security-plan.html",
        security_plan(session, principal, scope),
        "The system security plan, to read and print",
    )
    controls = session.scalars(
        select(Implementation.control_id).where(Implementation.scope_id == scope.id)
    ).all()
    rows = _evidence_of(session, [("scope", scope.id), *(("control", c) for c in controls)])
    seen = [row for row in rows if evidence.can_see(session, principal, row)]
    package.json(
        "evidence.json",
        records.cards(session, EVIDENCE, seen),
        "The evidence for the scope and the controls it uses",
    )
    _evidence_files(session, principal, package, seen, root)


def _risk(session: Session, principal: Principal, risk: Any, package: Package) -> None:
    from riskwren.treatment import service as treatment

    package.json(
        "risk/treatment.json",
        treatment.of_risk(session, principal, risk),
        "Its response, plans and their actions, and acceptances",
    )
    found, _ = records.search(session, principal, ISSUE, {"about": risk.ref}, limit=200)
    package.json(
        "risk/issues.json", records.cards(session, ISSUE, list(found)), "Issues about the risk"
    )


def _third_party(
    session: Session, principal: Principal, party: Any, package: Package, root: Path
) -> None:
    from riskwren.thirdparty import assurance, coverage
    from riskwren.thirdparty.reviews import REVIEW

    reviews, _ = records.search(
        session, principal, REVIEW, {"third_party": party.ref, "status": "all"}, limit=200
    )
    package.json(
        "third-party/reviews.json",
        [records.detail(session, principal, REVIEW, row) for row in reviews],
        "Due diligence: each review, its answers and concerns, and what was concluded",
    )
    package.json(
        "third-party/assurance.json",
        assurance.documents_of(session, principal, party),
        "Its reports and certificates, and what each was found to cover",
    )
    package.json(
        "third-party/coverage.json",
        coverage.stops_for(session, principal, "third_party", party.id),
        "Information shared with it that no agreement covers",
    )
    package.json(
        "third-party/agreements.json",
        coverage.agreements_with(session, principal, party),
        "The agreements with it",
    )
    found, _ = records.search(session, principal, ISSUE, {"about": party.ref}, limit=200)
    package.json(
        "third-party/issues.json",
        records.cards(session, ISSUE, list(found)),
        "Issues about it, findings among them",
    )
    risks, _ = records.search(session, principal, RISK, {"subject": party.ref}, limit=200)
    package.json(
        "third-party/risks.json", records.cards(session, RISK, list(risks)), "Risks that concern it"
    )
    papers = assurance.documents_of(session, principal, party)
    refs = [paper["ref"] for paper in papers] or [""]
    documents = session.scalars(select(Evidence).where(Evidence.ref.in_(refs))).all()
    _evidence_files(session, principal, package, list(documents), root)


def _index(
    record_type: RecordType,
    detail: dict[str, Any],
    story: list[dict[str, Any]],
    manifest_files: list[dict[str, Any]],
    left_out: list[dict[str, str]],
) -> bytes:
    rows = [
        ("Reference", detail["ref"]),
        ("Kind", record_type.label),
        ("Name", detail["name"]),
        ("Summary", detail.get("summary")),
        ("Owners", _owners(detail)),
        ("Status", detail.get("status")),
        ("Restricted", "Yes" if detail.get("restricted") else "No"),
    ]
    body = [
        f'<p class="muted">Dossier · {_e(record_type.label)} {_e(detail["ref"])} · taken '
        f"{_e(isoformat(utc_now()))} with RiskWren {_e(__version__)}</p>",
        f"<h1>{_e(detail['name'])}</h1>",
        _facts(rows),
        "<h2>What is in this package</h2>",
        _table(
            ["File", "What it is", "Bytes", "SHA-256"],
            [[f["path"], f["about"], f["size"], f["sha256"]] for f in manifest_files],
        ),
        (
            "<h3>Left out</h3>" + _table(["File", "Why"], [[x["path"], x["why"]] for x in left_out])
            if left_out
            else ""
        ),
        "<h2>How to check it</h2>",
        "<p><code>manifest.json</code> lists every other file with its size and SHA-256, which "
        "<code>shasum -a 256 FILE</code> reproduces. Its <code>fingerprint</code> is the "
        "SHA-256 of the manifest written canonically (keys sorted, no spaces, UTF-8) without the "
        "fingerprint; RiskWren's history recorded the same fingerprint when the dossier was "
        "taken. <strong>Reports → Check a dossier</strong> in RiskWren checks all of it at "
        "once.</p>",
        "<h2>History</h2>",
        _table(
            ["When", "Who", "What"],
            [
                [
                    entry["at"],
                    entry["actor"],
                    entry["title"]
                    + "".join(
                        f"; {line['label']}: {line['before'] or '—'} → {line['after'] or '—'}"
                        for line in entry["lines"]
                    ),
                ]
                for entry in story
            ],
        ),
    ]
    return page(f"Dossier: {detail['ref']} {detail['name']}", "".join(body))


def build(
    session: Session, principal: Principal, ref: str, root: Path
) -> tuple[bytes, dict[str, Any], Any]:
    """A dossier of the record, as a ZIP, with its manifest; and the record."""
    record_type, record = find_any(session, ref)
    if record_type.key not in KINDS:
        raise Invalid(
            "A dossier is taken of a scope, a risk, or a third party.",
            {"ref": "Name a scope, a risk, or a third party."},
        )
    detail = records.detail(session, principal, record_type, record)  # NotFound if not seen
    story = history.for_record(session, record_type, record, limit=100_000, principal=principal)
    package = Package()
    package.json("record.json", detail, f"The {record_type.label.lower()} as it stands")
    package.json("history.json", story, "Every change to it, newest first")
    if record_type.key == "scope":
        _scope(session, principal, record, package, root)
    elif record_type.key == "risk":
        _risk(session, principal, record, package)
    elif record_type.key == "third_party":
        _third_party(session, principal, record, package, root)
    listed = [
        {"path": path, "about": about, "size": len(data), "sha256": sha256(data)}
        for path, (data, about) in sorted(package.files.items())
    ]
    index = _index(record_type, detail, story, listed, package.left_out)
    listed.append(
        {
            "path": "index.html",
            "about": "This dossier, to read and print",
            "size": len(index),
            "sha256": sha256(index),
        }
    )
    listed.sort(key=lambda item: item["path"])
    manifest: dict[str, Any] = {
        "format": FORMAT,
        "record": {"type": record_type.key, "ref": record.ref, "name": record.name},
        "taken_at": isoformat(utc_now()),
        "taken_by": principal.name,
        "riskwren": __version__,
        "files": listed,
        "left_out": package.left_out,
    }
    manifest["fingerprint"] = fingerprint(manifest)
    audit.record(
        session,
        "dossier.taken",
        record,
        changes={"fingerprint": [None, manifest["fingerprint"]], "files": [None, len(listed)]},
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST, as_json(manifest))
        archive.writestr("index.html", index)
        for path, (data, _) in sorted(package.files.items()):
            archive.writestr(path, data)
    return out.getvalue(), manifest, record


# --- Checking one -------------------------------------------------------------------------


def _safe(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name


def verify(data: bytes, session: Session | None = None) -> dict[str, Any]:
    """Whether a dossier is whole and unchanged: every file the manifest lists is there with
    its size and hash, nothing else is, and the manifest's fingerprint is its own. With a
    session, also when and by whom the history says it was taken."""
    problems: list[str] = []
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return {"verified": False, "problems": ["This is not a ZIP file."], "manifest": None}
    with archive:
        infos = archive.infolist()
        if sum(info.file_size for info in infos) > MAX_READ:
            return {"verified": False, "problems": ["It is too large to check."], "manifest": None}
        names = {info.filename for info in infos if not info.is_dir()}
        if any(not _safe(name) for name in names):
            problems.append("It holds a file whose name points outside the package.")
        if MANIFEST not in names:
            return {"verified": False, "problems": ["It has no manifest.json."], "manifest": None}
        if archive.getinfo(MANIFEST).file_size > MAX_MANIFEST:
            return {"verified": False, "problems": ["Its manifest is too large to be a dossier's."],
                    "manifest": None}  # fmt: skip
        try:
            manifest = json.loads(archive.read(MANIFEST))
            listed = {item["path"]: item for item in manifest["files"]}
        except (ValueError, KeyError, TypeError, zipfile.BadZipFile, EOFError, OSError):
            return {
                "verified": False,
                "problems": ["Its manifest cannot be read."],
                "manifest": None,
            }
        if manifest.get("format") != FORMAT:
            problems.append(f"It is not a dossier this version reads ({manifest.get('format')}).")
        if manifest.get("fingerprint") != fingerprint(manifest):
            problems.append("The manifest has been changed: its fingerprint is not its own.")
        for path, item in sorted(listed.items()):
            if path not in names:
                problems.append(f"{path} is missing.")
                continue
            digest, size = hashlib.sha256(), 0
            try:
                with archive.open(path) as handle:  # in pieces: never the whole file at once
                    for block in iter(lambda handle=handle: handle.read(1 << 20), b""):
                        digest.update(block)
                        size += len(block)
            except (zipfile.BadZipFile, EOFError, OSError):
                problems.append(f"{path} cannot be read.")
                continue
            if size != item.get("size") or digest.hexdigest() != item.get("sha256"):
                problems.append(f"{path} has been changed.")
        for extra in sorted(names - set(listed) - {MANIFEST}):
            problems.append(f"{extra} is not in the manifest.")
    recorded = None
    if session is not None and isinstance(manifest.get("fingerprint"), str):
        event = session.scalars(
            select(Event).where(Event.action == "dossier.taken").order_by(Event.id.desc())
        ).all()
        for row in event:
            if (row.changes or {}).get("fingerprint", [None, None])[1] == manifest["fingerprint"]:
                recorded = {"at": row.at, "by": row.actor_label, "event": row.id}
                break
    return {
        "verified": not problems,
        "problems": problems,
        "manifest": {
            key: manifest.get(key)
            for key in ("format", "record", "taken_at", "taken_by", "riskwren", "fingerprint")
        }
        | {"files": len(listed)},
        "recorded": recorded,
    }
