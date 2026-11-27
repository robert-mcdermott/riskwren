"""The bow-tie (RSK-20): a risk's causes, the controls that keep the event from happening, the
event, the controls that soften what follows, and its consequences, on one diagram.

Nothing is entered for it: it reads the risk's cause, event, and consequence, and the
controls that bear on the risk. A control that reduces likelihood stands between the causes
and the event; one that reduces impact, between the event and the consequences; one that
reduces both stands on both sides. A cause or consequence written as several, one to a line
or separated by semicolons, is drawn as several.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from riskwren.access.principal import Principal
from riskwren.controls import service as controls
from riskwren.db.models import Risk


def parts(text: str | None) -> list[str]:
    """A cause or a consequence as the separate things it names."""
    if not text:
        return []
    pieces = [piece.strip(" .-•*") for piece in re.split(r"[;\n]+", text)]
    return [_first_upper(piece) for piece in pieces if piece]


def _first_upper(text: str) -> str:
    return text[:1].upper() + text[1:]


def view(session: Session, principal: Principal, risk: Risk) -> dict[str, Any]:
    found = controls.of_risk(session, principal, risk)

    def side(*kinds: str) -> list[dict[str, Any]]:
        return [
            {
                **link["control"],
                "reduces": link["reduces"],
                "reliance": link["reliance"],
                "note": link["note"],
            }
            for link in found["controls"]
            if link["reduces"] in kinds and link["control"]["status"] == "active"
        ]

    return {
        "causes": parts(risk.cause),
        "preventive": side("likelihood", "both"),
        "event": _first_upper(risk.event or risk.name),
        "mitigating": side("impact", "both"),
        "consequences": parts(risk.consequence),
        "hidden": found["hidden"],
    }
