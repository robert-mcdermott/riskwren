"""Every ORM model. Importing this package registers them all on ``Base.metadata``."""

from __future__ import annotations

from riskwren.db.models.controls import (
    Acceptance,
    Action,
    Control,
    ControlLibraryEntry,
    ControlRating,
    RiskControl,
    TreatmentPlan,
)
from riskwren.db.models.inventory import Process, RecordLink, RecordOwner, System, ThirdParty
from riskwren.db.models.people import (
    Account,
    Credential,
    FailedSignIn,
    Membership,
    OrgUnit,
    RoleGrant,
    SessionToken,
)
from riskwren.db.models.program import Setting
from riskwren.db.models.risk import (
    Risk,
    RiskAssessment,
    RiskCategory,
    RiskLibraryEntry,
    RiskSubject,
    ScoringMethod,
)
from riskwren.db.models.system import ChainHead, Counter, Event

__all__ = [
    "Acceptance",
    "Account",
    "Action",
    "ChainHead",
    "Control",
    "ControlLibraryEntry",
    "ControlRating",
    "Counter",
    "Credential",
    "Event",
    "FailedSignIn",
    "Membership",
    "OrgUnit",
    "Process",
    "RecordLink",
    "RecordOwner",
    "Risk",
    "RiskAssessment",
    "RiskCategory",
    "RiskControl",
    "RiskLibraryEntry",
    "RiskSubject",
    "RoleGrant",
    "ScoringMethod",
    "SessionToken",
    "Setting",
    "System",
    "ThirdParty",
    "TreatmentPlan",
]
