from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_terms.py"
spec = importlib.util.spec_from_file_location("check_terms", SCRIPT)
assert spec and spec.loader
check_terms = importlib.util.module_from_spec(spec)
sys.modules["check_terms"] = check_terms  # dataclasses look their module up by name
spec.loader.exec_module(check_terms)


def test_terms_match_whole_words_whatever_the_case() -> None:
    terms = check_terms.parse_terms(["# a comment", "", "Acme Corp", "=NASA"])
    text = "We met acme   corp today.\nAcmeCorporation is different.\nnasa is lower case.\nNASA."
    hits = list(check_terms.find_hits("notes.md", text, terms))
    assert [(hit.line, hit.term) for hit in hits] == [(1, "Acme Corp"), (4, "NASA")]


def test_no_term_list_is_not_a_failure(tmp_path: Path) -> None:
    assert check_terms.main(["--terms", str(tmp_path / "absent.txt")]) == 0


def test_a_commit_message_is_checked(tmp_path: Path) -> None:
    terms = tmp_path / "terms.txt"
    terms.write_text("Acme Corp\n")
    message = tmp_path / "MSG"
    message.write_text("Add the thing\n\n# Acme Corp in a comment is ignored\n")
    assert check_terms.main(["--terms", str(terms), "--message", str(message)]) == 0
    message.write_text("Add the Acme Corp importer\n")
    assert check_terms.main(["--terms", str(terms), "--message", str(message)]) == 1
