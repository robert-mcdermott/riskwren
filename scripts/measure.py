#!/usr/bin/env python3
"""Measure how RiskWren performs with many records and many people at once.

    uv run python scripts/measure.py                       10,000 records, 2 workers, SQLite
    uv run python scripts/measure.py --records 20000 --people 40 --seconds 60
    uv run --extra postgres python scripts/measure.py --database postgresql+psycopg://...

It builds the demo organization in a folder of its own, adds systems, processes, and risks
(half of them assessed) until the inventory, risks, and controls number as many records as
asked, starts the server with that many workers, and has that many people sign in and read
the pages people read most, all at once, for a while. It prints how long each took. Nothing
here touches an installation of yours: the folder is new and is removed afterwards, unless
``--keep`` is given.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import platform
import random
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parent.parent
# What people read most: their home page, the lists, a record, search, and the dashboards.
ROUTES = [
    ("home", "/api/v1/home"),
    ("risks", "/api/v1/risks?limit=50"),
    ("systems", "/api/v1/systems?limit=50"),
    ("search", "/api/v1/search?q=data"),
    ("risk dashboard", "/api/v1/dashboard"),
    ("heat map", "/api/v1/heat-map"),
    ("compliance", "/api/v1/compliance"),
    ("a risk", "RISK"),
    ("notices", "/api/v1/notices"),
]
PEOPLE = ["cro", "ciso", "bio_mgr", "bio_dir", "assess1", "auditor", "member", "president"]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def grow(config_path: Path, records: int) -> dict[str, int]:
    """Add systems, processes, and risks until there are ``records`` of them, with controls."""
    from riskwren.config import load_config
    from riskwren.db.engine import Database
    from riskwren.db.models import Account, Control, OrgUnit, Process, Risk, RiskCategory, System
    from riskwren.inventory import records as inventory
    from riskwren.inventory.registry import PROCESS, SYSTEM
    from riskwren.people import accounts
    from riskwren.risk import register

    config = load_config(config_path)
    db = Database(config.database_url)
    rng = random.Random(9)
    try:
        with db.read() as session:
            kinds = [Process, System, Risk, Control]
            have = sum(session.scalar(select(func.count()).select_from(k)) or 0 for k in kinds)
            units = [row.id for row in session.scalars(select(OrgUnit))]
            named = Account.display_name == "Mireille Lachance"  # the demo's risk manager
            account = session.scalars(select(Account).where(named)).one()
            manager = accounts.principal_for(session, account)
            categories = sorted(
                row.key for row in session.scalars(select(RiskCategory)) if row.parent_id
            )
        made = {"systems": 0, "processes": 0, "risks": 0}
        number = 0
        while have < records:
            with db.write(manager.actor) as session:
                for _ in range(min(250, records - have)):
                    number += 1
                    unit = rng.choice(units)
                    roll = number % 5
                    if roll in (0, 1):
                        inventory.create(session, manager, SYSTEM, {
                            "name": f"Measured system {number}", "kind": "application",
                            "criticality": rng.choice(["low", "moderate", "high", "critical"]),
                            "org_unit_id": unit})  # fmt: skip
                        made["systems"] += 1
                    elif roll == 2:
                        inventory.create(session, manager, PROCESS, {
                            "name": f"Measured process {number}", "kind": "administrative",
                            "criticality": rng.choice(["low", "moderate", "high"]),
                            "org_unit_id": unit})  # fmt: skip
                        made["processes"] += 1
                    else:
                        risk = register.create(session, manager, {
                            "name": f"Measured risk {number}: data reaches the wrong people",
                            "cause": "A mistake", "event": "Data is disclosed",
                            "consequence": "Harm to those it is about",
                            "category": rng.choice(categories), "org_unit_id": unit})  # fmt: skip
                        if number % 2:
                            register.assess(session, manager, risk, kind="inherent",
                                            likelihood=rng.randint(1, 5),
                                            impact_levels={"mission": rng.randint(1, 5)},
                                            rationale="Measured.")  # fmt: skip
                        made["risks"] += 1
                    have += 1
        return made
    finally:
        db.dispose()


class Person:
    def __init__(self, base: str, email: str) -> None:
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        body = json.dumps({"email": email}).encode()
        request = urllib.request.Request(f"{base}/api/v1/session/demo", data=body,
                                         headers={"Content-Type": "application/json"})  # fmt: skip
        with self.opener.open(request, timeout=60) as response:
            response.read()

    def get(self, path: str) -> tuple[float, int]:
        started = time.perf_counter()
        try:
            with self.opener.open(f"{self.base}{path}", timeout=120) as response:
                response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        return time.perf_counter() - started, status


def run(args: argparse.Namespace) -> int:
    work = Path(tempfile.mkdtemp(prefix="riskwren-measure-"))
    env = {**os.environ, "RISKWREN_SERVER_SCHEDULER": "false"}
    if args.database:
        env["RISKWREN_DATABASE_URL"] = args.database
    server = None
    try:
        print(f"Building the demo organization in {work} …", flush=True)
        built = {k: v for k, v in env.items() if k != "RISKWREN_DATABASE_URL"}
        subprocess.run(["uv", "run", "-q", "riskwren", "demo", "--force", str(work / "demo")],
                       cwd=ROOT, env=built, check=True, stdout=subprocess.DEVNULL)  # fmt: skip
        config = work / "demo" / "riskwren.toml"
        if args.database:
            # The demo is built in SQLite; it moves to PostgreSQL the way an installation would.
            print("Moving it to PostgreSQL with a backup and a restore …", flush=True)
            subprocess.run(["uv", "run", "-q", "riskwren", "--config", str(config), "backup",
                            str(work / "demo.zip")], cwd=ROOT, env=built, check=True,
                           stdout=subprocess.DEVNULL)  # fmt: skip
            (work / "pg").mkdir()
            text = config.read_text(encoding="utf-8").replace(
                'home = "var"', f'home = "{work / "pg" / "var"}"'
            )
            config = work / "pg" / "riskwren.toml"
            config.write_text(text, encoding="utf-8")
            subprocess.run(["uv", "run", "-q", "--extra", "postgres", "riskwren", "--config",
                            str(config), "restore", str(work / "demo.zip")], cwd=ROOT, env=env,
                           check=True, stdout=subprocess.DEVNULL)  # fmt: skip
        os.environ.update({k: v for k, v in env.items() if k.startswith("RISKWREN_")})
        started = time.perf_counter()
        made = grow(config, args.records)
        print(f"Added {made} in {time.perf_counter() - started:.0f} s.", flush=True)
        port = free_port()
        server = subprocess.Popen(
            ["uv", "run", "-q", "riskwren", "--config", str(config), "serve", "--port", str(port),
             "--workers", str(args.workers)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # fmt: skip
        base = f"http://127.0.0.1:{port}"
        for _ in range(300):
            try:
                with urllib.request.urlopen(f"{base}/api/v1/health/ready", timeout=2):
                    break
            except OSError:
                time.sleep(0.2)
        meta = json.loads(urllib.request.urlopen(f"{base}/api/v1/meta").read())["data"]
        emails = {person["key"]: person["email"] for person in meta["demo"]["accounts"]}
        crowd = [Person(base, emails[PEOPLE[i % len(PEOPLE)]]) for i in range(args.people)]
        risks = json.loads(crowd[0].opener.open(f"{base}/api/v1/risks?limit=200").read())["data"]
        refs = [row["ref"] for row in risks]
        timings: dict[str, list[float]] = {name: [] for name, _ in ROUTES}
        failures: dict[str, int] = {name: 0 for name, _ in ROUTES}
        lock = threading.Lock()
        stop = time.perf_counter() + args.seconds

        def browse(person: Person, seed: int) -> None:
            rng = random.Random(seed)
            while time.perf_counter() < stop:
                name, path = rng.choice(ROUTES)
                if path == "RISK":
                    path = f"/api/v1/risks/{rng.choice(refs)}"
                took, status = person.get(path)
                with lock:
                    timings[name].append(took)
                    if status >= 500:
                        failures[name] += 1

        print(f"{args.people} people reading for {args.seconds} s with {args.workers} worker(s) …",
              flush=True)  # fmt: skip
        threads = [threading.Thread(target=browse, args=(p, i)) for i, p in enumerate(crowd)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        total = sum(len(values) for values in timings.values())
        database = "PostgreSQL" if args.database else "SQLite"
        print(f"\n{args.records:,} records · {args.people} people at once · {args.workers} "
              f"worker(s) · {database} · {platform.machine()}, {os.cpu_count()} cores · "
              f"{total / args.seconds:.0f} requests a second\n")  # fmt: skip
        print("| Page | Requests | Median | 95th percentile | Slowest | Failed |")
        print("|---|---:|---:|---:|---:|---:|")
        for name, values in timings.items():
            if not values:
                continue
            values.sort()
            p95 = values[min(len(values) - 1, int(len(values) * 0.95))]
            median = statistics.median(values) * 1000
            print(f"| {name} | {len(values)} | {median:.0f} ms | {p95 * 1000:.0f} ms | "
                  f"{values[-1] * 1000:.0f} ms | {failures[name]} |")  # fmt: skip
        return 1 if any(failures.values()) else 0
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=30)
        if args.keep:
            print(f"\nKept {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--records", type=int, default=10_000)
    parser.add_argument("--people", type=int, default=25)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seconds", type=int, default=45)
    parser.add_argument("--database", help="a PostgreSQL address; SQLite if left out")
    parser.add_argument("--keep", action="store_true", help="keep the folder it built in")
    return run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
