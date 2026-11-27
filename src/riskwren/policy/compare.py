"""Two versions of a document's text, line by line, with the differing words marked (POL-08).

Pure functions, no database. A line that is in both is kept; a line in only one is added or
removed; a line that was reworded is paired with what it became, and the words that differ
are marked on each side. Long stretches that did not change are folded to a count, with a
little kept on either side of each change so that it can be read in place.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

CONTEXT = 2  # unchanged lines kept on either side of a change
ALIKE = 0.5  # how alike two lines must be to be one line reworded
TOKEN = re.compile(r"\s+|\w+|[^\w\s]")


def lines(text: str | None) -> list[str]:
    """The lines that carry words. Blank lines only separate paragraphs, and trailing spaces
    mean nothing, so neither counts as a difference."""
    return [
        line.rstrip() for line in (text or "").replace("\r\n", "\n").split("\n") if line.strip()
    ]


def _words(before: str, after: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Each side cut into pieces, the ones that differ marked."""
    a, b = TOKEN.findall(before), TOKEN.findall(after)
    left: list[dict[str, Any]] = []
    right: list[dict[str, Any]] = []

    def put(side: list[dict[str, Any]], text: str, mark: bool) -> None:
        if not text:
            return
        if side and side[-1]["mark"] == mark:
            side[-1]["text"] += text
        else:
            side.append({"text": text, "mark": mark})

    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        put(left, "".join(a[i1:i2]), tag != "equal")
        put(right, "".join(b[j1:j2]), tag != "equal")
    return left, right


def _plain(text: str) -> list[dict[str, Any]]:
    return [{"text": text, "mark": False}]


def _marked(text: str) -> list[dict[str, Any]]:
    return [{"text": text, "mark": True}]


def _pair(old: list[str], new: list[str]) -> list[dict[str, Any]]:
    """Lines that were replaced, each paired with the most like it of those that replaced it,
    in order. A line with nothing like it was removed; one left over was added. So a step
    put in the middle of a list reads as one added line, not every line after it changed."""
    rows: list[dict[str, Any]] = []
    start = 0
    for line in old:
        best, likeness = None, ALIKE
        for at in range(start, len(new)):
            score = SequenceMatcher(None, line, new[at], autojunk=False).ratio()
            if score > likeness:
                best, likeness = at, score
        if best is None:
            rows.append({"op": "removed", "before": _marked(line), "after": None})
            continue
        rows += [
            {"op": "added", "before": None, "after": _marked(each)} for each in new[start:best]
        ]
        left, right = _words(line, new[best])
        rows.append({"op": "changed", "before": left, "after": right})
        start = best + 1
    rows += [{"op": "added", "before": None, "after": _marked(each)} for each in new[start:]]
    return rows


def compare(before: str | None, after: str | None, *, context: int = CONTEXT) -> dict[str, Any]:
    """Rows to show side by side: same, changed, removed, added, and folded stretches."""
    a, b = lines(before), lines(after)
    rows: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            rows += [
                {"op": "same", "before": _plain(line), "after": _plain(line)} for line in a[i1:i2]
            ]
            continue
        rows += _pair(a[i1:i2], b[j1:j2])

    counts = {
        op: sum(1 for row in rows if row["op"] == op) for op in ("added", "removed", "changed")
    }
    # Fold what did not change, keeping a little around each change.
    near = set()
    for index, row in enumerate(rows):
        if row["op"] != "same":
            near.update(range(index - context, index + context + 1))
    shown: list[dict[str, Any]] = []
    folded = 0
    for index, row in enumerate(rows):
        if row["op"] == "same" and index not in near:
            folded += 1
            continue
        if folded:
            shown.append({"op": "folded", "count": folded})
            folded = 0
        shown.append(row)
    if folded:
        shown.append({"op": "folded", "count": folded})
    return {"rows": shown, "counts": counts, "same": not any(counts.values())}
