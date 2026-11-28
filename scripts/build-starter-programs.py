#!/usr/bin/env python3
"""Write the starter programs: a program for each kind of organization, to start from.

Each is the default program (a research institute's) with what differs for an academic
medical center, a university, or a general nonprofit: its risk categories, the kinds of unit,
process, and information it has, and the words its scales use. A starter is a program pack,
chosen at `riskwren init --program KEY` or loaded later with `riskwren program import KEY`.
Categories the default has and a starter does not need are retired, not removed, so that a
program can take one up again.

    uv run python scripts/build-starter-programs.py
"""

from __future__ import annotations

import copy
import json
import runpy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src/riskwren/resources/packs/programs"
DEFAULT: dict[str, Any] = runpy.run_path(str(ROOT / "scripts/build-default-program.py"))["PACK"]


def _pack(key: str, title: str, description: str) -> dict[str, Any]:
    pack = copy.deepcopy(DEFAULT)
    pack["pack"] = {
        **pack["pack"], "key": key, "title": title, "description": description,
        "publisher": "The RiskWren Authors", "license": "Apache-2.0",
    }  # fmt: skip
    return pack


def _category(pack: dict[str, Any], key: str) -> dict[str, Any]:
    return next(item for item in pack["categories"] if item["key"] == key)


def _retire(pack: dict[str, Any], *keys: str) -> None:
    for key in keys:
        found = _category(pack, key)
        found["status"] = "retired"
        for child in found.get("children", []):
            child["status"] = "retired"


def _retire_child(pack: dict[str, Any], key: str, child: str) -> None:
    next(row for row in _category(pack, key)["children"] if row["key"] == child)["status"] = (
        "retired"
    )


def _children(pack: dict[str, Any], key: str, *children: tuple[str, str]) -> None:
    _category(pack, key)["children"] += [{"key": k, "name": n} for k, n in children]


def _add(pack: dict[str, Any], key: str, name: str, appetite: str, description: str,
         *children: tuple[str, str], after: str | None = None) -> None:  # fmt: skip
    item = {"key": key, "name": name, "appetite": appetite, "description": description,
            "children": [{"key": k, "name": n} for k, n in children]}  # fmt: skip
    keys = [row["key"] for row in pack["categories"]]
    at = keys.index(after) + 1 if after in keys else len(keys)
    pack["categories"].insert(at, item)


def _values(pack: dict[str, Any], name: str, *rows: tuple[str, ...]) -> None:
    have = {item["key"] for item in pack["vocabularies"][name]}
    for row in rows:
        if row[0] not in have:
            item = {"key": row[0], "label": row[1]}
            if len(row) > 2:
                item["description"] = row[2]
            pack["vocabularies"][name].append(item)


def _say(pack: dict[str, Any], old: str, new: str) -> None:
    """Change how the scales speak of the work, in every question and level."""
    for dimension in pack["scoring_method"]["dimensions"]:
        dimension["question"] = dimension["question"].replace(old, new)
        dimension["levels"] = {k: v.replace(old, new) for k, v in dimension["levels"].items()}


def research_institute() -> dict[str, Any]:
    return _pack("research-institute", "Research institute",
                 "Research with a clinic: the default program.")  # fmt: skip


def academic_medical_center() -> dict[str, Any]:
    pack = _pack("academic-medical-center", "Academic medical center",
                 "Hospitals and clinics, with research and the education of clinicians.")  # fmt: skip
    clinical = _category(pack, "clinical")
    clinical["name"] = "Patient care and safety"
    clinical["description"] = "The safety and quality of care, and of participants in research."
    _children(pack, "clinical", ("quality_of_care", "Quality of care"),
              ("emergency_preparedness", "Emergency preparedness"))  # fmt: skip
    _children(pack, "regulatory", ("billing", "Billing and coding"),
              ("referrals", "Referrals and financial relationships"))  # fmt: skip
    _add(pack, "education", "Education and training", "moderate",
         "The education of residents, fellows, students, and staff.",
         ("graduate_medical_education", "Graduate medical education"),
         ("learner_wellbeing", "Wellbeing of learners"),
         ("program_accreditation", "Accreditation of programs"), after="clinical")  # fmt: skip
    _values(pack, "unit_kinds", ("hospital", "Hospital"), ("service_line", "Service line"))
    _values(pack, "process_kinds", ("patient_care", "Patient care", "Caring for patients"),
            ("revenue_cycle", "Revenue cycle", "Registration, coding, billing, and collection"))  # fmt: skip
    _say(pack, "research, care, or teaching", "patient care, research, or teaching")
    return pack


def university() -> dict[str, Any]:
    pack = _pack("university", "University",
                 "Teaching, research, and the life of a campus.")  # fmt: skip
    _retire(pack, "clinical")
    _retire_child(pack, "strategic", "scientific_direction")
    _children(pack, "strategic", ("enrollment", "Enrollment and tuition"))
    _add(pack, "academic", "Teaching and learning", "moderate",
         "The quality and standing of what is taught, and how it is assessed.",
         ("academic_quality", "Academic quality"), ("accreditation", "Accreditation"),
         ("academic_integrity", "Academic integrity"), after="strategic")  # fmt: skip
    _add(pack, "students", "Students", "low",
         "The safety, wellbeing, and fair treatment of students.",
         ("student_safety", "Safety and wellbeing of students"),
         ("discrimination", "Discrimination and harassment"),
         ("campus_life", "Housing and campus life"), ("athletics", "Athletics"),
         after="academic")  # fmt: skip
    _children(pack, "regulatory", ("student_records", "Student records"),
              ("campus_safety_reporting", "Campus safety reporting"))  # fmt: skip
    _values(pack, "unit_kinds", ("college", "College"), ("school", "School"))
    _values(pack, "process_kinds", ("teaching", "Teaching", "Courses, programs, and assessment"),
            ("student_services", "Student services", "Advising, housing, health, and support"),
            ("admissions", "Admissions and financial aid", "Recruiting, admitting, and aiding"))  # fmt: skip
    _values(pack, "information_kinds", ("student_records", "Student records"))
    _values(pack, "protected_information", ("education", "Education records"))
    _say(pack, "research, care, or teaching", "teaching, research, or student life")
    return pack


def nonprofit() -> dict[str, Any]:
    pack = _pack("nonprofit", "General nonprofit",
                 "Programs and services funded by grants and gifts.")  # fmt: skip
    _retire(pack, "research", "clinical")
    _retire_child(pack, "strategic", "scientific_direction")
    _children(pack, "strategic", ("mission_impact", "Mission and impact"))
    _add(pack, "programs", "Programs and services", "moderate",
         "Delivering what the organization exists to do, safely and well.",
         ("program_delivery", "Program delivery"),
         ("beneficiary_safety", "Safety of the people served"),
         ("volunteers", "Volunteers"), after="strategic")  # fmt: skip
    _children(pack, "financial", ("donor_restrictions", "Donor restrictions"))
    _children(pack, "regulatory", ("tax_exempt_status", "Tax-exempt status"))
    _values(pack, "unit_kinds", ("program", "Program"), ("chapter", "Chapter"))
    _values(pack, "process_kinds", ("programs", "Programs and services", "Serving those the mission is for"),
            ("fundraising", "Fundraising", "Grants, gifts, and events"))  # fmt: skip
    _values(pack, "information_kinds", ("donor_records", "Donor records"),
            ("client_records", "Records of the people served"))  # fmt: skip
    _say(pack, "research, care, or teaching", "the organization's programs and services")
    return pack


STARTERS = {
    "research-institute": research_institute,
    "academic-medical-center": academic_medical_center,
    "university": university,
    "nonprofit": nonprofit,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key, make in STARTERS.items():
        path = OUT / f"{key}.json"
        path.write_text(json.dumps(make(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
