"""Build the fictional institute by using RiskWren the way its people would.

Nothing here inserts a row. Every unit, account, system, risk, assessment, rating, plan, and
acceptance is made by calling the same services the web app calls, as the person who would
have done it, with the clock set to when they would have done it. So everything in a demo is
genuine output of the product, and its history verifies like any other.

Time runs forward from two years ago to the day of the build. Each risk, control, and plan is
a small script that says what happens next and when; the scripts are interleaved in time
order, and whatever would happen after today simply has not happened yet. That is why a fresh
demo always has work in progress, something overdue, and an acceptance about to expire.
"""

from __future__ import annotations

import heapq
import random
import unicodedata
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from riskwren import reminders
from riskwren.access.principal import Grant, Principal
from riskwren.compliance import (
    agreements,
    assessments,
    crosswalk,
    evidence,
    exceptions,
    frameworks,
    issues,
    scopes,
)
from riskwren.compliance import packs as framework_packs
from riskwren.compliance.agreements import AGREEMENT
from riskwren.compliance.evidence import EVIDENCE
from riskwren.compliance.scopes import SCOPE
from riskwren.controls import service as controls
from riskwren.controls.service import CONTROL
from riskwren.core.clock import clock_set_to
from riskwren.core.errors import Conflict, PermissionDenied, RiskWrenError
from riskwren.db.engine import Database
from riskwren.db.models import (
    Acceptance,
    Action,
    Campaign,
    CampaignItem,
    Control,
    ControlTest,
    Evidence,
    EvidenceLink,
    ExceptionRequest,
    Indicator,
    Issue,
    PolicyDocument,
    Risk,
    RiskAnalysis,
    RiskAnalysisItem,
    Scope,
    TreatmentPlan,
)
from riskwren.demo import content as c
from riskwren.inventory import access, links, records, views
from riskwren.inventory.registry import INFORMATION, PROCESS, SYSTEM, THIRD_PARTY, RecordType
from riskwren.oversight import campaigns
from riskwren.people import accounts, handover, units
from riskwren.policy import documents, governs, library
from riskwren.program import branding, packs, settings
from riskwren.risk import analysis, categories, indicators, register
from riskwren.risk.indicators import INDICATOR
from riskwren.risk.register import RISK
from riskwren.treatment import service as treatment

SETTING = "demo"
ORGANIZATION = c.ORGANIZATION
MONTHS = 24
ME = Principal.for_command("Demo build")
Script = Iterator[datetime]


class _Gone(Exception):
    """Someone who has left was about to act. Whatever they were doing stops there."""


@dataclass
class Summary:
    seed: int
    built_on: date
    counts: dict[str, int]
    sample_accounts: list[dict[str, str]]


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def email_for(name: str) -> str:
    words = _ascii(name).lower().replace("'", "").split()
    return f"{words[0]}.{words[-1]}@{c.DOMAIN}"


class Builder:
    def __init__(self, db: Database, *, seed: int, today: date, files: Path | None = None) -> None:
        self.db = db
        self.files = files  # where evidence files are kept; without it, items have none
        self._doc_refs: dict[str, str] = {}  # the reference each demo document was given
        self._agreement_refs: dict[str, str] = {}  # and each demo agreement
        self.seed = seed
        self.rng = random.Random(seed)
        # A second stream for details added later, so that they do not shift the first.
        self.side = random.Random(seed + 7919)
        self.end = datetime(today.year, today.month, today.day, 16, 30, tzinfo=UTC)
        self.start = self._workday(self.end - timedelta(days=MONTHS * 30.4))
        self.now = self.start
        self.library = {r["key"]: r for r in packs.builtin("risk-library.json")["risks"]}
        self.control_library = {
            r["key"]: r for r in packs.builtin("starter-controls.json")["controls"]
        }
        self.units: dict[str, int] = {}
        self.unit_names: dict[int, str] = {}
        self.unit_kinds: dict[int, str] = {}
        self.parent: dict[int, int | None] = {}
        self.labs: dict[str, list[int]] = {}
        self.lab_heads: dict[int, str] = {}
        self.cast: dict[str, int] = {}
        self.names: dict[int, str] = {}
        self.staff: dict[int, list[int]] = {}
        self.stewards: dict[int, int] = {}
        self.heads: dict[int, int] = {}
        self.leads: dict[int, list[int]] = {}
        self.departed: set[int] = set()
        self._principals: dict[int, Principal] = {}
        self._emails: set[str] = set()
        # Inventory: a key (or a process's name) → its type, id, and reference.
        self.things: dict[str, tuple[RecordType, int, str]] = {}
        self.unit_things: dict[int, list[str]] = {}
        self.controls: dict[tuple[str, int], int] = {}
        self.fixed_rating: dict[int, Any] = {}
        self.last_rated: dict[int, datetime] = {}
        self.risks: dict[int, dict[str, Any]] = {}
        self.unit_risks: dict[int, list[int]] = {}
        self.usage: dict[str, int] = {}
        self.sample: list[dict[str, str]] = []
        self._queue: list[tuple[datetime, int, Script]] = []
        self._count = 0
        self.counts: dict[str, int] = {}

    # --- Time ---------------------------------------------------------------------------

    def _workday(self, moment: datetime) -> datetime:
        """The same moment, moved into working hours on a weekday."""
        moment = moment.replace(second=self.rng.randrange(60), microsecond=0)
        if moment.hour < 8:
            moment = moment.replace(hour=8 + self.rng.randrange(3))
        elif moment.hour >= 18:
            moment = (moment + timedelta(days=1)).replace(hour=8 + self.rng.randrange(3))
        while moment.weekday() >= 5:
            moment += timedelta(days=1)
        return moment

    def later(self, low: float, high: float) -> datetime:
        """A working moment between ``low`` and ``high`` days from now."""
        return self._workday(self.now + timedelta(days=self.rng.uniform(low, high)))

    def ago(self, days: float, hour: int = 10) -> datetime:
        """A working moment that many days before the build."""
        moment = (self.end - timedelta(days=days)).replace(hour=hour, minute=self.rng.randrange(60))
        while moment.weekday() >= 5:
            moment -= timedelta(days=1)
        return moment

    def on(self, day: date, spread: tuple[float, float] = (0, 0)) -> datetime:
        """A working moment on a date, or within some days either side of it."""
        moment = datetime(day.year, day.month, day.day, 9 + self.rng.randrange(8), tzinfo=UTC)
        return self._workday(moment + timedelta(days=self.rng.uniform(*spread)))

    def day(self, offset: float) -> date:
        """The date that many days after the build (before it, if negative)."""
        return (self.end + timedelta(days=offset)).date()

    @property
    def today(self) -> date:
        return self.now.date()

    # --- Acting as someone --------------------------------------------------------------

    def principal(self, account_id: int) -> Principal:
        if account_id not in self._principals:
            with self.db.read() as session:
                self._principals[account_id] = accounts.principal_for(
                    session, accounts.get(session, account_id)
                )
        return self._principals[account_id]

    @contextmanager
    def act(self, account_id: int) -> Iterator[tuple[Session, Principal]]:
        if account_id in self.departed:
            raise _Gone
        who = self.principal(account_id)
        with self.db.write(who.actor) as session:
            yield session, who

    def tally(self, what: str, by: int = 1) -> None:
        self.counts[what] = self.counts.get(what, 0) + by

    # --- The schedule -------------------------------------------------------------------

    def schedule(self, script: Script) -> None:
        try:
            first = next(script)
        except StopIteration:
            return
        self._count += 1
        heapq.heappush(self._queue, (first, self._count, script))

    def run(self) -> None:
        checked = self.start.date()
        with clock_set_to(lambda: self.now):
            while self._queue:
                moment, order, script = heapq.heappop(self._queue)
                if moment > self.end:
                    continue  # it has not happened yet
                self.now = max(self.now, moment)
                if (self.today - checked).days >= 7:
                    # People read the register every week, which is when it notices that
                    # an acceptance has expired or a plan has gone past its date.
                    treatment.catch_up(self.db, today=self.today)
                    checked = self.today
                try:
                    following = next(script)
                except (StopIteration, _Gone):
                    continue
                heapq.heappush(self._queue, (max(following, self.now), order, script))
            self.now = self.end
            treatment.catch_up(self.db, today=self.today)

    # --- The institute ------------------------------------------------------------------

    def found(self) -> None:
        """The day RiskWren was installed: the program, the organization, and its people."""
        with clock_set_to(lambda: self.now):
            with self.db.write(ME.actor) as session:
                packs.install(session)
                branding.save(session, ME, {"organization_name": c.ORGANIZATION})
                self._units(session)
            with self.db.write(ME.actor) as session:
                self._people(session)
            self.now += timedelta(minutes=30)

    def _unit(self, session: Session, name: str, kind: str, code: str, parent: str | None) -> int:
        parent_id = self.units[parent] if parent else None
        unit = units.create(session, ME, name=name, kind=kind, code=code, parent_id=parent_id)
        self.units[code] = unit.id
        self.unit_names[unit.id], self.unit_kinds[unit.id] = name, kind
        self.parent[unit.id] = parent_id
        self.staff[unit.id], self.leads[unit.id], self.unit_things[unit.id] = [], [], []
        self.unit_risks[unit.id] = []
        self.tally("units")
        return unit.id

    def _units(self, session: Session) -> None:
        for code, name, kind, parent in c.UNITS:
            self._unit(session, name, kind, code, parent)
        surnames = list(c.FAMILY)
        self.rng.shuffle(surnames)
        for department, count in c.LAB_DEPARTMENTS.items():
            self.labs[department] = []
            for _ in range(count):
                surname = surnames.pop()
                code = f"{department}-{_ascii(surname).upper()}"
                lab = self._unit(session, f"{surname} Lab", "lab", code, department)
                self.labs[department].append(lab)
                self.lab_heads[lab] = surname

    def _names(self, taken: set[str]) -> Iterator[str]:
        pairs = [(given, family) for given in c.GIVEN for family in c.FAMILY]
        self.rng.shuffle(pairs)
        self._emails |= {email_for(name) for name in taken}
        for given, family in pairs:
            name = f"{given} {family}"
            if email_for(name) not in self._emails:
                self._emails.add(email_for(name))
                yield name

    def _person(self, session: Session, name: str, title: str, unit: int, *grants: Grant) -> int:
        account = accounts.create(
            session, ME, email=email_for(name), display_name=name, title=title, grants=grants
        )
        # Nobody in the demo has a password: the sign-in page signs you in as a sample
        # person, and only from this machine.
        accounts.set_status(session, ME, account, "active")
        accounts.set_memberships(session, ME, account, [unit])
        self.staff[unit].append(account.id)
        self.names[account.id] = name
        for grant in grants:
            if grant.role == "steward" and grant.org_unit_id is not None:
                self.stewards.setdefault(grant.org_unit_id, account.id)
            if grant.role == "leader" and grant.org_unit_id is not None:
                self.leads[grant.org_unit_id].append(account.id)
        self.tally("accounts")
        return account.id

    def _people(self, session: Session) -> None:
        names = self._names({name for _, name, *_ in c.CAST})
        for key, name, title, unit, roles_ in c.CAST:
            grants = [
                Grant(role, self.units[where] if where else None, limit)
                for role, where, limit in roles_
            ]
            self.cast[key] = self._person(session, name, title, self.units[unit], *grants)
        for code, name, kind, _ in c.UNITS:
            unit = self.units[code]
            if code in ("NMI", "RISK"):
                continue
            if kind not in ("division", "organization") and code != "PRES" and not self.leads[unit]:
                title = c.HEAD_TITLES.get(kind, f"Director, {name}")
                self.heads[unit] = self._person(
                    session, next(names), title, unit, Grant("leader", unit, "moderate")
                )
            if unit not in self.stewards:
                title = c.STEWARD_TITLES.get(kind, "Operations Manager")
                self._person(session, next(names), title, unit, Grant("steward", unit))
            for _ in range(self.rng.randint(1, 2)):
                titles = c.STAFF_TITLES.get(kind, c.STAFF_TITLES["department"])
                self._person(session, next(names), self.rng.choice(titles), unit)
        given = list(c.GIVEN)
        for lab, surname in self.lab_heads.items():
            self.rng.shuffle(given)
            head = next(
                f"{g} {surname}" for g in given if email_for(f"{g} {surname}") not in self._emails
            )
            self._emails.add(email_for(head))
            self.heads[lab] = self._person(
                session, head, c.HEAD_TITLES["lab"], lab, Grant("leader", lab, "moderate")
            )
            self._person(session, next(names), c.STEWARD_TITLES["lab"], lab, Grant("steward", lab))
            for _ in range(self.rng.randint(1, 2)):
                self._person(session, next(names), self.rng.choice(c.STAFF_TITLES["lab"]), lab)
        for key, role, about in c.SAMPLE:
            account = accounts.get(session, self.cast[key])
            self.sample.append(
                {
                    "key": key,
                    "email": account.email,
                    "name": account.display_name,
                    "title": account.title or "",
                    "role": role,
                    "about": about,
                }
            )

    # --- Who does what ------------------------------------------------------------------

    def chain(self, unit: int | None) -> Iterator[int]:
        while unit is not None:
            yield unit
            unit = self.parent[unit]

    def manager(self) -> int:
        return self.cast[self.rng.choice(["risk1", "risk2", "risk3"])]

    def assessor(self) -> int:
        return self.cast[self.rng.choice(["assess1", "assess2"])]

    def steward(self, unit: int) -> int:
        """Whoever keeps this unit's records: its steward, one above it, or the risk team."""
        for each in self.chain(unit):
            found = self.stewards.get(each)
            if found is not None and found not in self.departed:
                return found
        return self.manager()

    def pick(self, unit: int) -> int:
        """Someone who works in the unit, to own something."""
        for each in self.chain(unit):
            people = [p for p in self.staff[each] if p not in self.departed]
            if people:
                return self.rng.choice(people)
        return self.manager()

    def acceptor(self, risk_id: int) -> int | None:
        """The nearest leader with the authority to accept this risk as it stands."""
        with self.db.read() as session:
            risk = session.get(Risk, risk_id)
            assert risk is not None
            for unit in self.chain(risk.org_unit_id):
                for leader in self.leads[unit]:
                    if leader in self.departed:
                        continue
                    if treatment.authority(session, self.principal(leader), risk)["allowed"]:
                        return leader
        return None

    # --- The inventory ------------------------------------------------------------------

    def add_thing(
        self, by: int, record_type: RecordType, key: str, values: dict[str, Any], owner: int
    ) -> None:
        unit = values["org_unit_id"]
        # Some things are known by a number elsewhere: an asset tag, or a contract.
        if record_type.key == "system" and self.side.random() < 0.45:
            tag = f"NM-{self.side.randrange(100000, 999999)}"
            values = {**values, "external_refs": [{"system": "asset_tag", "value": tag}]}
        elif record_type.key == "third_party" and self.side.random() < 0.6:
            number = (
                f"C-{self.side.choice((2022, 2023, 2024, 2025))}-{self.side.randrange(100, 999)}"
            )
            values = {**values, "external_refs": [{"system": "contract", "value": number}]}
        with self.act(by) as (session, who):
            record = records.create(session, who, record_type, values)
            if owner != by:
                wanted = [{"account_id": owner, "kind": "owner"}]
                if self.stewards.get(unit) == by:
                    wanted.append({"account_id": by, "kind": "delegate"})
                records.set_owners(session, who, record_type, record, wanted)
            self.things[key] = (record_type, record.id, record.ref)
        self.unit_things[unit].append(key)
        self.tally(record_type.plural)

    def _unit_inventory(self, code: str) -> Script:
        unit = self.units[code]
        yield self.later(4, 80)
        by = self.steward(unit)
        for name, kind, criticality, data_class in c.PROCESSES.get(code, []):
            values = {"name": name, "kind": kind, "criticality": criticality,
                      "data_class": data_class, "org_unit_id": unit}  # fmt: skip
            self.add_thing(by, PROCESS, name, values, self.pick(unit))
        yield self.later(1, 8)
        for key, name, where, kind, criticality, data_class, hosting, lifecycle in c.SYSTEMS:
            if where == code:
                values = {"name": name, "kind": kind, "criticality": criticality,
                          "data_class": data_class, "hosting": hosting, "lifecycle": lifecycle,
                          "org_unit_id": unit}  # fmt: skip
                self.add_thing(by, SYSTEM, key, values, self.pick(unit))
        yield self.later(1, 8)
        for key, name, where, kind, criticality, data_class, summary in c.PARTIES:
            if where == code:
                values = {"name": name, "kind": kind, "criticality": criticality,
                          "data_class": data_class, "summary": summary, "org_unit_id": unit}  # fmt: skip
                self.add_thing(by, THIRD_PARTY, key, values, self.pick(unit))

    def _information(self) -> Script:
        """The bodies of information the institute holds, and where each is kept."""
        yield self.start + timedelta(days=104)
        for index, (
            key,
            name,
            code,
            kind,
            criticality,
            data_class,
            held,
            shared,
            agreement,
        ) in enumerate(c.INFORMATION):
            if index % 4 == 3:
                yield self.later(0.5, 4)
            unit = self.units[code]
            values = {"name": name, "kind": kind, "criticality": criticality, "data_class": data_class,
                      "held_in": held, "shared_with": shared, "agreement": agreement, "org_unit_id": unit}  # fmt: skip
            self.add_thing(self.steward(unit), INFORMATION, key, values, self.pick(unit))
        yield self.later(2, 6)
        for source, relation, target in c.INFORMATION_LINKS:
            with self.db.read() as session:
                record_type, record_id, _ = self.things[source]
                unit = session.get(record_type.model, record_id).org_unit_id
            self.link_things(self.steward(unit), source, relation, target)

    def _lab_inventory(self, lab: int) -> Script:
        yield self.later(10, 110)
        by, name = self.steward(lab), self.unit_names[lab]
        process = f"{name} bench research"
        for template, kind, criticality, data_class in c.LAB_PROCESSES:
            values = {"name": template.format(lab=name), "kind": kind, "criticality": criticality,
                      "data_class": data_class, "org_unit_id": lab}  # fmt: skip
            self.add_thing(by, PROCESS, values["name"], values, self.heads[lab])
        made = []
        for template, kind, criticality, data_class, hosting, lifecycle in c.LAB_SYSTEMS:
            values = {"name": template.format(lab=name), "kind": kind, "criticality": criticality,
                      "data_class": data_class, "hosting": hosting, "lifecycle": lifecycle,
                      "org_unit_id": lab}  # fmt: skip
            self.add_thing(by, SYSTEM, values["name"], values, self.pick(lab))
            made.append(values["name"])
        yield self.later(90, 140)  # once central systems are on record
        shared = self.rng.sample(["storage", "cluster", "eln"], self.rng.randint(1, 2))
        for target in [*made, *shared]:
            if target in self.things:
                self.link_things(by, process, "relies_on", target)
        if self.rng.random() < 0.2:
            # An old instrument computer is replaced, and its record kept.
            yield self.later(120, 420)
            record_type, record_id, _ = self.things[made[-1]]
            with self.act(by) as (session, who):
                record = session.get(record_type.model, record_id)
                records.update(
                    session, who, record_type, record,
                    {"status": "retired", "summary": c.RETIRE_NOTE}, version=record.version,
                )  # fmt: skip
            self.tally("systems retired")

    def link_things(self, by: int, source: str, relation: str, target: str) -> None:
        from_type, from_id, _ = self.things[source]
        to_type, to_id, _ = self.things[target]
        with self.act(by) as (session, who):
            links.add(
                session, who, from_type, session.get(from_type.model, from_id), relation,
                to_type, session.get(to_type.model, to_id),
            )  # fmt: skip
        self.tally("links")

    def _links(self) -> Script:
        yield self.start + timedelta(days=100)
        for index, (source, relation, target) in enumerate(c.LINKS):
            if index % 12 == 11:
                yield self.later(0.5, 3)
            with self.db.read() as session:
                record_type, record_id, _ = self.things[source]
                unit = session.get(record_type.model, record_id).org_unit_id
            self.link_things(self.steward(unit), source, relation, target)

    # --- Controls -----------------------------------------------------------------------

    def control_unit(self, key: str, unit: int) -> int:
        """Where a control lives: with the unit that runs it for everyone, with the unit
        itself, or, for a lab, with its department."""
        if key in c.CENTRAL:
            return self.units[c.CENTRAL[key]]
        if self.unit_kinds[unit] == "lab":
            parent = self.parent[unit]
            assert parent is not None
            return parent
        return unit

    def control(
        self,
        key: str,
        unit: int,
        *,
        rating: Any = None,
        name: str | None = None,
        statement: str | None = None,
        owner: int | None = None,
        **more: Any,
    ) -> int:
        """The unit's control of that kind, made if it is not on record yet. ``rating`` fixes
        what is known of it: ``(design, operation, note)``, or ``"never"``."""
        known = self.controls.get((key, unit))
        if known is None:
            entry = self.control_library.get(key, {})
            central = c.CENTRAL.get(key) is not None and self.units[c.CENTRAL[key]] == unit
            title = name or entry["title"]
            if not name and not central:
                title = f"{title}: {self.unit_names[unit]}"
            values = {
                "name": title,
                "statement": statement or entry["statement"],
                "kind": entry.get("kind", "preventive"),
                "nature": entry.get("nature"),
                "frequency": entry.get("frequency"),
                "library_key": key if entry else None,
                "org_unit_id": unit,
                **more,
            }
            by = self.steward(unit)
            owner = owner or self.pick(unit)
            with self.act(by) as (session, who):
                record = records.create(session, who, CONTROL, values)
                if owner != by:
                    records.set_owners(
                        session, who, CONTROL, record, [{"account_id": owner, "kind": "owner"}]
                    )
                known = record.id
            self.controls[(key, unit)] = known
            self.tally("controls")
            self.schedule(self._control_life(known, unit))
        if rating == "never":
            self.fixed_rating[known] = rating
        elif rating is not None:
            self.fixed_rating[known] = rating
            self.rate(self.assessor(), known, *rating)
        return known

    def rate(self, by: int, control_id: int, design: str, operation: str, note: str) -> None:
        try:
            with self.act(by) as (session, who):
                control = session.get(Control, control_id)
                controls.rate(session, who, control, design=design, operation=operation, note=note)
        except Conflict:
            return  # a test result still holds, and a judgment does not replace it
        self.last_rated[control_id] = self.now
        self.tally("control ratings")
        if self.rng.random() < 0.6:
            self._evidence(by, control_id, note)

    def _evidence(self, by: int, control_id: int, seen: str) -> None:
        """Whoever rates a control often keeps what they looked at. It holds for a year, so
        what was collected for an old rating has stopped counting by now."""
        kind = self.rng.choices(["file", "link", "note", "attestation"], weights=[40, 20, 30, 10])[
            0
        ]
        name, said = self.rng.choice(c.EVIDENCE[kind])
        day = self.today
        with self.act(by) as (session, who):
            control = session.get(Control, control_id)
            assert control is not None
            values = {
                "name": f"{name}: {control.name}"[:200],
                "kind": kind,
                "org_unit_id": control.org_unit_id,
                "collected_on": day,
                "covers_from": day - timedelta(days=90),
                "covers_to": day,
                "data_class": self.rng.choice(["internal", "internal", "confidential"]),
                "note": seen if kind == "note" else said if kind == "attestation" else None,
                "url": f"https://docs.{c.DOMAIN}/controls/{control.ref.lower()}"
                if kind == "link"
                else None,
                "summary": said if kind == "link" else None,
            }
            item = records.create(session, who, EVIDENCE, values)
            if kind == "file" and self.files is not None:
                days = [
                    (day - timedelta(days=offset)).isoformat() for offset in (80, 62, 41, 23, 5)
                ]
                rows = "\n".join(c.EVIDENCE_ROWS).format(
                    **{f"d{n + 1}": d for n, d in enumerate(days)}
                )
                text = f"# {control.ref} {control.name}\n{rows}\n"
                evidence.attach_file(
                    session,
                    who,
                    item,
                    self.files,
                    text.encode(),
                    f"{control.ref.lower()}-{said}.csv",
                )
            evidence.set_subjects(session, who, item, [control.ref])
        self.tally("evidence")

    def _rating(self, fate: str) -> tuple[str, str, str]:
        note = self.rng.choice(c.RATING_NOTES[fate])
        if fate == "effective":
            return "effective", "effective", note
        if fate == "partly":
            design, operation = self.rng.choice(
                [("effective", "partly"), ("effective", "partly"), ("partly", "partly"),
                 ("partly", "effective")]
            )  # fmt: skip
            return design, operation, note
        return self.rng.choice(["effective", "partly"]), "ineffective", note

    def _control_life(self, control_id: int, unit: int) -> Script:
        """What comes to be known about a control: rated some weeks after it is recorded,
        and again each year, unless nobody gets to it."""
        fate = self.rng.choices(
            ["effective", "partly", "ineffective", "never"], weights=[62, 24, 5, 9]
        )[0]
        yield self.later(8, 50)
        while True:
            fixed = self.fixed_rating.get(control_id)
            if fixed == "never" or (fixed is None and fate == "never"):
                return
            recent = self.last_rated.get(control_id)
            if recent is None or (self.now - recent).days > 200:
                by = self.assessor() if self.rng.random() < 0.7 else self.steward(unit)
                self.rate(by, control_id, *(fixed or self._rating(fate)))
            if fixed is None and self.rng.random() < 0.13:
                return  # nobody rates it again, and what is known of it goes stale
            yield self.later(320, 385)
            roll = self.rng.random()
            if fate == "partly" and roll < 0.45:
                fate = "effective"
            elif (fate == "effective" and roll < 0.07) or (fate == "ineffective" and roll < 0.6):
                fate = "partly"

    def link(
        self, by: int, risk_id: int, control_id: int, reduces: str, reliance: str,
        note: str | None = None,
    ) -> None:  # fmt: skip
        """Say a control bears on a risk. A steward links what they can see; a control that
        another unit runs is linked by the risk team, who see everything."""
        with self.db.read() as session:
            control = session.get(Control, control_id)
            seen = access.can_see(session, self.principal(by), CONTROL, control)
        with self.act(by if seen else self.manager()) as (session, who):
            controls.link(
                session, who, session.get(Risk, risk_id), session.get(Control, control_id),
                reduces=reduces, reliance=reliance, note=note,
            )  # fmt: skip
        self.tally("control links")

    # --- Risks --------------------------------------------------------------------------

    def raise_risk(
        self,
        by: int,
        unit: int,
        key: str,
        *,
        name: str | None = None,
        owner: int | None = None,
        subjects: list[str] | None = None,
        **more: Any,
    ) -> int:
        entry = self.library[key]
        title = name or entry["title"]
        if not name and self.usage.get(key, 0) > 1:
            title = f"{title}: {self.unit_names[unit]}"
        values = {
            "name": title,
            "category": entry["category"],
            "cause": entry["cause"],
            "event": entry["event"],
            "consequence": entry["consequence"],
            "library_key": key,
            "org_unit_id": unit,
            **more,
        }
        owner = owner or by
        with self.act(by) as (session, who):
            risk = register.create(session, who, values)
            if owner != by:
                records.set_owners(
                    session, who, RISK, risk, [{"account_id": owner, "kind": "owner"}]
                )
            refs = [self.things[key][2] for key in subjects or [] if key in self.things]
            if refs:
                register.set_subjects(session, who, risk, refs)
            risk_id = risk.id
        self.risks[risk_id] = {"unit": unit, "owner": owner, "key": key, "lean": 0}
        self.unit_risks[unit].append(risk_id)
        self.tally("risks")
        return risk_id

    def assess(
        self, by: int, risk_id: int, kind: str, likelihood: int, impacts: dict[str, int], why: str
    ) -> str:
        with self.act(by) as (session, who):
            risk = session.get(Risk, risk_id)
            register.assess(
                session, who, risk, kind=kind, likelihood=likelihood, impact_levels=impacts,
                rationale=why,
            )  # fmt: skip
            standing = risk.standing
        if kind == "inherent":
            self.risks[risk_id]["inherent"] = (likelihood, dict(impacts))
        self.tally("assessments")
        return str(standing)

    def residual(self, by: int, risk_id: int, why: str | None = None) -> tuple[str, str]:
        """Judge what remains: what the controls suggest, moved by however this owner leans.
        Returns the risk's standing and its rating."""
        about = self.risks[risk_id]
        start, impacts = about["inherent"]
        with self.db.read() as session:
            hint = register.suggestion(session, session.get(Risk, risk_id))
        likelihood = hint["likelihood"] if hint else start
        down = max(impacts.values()) - hint["impact"] if hint else 0
        lean = about["lean"]
        likelihood = max(1, min(5, likelihood + lean))
        if why is None:
            words = (
                c.WHY_RESIDUAL_HIGHER if lean > 0
                else c.WHY_RESIDUAL_LOWER if lean < 0
                else c.WHY_REVIEW if about.get("judged") else c.WHY_RESIDUAL_AGREE
            )  # fmt: skip
            why = self.rng.choice(words)
        levels = {key: max(1, level - down) for key, level in impacts.items()}
        standing = self.assess(by, risk_id, "residual", likelihood, levels, why)
        about["judged"] = True
        with self.db.read() as session:
            risk = session.get(Risk, risk_id)
            return standing, str(risk.residual_rating)

    def respond(self, by: int, risk_id: int, response: str, why: str) -> None:
        with self.act(by) as (session, who):
            treatment.respond(session, who, session.get(Risk, risk_id), response, why)

    def plan(
        self, by: int, risk_id: int, objective: str, owner: int, due: date,
        target: str | None = None,
    ) -> int:  # fmt: skip
        with self.act(by) as (session, who):
            made = treatment.create_plan(
                session, who, session.get(Risk, risk_id), objective=objective, owner_id=owner,
                due_on=due, target_rating=target,
            )  # fmt: skip
            self.tally("plans")
            return made.id

    def action(self, by: int, plan_id: int, title: str, owner: int, due: date) -> int:
        with self.act(by) as (session, who):
            made = treatment.add_action(
                session, who, session.get(TreatmentPlan, plan_id), title=title, owner_id=owner,
                due_on=due,
            )  # fmt: skip
            self.tally("actions")
            return made.id

    def progress(self, by: int, action_id: int, **changes: Any) -> None:
        with self.act(by) as (session, who):
            treatment.update_action(session, who, session.get(Action, action_id), changes)

    def accept(
        self, by: int, risk_id: int, why: str, until: date, conditions: str | None = None
    ) -> int:
        with self.act(by) as (session, who):
            made = treatment.accept(
                session, who, session.get(Risk, risk_id), rationale=why, expires_on=until,
                conditions=conditions,
            )  # fmt: skip
            self.tally("acceptances")
            return made.id

    def refused(self, by: int, risk_id: int) -> str:
        """Someone tries to accept a risk they have no authority for, and is told why not."""
        try:
            self.accept(by, risk_id, "Accepted for the core.", self.today + timedelta(days=90))
        except PermissionDenied as refusal:
            self.tally("acceptances refused")
            return str(refusal)
        raise AssertionError("An acceptance beyond the leader's limit was allowed.")

    def escalate(self, by: int, risk_id: int, to: int, why: str) -> None:
        with self.act(by) as (session, who):
            register.escalate(session, who, session.get(Risk, risk_id), to, why)
        self.tally("escalations")

    def _inherent(self, key: str, unit: int) -> tuple[int, dict[str, int]]:
        likelihood, impacts = c.INHERENT[key]
        likelihood = max(1, min(5, likelihood + self.rng.choice([-1, -1, 0, 0, 0, 1])))
        impacts = dict(impacts)
        if self.unit_kinds[unit] == "lab" and self.rng.random() < 0.6:
            impacts = {key: max(1, level - 1) for key, level in impacts.items()}  # a smaller stake
        return likelihood, impacts

    def _risk(self, unit: int, key: str, start: datetime, owner: int | None = None) -> Script:
        """One risk, from the day it is raised: assessed, tied to controls, judged again once
        they are rated, answered if it is above appetite, and then reviewed when due."""
        yield start
        by = self.steward(unit)
        owner = (
            owner or (self.heads.get(unit) if self.rng.random() < 0.4 else None) or self.pick(unit)
        )
        things = self.unit_things[unit]
        subjects = self.rng.sample(things, min(len(things), self.rng.randint(0, 2)))
        risk_id = self.raise_risk(by, unit, key, owner=owner, subjects=subjects)
        about = self.risks[risk_id]
        yield self.later(1, 14)
        likelihood, impacts = self._inherent(key, unit)
        self.assess(
            owner, risk_id, "inherent", likelihood, impacts, self.rng.choice(c.WHY_INHERENT)
        )
        yield self.later(3, 20)
        suggested = self.library[key]["controls"]
        wanted = suggested[: self.rng.randint(min(2, len(suggested)), min(4, len(suggested)))]
        for index, control_key in enumerate(wanted):
            control = self.control(control_key, self.control_unit(control_key, unit))
            main = index <= 1
            reduces = self.control_library[control_key]["reduces"]
            self.link(by, risk_id, control, reduces, "primary" if main else "supporting")
        yield self.later(45, 80)  # once the controls have been looked at
        about["lean"] = self.rng.choices([0, 1, -1], weights=[74, 9, 17])[0]
        judge = owner if self.rng.random() < 0.75 else self.assessor()
        standing, rating = self.residual(judge, risk_id)
        if standing == "needs_decision":
            roll = self.rng.random()
            if roll < 0.45:
                self.schedule(self._treat(risk_id))
            elif roll < 0.8:
                self.schedule(self._live_with(risk_id))
            parent = self.parent[unit]
            if rating in ("high", "critical") and parent is not None and self.rng.random() < 0.28:
                self.schedule(self._escalate(risk_id, parent))
        yield from self._reviews(risk_id)

    def _reviews(self, risk_id: int) -> Script:
        owner = self.risks[risk_id]["owner"]
        lapses = self.rng.random() < 0.14  # some owners stop looking
        while True:
            with self.db.read() as session:
                risk = session.get(Risk, risk_id)
                due, closed = risk.next_review_on, risk.status == "closed"
            if due is None or closed:
                return
            moment = self.on(due, (-18, 16))
            if lapses and moment > self.end - timedelta(days=200):
                return
            yield max(moment, self.now + timedelta(days=1))
            if self.rng.random() < 0.07:
                self.risks[risk_id]["lean"] = self.rng.choice([0, 0, 1, -1])
            self.residual(owner, risk_id)

    def _escalate(self, risk_id: int, to: int) -> Script:
        yield self.later(4, 40)
        about = self.risks[risk_id]
        self.escalate(self.steward(about["unit"]), risk_id, to, self.rng.choice(c.ESCALATE_REASONS))

    def _treat(self, risk_id: int) -> Script:
        """A plan to bring the risk down. Most are finished; some stall."""
        yield self.later(3, 25)
        about = self.risks[risk_id]
        owner, unit = about["owner"], about["unit"]
        with self.db.read() as session:
            risk = session.get(Risk, risk_id)
            if risk.standing != "needs_decision":
                return
            appetite = categories.Tree(session).appetite(risk.category_id)
            name, level = risk.name, risk.residual_likelihood
        self.respond(owner, risk_id, "reduce", self.rng.choice(c.RESPOND_REDUCE))
        objective = c.PLAN_OBJECTIVES.get(about["key"]) or f"Bring “{name}” within appetite"
        horizon = self.rng.randint(100, 320)
        plan = self.plan(
            owner, risk_id, objective, owner, self.today + timedelta(days=horizon), appetite
        )
        start, impacts = about["inherent"]
        levels = {key: max(1, value - 2) for key, value in impacts.items()}
        self.assess(owner, risk_id, "target", max(1, (level or start) - 1), levels, c.TARGET_WHY)
        titles = self.rng.choice(c.PLAN_ACTIONS)
        begun = self.now
        steps = []
        for index, title in enumerate(titles):
            due = (begun + timedelta(days=horizon * (index + 1) / len(titles))).date()
            doer = self.pick(unit) if self.rng.random() < 0.6 else owner
            steps.append((self.action(owner, plan, title, doer, due), doer, due))
        stalls = self.rng.random() < 0.24
        for index, (action, doer, due) in enumerate(steps):
            if stalls and index >= len(steps) - 2:
                yield self.on(due, (-30, -5))
                self.progress(doer, action, status="in_progress")
                if self.rng.random() < 0.5:
                    yield self.on(due, (-3, 6))
                    moved = due + timedelta(days=self.rng.randint(20, 45))
                    self.progress(
                        doer, action, due_on=moved, reason=self.rng.choice(c.MOVE_REASONS)
                    )
                continue
            if self.rng.random() < 0.2:
                yield self.on(due, (-8, -1))
                due += timedelta(days=self.rng.randint(14, 40))
                self.progress(doer, action, due_on=due, reason=self.rng.choice(c.MOVE_REASONS))
            yield self.on(due, (-24, 9))
            self.progress(
                doer, action, status="done", completion_note=self.rng.choice(c.DONE_NOTES)
            )
        if stalls:
            return
        yield self.later(4, 25)  # the plan is complete, and the owner is asked to assess again
        about["lean"] = -1
        self.residual(owner, risk_id, c.PLAN_DONE_WHY)

    def _live_with(self, risk_id: int) -> Script:
        """Acceptance: by the nearest leader with the authority, until a date, and then again
        or not."""
        yield self.later(5, 30)
        about = self.risks[risk_id]
        with self.db.read() as session:
            if session.get(Risk, risk_id).standing != "needs_decision":
                return
        self.respond(about["owner"], risk_id, "accept", self.rng.choice(c.ACCEPT_WHY))
        yield self.later(2, 20)
        while True:
            leader = self.acceptor(risk_id)
            if leader is None:
                return
            with self.db.read() as session:
                latest = treatment.authority(
                    session, self.principal(leader), session.get(Risk, risk_id)
                )["latest"]
            longest = (latest - self.today).days
            until = self.today + timedelta(days=self.rng.randint(longest // 2, longest - 3))
            acceptance = self.accept(
                leader, risk_id, self.rng.choice(c.ACCEPT_WHY), until,
                self.rng.choice(c.ACCEPT_CONDITIONS),
            )  # fmt: skip
            if self.rng.random() < 0.12:
                yield self.later(40, 120)
                with self.act(leader) as (session, who):
                    treatment.withdraw(
                        session, who, session.get(Acceptance, acceptance),
                        self.rng.choice(c.WITHDRAW_REASONS),
                    )  # fmt: skip
                self.tally("acceptances withdrawn")
                return
            yield self.on(until, (-12, 24))
            if self.rng.random() < 0.35:
                return  # nobody renews it, and it is left needing a decision

    # --- The stories people will read -----------------------------------------------------

    def _story_specimens(self) -> Script:
        """A critical risk brought to high by controls of known effectiveness, with a plan."""
        cast, bio = self.cast, self.units["BIO"]
        chidi, dalia = cast["bio_mgr"], cast["member"]
        yield self.ago(612)
        risk = self.raise_risk(
            chidi, bio, "specimen_loss", owner=chidi,
            name="Loss of irreplaceable specimens from freezer failure",
            subjects=["Specimen storage and retrieval", "freezers", "monitor", "nitrogen", "coldline"],
            summary="The repository holds about 400,000 specimens collected over thirty years. "
            "Most could not be collected again.",
        )  # fmt: skip
        yield self.ago(606)
        self.assess(
            chidi, risk, "inherent", 4, {"mission": 5, "financial": 3, "trust": 4},
            "Two freezers failed in the three years before monitoring was installed, and an "
            "alarm went unanswered over a holiday weekend. Without the safeguards we now rely "
            "on, a loss would be expected about once a year, and it would end studies that "
            "cannot be repeated.",
        )  # fmt: skip
        yield self.ago(598)
        made = [
            (self.control("preventive_maintenance", bio, rating=(
                "effective", "effective",
                "Coldline's service reports for the last four quarters cover every freezer, "
                "and each fault found was fixed within the contract's time.")),
             "likelihood", "primary"),
            (self.control("freezer_monitoring", bio, is_key=True, rating=(
                "effective", "partly",
                "Alarms are raised within a minute and answered within twenty in working "
                "hours. Out of hours, three of eleven alarms last year waited more than two "
                "hours: the call list had lapsed.")),
             "likelihood", "primary"),
            (self.control("specimen_split", bio, rating=(
                "partly", "partly",
                "About a third of collections are split between rooms. The rest are held in "
                "one room of one building.")),
             "impact", "primary"),
            (self.control("backup_capacity", bio, rating=(
                "effective", "effective",
                "Two empty freezers are kept cold. They were used in March, and the transfer "
                "took forty minutes.")),
             "impact", "supporting"),
        ]  # fmt: skip
        for control, reduces, reliance in made:
            self.link(chidi, risk, control, reduces, reliance)
        yield self.ago(575)
        self.residual(
            chidi, risk,
            "I agree with what the controls suggest. Maintenance is sound and the alarm works, "
            "but nobody is certain to answer it at night, and most collections sit in one room.",
        )  # fmt: skip
        yield self.ago(566)
        self.respond(
            chidi, risk, "reduce",
            "High is above the appetite for research risk, and both gaps can be closed: a "
            "second freezer room, and an alarm that is answered at any hour.",
        )  # fmt: skip
        plan = self.plan(
            chidi, risk, "Split every collection across two buildings, and have the alarm "
            "answered at any hour", chidi, self.day(75), "moderate",
        )  # fmt: skip
        self.assess(
            chidi, risk, "target", 2, {"mission": 3, "financial": 2, "trust": 2},
            "With every collection split, the loss of one room loses no collection outright, "
            "and an answered alarm makes even that unlikely.",
        )  # fmt: skip
        space = self.action(chidi, plan, "Agree space in the east building for a second freezer room", cast["bio_dir"], self.day(-440))  # fmt: skip
        install = self.action(chidi, plan, "Install and commission eight freezers in the east building", chidi, self.day(-310))  # fmt: skip
        move = self.action(chidi, plan, "Move the second aliquot of each collection to the east building", dalia, self.day(40))  # fmt: skip
        answer = self.action(chidi, plan, "Contract an out-of-hours alarm response service", chidi, self.day(5))  # fmt: skip
        self.action(chidi, plan, "Have the controls rated again, and assess the residual risk", chidi, self.day(75))  # fmt: skip
        yield self.ago(452)
        self.progress(cast["bio_dir"], space, status="done", completion_note="Room E-014 is ours from January.")  # fmt: skip
        yield self.ago(390)
        self.residual(chidi, risk, "Reviewed at six months. The east room is agreed; nothing has changed yet in what protects the specimens.")  # fmt: skip
        yield self.ago(318)
        self.progress(
            chidi, install, due_on=self.day(-245),
            reason="The electrical work needs a building shutdown, which could only be "
            "scheduled for the spring.",
        )  # fmt: skip
        yield self.ago(251)
        self.progress(chidi, install, status="done", completion_note="Eight freezers commissioned and on the monitoring system.")  # fmt: skip
        yield self.ago(205)
        self.residual(chidi, risk, "Reviewed at six months. The freezers are in, but only two collections have moved, so the picture is the same.")  # fmt: skip
        yield self.ago(160)
        self.progress(dalia, move, status="in_progress")
        yield self.ago(24)
        self.residual(chidi, risk, "Reviewed. Fourteen of thirty-one collections are now split. I will assess again when the move is complete and the alarm service is in place.")  # fmt: skip
        yield self.ago(9)
        self.progress(chidi, answer, status="in_progress")

    def _story_ransomware(self) -> Script:
        """Controls run by two units, and a judgment that departs from the suggestion."""
        cast, sec, it = self.cast, self.units["SEC"], self.units["IT"]
        viktor, esme = cast["sec_mgr"], cast["it_mgr"]
        yield self.ago(655)
        risk = self.raise_risk(
            viktor, sec, "ransomware", owner=viktor, name="Ransomware reaching research storage",
            subjects=["Research data storage", "storage", "backup", "cluster", "backupco"],
            summary="Research storage holds the working data of every lab and core.",
        )  # fmt: skip
        yield self.ago(650)
        self.assess(
            viktor, risk, "inherent", 4, {"mission": 5, "financial": 4, "trust": 4},
            "Institutes like ours are hit every year. Research storage is reachable from "
            "every lab workstation, and losing it would stop most research for weeks.",
        )  # fmt: skip
        yield self.ago(640)
        for key, unit, reduces, reliance, rating in [
            ("patching", it, "likelihood", "primary", ("effective", "effective",
             "Ninety-six percent of servers and managed workstations were patched within "
             "thirty days in each of the last four quarters.")),
            ("malware_protection", sec, "likelihood", "primary", ("effective", "effective",
             "Present and reporting on every managed machine; alerts are answered the same day.")),
            ("network_segmentation", it, "likelihood", "supporting", ("partly", "effective",
             "Clinical and administrative networks are separated. Research storage is still "
             "reachable from every lab network.")),
            ("logging_monitoring", sec, "likelihood", "supporting", ("effective", "partly",
             "Storage and identity logs are watched. Lab instrument computers send nothing.")),
            ("backups_tested", it, "impact", "primary", ("effective", "partly",
             "Restores are tested each quarter for administrative systems. Research storage "
             "was last restored in full two years ago.")),
            ("incident_response", sec, "impact", "supporting", ("effective", "effective",
             "The plan was exercised in the autumn with Research Computing and Facilities.")),
        ]:  # fmt: skip
            self.link(viktor, risk, self.control(key, unit, rating=rating), reduces, reliance)
        yield self.ago(610)
        self.risks[risk]["lean"] = 1
        self.residual(
            viktor, risk,
            "Higher than the controls suggest. Patching and malware protection are rated "
            "effective, but two institutes we work with were hit this year through a "
            "supplier's remote access, which neither control addresses.",
        )  # fmt: skip
        yield self.ago(596)
        self.respond(viktor, risk, "reduce", "An offline copy that is known to restore turns a catastrophe into an outage.")  # fmt: skip
        plan = self.plan(
            viktor, risk, "Keep an offline copy of research storage, restored in full each quarter",
            esme, self.day(110), "moderate",
        )  # fmt: skip
        self.assess(viktor, risk, "target", 2, {"mission": 3, "financial": 3, "trust": 3}, c.TARGET_WHY)  # fmt: skip
        steps = [
            self.action(viktor, plan, "Agree the offline copy's design and budget", esme, self.day(-480)),
            self.action(viktor, plan, "Contract offline vaulting with Stonebridge Data Vaulting", esme, self.day(-330)),
            self.action(viktor, plan, "Restore research storage in full, and time it", cast["rc_dir"], self.day(-20)),
            self.action(viktor, plan, "Close suppliers' standing remote access", viktor, self.day(60)),
        ]  # fmt: skip
        yield self.ago(488)
        self.progress(
            esme, steps[0], status="done", completion_note="Approved in the capital plan."
        )
        yield self.ago(425)
        self.residual(viktor, risk)
        yield self.ago(322)
        self.progress(esme, steps[1], status="done", completion_note="First full copy vaulted.")
        yield self.ago(240)
        self.residual(viktor, risk)
        yield self.ago(58)
        self.progress(cast["rc_dir"], steps[2], status="in_progress")
        yield self.ago(52)
        self.residual(viktor, risk)
        yield self.ago(26)
        self.progress(
            cast["rc_dir"], steps[2], due_on=self.day(21),
            reason="The first restore filled the staging array. More capacity arrives this month.",
        )  # fmt: skip

    def _story_workstation(self) -> Script:
        """A named, time-limited acceptance with conditions, expiring next month."""
        cast, img = self.cast, self.units["IMG"]
        dev, soren = cast["img_mgr"], cast["cores_lead"]
        yield self.ago(428)
        risk = self.raise_risk(
            dev, img, "unsupported_systems", owner=dev,
            name="Unsupported workstation controlling the cryo-electron microscope",
            subjects=["Microscopy service", "imgws", "cryo", "optics"],
            cause="The control workstation runs an operating system its maker no longer "
            "supports, and the microscope's maker will not certify a newer one",
            event="a known weakness is used to take over or disable the workstation",
            consequence="the microscope is out of use for weeks and eleven labs lose their bookings",
        )  # fmt: skip
        yield self.ago(424)
        self.assess(
            dev, risk, "inherent", 4, {"mission": 4, "financial": 3},
            "Unpatched machines of this kind are found and used within months when they can "
            "be reached. A rebuild needs the maker's engineer on site.",
        )  # fmt: skip
        yield self.ago(415)
        contained = self.control("unsupported_contained", self.units["SEC"], rating=(
            "effective", "partly",
            "Each unsupported machine is on its own network segment. Removable media are "
            "still used on four of them, because that is how data comes off the instrument."))  # fmt: skip
        self.link(dev, risk, contained, "likelihood", "primary")
        self.link(dev, risk, self.control("network_segmentation", self.units["IT"]), "likelihood", "supporting")  # fmt: skip
        yield self.ago(380)
        self.residual(dev, risk, "I agree with the suggestion. The segment helps, but images leave the workstation on removable drives every day.")  # fmt: skip
        yield self.ago(366)
        self.respond(
            dev, risk, "accept",
            "Replacing the workstation means replacing the detector it drives, which is in "
            "next year's equipment budget. Until then the exposure is contained and understood.",
        )  # fmt: skip
        yield self.ago(338)
        self.accept(
            soren, risk,
            "The microscope is booked ten months ahead and cannot be taken out of service. "
            "The replacement is funded for next fiscal year, and the interim safeguards are "
            "proportionate.",
            self.day(24),
            "The workstation stays on its own network segment. Removable drives are scanned "
            "on the core's clean machine before each use. Reviewed at each quarterly meeting "
            "of core directors.",
        )  # fmt: skip
        yield self.ago(196)
        self.residual(dev, risk, "Reviewed. The conditions of the acceptance are being met; nothing else has changed.")  # fmt: skip
        yield self.ago(17)
        self.residual(dev, risk, "Reviewed ahead of the acceptance expiring. The detector order has slipped a quarter, so this will need accepting again.")  # fmt: skip

    def _story_authority(self) -> Script:
        """A unit's own leader may not accept a high risk; the leader above may."""
        cast, bio = self.cast, self.units["BIO"]
        chidi, dalia, ines, soren = (
            cast["bio_mgr"],
            cast["member"],
            cast["bio_dir"],
            cast["cores_lead"],
        )
        yield self.ago(305)
        risk = self.raise_risk(
            chidi, bio, "hosted_service_outage", owner=dalia,
            name="Outage of the hosted specimen tracking service",
            subjects=["Specimen receipt and processing", "tracking", "trackco"],
        )  # fmt: skip
        yield self.ago(300)
        self.assess(
            dalia, risk, "inherent", 4, {"mission": 4},
            "Without tracking, specimens cannot be received or found. The supplier has had "
            "two outages in four years, one of them lasting three days.",
        )  # fmt: skip
        yield self.ago(292)
        plan_ = self.control("continuity_plan", bio, rating=(
            "partly", "partly",
            "Paper logs cover receipt for about three days. Retrieval has no workaround."))  # fmt: skip
        self.link(chidi, risk, plan_, "impact", "primary")
        self.link(
            chidi, risk, self.control("exit_plan", bio, rating="never"), "impact", "supporting"
        )
        self.link(chidi, risk, self.control("supplier_assessed", self.units["SEC"]), "likelihood", "supporting")  # fmt: skip
        yield self.ago(262)
        self.residual(dalia, risk, "I agree with the suggestion: the paper process helps for a few days and nothing else is known to work.")  # fmt: skip
        yield self.ago(255)
        self.respond(dalia, risk, "accept", "A second tracking system is out of proportion. The contract is up for renewal next year, which is the time to decide.")  # fmt: skip
        yield self.ago(249)
        self.refused(ines, risk)
        yield self.ago(241)
        self.accept(
            soren, risk,
            "Brought to me because a High risk is beyond what a core director may accept. "
            "The supplier's record is two short outages in four years, and paper logs cover "
            "receipt meanwhile. Accepted while the contract runs.",
            self.day(96),
            "An exit plan is written and assessed before the contract is renewed.",
        )  # fmt: skip
        yield self.ago(74)
        self.residual(dalia, risk, "Reviewed. No outages since the last review; the exit plan is still not written.")  # fmt: skip

    def _story_costs(self) -> Script:
        """A low appetite, a detective control that partly works, and a plan gone late."""
        cast, sp = self.cast, self.units["SP"]
        zofia = cast["sp_mgr"]
        yield self.ago(528)
        risk = self.raise_risk(
            zofia, sp, "unallowable_costs", owner=zofia,
            name="Unallowable costs charged to a federal award",
            subjects=["Award setup and management", "grants", "funder1"],
        )  # fmt: skip
        yield self.ago(522)
        self.assess(
            zofia, risk, "inherent", 4, {"financial": 3, "legal": 4, "trust": 3},
            "Last year's audit sampled sixty charges and questioned four. Repayment is the "
            "small part: a finding puts every award under closer review.",
        )  # fmt: skip
        yield self.ago(512)
        review = self.control("cost_review", sp, is_key=True, rating=(
            "effective", "partly",
            "The forty largest awards are reviewed every month. Smaller awards were "
            "reviewed in five months of the last twelve."))  # fmt: skip
        self.link(zofia, risk, review, "likelihood", "primary")
        self.link(zofia, risk, self.control("separation_of_duties", self.units["FIN"]), "likelihood", "supporting")  # fmt: skip
        yield self.ago(480)
        self.residual(zofia, risk, "I agree with the suggestion. The review works where it is done, and it is not done everywhere.")  # fmt: skip
        yield self.ago(470)
        self.respond(zofia, risk, "reduce", "The appetite for this is low, and the gap is one of capacity, which can be fixed.")  # fmt: skip
        plan = self.plan(
            zofia, risk, "Review charges on every award each month, by someone trained in its terms",
            zofia, self.day(-34), "low",
        )  # fmt: skip
        self.assess(
            zofia, risk, "target", 2, {"financial": 2, "legal": 2, "trust": 2}, c.TARGET_WHY
        )
        analyst = self.pick(sp)
        steps = [
            self.action(zofia, plan, "Train two more analysts in the federal cost principles", zofia, self.day(-360)),
            self.action(zofia, plan, "Add a monthly exception report to the grants management system", analyst, self.day(-230)),
            self.action(zofia, plan, "Extend monthly review to every award", analyst, self.day(-62)),
            self.action(zofia, plan, "Sample three months of reviews, and have the control rated again", zofia, self.day(-34)),
        ]  # fmt: skip
        yield self.ago(371)
        self.progress(
            zofia,
            steps[0],
            status="done",
            completion_note="Both completed the course and are reviewing.",
        )
        yield self.ago(300)
        self.residual(zofia, risk)
        yield self.ago(236)
        self.progress(analyst, steps[1], due_on=self.day(-170), reason="Awardline's release with the report slipped a quarter.")  # fmt: skip
        yield self.ago(163)
        self.progress(
            analyst,
            steps[1],
            status="done",
            completion_note="Report runs on the third working day of each month.",
        )
        yield self.ago(118)
        self.residual(zofia, risk)
        yield self.ago(90)
        self.progress(analyst, steps[2], status="in_progress")

    def _story_supplier(self) -> Script:
        """A third-party risk: first transferred by contract, then reduced by a plan."""
        cast, gen = self.cast, self.units["GEN"]
        maren = cast["gen_mgr"]
        yield self.ago(465)
        risk = self.raise_risk(
            maren, gen, "sole_supplier", owner=maren,
            name="Sole-source dependence on Brightwater Reagents for sequencing chemistry",
            subjects=["Sequencing service", "sequencer1", "sequencer2", "reagents"],
        )  # fmt: skip
        yield self.ago(460)
        self.assess(
            maren, risk, "inherent", 3, {"mission": 4, "financial": 3},
            "Brightwater is the only maker of the chemistry our sequencers run. A recall two "
            "years ago stopped the core for five weeks.",
        )  # fmt: skip
        yield self.ago(450)
        stock = self.control(
            "reagent_stock", gen, name="Ten weeks of sequencing chemistry held in stock",
            statement="The core keeps at least ten weeks' supply of each sequencing kit, "
            "counted on the first Monday of each month.", frequency="monthly", nature="manual",
            rating=("effective", "partly", "Stock was above ten weeks in seven of the last "
                    "twelve monthly counts, and fell to three weeks in June."),
        )  # fmt: skip
        self.link(maren, risk, stock, "impact", "primary")
        second = self.control("alternate_supplier", gen, rating=(
            "partly", "ineffective",
            "A second chemistry was tried once in a pilot. It is not validated for any of "
            "the core's assays."))  # fmt: skip
        self.link(maren, risk, second, "likelihood", "primary")
        # The contract helps the odds a little and the consequence not at all, so however it
        # is rated the picture stays the same.
        self.link(
            maren, risk, self.control("agreements_in_place", self.units["LEGAL"]), "likelihood", "supporting"
        )  # fmt: skip
        yield self.ago(418)
        self.residual(maren, risk, "I agree with the suggestion: stock buys weeks, not months, and there is no second source.")  # fmt: skip
        yield self.ago(404)
        self.respond(
            maren, risk, "transfer",
            "The supply agreement now has Brightwater hold twelve weeks of our chemistry and "
            "pay for expedited replacement if it fails to deliver.",
        )  # fmt: skip
        yield self.ago(228)
        self.residual(maren, risk, "Reviewed. The agreement moves the cost, not the lost weeks. Still High.")  # fmt: skip
        yield self.ago(214)
        self.respond(maren, risk, "reduce", "The contract terms help with cost. Only a second source helps with the science.")  # fmt: skip
        plan = self.plan(maren, risk, "Qualify a second source for the two highest-volume assays", maren, self.day(150), "moderate")  # fmt: skip
        self.assess(maren, risk, "target", 2, {"mission": 3, "financial": 2}, c.TARGET_WHY)
        tech = self.pick(gen)
        steps = [
            self.action(maren, plan, "Choose the alternative chemistry to validate", maren, self.day(-150)),
            self.action(maren, plan, "Validate it against reference samples for both assays", tech, self.day(45)),
            self.action(maren, plan, "Agree supply terms with the second source", maren, self.day(150)),
        ]  # fmt: skip
        yield self.ago(158)
        self.progress(
            maren,
            steps[0],
            status="done",
            completion_note="Chosen after a paper comparison of three.",
        )
        yield self.ago(96)
        self.progress(tech, steps[1], status="in_progress")
        yield self.ago(41)
        self.residual(maren, risk)

    def _story_unassessed(self) -> Script:
        """The control a risk relies on has never been assessed, so it counts for nothing."""
        cmp_ = self.units["CMP"]
        by = self.steward(cmp_)
        yield self.ago(332)
        risk = self.raise_risk(
            by, cmp_, "environmental_control", owner=by,
            name="Loss of environmental control in the animal facility",
            subjects=["Animal husbandry", "vivarium", "bms"],
        )  # fmt: skip
        yield self.ago(327)
        self.assess(
            by, risk, "inherent", 3, {"mission": 4, "safety": 3},
            "Room temperature left its range twice last year when the building management "
            "system, which is out of support, lost contact with the air handlers.",
        )  # fmt: skip
        yield self.ago(318)
        alarm = self.control(
            "animal_room_alarms", cmp_, name="Animal room alarms answered around the clock",
            statement="Temperature, humidity, and airflow alarms from every animal room reach "
            "the on-call technician, who attends within thirty minutes.", kind="detective",
            nature="both", frequency="continuous", rating="never",
        )  # fmt: skip
        self.link(by, risk, alarm, "likelihood", "primary")
        checks = self.control("animal_care_checks", cmp_, rating=(
            "effective", "effective", "Daily check sheets are complete for every room for the last quarter."))  # fmt: skip
        self.link(by, risk, checks, "impact", "supporting")
        yield self.ago(286)
        self.residual(
            by, risk,
            "The alarm response is the control this risk relies on, and nobody has assessed "
            "it yet, so it counts for nothing. Rated as though it were absent until it is.",
        )  # fmt: skip
        yield self.ago(101)
        self.residual(by, risk, "Reviewed. The alarm response is still not assessed; I have asked for it to be.")  # fmt: skip

    def _story_worse(self) -> Script:
        """A re-assessment after an incident elsewhere raises the likelihood."""
        cast, sec, it = self.cast, self.units["SEC"], self.units["IT"]
        viktor = cast["sec_mgr"]
        yield self.ago(548)
        risk = self.raise_risk(
            viktor, sec, "compromised_account", owner=viktor,
            name="Staff accounts taken over through stolen passwords",
            subjects=["Identity and access administration", "identity", "email", "cloud"],
        )  # fmt: skip
        yield self.ago(544)
        self.assess(
            viktor, risk, "inherent", 5, {"trust": 3, "legal": 3, "mission": 3},
            "Passwords are stolen from our staff every month. With nothing else in the way, "
            "each one is an account lost.",
        )  # fmt: skip
        yield self.ago(536)
        for key, unit, reliance, rating in [
            ("second_factor", it, "primary", ("effective", "effective",
             "Required for every account, with no exceptions on record.")),
            ("access_reviewed", sec, "primary", ("effective", "effective",
             "Reviewed each quarter by system owners; removals are made within the week.")),
            ("security_training", sec, "supporting", ("effective", "partly",
             "Completed by ninety-one percent of staff. One in nine still enters a password "
             "in the simulated exercise.")),
        ]:  # fmt: skip
            self.link(viktor, risk, self.control(key, unit, rating=rating), "likelihood", reliance)
        yield self.ago(500)
        self.residual(viktor, risk, "I agree with the suggestion. A stolen password alone no longer opens an account.")  # fmt: skip
        yield self.ago(141)
        self.risks[risk]["lean"] = 1
        self.residual(
            viktor, risk,
            "Raised after a neighbouring institute's accounts were taken over by tricking "
            "staff into approving sign-in prompts. Our second factor uses the same prompts, "
            "and we have seen the same attempts here since. Higher than the controls suggest.",
        )  # fmt: skip
        yield self.ago(126)
        self.respond(
            viktor,
            risk,
            "reduce",
            "The second factor can be made resistant to this at modest cost.",
        )
        plan = self.plan(
            viktor, risk, "Replace approval prompts with number matching, and give administrators security keys",
            viktor, self.day(64), "moderate",
        )  # fmt: skip
        first = self.action(viktor, plan, "Turn on number matching for every account", cast["it_mgr"], self.day(-48))  # fmt: skip
        self.action(
            viktor, plan, "Issue security keys to every administrator", cast["it_mgr"], self.day(18)
        )
        self.action(viktor, plan, "Have the second factor rated again", viktor, self.day(64))
        yield self.ago(55)
        self.progress(
            cast["it_mgr"],
            first,
            status="done",
            completion_note="On for everyone since the first of the month.",
        )

    def _story_closed(self) -> Script:
        """A risk closed when the activity moved, and kept for the record."""
        cast, pharm = self.cast, self.units["PHARM"]
        uma = cast["pharm_mgr"]
        yield self.ago(570)
        risk = self.raise_risk(
            uma, pharm, "environmental_control", owner=uma, category="medication",
            name="Loss of refrigerated medication from a failed pharmacy refrigerator",
            cause="A refrigerator fails, or its door is left open, outside pharmacy hours",
            event="medication is held out of its temperature range before anyone notices",
            consequence="stock is destroyed and infusions are postponed",
        )  # fmt: skip
        yield self.ago(565)
        self.assess(uma, risk, "inherent", 3, {"safety": 3, "financial": 3}, "It happened once in each of the last two years.")  # fmt: skip
        yield self.ago(556)
        monitor = self.control("environmental_monitoring", self.units["FAC"], rating=(
            "effective", "effective", "Every monitored point alarmed in the annual test, and each alarm was answered."))  # fmt: skip
        self.link(uma, risk, monitor, "likelihood", "primary")
        yield self.ago(520)
        self.residual(uma, risk, "I agree with the suggestion.")
        yield self.ago(150)
        self.residual(uma, risk, "Reviewed. Refrigerated stock moves to the hospital partner's pharmacy next quarter.")  # fmt: skip
        yield self.ago(88)
        with self.act(uma) as (session, who):
            record = session.get(Risk, risk)
            register.update(
                session, who, record,
                {"status": "closed", "closed_reason": "Refrigerated medication moved to the "
                 "hospital partner's pharmacy with the infusion service's supply. Northmere "
                 "no longer stores any."},
                version=record.version,
            )  # fmt: skip
        self.tally("risks closed")

    def _story_power(self) -> Script:
        """A critical risk that only an executive may accept, and only for six months."""
        cast, fac = self.cast, self.units["FAC"]
        by, bryn, henrik = self.steward(fac), cast["fac_dir"], cast["coo"]
        yield self.ago(236)
        risk = self.raise_risk(
            by, fac, "power_failure", owner=bryn,
            name="Emergency power cannot carry the freezer farm and animal facility",
            subjects=["Emergency power", "generators", "freezers", "vivarium", "gensvc"],
        )  # fmt: skip
        yield self.ago(232)
        self.assess(
            bryn, risk, "inherent", 4, {"mission": 5, "safety": 4, "financial": 4},
            "The campus lost utility power for more than four hours twice in three years. "
            "Without working backup power, the freezers and the animal rooms are lost together.",
        )  # fmt: skip
        yield self.ago(225)
        tested = self.control("backup_power_tested", fac, is_key=True, rating=(
            "effective", "ineffective",
            "Both generators start. Under full load the older one tripped in both tests this "
            "year, and fuel on site lasts nineteen hours, not the seventy-two the plan assumes."))  # fmt: skip
        self.link(by, risk, tested, "likelihood", "primary")
        yield self.ago(204)
        self.residual(bryn, risk, "I agree with the suggestion: the control this rests on did not work when it was tested, so nothing is taken off.")  # fmt: skip
        yield self.ago(198)
        self.escalate(by, risk, self.units["ADMIN"], "Replacing a generator is a capital decision beyond Facilities, and a Critical risk is beyond my authority to accept.")  # fmt: skip
        yield self.ago(190)
        self.respond(bryn, risk, "reduce", "The older generator is to be replaced and the fuel store enlarged. Until then the exposure has to be accepted by someone who may.")  # fmt: skip
        plan = self.plan(
            bryn, risk, c.PLAN_OBJECTIVES["power_failure"], bryn, self.day(170), "moderate"
        )
        self.assess(
            bryn, risk, "target", 2, {"mission": 4, "safety": 3, "financial": 3}, c.TARGET_WHY
        )
        first = self.action(bryn, plan, "Contract a standby mobile generator, on site within four hours", by, self.day(-150))  # fmt: skip
        self.action(bryn, plan, "Replace the older generator", bryn, self.day(120))
        self.action(bryn, plan, "Enlarge the fuel store to seventy-two hours", by, self.day(170))
        yield self.ago(160)
        self.progress(
            by,
            first,
            status="done",
            completion_note="Ironhaven holds a unit for us; the call-out was tested in a drill.",
        )
        yield self.ago(152)
        self.accept(
            henrik, risk,
            "There is no quick fix: the replacement generator has a nine-month lead time. A "
            "standby unit is contracted, and I accept what remains until the work is done.",
            self.day(22),
            "The standby generator contract stays in force. Load tests are run monthly and "
            "reported to me. Fuel is topped up after every test.",
        )  # fmt: skip
        yield self.ago(108)
        self.residual(bryn, risk, "Reviewed at three months. The standby contract helps the consequence, not the cause; still Critical until the generator is replaced.")  # fmt: skip
        yield self.ago(15)
        self.residual(bryn, risk, "Reviewed. The new generator is due in the spring. The acceptance expires this month and will need to be given again.")  # fmt: skip

    def _story_agreement(self) -> Script:
        """An agreement's terms, entered as a framework of the institute's own."""
        lead = self.cast["risk2"]
        yield self.ago(402)
        with self.act(lead) as (session, who):
            made = frameworks.create(session, who, c.AGREEMENT)
            frameworks.paste(session, who, made, c.AGREEMENT_TERMS, dry_run=False)
        self.tally("frameworks of its own")
        yield self.ago(396)
        with self.act(lead) as (session, who):
            made = frameworks.by_key(session, frameworks.slug(c.AGREEMENT["title"]))
            frameworks.update_requirement(
                session, who, made, frameworks.find(session, made, "DUA-5.1"),
                {"guidance": "The trust's privacy office confirmed that discovery means the "
                 "moment anyone at the institute first suspects it, not when it is confirmed."},
            )  # fmt: skip
        yield self.ago(381)
        # The controls the institute already runs answer most of the agreement's terms.
        for key, unit, code, coverage, note in c.AGREEMENT_CONTROLS:
            control = self.control(key, self.units[unit])
            with self.act(lead) as (session, who):
                crosswalk.map_(
                    session, who, session.get(Control, control), framework=made.key, code=code,
                    coverage=coverage, note=note,
                )  # fmt: skip
            self.tally("requirements mapped by hand")

    def _story_agreements(self) -> Script:
        """The agreements themselves, with their dates, owners, and what they cover. What one
        covers binds the scopes that hold it to its terms."""
        lead = self.cast["risk2"]
        for spec in sorted(c.AGREEMENTS, key=lambda each: -each["made"]):
            yield self._on(spec["made"])
            owner = self.cast.get(spec["owner"]) or self.steward(self.units[spec["owner"]])
            with self.act(lead) as (session, who):
                values = {
                    "name": spec["name"], "kind": spec["kind"], "parties": spec["parties"],
                    "reference": spec.get("reference"), "summary": spec["summary"],
                    "org_unit_id": self.units[spec["unit"]],
                    "starts_on": self.day(spec["starts"]).isoformat(),
                    "ends_on": self.day(spec["ends"]).isoformat(),
                    "notice_days": spec.get("notice_days"), "renews": spec["renews"],
                    "framework": (
                        frameworks.slug(c.AGREEMENT["title"])
                        if spec.get("terms") == "own"
                        else spec.get("terms")
                    ),
                }  # fmt: skip
                agreement = records.create(session, who, AGREEMENT, values)
                records.set_owners(
                    session, who, AGREEMENT, agreement, [{"account_id": owner, "kind": "owner"}]
                )
                refs = [self.things[key][2] for key in spec["covers"]]
                refs += [self._scope_named(session, name).ref for name in spec.get("scopes", [])]
                if refs:
                    agreements.set_coverage(session, who, agreement, refs)
                self._agreement_refs[spec["key"]] = agreement.ref
            self.tally("agreements")
        for spec in c.AGREEMENTS:
            if spec.get("closed"):
                days, why = spec["closed"]
                yield self._on(days)
                owner = self.cast.get(spec["owner"]) or self.steward(self.units[spec["owner"]])
                with self.act(owner) as (session, who):
                    agreement = records.load(
                        session, who, AGREEMENT, self._agreement_refs[spec["key"]]
                    )
                    agreements.close(session, who, agreement, why)

    def _story_framework_update(self) -> Script:
        """The trial data platform was set up on SP 800-53 Rev. 4, loaded beside Rev. 5 for
        it. It has not moved yet. Crosswalks the publisher's mapping between SP 800-171 and
        SP 800-53 suggests are being worked through: some mapped, one set aside."""
        lead = self.cast["risk2"]
        spec = c.SCOPE_TRIALS
        yield self._on(spec["loaded"])
        with self.act(lead) as (session, who):
            framework_packs.load(
                session, framework_packs.builtin("nist-800-53-r4"), account_id=who.account_id
            )
        self.tally("frameworks loaded beside another version")
        yield self._on(spec["made"])
        made = self._scope(lead, spec)
        with self.act(lead) as (session, who):
            scope = session.get(Scope, made)
            for code, applicable, reason in spec["decisions"]:
                scopes.decide(
                    session, who, scope, framework=spec["framework"][0], code=code,
                    applicable=applicable, reason=reason,
                )  # fmt: skip
            for key, unit, code in spec["mapped"]:
                found = self.controls.get((key, self.units[unit]))
                if found is not None:
                    crosswalk.map_(
                        session, who, session.get(Control, found),
                        framework=spec["framework"][0], code=code, coverage="partial",
                    )  # fmt: skip
                    self.tally("requirements mapped by hand")
        yield self._on(spec["reviewed"])
        with self.act(lead) as (session, who):
            sp53 = frameworks.by_key(session, "nist-800-53")
            found = crosswalk.publisher_suggestions(session, who, sp53)
            for group in found["controls"][:4]:
                control = records.load(session, who, CONTROL, group["control"]["ref"])
                first, *rest = group["suggestions"]
                crosswalk.confirm_suggestion(session, who, sp53, control, first["code"])
                self.tally("suggested crosswalks confirmed")
                if rest:
                    crosswalk.set_aside(session, who, sp53, control, rest[-1]["code"])
                    self.tally("suggested crosswalks set aside")

    def _scope(self, by: int, spec: dict[str, Any]) -> int:
        """A scope with its boundary and the framework it is held to."""
        values = {"name": spec["name"], "org_unit_id": self.units[spec["unit"]],
                  "summary": spec["summary"], "boundary": spec["boundary"]}  # fmt: skip
        with self.act(by) as (session, who):
            scope = records.create(session, who, SCOPE, values)
            scopes.set_members(
                session, who, scope, [self.things[key][2] for key in spec["members"]],
                [self.units[code] for code in spec["units"]],
            )  # fmt: skip
            scopes.hold_to(session, who, scope, *spec["framework"])
            self.tally("scopes")
            return scope.id

    def _standing(self, control_id: int) -> str:
        """Where a control stands in its own scope, from what is known of how well it works."""
        with self.db.read() as session:
            state = controls.state_of(session, session.get(Control, control_id))
        return "partly" if state in ("partly", "ineffective") else "in_place"

    def _story_scopes(self) -> Script:
        """Central IT provides controls; the clinic and the data enclave inherit them."""
        lead = self.cast["risk2"]
        yield self.ago(296)
        provider = self._scope(lead, c.SCOPE_PROVIDER)
        offered: dict[str, int] = {}
        for key, unit, team, known, standing in c.SCOPE_PROVIDER["controls"]:
            # What is known of each is fixed, so that the scopes tell the story as written. A
            # storyline that has already said how well a control works is left to stand.
            there = self.controls.get((key, self.units[unit]))
            rating = None
            if there is None or there not in self.fixed_rating:
                rating = "never" if known == "never" else self._rating(known)
            control = self.control(key, self.units[unit], rating=rating)
            with self.act(lead) as (session, who):
                row = scopes.implement(
                    session, who, session.get(Scope, provider), session.get(Control, control),
                    status=standing or self._standing(control), responsibility=team,
                )  # fmt: skip
                offered[key] = row.id
        yield self.ago(288)
        with self.act(lead) as (session, who):
            scope = session.get(Scope, provider)
            records.update(
                session, who, SCOPE, scope, {"offers_controls": True}, version=scope.version
            )
        for days, spec in ((262, c.SCOPE_CLINIC), (231, c.SCOPE_ENCLAVE)):
            yield self.ago(days)
            made = self._scope(lead, spec)
            framework = spec["framework"][0]
            with self.act(lead) as (session, who):
                scope = session.get(Scope, made)
                for key in spec["inherited"]:
                    scopes.inherit(session, who, scope, offered[key], inheritance="inherited")
                for key, status, part in spec["shared"]:
                    scopes.inherit(
                        session, who, scope, offered[key], inheritance="shared", status=status,
                        statement=part,
                    )  # fmt: skip
            yield self.ago(days - 6)
            for key, status, team, how in spec["own"]:
                control = self.control(key, self.units[spec["unit"]])
                with self.act(lead) as (session, who):
                    scopes.implement(
                        session, who, session.get(Scope, made), session.get(Control, control),
                        status=status, responsibility=team, statement=how,
                    )  # fmt: skip
            for codes, reason in spec["excluded"]:
                with self.act(lead) as (session, who):
                    for code in codes:
                        scopes.decide(
                            session, who, session.get(Scope, made), framework=framework, code=code,
                            applicable=False, reason=reason,
                        )  # fmt: skip

    def _independent(self, control_id: int, *, besides: int | None = None) -> int:
        """Someone who may test or review this control: an assessor who does not own it."""
        with self.db.read() as session:
            for key in ("assess1", "assess2", "risk1", "risk2", "risk3"):
                person = self.cast[key]
                if person != besides and not access.owner_kinds(
                    session, CONTROL, control_id, person
                ):
                    return person
        raise AssertionError("nobody is left to test this control")

    def _result(
        self, test_id: int, by: int, found: tuple[str, str, str, str], *, collect: bool = True
    ) -> int:
        """Record what a test found, citing what is already held for the control or, unless
        told not to, something collected for the test."""
        design, operation, sample, note = found
        with self.db.read() as session:
            control_id = session.get(ControlTest, test_id).control_id
            held = [
                item.ref
                for item in session.scalars(
                    select(Evidence)
                    .join(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
                    .where(
                        EvidenceLink.subject_type == "control",
                        EvidenceLink.subject_id == control_id,
                    )
                    .order_by(Evidence.id.desc())
                )
                if evidence.state_of(item, self.today) != "stale"
            ][:1]
        if not held and collect:
            self._evidence(by, control_id, note)
            return self._result(test_id, by, found)
        with self.act(by) as (session, who):
            result = assessments.record(
                session, who, session.get(ControlTest, test_id), design=design,
                operation=operation, sample=sample, note=note, evidence_refs=held,
            )  # fmt: skip
            self.tally("test results")
            return result.id

    def _confirm(self, result_id: int, by: int, *, confirm: bool = True, note: str | None = None) -> None:  # fmt: skip
        with self.act(by) as (session, who):
            result, test, _ = assessments.find_result(session, who, result_id)
            assessments.review(session, who, result, confirm=confirm, note=note)
            if confirm:
                self.last_rated[test.control_id] = self.now

    def _story_assessment(self) -> Script:
        """The security team tests what central IT provides. Most results are counted, one is
        sent back and recorded again, one waits for a second person, and the two controls
        that are not yet in place are still to do. One control is found wanting that was
        believed to work, and shows as failing wherever it is inherited."""
        lead = self.cast["assess1"]
        yield self.ago(76)
        with self.act(lead) as (session, who):
            scope = session.scalars(
                select(Scope).where(Scope.name == c.SCOPE_PROVIDER["name"])
            ).one()
            made = assessments.create(
                session, who,
                {"name": f"{c.ASSESSMENT['name']} {self.end.year}", "scope": scope.ref,
                 "framework": c.SCOPE_PROVIDER["framework"][0], "period_start": self.today,
                 "period_end": self.day(24), "approach": c.ASSESSMENT["approach"]},
            )  # fmt: skip
            planned = [
                (test["id"], session.get(ControlTest, test["id"]).control_id)
                for test in assessments.tests_of(session, who, made)
            ]
            self.tally("assessments")
        finding_key, *finding = c.ASSESSMENT["finding"]
        wanting = self.controls.get((finding_key, self.units["IT"]))
        open_ = [each for each in planned if each[1] != wanting]
        # A control that is not yet in place waits to be tested until it is.
        unready = {
            self.controls[(key, self.units[unit])]
            for key, unit, _, _, standing in c.SCOPE_PROVIDER["controls"]
            if standing
        }
        todo = [each for each in open_ if each[1] in unready][-2:] or open_[-2:]
        # The result that waits at the end is on a control the lead may review.
        mine = [e for e in open_ if e not in todo and self._independent(e[1]) == lead]
        waiting = mine[len(mine) // 2]
        done = [each for each in planned if each != waiting and each not in todo]
        testers = {}
        for index, (test_id, control_id) in enumerate(planned):
            # The two assessors take turns, and each confirms what the other found. The lead
            # keeps the last of the tests still to do.
            each = (test_id, control_id)
            turn = each == todo[-1] or (index % 2 == 1 and each not in (waiting, todo[0]))
            tester = lead if turn and self._independent(control_id) == lead else None
            tester = tester or self._independent(control_id, besides=lead)
            testers[test_id] = tester
            with self.act(lead) as (session, who):
                assessments.update_test(
                    session, who, session.get(ControlTest, test_id),
                    {"assigned_to": tester, "method": self.rng.choice(["examine", "examine", "interview", "test"])},
                )  # fmt: skip
        for index, (test_id, control_id) in enumerate(done):
            yield self.ago(74 - index * 2)
            tester = testers[test_id]
            if control_id == wanting:
                found = tuple(finding)
            else:
                with self.db.read() as session:
                    state = controls.state_of(session, session.get(Control, control_id))
                outcome = state if state in ("partly", "ineffective") else "effective"
                sample, note = self.rng.choice(c.TESTS[outcome])
                design, operation = {
                    "effective": ("effective", "effective"), "partly": ("effective", "partly"),
                    "ineffective": ("partly", "ineffective"),
                }[outcome]  # fmt: skip
                found = (design, operation, sample, note)
            # Now and then a tester cites nothing, and the result counts for less: the control
            # is known to work, and nothing on record shows it.
            result = self._result(test_id, tester, found, collect=index % 9 != 4)
            reviewer = self._independent(control_id, besides=tester)
            yield self.later(0.2, 0.8)
            if index == 1:
                # Sent back once, recorded again with what was asked for, then confirmed.
                self._confirm(result, reviewer, confirm=False, note=c.ASSESSMENT["returned"])
                yield self.later(0.2, 0.8)
                design, operation, sample, note = found
                again = (design, operation, f"{sample} Quarter three; ten instances.", note)
                result = self._result(test_id, tester, again)
                yield self.later(0.2, 0.8)
            self._confirm(result, reviewer)
        yield self.ago(2)
        test_id, control_id = waiting
        sample, note = c.TESTS["effective"][0]
        self._result(test_id, testers[test_id], ("effective", "effective", sample, note))

    # --- Indicators -----------------------------------------------------------------------

    def _story_indicators(self) -> Script:
        """Numbers the institute already watches, read month by month. One has crossed its
        limit this month, some are past their warning level, one is getting better, one has
        not been read for two quarters, and one has never been read."""
        days = {"monthly": 30.4, "quarterly": 91.3}
        # Everything that happens, in the order it happens: each indicator is set up, then
        # read once a period up to now.
        steps: list[tuple[float, int, float | None]] = []
        for index, spec in enumerate(c.INDICATORS):
            values = spec[9] or []
            # The freezer alarms have not been counted for two quarters: the last is long past.
            late = 200 if spec[1] == "BIO" else 4
            period = days[spec[6]]
            steps.append((late + period * len(values) + 26 - index if values else 20, index, None))
            steps += [
                (late + period * (len(values) - 1 - at), index, value)
                for at, value in enumerate(values)
            ]
        made: dict[int, tuple[int, int]] = {}
        for ago, index, value in sorted(steps, key=lambda step: (-step[0], step[1])):
            yield self._on(ago, hour=9)
            if value is not None:
                row_id, keeper = made[index]
                with self.act(keeper) as (session, who):
                    indicators.record_reading(
                        session, who, session.get(Indicator, row_id), value=value
                    )
                self.tally("indicator readings")
                continue
            name, unit, measure, direction, warn, limit, frequency, source, warns_of, _ = (
                c.INDICATORS[index]
            )
            keeper = self.steward(self.units[unit])
            with self.act(keeper) as (session, who):
                row = records.create(
                    session, who, INDICATOR,
                    {"name": name, "org_unit_id": self.units[unit], "measure": measure,
                     "direction": direction, "warn_at": warn, "breach_at": limit,
                     "frequency": frequency, "source": source},
                )  # fmt: skip
                risks = list(
                    session.scalars(
                        select(Risk.ref)
                        .where(Risk.library_key.in_(warns_of), Risk.status == "open")
                        .order_by(Risk.id)
                        .limit(3)
                    )
                )
                indicators.set_risks(session, self.principal(self.manager()), row, risks)
                self.tally("indicators")
                made[index] = (row.id, keeper)

    # --- Policy documents -------------------------------------------------------------------

    def _story_documents(self) -> Script:
        """The information security policy and the documents beneath it, written, approved,
        published, and revised over two years. Now: a new version of the policy waits for
        the president's approval, a guideline has been sent back to its author, and the
        access control standard is overdue for review."""
        steps: list[tuple[float, int, int, Callable[[Session, Principal], None]]] = []
        made: dict[str, int] = {}
        order = 0
        # Who reads what, and when, is chosen apart from the dice the other stories use.
        readers = random.Random(self.seed + 4241)
        everyone = sorted(self.names)

        def who_is(key: str) -> int:
            return self.steward(self.units[key]) if key in self.units else self.cast[key]

        def step(ago: float, actor: int, act: Callable[[Session, Principal], None]) -> None:
            nonlocal order
            order += 1
            steps.append((ago, order, actor, act))

        def doc(session: Session, key: str) -> PolicyDocument:
            return session.get(PolicyDocument, made[key])

        def content(spec: dict[str, Any], text: str | None) -> dict[str, Any]:
            if spec.get("link"):
                return {"form": "link", "url": spec["link"]}
            return {"form": "text", "body": text}

        for spec in c.DOCUMENTS:
            author = who_is(spec["by"])
            approvers = [self.cast[key] for key in spec["approvers"]]
            texts: list[str | None] = []
            text: str | None = None
            for _ago, body, _note in spec["versions"]:
                if isinstance(body, list):
                    for old, new in body:
                        text = (text or "").replace(old, new)
                else:
                    text = body
                texts.append(text)
            first = spec["versions"][0][0] if spec["versions"] else spec["draft"]["since"] + 4

            def create(
                session: Session,
                by: Principal,
                spec: dict[str, Any] = spec,
                text: str | None = texts[0] if texts else spec.get("draft", {}).get("body"),
            ) -> None:
                values = {
                    "name": spec["name"],
                    "kind": spec["kind"],
                    "summary": spec["summary"],
                    "org_unit_id": self.units[spec["unit"]],
                    "parent": self._doc_refs.get(spec.get("parent", "")),
                    "review_months": spec.get("review_months"),
                    "acknowledge": "acknowledge" in spec,
                    **content(spec, text),
                }
                document = documents.create(session, by, values)
                made[spec["key"]] = document.id
                self._doc_refs[spec["key"]] = document.ref
                if spec.get("audience"):
                    chosen = spec["audience"]
                    library.set_audience(
                        session, by, document, False,
                        [self.units[code] for code in chosen["units"]], chosen["roles"],
                    )  # fmt: skip
                if spec.get("file"):
                    if self.files is not None:
                        documents.attach_file(
                            session,
                            by,
                            document,
                            self.files,
                            _pdf(spec["file"]),
                            f"{spec['name']}.pdf",
                        )
                    else:
                        documents.save_draft(
                            session,
                            by,
                            document,
                            {
                                "form": "link",
                                "url": f"https://intranet.{c.DOMAIN}/policies/{spec['key']}.pdf",
                            },
                        )
                self.tally("documents")

            step(first + 21, author, create)
            for index, (ago, _body, note) in enumerate(spec["versions"]):
                if index:

                    def redraft(
                        session: Session,
                        by: Principal,
                        key: str = spec["key"],
                        text: str | None = texts[index],
                        note: str | None = note,
                        spec: dict[str, Any] = spec,
                    ) -> None:
                        document = doc(session, key)
                        documents.start_draft(session, by, document)
                        documents.save_draft(
                            session, by, document, {**content(spec, text), "change_note": note}
                        )

                    step(ago + 14, author, redraft)

                def send(
                    session: Session,
                    by: Principal,
                    key: str = spec["key"],
                    approvers: list[int] = approvers,
                ) -> None:
                    documents.submit(session, by, doc(session, key), approvers)

                step(ago + 9, author, send)
                for place, approver in enumerate(approvers):

                    def approve(session: Session, by: Principal, key: str = spec["key"]) -> None:
                        documents.decide(session, by, doc(session, key), "approved", None)

                    step(ago + 6 - place, approver, approve)

                def go(session: Session, by: Principal, key: str = spec["key"]) -> None:
                    documents.publish(session, by, doc(session, key))
                    self.tally("document versions published")

                step(ago, author, go)
                asking = spec.get("acknowledge")
                if asking:
                    following = (
                        spec["versions"][index + 1][0] if index + 1 < len(spec["versions"]) else 0
                    )
                    latest = index + 1 == len(spec["versions"])
                    for person in everyone:
                        if readers.random() >= asking["shares"][index]:
                            continue
                        if latest and person == self.cast["member"]:
                            continue  # the guides show them with it still to do
                        # Most read it within a fortnight of being told; a few take longer.
                        late = min(1 + readers.expovariate(1 / 9), ago - following - 1)
                        if late < 1:
                            continue

                        def read(session: Session, by: Principal, key: str = spec["key"]) -> None:
                            document = doc(session, key)
                            if library.applies(session, document, by):
                                library.acknowledge(session, by, document)
                                self.tally("acknowledgments")

                        step(ago - late, person, read)
                    if latest and asking.get("campaign"):
                        chase = asking["campaign"]

                        def launch(
                            session: Session,
                            by: Principal,
                            key: str = spec["key"],
                            chase: dict[str, Any] = chase,
                        ) -> None:
                            campaigns.launch(
                                session,
                                by,
                                {
                                    "kind": "acknowledgment",
                                    "name": chase["name"],
                                    "document": doc(session, key).ref,
                                    "due_on": self.day(chase["due"]).isoformat(),
                                },
                            )
                            self.tally("campaigns")

                        step(chase["ago"], self.cast[chase["by"]], launch)
            for ago, said in spec.get("reviews", []):

                def keep(
                    session: Session, by: Principal, key: str = spec["key"], said: str = said
                ) -> None:
                    documents.review(session, by, doc(session, key), said)

                step(ago, author, keep)
            working = spec.get("draft")
            if working is None:
                continue
            since = working["since"]
            if spec["versions"]:

                def begin(
                    session: Session,
                    by: Principal,
                    key: str = spec["key"],
                    working: dict[str, Any] = working,
                    text: str | None = texts[-1],
                ) -> None:
                    document = doc(session, key)
                    documents.start_draft(session, by, document)
                    for old, new in working["edits"]:
                        text = (text or "").replace(old, new)
                    documents.save_draft(
                        session, by, document, {"body": text, "change_note": working["note"]}
                    )

                step(since + 6, author, begin)
            asked = [self.cast[key] for key in working["approvers"]]

            def ask(
                session: Session, by: Principal, key: str = spec["key"], asked: list[int] = asked
            ) -> None:
                documents.submit(session, by, doc(session, key), asked)

            step(since, author, ask)
            for place, key in enumerate(working.get("approved", [])):

                def agree(session: Session, by: Principal, doc_key: str = spec["key"]) -> None:
                    documents.decide(session, by, doc(session, doc_key), "approved", "Agreed.")

                step(since - 3 - place, self.cast[key], agree)
            if working.get("returned"):
                back, why = working["returned"]

                def refuse(
                    session: Session, by: Principal, key: str = spec["key"], why: str = why
                ) -> None:
                    documents.decide(session, by, doc(session, key), "returned", why)

                step(since - 4, self.cast[back], refuse)

        # Later, once the central controls are on record, each document's author says what it
        # governs; and departures from two of them are asked for.
        for key, (directed, answered) in c.GOVERNS.items():
            spec = next(each for each in c.DOCUMENTS if each["key"] == key)

            def tie(
                session: Session,
                by: Principal,
                key: str = key,
                directed: list[tuple[str, str]] = directed,
                answered: list[tuple[str, str]] = answered,
            ) -> None:
                document = doc(session, key)
                for control_key, unit in directed:
                    found = self.controls.get((control_key, self.units[unit]))
                    if found is not None:
                        ref = session.get(Control, found).ref
                        governs.direct(session, by, document, ref)
                        self.tally("controls a document directs")
                for framework, code in answered:
                    governs.answer(session, by, document, framework=framework, code=code)
                    self.tally("requirements a document answers")

            step(250, who_is(spec["by"]), tie)
        for asked in c.DOCUMENT_EXCEPTIONS:
            made_ref: dict[str, str] = {}

            def ask(
                session: Session,
                by: Principal,
                asked: dict[str, Any] = asked,
                made_ref: dict[str, str] = made_ref,
            ) -> None:
                item = exceptions.request(
                    session, by,
                    {"document": doc(session, asked["document"]).ref, "name": asked["name"],
                     "justification": asked["justification"],
                     "compensating": asked["compensating"],
                     "expires_on": self.day(asked["until"]).isoformat()},
                )  # fmt: skip
                made_ref["ref"] = item.ref
                self.tally("exceptions to documents")

            step(asked["ago"], self.steward(self.units[asked["unit"]]), ask)
            if asked.get("decided"):
                decided = asked["decided"]

                def agree(
                    session: Session,
                    by: Principal,
                    decided: dict[str, Any] = decided,
                    made_ref: dict[str, str] = made_ref,
                ) -> None:
                    item = records.load(session, by, exceptions.EXCEPTION, made_ref["ref"])
                    exceptions.decide(session, by, item, approve=True, note=decided["note"])

                step(decided["ago"], self.cast[decided["by"]], agree)

        for ago, _order, actor, act in sorted(steps, key=lambda each: (-each[0], each[1])):
            yield self._on(ago, hour=10)
            if actor in self.departed:
                continue  # they left before they got to it
            with self.act(actor) as (session, who):
                act(session, who)

    # --- Campaigns ------------------------------------------------------------------------

    def _on(self, days: float, hour: int = 11) -> datetime:
        """A working moment that many days before the build, chosen without the dice, so that
        what is added here leaves every other story as it was."""
        moment = (self.end - timedelta(days=days)).replace(hour=hour, minute=20)
        while moment.weekday() >= 5:
            moment -= timedelta(days=1)
        return moment

    def _answer(self, campaign_id: int, item_id: int, answers: dict[str, Any]) -> None:
        with self.db.read() as session:
            asked = session.get(CampaignItem, item_id).account_id
        if asked is None or asked in self.departed:
            return
        with self.act(asked) as (session, who):
            campaigns.answer(
                session, who, session.get(CampaignItem, item_id),
                session.get(Campaign, campaign_id), answers,
            )  # fmt: skip
        self.tally("campaign answers")

    def _story_campaigns(self) -> Script:
        """Owners asked to look again and to attest. One campaign is closed, one is most of the
        way through with two owners saying their control is not as described, one has only
        just asked for evidence."""
        lead, security = self.cast["risk2"], self.cast["assess1"]
        spec = c.CAMPAIGNS
        yield self._on(128)
        with self.act(lead) as (session, who):
            made = campaigns.launch(
                session, who,
                {"kind": "self_assessment", "name": f"{spec['risks']['name']} {self.end.year}",
                 "summary": spec["risks"]["summary"], "org_unit_id": self.units["CORES"],
                 "due_on": self.day(-100).isoformat()},
            )  # fmt: skip
            risks_id = made.id
            asked = [item.id for item in session.scalars(
                select(CampaignItem).where(CampaignItem.campaign_id == made.id)
                .order_by(CampaignItem.id)
            )]  # fmt: skip
        self.tally("campaigns")
        stands = {"relevant": True, "changed": ["nothing"], "controls_working": "yes",
                  "rating_right": True, "plan": "none"}  # fmt: skip
        for index, item_id in enumerate(asked):
            if index % 9 == 8:
                continue  # one in nine never answered
            if index % 4 == 0:
                yield self._on(126 - index % 20)
            said = dict(stands)
            if index % 7 == 3:
                said.update(changed=["controls"], what_changed="A control was replaced this year.",
                            controls_working="partly")  # fmt: skip
            if index % 11 == 5:
                said.update(rating_right=False,
                            rating_note="Lower. The backlog that drove it has been cleared.")  # fmt: skip
            self._answer(risks_id, item_id, said)
        yield self._on(96)
        with self.act(lead) as (session, who):
            campaigns.end(session, who, session.get(Campaign, risks_id))

        yield self._on(21)
        with self.db.read() as session:
            scope_ref = self._scope_named(session, c.SCOPE_PROVIDER["name"]).ref
            clinic_ref = self._scope_named(session, c.SCOPE_CLINIC["name"]).ref
        with self.act(security) as (session, who):
            made = campaigns.launch(
                session, who,
                {"kind": "attestation", "name": f"{spec['attest']['name']} {self.end.year}",
                 "summary": spec["attest"]["summary"], "scope": scope_ref,
                 "due_on": self.day(6).isoformat()},
            )  # fmt: skip
            attest_id = made.id
            asked_of = {
                item.subject_id: item.id
                for item in session.scalars(
                    select(CampaignItem).where(CampaignItem.campaign_id == made.id)
                )
            }
        self.tally("campaigns")
        keys = {control_id: key for (key, _unit), control_id in self.controls.items()}
        fine = {"operates": "yes", "statement_right": True, "evidence": "yes", "owner_right": True}
        answering = sorted(asked_of.items())[: -spec["attest"]["waiting"]]
        for index, (control_id, item_id) in enumerate(answering):
            if index % 5 == 0:
                yield self._on(19 - index // 5 * 2)
            key = keys.get(control_id)
            said = dict(fine)
            if key in spec["attest"]["said"]:
                operates, difference = spec["attest"]["said"][key]
                said.update(operates=operates, difference=difference)
            elif key == spec["attest"]["not_mine"][0]:
                said.update(owner_right=False, owner_instead=spec["attest"]["not_mine"][1])
            elif index % 6 == 4:
                said.update(evidence="out_of_date", evidence_plan="Before the assessment closes.")
            self._answer(attest_id, item_id, said)

        yield self._on(3)
        with self.act(security) as (session, who):
            campaigns.launch(
                session, who,
                {"kind": "evidence", "name": spec["evidence"]["name"],
                 "wanted": spec["evidence"]["wanted"], "scope": clinic_ref,
                 "due_on": self.day(25).isoformat()},
            )  # fmt: skip
        self.tally("campaigns")

    # --- Issues and exceptions ------------------------------------------------------------

    def _story_issues_later(self) -> Script:
        """Issues begin once the scopes are there for them to be about."""
        yield self.ago(232)
        self.schedule(self._story_issues())

    def _story_exceptions_later(self) -> Script:
        yield self.ago(205)
        self.schedule(self._story_exceptions())

    def _raise(self, by: int, key: str, owner: int, **more: Any) -> int:
        spec = c.ISSUES[key]
        values = {
            "name": spec.get("name"), "summary": spec["summary"], "severity": spec["severity"],
            "org_unit_id": self.units[spec["unit"]], "source_kind": spec["source"],
            "owner_id": owner, **more,
        }  # fmt: skip
        with self.act(by) as (session, who):
            issue = issues.create(session, who, values)
            self.tally("issues")
            return issue.id

    def _issue_actions(self, by: int, issue_id: int, wanted: list[tuple[str, int, bool]], owners: list[int]) -> list[tuple[str, int, bool]]:  # fmt: skip
        made = []
        for index, (title, due, done) in enumerate(wanted):
            with self.act(by) as (session, who):
                action = issues.add_action(
                    session, who, session.get(Issue, issue_id), title=title,
                    owner_id=owners[index % len(owners)], due_on=self.day(due),
                )  # fmt: skip
                made.append((action.ref, action.owner_id, done))
                self.tally("actions")
        return made

    def _finish(self, actions: list[tuple[str, int, bool]]) -> None:
        for ref, owner, done in actions:
            if done:
                with self.act(owner) as (session, who):
                    treatment.update_action(
                        session, who, treatment.find_action(session, ref), {"status": "done"}
                    )

    def _propose(self, by: int, issue_id: int, key: str) -> None:
        spec = c.ISSUES[key]
        cited = []
        if spec.get("proof"):
            name, note = spec["proof"]
            with self.act(by) as (session, who):
                item = records.create(
                    session, who, EVIDENCE,
                    {"name": name, "kind": "note", "note": note,
                     "org_unit_id": self.units[spec["unit"]], "collected_on": self.today},
                )  # fmt: skip
                cited.append(item.ref)
                self.tally("evidence")
        with self.act(by) as (session, who):
            issues.propose(
                session, who, session.get(Issue, issue_id), note=spec["done"],
                root_cause=spec["cause"], evidence_refs=cited,
            )  # fmt: skip

    def _issue_story(self, key: str, raised: float, by: int, owner: int, **more: Any) -> Script:
        """One issue from the day it is raised to wherever it has got to."""
        spec = c.ISSUES[key]
        yield self.ago(raised)
        issue = self._raise(by, key, owner, **more)
        if spec["actions"]:
            yield self.later(0.3, 1) if spec.get("urgent") else self.later(2, 6)
            staff = self.staff[self.units[spec["unit"]]]
            # Whoever noticed it helps to put it right, if they work there.
            helper = (
                by
                if by != owner and by in staff
                else next((person for person in staff if person != owner), owner)
            )
            actions = self._issue_actions(owner, issue, spec["actions"], [helper, owner])
            yield self.later(2, 4) if spec.get("urgent") else self.later(12, 25)
            self._finish(actions)
        if spec.get("withdrawn"):
            yield self.later(1, 3)
            with self.act(self.cast["assess1"]) as (session, who):
                issues.cancel(session, who, session.get(Issue, issue), reason=spec["withdrawn"])
            return
        if not spec.get("done"):
            return
        yield (
            self.later(8, 20) if key == "visitors" else self.ago(20 if spec.get("returned") else 3)
        )
        self._propose(owner, issue, key)
        if spec.get("returned"):
            yield self.later(3, 4)
            with self.act(self.cast["assess2"]) as (session, who):
                issues.validate(
                    session, who, session.get(Issue, issue), confirm=False, note=spec["returned"]
                )
            yield self.later(2, 3)
            days, why = spec["moved"]
            with self.act(owner) as (session, who):
                issues.reschedule(
                    session, who, session.get(Issue, issue), due_on=self.day(days), reason=why
                )
        elif key == "visitors":
            yield self.later(4, 9)
            with self.act(self.cast["assess2"]) as (session, who):
                issues.validate(session, who, session.get(Issue, issue), confirm=True, note=None)

    def _scope_named(self, session: Session, name: str) -> Scope:
        return session.scalars(select(Scope).where(Scope.name == name)).one()

    def _first_gap(self, name: str, framework: str, prefix: str = "") -> str:
        """A requirement that nothing in a scope answers: the first under a prefix, or at all."""
        with self.db.read() as session:
            found = scopes.statement(
                session, Principal.for_command(), self._scope_named(session, name), framework,
                state="gap",
            )  # fmt: skip
        codes = [row["code"] for row in found["requirements"]]
        return next((code for code in codes if code.startswith(prefix)), codes[0])

    def _story_issues(self) -> Script:
        """Issues at every stage: raised by someone who noticed, found by audit, sent back,
        closed, withdrawn, and a gap nobody has taken up; and what is being done about the
        control the assessment found wanting."""
        member, chidi = self.cast["member"], self.cast["bio_mgr"]
        bio = self.units["BIO"]
        cold = next((cid for (_, unit), cid in sorted(self.controls.items()) if unit == bio), None)
        about = []
        if cold is not None:
            with self.db.read() as session:
                about = [session.get(Control, cold).ref]
        self.schedule(self._issue_story("alarm", 75, member, chidi, subjects=about))
        self.schedule(
            self._issue_story("cabinets", 100, self.cast["risk2"], self.cast["pharm_mgr"])
        )
        fac, sp, it = (self.units[code] for code in ("FAC", "SP", "IT"))
        walls = self.controls.get(("network_segmentation", it))
        with self.db.read() as session:
            about = [session.get(Control, walls).ref] if walls else []
        self.schedule(
            self._issue_story("pentest", 13, self.cast["assess1"], self.steward(it), subjects=about)
        )
        self.schedule(self._issue_story("visitors", 230, self.pick(fac), self.steward(fac)))
        self.schedule(self._issue_story("letters", 170, self.cast["risk1"], self.steward(sp)))
        self.schedule(self._issue_story("duplicate", 6, self.pick(it), self.steward(it)))
        yield self.ago(200)
        clinic = c.SCOPE_CLINIC
        code = self._first_gap(clinic["name"], clinic["framework"][0], "164.310")
        with self.db.read() as session:
            scope_ref = self._scope_named(session, clinic["name"]).ref
        self._raise(
            self.cast["risk2"], "gap", self.steward(self.units["CLIN"]),
            name=f"{code}: nothing answers it in {clinic['name']}", subjects=[scope_ref],
            requirements=[{"framework": clinic["framework"][0], "code": code}],
        )  # fmt: skip
        # The assessment's own finding: its owners have a plan, and have done half of it.
        yield self.ago(4)
        finding = self.controls.get((c.ASSESSMENT["finding"][0], it))
        with self.db.read() as session:
            control = session.get(Control, finding) if finding else None
            found = issues.open_for_test(session, control) if control is not None else None
            issue = found.id if found is not None else None
        if issue is not None:
            steward = self.steward(it)
            actions = self._issue_actions(steward, issue, c.FINDING_ACTIONS, [steward])
            yield self.later(1, 2)
            self._finish(actions)

    def _ask(self, by: int, key: str, values: dict[str, Any]) -> int:
        spec = c.EXCEPTIONS[key]
        with self.act(by) as (session, who):
            item = exceptions.request(
                session, who,
                {"justification": spec["why"], "compensating": spec["instead"], **values},
            )  # fmt: skip
            self.tally("exceptions")
            return item.id

    def _decide(self, by: int, exception_id: int, key: str) -> None:
        spec = c.EXCEPTIONS[key]
        with self.act(by) as (session, who):
            exceptions.decide(
                session, who, session.get(ExceptionRequest, exception_id),
                approve="refused" not in spec, note=spec.get("refused") or spec.get("note"),
            )  # fmt: skip

    def _story_exceptions(self) -> Script:
        """Exceptions at every stage: one that has ended, one refused, one in force, one about
        to end, and one waiting to be decided."""
        clinic, enclave = c.SCOPE_CLINIC, c.SCOPE_ENCLAVE
        clin, rc, it = (self.units[code] for code in ("CLIN", "RC", "IT"))
        with self.db.read() as session:
            refs = {
                name: self._scope_named(session, name).ref
                for name in (clinic["name"], enclave["name"])
            }

        def control(key: str, unit: int) -> str:
            with self.db.read() as session:
                return session.get(Control, self.controls[(key, unit)]).ref

        yield self.ago(200)
        logs = self._ask(
            self.steward(rc), "logs",
            {"scope": refs[enclave["name"]], "control": control("logging_monitoring", self.units["SEC"]),
             "expires_on": self.day(-35)},
        )  # fmt: skip
        yield self.later(3, 5)
        self._decide(self.cast["rc_dir"], logs, "logs")
        yield self.ago(90)
        patching = self._ask(
            self.steward(it),
            "patching",
            {"control": control("patching", it), "expires_on": self.day(120)},
        )
        yield self.later(3, 5)
        self._decide(self.cast["cio"], patching, "patching")
        yield self.ago(60)
        code = self._first_gap(enclave["name"], enclave["framework"][0], "03.10")
        rooms = self._ask(
            self.steward(rc), "rooms",
            {"scope": refs[enclave["name"]], "expires_on": self.day(150),
             "requirement": {"framework": enclave["framework"][0], "code": code}},
        )  # fmt: skip
        yield self.later(2, 4)
        self._decide(self.cast["rc_dir"], rooms, "rooms")
        yield self.ago(6)
        leavers = self._ask(
            self.steward(clin), "leavers",
            {"scope": refs[clinic["name"]], "expires_on": self.day(21),
             "control": control("access_removed_on_leaving", it)},
        )  # fmt: skip
        yield self.later(1, 2)
        self._decide(self.cast["clinic_lead"], leavers, "leavers")
        yield self.ago(2)
        self._ask(
            self.steward(clin), "training",
            {"scope": refs[clinic["name"]], "expires_on": self.day(170),
             "control": control("security_training", self.units["SEC"])},
        )  # fmt: skip

    def _story_escalated(self) -> Script:
        """A lab's privacy risk raised to its department, with the reason."""
        lab = self.labs["PS"][0]
        by, head, department = self.steward(lab), self.heads[lab], self.units["PS"]
        yield self.ago(214)
        risk = self.raise_risk(
            by, lab, "participant_privacy", owner=head,
            name="Identifiable survey responses held on lab laptops",
            subjects=["Survey data collection", "survey", "surveyco"],
        )  # fmt: skip
        yield self.ago(209)
        self.assess(
            head, risk, "inherent", 4, {"trust": 4, "legal": 4},
            "Exports from the survey platform carry names and addresses, and are worked on "
            "where the analysis happens: on laptops that travel.",
        )  # fmt: skip
        yield self.ago(200)
        encrypted = self.control("encryption_at_rest", self.units["IT"], rating=(
            "effective", "partly",
            "Every managed laptop is encrypted. Personally owned machines used for research "
            "are not checked."))  # fmt: skip
        self.link(by, risk, encrypted, "impact", "primary")
        self.link(
            by,
            risk,
            self.control("data_classified", self.units["CMPL"]),
            "likelihood",
            "supporting",
        )
        yield self.ago(176)
        self.residual(head, risk, "I agree with the suggestion. Encryption covers the laptops we manage, and students use their own.")  # fmt: skip
        yield self.ago(168)
        self.escalate(
            by, risk, department,
            "At least four labs in the department work this way. It needs one answer, and "
            "managed storage that a single lab cannot fund.",
        )  # fmt: skip

    def _story_departure(self) -> Script:
        """A principal investigator leaves. What they alone answered for passes to the
        lab's steward, who keeps one risk for good; the rest still waits for a name."""
        lab = self.labs["CB"][0]
        head, by = self.heads[lab], self.steward(lab)
        yield self.ago(400)
        copy = self.control(
            "nightly_copy", lab, name="Instrument data copied to managed storage each night",
            statement="Data from the lab's instruments is copied to research storage every "
            "night, and the copy is checked each Monday.", frequency="daily", nature="automated",
            owner=head,
        )  # fmt: skip
        for risk in self.unit_risks[lab][:1]:
            self.link(by, risk, copy, "impact", "supporting")
        yield self.ago(47)
        with self.act(self.cast["admin"]) as (session, who):
            accounts.set_status(session, who, accounts.get(session, head), "disabled")
        self.departed.add(head)
        self.tally("accounts disabled")
        yield self.ago(31)
        owned = [r for r in self.unit_risks[lab] if self.risks[r]["owner"] == head]
        for risk in owned[:1]:
            with self.act(by) as (session, who):
                handover.pass_on(
                    session, who, accounts.get(session, head), accounts.get(session, by),
                    only=[("risk", risk)],
                )  # fmt: skip
            self.risks[risk]["owner"] = by

    def _story_analyses(self) -> Script:
        """Two risk analyses by the assurance team: one of the clinic's systems, finished and
        reported, and one of the data enclave, part of the way through."""
        lead = self.cast["assess1"]
        for spec in c.ANALYSES:
            yield self._on(spec["began"])
            with self.act(lead) as (session, who):
                scope = session.scalars(select(Scope).where(Scope.name == spec["scope"])).one()
                found = analysis.start(
                    session, who,
                    {"name": spec["name"], "summary": spec["summary"], "scope": scope.ref,
                     "categories": spec["categories"]},
                )  # fmt: skip
                made = found.id
                refs = list(dict.fromkeys(
                    session.scalars(
                        select(RiskAnalysisItem.subject_ref)
                        .where(RiskAnalysisItem.analysis_id == made)
                        .order_by(RiskAnalysisItem.id)
                    )
                ))  # fmt: skip
            self.tally("risk analyses")
            walked = refs[: max(1, round(len(refs) * spec["walked"]))]
            raised = 0
            for at, ref in enumerate(walked):
                yield self._on(spec["began"] - 1 - at * spec["pace"], hour=14)
                with self.act(lead) as (session, who):
                    found = session.get(RiskAnalysis, made)
                    page = analysis.asset(session, who, found, ref)
                    for index, item in enumerate(page["items"]):
                        row = session.get(RiskAnalysisItem, item["id"])
                        if item["suggested"]:
                            again = (at + index) % 5 == 0
                            values = {"outcome": "covered", "risk": item["suggested"][0]["ref"],
                                      "look_again": again,
                                      "note": c.ANALYSIS_NOTES["again" if again else "covered"]}  # fmt: skip
                        elif (at * 3 + index) % 11 == 4 and raised < spec["raises"]:
                            values = {"outcome": "raised", "note": c.ANALYSIS_NOTES["raised"]}
                            raised += 1
                            self.tally("risks raised by an analysis")
                        else:
                            notes = c.ANALYSIS_NOTES["not_applicable"]
                            values = {"outcome": "not_applicable",
                                      "note": notes[(at + index) % len(notes)]}  # fmt: skip
                        analysis.consider(session, who, found, row, values)
            if spec.get("conclusion"):
                yield self._on(spec["began"] - 2 - len(walked) * spec["pace"], hour=16)
                with self.act(lead) as (session, who):
                    analysis.close(
                        session, who, session.get(RiskAnalysis, made), spec["conclusion"]
                    )

    def _story_views(self) -> Script:
        """Lists people keep coming back to, saved and shared."""
        yield self.ago(60)
        for key, name, path, query in c.VIEWS:
            with self.act(self.cast[key]) as (session, who):
                views.create(
                    session, who, {"name": name, "path": path, "query": query, "shared": True}
                )
            self.tally("saved views")

    # --- Everything -----------------------------------------------------------------------

    def _plan_risks(self) -> list[tuple[int, str, datetime, int | None]]:
        planned: list[tuple[int, str, datetime, int | None]] = []
        span = MONTHS * 30.4 - 15
        for code, keys in c.UNIT_RISKS.items():
            for key in keys:
                planned.append((self.units[code], key, self._early(span), None))
        departing = self.labs["CB"][0]
        for labs in self.labs.values():
            for lab in labs:
                for key in self.rng.sample(c.LAB_RISKS, 3):
                    if lab == departing:
                        # Raised early and owned by the lab's head, who will later leave.
                        planned.append((lab, key, self._early(150), self.heads[lab]))
                    else:
                        planned.append((lab, key, self._early(span), None))
        for _, key, _, _ in planned:
            self.usage[key] = self.usage.get(key, 0) + 1
        return planned

    def _early(self, span: float) -> datetime:
        """A moment in the first ``span`` days after the inventory is in, weighted early."""
        days = (
            125 + self.rng.random() ** 1.5 * (span - 125)
            if span > 200
            else 125 + self.rng.random() * span
        )
        return self._workday(self.start + timedelta(days=days))

    def build(self) -> Summary:
        self.found()
        for code, *_ in c.UNITS:
            self.schedule(self._unit_inventory(code))
        for labs in self.labs.values():
            for lab in labs:
                self.schedule(self._lab_inventory(lab))
        self.schedule(self._links())
        self.schedule(self._information())
        for unit, key, start, owner in self._plan_risks():
            self.schedule(self._risk(unit, key, start, owner))
        for story in (
            self._story_specimens, self._story_ransomware, self._story_workstation,
            self._story_authority, self._story_costs, self._story_supplier,
            self._story_unassessed, self._story_worse, self._story_closed,
            self._story_escalated, self._story_departure, self._story_power,
            self._story_agreement, self._story_scopes, self._story_assessment,
            self._story_issues_later, self._story_exceptions_later, self._story_campaigns,
            self._story_indicators, self._story_views, self._story_analyses,
            self._story_documents, self._story_agreements, self._story_framework_update,
        ):  # fmt: skip
            self.schedule(story())
        self.run()
        # The scheduler's turn, as it would take on a real server: whoever something is
        # waiting on is reminded, and what has stayed late has gone up to a steward or leader.
        with clock_set_to(lambda: self.end), self.db.bookkeeping() as session:
            self.tally("reminders", sum(reminders.send(session).values()))
        with clock_set_to(lambda: self.end), self.db.write(ME.actor) as session:
            settings.put(
                session, SETTING,
                {"built_on": self.end.date().isoformat(), "seed": self.seed,
                 "accounts": self.sample},
            )  # fmt: skip
        return Summary(self.seed, self.end.date(), dict(sorted(self.counts.items())), self.sample)


def build(
    db: Database, *, seed: int = 1, today: date | None = None, files: Path | None = None
) -> Summary:
    """Build the demo organization in an empty, migrated database."""
    with db.read() as session:
        if settings.get(session, SETTING) is not None or units.all_units(session):
            raise RiskWrenError("This installation already has an organization in it.")
    from riskwren.core.clock import today as real_today

    return Builder(db, seed=seed, today=today or real_today(), files=files).build()


def marker(session: Session) -> dict[str, Any] | None:
    """What says this installation is a demo, or None if it is not."""
    value = settings.get(session, SETTING)
    return value if isinstance(value, dict) else None


def _pdf(lines: list[str]) -> bytes:
    """A one-page PDF of plain lines, for a document the demo keeps as a file."""

    def escaped(line: str) -> str:
        return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    text = (
        "BT /F1 11 Tf 15 TL 72 740 Td " + " ".join(f"({escaped(line)}) '" for line in lines) + " ET"
    )
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(text)} >>\nstream\n{text}\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    table = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{table}\n%%EOF\n".encode()
    )
    return out
