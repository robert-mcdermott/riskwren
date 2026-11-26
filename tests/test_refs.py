from __future__ import annotations

import threading

import pytest

from riskwren.db.engine import Database
from riskwren.db.refs import PREFIXES, format_ref, next_ref, parse_ref
from tests.conftest import TESTER


def test_references_count_up_per_prefix(db: Database) -> None:
    with db.write(TESTER) as session:
        assert [next_ref(session, "RSK") for _ in range(3)] == ["RSK-0001", "RSK-0002", "RSK-0003"]
        assert next_ref(session, "SYS") == "SYS-0001"
    with db.write(TESTER) as session:
        assert next_ref(session, "RSK") == "RSK-0004"


def test_a_reference_grows_past_four_digits() -> None:
    assert format_ref("RSK", 12345) == "RSK-12345"


def test_unknown_prefixes_are_refused(db: Database) -> None:
    with db.write(TESTER) as session, pytest.raises(ValueError, match="Unknown reference prefix"):
        next_ref(session, "ZZ")


def test_parsing() -> None:
    assert parse_ref(" rsk-0142 ") == ("RSK", 142)
    assert parse_ref("SYS-10000") == ("SYS", 10000)
    assert parse_ref("RSK-12") is None
    assert parse_ref("ZZ-0001") is None
    assert parse_ref("the RSK-0001") is None
    assert all(parse_ref(format_ref(prefix, 1)) == (prefix, 1) for prefix in PREFIXES)


def test_two_writers_never_get_the_same_reference(db: Database) -> None:
    with db.write(TESTER) as session:
        next_ref(session, "RSK")  # the first use creates the counter
    taken: list[str] = []
    failures: list[BaseException] = []

    def work() -> None:
        try:
            for _ in range(20):
                with db.write(TESTER) as session:
                    taken.append(next_ref(session, "RSK"))
        except BaseException as exc:
            failures.append(exc)

    threads = [threading.Thread(target=work) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert failures == []
    assert len(taken) == len(set(taken)) == 80
