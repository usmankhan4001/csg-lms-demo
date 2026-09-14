"""
Schemas and DEFAULTS for CSG School Settings.

This module is the single source of truth for what a school can configure and
what every setting falls back to. It deliberately imports nothing from
`services/`, so that `services/sms/fees.py` and `services/sms/gradebook.py`
can later import their defaults FROM HERE without a circular import.

THE DEFAULTS BELOW MIRROR THE CURRENT HARDCODED CONSTANTS EXACTLY:

    fee_policy      <- services/sms/fees.py:150-153
    grading_policy  <- services/sms/gradebook.py:33 (DEFAULT_INTERVALS)

That is not a coincidence to be tidied away later -- it is the guarantee that
turning this feature on changes nothing for an existing school. A school with
no settings row must behave exactly as it does today. Anyone editing these
numbers is changing live behaviour for every school that has not overridden
them, so change the DEFAULT only when the product decision has actually
changed.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field


class SettingsGroup(str, Enum):
    """The configurable areas of a school.

    Stored as a plain string on the row (not a native DB enum), so adding a
    group here needs no migration.
    """

    SCHOOL_PROFILE = "school_profile"
    ACADEMIC_CALENDAR = "academic_calendar"
    GRADING_POLICY = "grading_policy"
    ATTENDANCE_POLICY = "attendance_policy"
    FEE_POLICY = "fee_policy"
    REPORT_CARDS = "report_cards"
    NOTIFICATIONS = "notifications"
    AI_TUTOR_POLICY = "ai_tutor_policy"
    ADMISSIONS_POLICY = "admissions_policy"
    CRISIS_RESOURCES = "crisis_resources"


# --------------------------------------------------------------------------
# Group payloads
# --------------------------------------------------------------------------


class SchoolProfileSettings(BaseModel):
    """Identity used on documents the school issues.

    Every field is optional and defaults to empty rather than to a plausible
    placeholder. Outbound copy in this codebase was previously caught naming a
    fictional campus ("CSG International Academy") and a fabricated principal;
    a blank that a UI can flag as unset is safe, an invented name is not.
    """

    legal_name: Optional[str] = None
    logo_url: Optional[str] = None
    principal_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None


class GradeInterval(BaseModel):
    """One band of the grading scale."""

    grade: str
    min_percentage: float
    max_percentage: float
    gpa_point: float


class GradingPolicySettings(BaseModel):
    """The scale every percentage is turned into a letter and GPA point by."""

    # Mirrors gradebook.DEFAULT_INTERVALS exactly.
    intervals: List[GradeInterval] = Field(
        default_factory=lambda: [
            GradeInterval(grade="A+", min_percentage=90.0, max_percentage=100.0, gpa_point=4.0),
            GradeInterval(grade="A", min_percentage=80.0, max_percentage=89.99, gpa_point=3.7),
            GradeInterval(grade="B+", min_percentage=75.0, max_percentage=79.99, gpa_point=3.3),
            GradeInterval(grade="B", min_percentage=70.0, max_percentage=74.99, gpa_point=3.0),
            GradeInterval(grade="C+", min_percentage=65.0, max_percentage=69.99, gpa_point=2.7),
            GradeInterval(grade="C", min_percentage=60.0, max_percentage=64.99, gpa_point=2.0),
            GradeInterval(grade="D", min_percentage=50.0, max_percentage=59.99, gpa_point=1.0),
            GradeInterval(grade="F", min_percentage=0.0, max_percentage=49.99, gpa_point=0.0),
        ]
    )
    # 50.0 is the bottom of "D" in the default scale above, i.e. the lowest
    # band that is not F. Stated explicitly rather than derived, because a
    # school may set a pass mark that does not line up with a band edge.
    pass_mark: float = 50.0


class FeePolicySettings(BaseModel):
    """Late-fee accrual. Mirrors fees.py:150-153 exactly."""

    late_fee_percent_per_period: float = 2.0
    late_fee_grace_days: int = 7
    late_fee_period_days: int = 30
    # Hard ceiling as a % of the overdue principal. Without it, accrual on a
    # long-unpaid voucher grows without bound.
    late_fee_max_percent: float = 20.0


class AcademicCalendarSettings(BaseModel):
    """Working week and period structure.

    `working_days` uses Python's weekday numbering (Monday=0 .. Sunday=6).
    The default is Monday-Friday; schools running a Sunday-Thursday week
    change it here rather than in code.
    """

    working_days: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    periods_per_day: int = 8
    period_minutes: int = 40
    # Whether ending a term automatically opens the next one.
    auto_rollover_terms: bool = False


class AttendancePolicySettings(BaseModel):
    """When a student counts as late, and when someone gets told."""

    late_after_minutes: int = 10
    # Consecutive unexplained absences before an alert is raised.
    absence_alert_after_days: int = 3
    excused_categories: List[str] = Field(
        default_factory=lambda: ["MEDICAL", "FAMILY", "SCHOOL_ACTIVITY"]
    )


class ReportCardSettings(BaseModel):
    """Who signs a report card and how it reaches a parent."""

    signatory_name: Optional[str] = None
    signatory_title: Optional[str] = None
    # False = a draft must be explicitly sent by a human. Defaults to the
    # safer option: report cards should not reach parents automatically.
    auto_send_on_generate: bool = False


class NotificationSettings(BaseModel):
    """Which channels carry which alerts."""

    email_enabled: bool = True
    in_app_enabled: bool = True
    # Crisis alerts deliberately have no "off" switch here: suppressing a
    # self-harm escalation is not a configuration option.
    notify_guardians_on_absence: bool = True
    notify_guardians_on_fee_due: bool = True


class AITutorPolicySettings(BaseModel):
    """Bounds on what the AI tutor will do for a student."""

    # Empty = every subject the student is enrolled in. An explicit list
    # narrows it.
    enabled_subjects: List[str] = Field(default_factory=list)
    max_hints_per_assignment: int = 3
    daily_message_limit: int = 1000


class AdmissionsPolicySettings(BaseModel):
    """How much the admissions funnel is allowed to do unsupervised.

    These govern whether an AI agent may talk to a real family without a human
    seeing the message first. The defaults are deliberately cautious: a school
    turns automation UP once it trusts it, rather than discovering after the
    fact that a robot has been answering parents all week.
    """

    # Auto-acknowledge an inbound enquiry (SDR reply + nurture enrolment).
    # ON by default: an enquiry that sits unanswered until a human opens the
    # CRM is the single most costly failure in this funnel -- families go
    # elsewhere overnight.
    auto_acknowledge_inbound: bool = True

    # Below this, the enquiry is held for human review instead of being
    # answered automatically. This is NOT a model probability -- the intent
    # matcher is deterministic pattern matching and produces no such number.
    # It is a heuristic over what was actually understood: which intents
    # matched, and how much contact detail the message carried. Documented as
    # a heuristic so nobody later mistakes it for a calibrated confidence.
    auto_acknowledge_min_confidence: float = 0.4

    # Enrol into the multi-stage drip sequence automatically on ingestion.
    auto_enrol_in_nurture: bool = True


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

class CrisisResourceContact(BaseModel):
    """One crisis helpline or support contact, as the school records it.

    `contact` is free text rather than a parsed phone number because the useful
    instruction differs by country and by service: "Call 1122", "Text HOME to
    741741", "WhatsApp +92 ...". Forcing it into a number field would lose the
    instruction a child in distress actually needs to follow.
    """

    label: str
    contact: str
    description: Optional[str] = None


class CrisisResourcesSettings(BaseModel):
    """The support resources shown to a student who discloses self-harm.

    THIS DEFAULTS TO EMPTY ON PURPOSE, and that is the whole point of the
    group. The crisis message previously hardcoded US helplines -- 988, Crisis
    Text Line, the Trevor Project, and "emergency services (911)". This
    deployment serves a school in Pakistan, where none of those numbers
    connect: a child in crisis was being handed numbers they could not call.

    The software must not guess a country's helplines. A wrong number is worse
    than no number -- a child dials it during the worst moment of their life
    and reaches nothing. So a school records its own, and an unconfigured
    school gets an honest message that says so (see
    `compose_crisis_message` in services/ai/crisis_classifier.py) rather than
    inheriting another country's.
    """

    resources: List[CrisisResourceContact] = Field(default_factory=list)
    # e.g. "15" (Pakistan police), "1122" (Pakistan rescue), "911" (US).
    # None means the school has not told us, and the message says so.
    emergency_number: Optional[str] = None
    extra_guidance: Optional[str] = None


GROUP_MODELS: Dict[SettingsGroup, Type[BaseModel]] = {
    SettingsGroup.SCHOOL_PROFILE: SchoolProfileSettings,
    SettingsGroup.ACADEMIC_CALENDAR: AcademicCalendarSettings,
    SettingsGroup.GRADING_POLICY: GradingPolicySettings,
    SettingsGroup.ATTENDANCE_POLICY: AttendancePolicySettings,
    SettingsGroup.FEE_POLICY: FeePolicySettings,
    SettingsGroup.REPORT_CARDS: ReportCardSettings,
    SettingsGroup.NOTIFICATIONS: NotificationSettings,
    SettingsGroup.AI_TUTOR_POLICY: AITutorPolicySettings,
    SettingsGroup.ADMISSIONS_POLICY: AdmissionsPolicySettings,
    SettingsGroup.CRISIS_RESOURCES: CrisisResourcesSettings,
}

# Groups with real editing UI today. The rest are readable and writable over
# the API but are shown as "not yet configurable" in the dash, rather than
# rendered as controls that look editable and are not.
UI_EDITABLE_GROUPS = [
    SettingsGroup.SCHOOL_PROFILE,
    SettingsGroup.GRADING_POLICY,
    SettingsGroup.FEE_POLICY,
]


def default_payload(group: SettingsGroup) -> Dict[str, Any]:
    """The code default for a group, as a plain dict."""
    return GROUP_MODELS[group]().model_dump(mode="json")


# --------------------------------------------------------------------------
# API payloads
# --------------------------------------------------------------------------


class SettingsSource(str, Enum):
    """Where a resolved group's values actually came from.

    An admin editing campus settings must be able to tell "this campus sets
    this" from "this is inherited and my edit will create an override".
    """

    CAMPUS = "CAMPUS"
    ORG = "ORG"
    DEFAULT = "DEFAULT"


class ResolvedSettingsGroup(BaseModel):
    group: SettingsGroup
    source: SettingsSource
    values: Dict[str, Any]
    editable_in_ui: bool
    updated_at: Optional[str] = None


class SchoolSettingsRead(BaseModel):
    org_id: int
    campus_id: Optional[int] = None
    groups: List[ResolvedSettingsGroup]


class SettingsGroupUpdate(BaseModel):
    """Write one group. `values` is validated against that group's model."""

    values: Dict[str, Any]
