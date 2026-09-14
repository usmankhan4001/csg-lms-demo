"""
Schemas and DEFAULTS for RevOps Admin Config (M30).

Every agent behaviour in the admissions funnel was a hardcoded Python
constant, so a school could not change what "qualified" means for its own
intake, or adjust a nurture cadence, without a developer. This module is the
single source of truth for what is configurable and what it falls back to.

Like `schemas/sms_settings.py`, this imports nothing from `services/`, so the
services that consume it can import their defaults FROM HERE without a
circular import.

THE DEFAULTS BELOW MIRROR THE CURRENT HARDCODED BEHAVIOUR EXACTLY:

    lead_scoring    <- services/ai/revops_lead_scoring.py
                       factor caps 25/20/15/20/20, HOT >= 75, WARM >= 45,
                       and the HIGH_/MODERATE_DEMAND_GRADES sets
    nurture         <- services/ai/revops_drip_engine.py
                       4 stages at days 1/3/7/14 with their channel strings
    consent_policy  <- services/ai/revops_drip_engine._stage_consent_blocked
                       explicit opt-out blocks; unknown does not

That mirroring is the guarantee that turning this feature on changes nothing
for an existing school. Anyone editing a DEFAULT here is changing live
behaviour for every school that has not overridden it.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field


class RevOpsConfigGroup(str, Enum):
    """The configurable areas of the admissions funnel.

    Stored as a plain string on the row (not a native DB enum), so adding a
    group needs no migration -- the activity-type enum in this project
    required exactly that ALTER TYPE.
    """

    LEAD_SCORING = "lead_scoring"
    NURTURE = "nurture"
    CONSENT_POLICY = "consent_policy"


# ---------------------------------------------------------------------------
# Lead scoring (M22 / M30)
# ---------------------------------------------------------------------------

# The factor caps the scoring engine was written against. A configured weight
# is expressed relative to these, so a factor scored 20/25 on completeness
# still means "80% of completeness" after an admin re-weights it. Exposed here
# rather than inlined so the scaling maths has one named source.
BASELINE_FACTOR_MAX: Dict[str, float] = {
    "completeness": 25.0,
    "responsiveness": 20.0,
    "grade_demand": 15.0,
    "budget_fit": 20.0,
    "timeline": 20.0,
}


class LeadScoringSettings(BaseModel):
    """What "qualified" means for this school's intake.

    The five weights are the maximum contribution of each factor. They default
    to the engine's original caps and sum to 100, but are NOT forced to: a
    school that cares little about budget fit may drop it to 5, and the
    resulting total simply has a smaller ceiling. `total_possible` is returned
    alongside every score so a number is never presented as "out of 100" when
    it is not.
    """

    weight_completeness: float = Field(default=25.0, ge=0.0, le=100.0)
    weight_responsiveness: float = Field(default=20.0, ge=0.0, le=100.0)
    weight_grade_demand: float = Field(default=15.0, ge=0.0, le=100.0)
    weight_budget_fit: float = Field(default=20.0, ge=0.0, le=100.0)
    weight_timeline: float = Field(default=20.0, ge=0.0, le=100.0)

    # Intent bands. A lead at or above hot_threshold is HOT, at or above
    # warm_threshold is WARM, below that COLD. These are the knobs that most
    # directly answer "what counts as a qualified lead here".
    hot_threshold: float = Field(default=75.0, ge=0.0, le=100.0)
    warm_threshold: float = Field(default=45.0, ge=0.0, le=100.0)

    # Grades this school genuinely competes for. Mirrors HIGH_DEMAND_GRADES /
    # MODERATE_DEMAND_GRADES, lowercased, matched as substrings.
    high_demand_grades: List[str] = Field(
        default_factory=lambda: sorted(
            [
                "kindergarten", "kg", "kg1", "kg2", "pre-k", "eyfs", "reception",
                "grade 1", "year 1", "grade 6", "year 7", "grade 9", "year 10",
                "grade 11", "year 12", "ib diploma", "a-levels", "a levels",
            ]
        )
    )
    moderate_demand_grades: List[str] = Field(
        default_factory=lambda: sorted(
            [
                "grade 2", "grade 3", "grade 4", "grade 5", "grade 7", "grade 8",
                "grade 10", "grade 12", "year 2", "year 3", "year 4", "year 5",
                "year 6", "year 8", "year 9", "year 11", "year 13",
            ]
        )
    )

    # Below this score an agent's decision awaits human review rather than
    # auto-advancing. 0.0 = today's behaviour (no gate), so enabling this
    # module changes nothing until a school opts in.
    human_review_below_score: float = Field(default=0.0, ge=0.0, le=100.0)


# ---------------------------------------------------------------------------
# Nurture cadence (M25 / M30)
# ---------------------------------------------------------------------------


class NurtureStageSettings(BaseModel):
    """One stage of the drip sequence.

    `content` is deliberately absent -- see NurtureSettings.
    """

    stage: int
    # Days after enrolment in the sequence that this stage is due.
    day: int = Field(ge=0)
    # Underscore-joined delivery channels, e.g. "email_whatsapp". Consent is
    # evaluated per channel token.
    channel: str
    enabled: bool = True


class NurtureSettings(BaseModel):
    """Cadence and channels for the nurture sequence.

    WHAT IS NOT CONFIGURABLE HERE, and why: the stage COPY. Each stage's
    subject and body are interpolated prose carrying anti-fabrication guards
    (`MissingSchoolIdentity` refuses to generate when the campus is unknown,
    rather than inventing a school name -- outbound copy naming a fictional
    campus has already had to be torn out of this codebase once). A template
    editor that preserved those guards is a real piece of work with its own
    injection and fabrication risks, and is deliberately not smuggled in here.

    Timing, channel and enablement are the knobs a school actually asks for,
    and none of them can produce a false statement about the school.
    """

    stages: List[NurtureStageSettings] = Field(
        default_factory=lambda: [
            NurtureStageSettings(stage=1, day=1, channel="email_whatsapp"),
            NurtureStageSettings(stage=2, day=3, channel="whatsapp_email"),
            NurtureStageSettings(stage=3, day=7, channel="email_sms"),
            NurtureStageSettings(stage=4, day=14, channel="phone_whatsapp"),
        ]
    )


# ---------------------------------------------------------------------------
# Consent policy (M33 / M30)
# ---------------------------------------------------------------------------


class ConsentPolicySettings(BaseModel):
    """How strictly outbound consent is interpreted.

    Today a stage is blocked ONLY by an explicit opt-out; a lead with no
    recorded consent for a channel is contacted. That matches the current
    `_stage_consent_blocked` behaviour and is the default here, so nothing
    changes on upgrade.

    `require_explicit_opt_in` inverts it for schools in stricter regimes:
    unknown consent then blocks too. This narrows who may be contacted -- it
    can never widen it -- so it is safe to expose.
    """

    require_explicit_opt_in: bool = False
    # Channels consent is tracked for. Tokens outside this set (phone, sms)
    # have no consent field and so never gate a stage on their own.
    consent_tracked_channels: List[str] = Field(
        default_factory=lambda: ["whatsapp", "email"]
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

REVOPS_GROUP_MODELS: Dict[RevOpsConfigGroup, Type[BaseModel]] = {
    RevOpsConfigGroup.LEAD_SCORING: LeadScoringSettings,
    RevOpsConfigGroup.NURTURE: NurtureSettings,
    RevOpsConfigGroup.CONSENT_POLICY: ConsentPolicySettings,
}


def revops_default_payload(group: RevOpsConfigGroup) -> Dict[str, Any]:
    """The code default for a group, as a plain dict."""
    return REVOPS_GROUP_MODELS[group]().model_dump(mode="json")


# ---------------------------------------------------------------------------
# API payloads
# ---------------------------------------------------------------------------


class RevOpsConfigSource(str, Enum):
    """Where a resolved group's values actually came from."""

    CAMPUS = "CAMPUS"
    ORG = "ORG"
    DEFAULT = "DEFAULT"


class ResolvedRevOpsGroup(BaseModel):
    group: RevOpsConfigGroup
    source: RevOpsConfigSource
    values: Dict[str, Any]
    updated_at: Optional[str] = None


class RevOpsConfigRead(BaseModel):
    org_id: int
    campus_id: Optional[int] = None
    groups: List[ResolvedRevOpsGroup]


class RevOpsConfigUpdate(BaseModel):
    """Write one group. `values` is validated against that group's model."""

    values: Dict[str, Any]
