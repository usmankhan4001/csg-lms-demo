import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GradeInterval(BaseModel):
    grade: str
    min_percentage: float
    max_percentage: float
    gpa_point: float


class GradingScaleBase(BaseModel):
    name: str
    description: Optional[str] = None
    intervals: List[GradeInterval] = Field(default_factory=list)
    is_default: bool = False


class GradingScaleCreate(GradingScaleBase):
    pass


class GradingScaleRead(GradingScaleBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AssessmentPlanBase(BaseModel):
    course_id: int
    section_id: Optional[int] = None
    academic_term_id: Optional[int] = None
    assessment_name: str
    weight_percentage: float = Field(..., ge=0.0, le=100.0)
    max_score: float = Field(default=100.0, gt=0.0)


class AssessmentPlanCreate(AssessmentPlanBase):
    pass


class AssessmentPlanRead(AssessmentPlanBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class GradebookEntryInput(BaseModel):
    student_id: int
    raw_score: float = Field(..., ge=0.0)
    remarks: Optional[str] = None


class BatchGradebookEntryRequest(BaseModel):
    assessment_plan_id: int
    entries: List[GradebookEntryInput]
    graded_by: Optional[int] = None
    # Recorded on the audit trail, not on the grade itself. A correction
    # without a stated reason is still recorded -- the reason is optional
    # because requiring it would tempt staff into typing "." to get past it.
    reason: Optional[str] = None


class GradebookEntryRead(BaseModel):
    id: int
    student_id: int
    assessment_plan_id: int
    raw_score: float
    max_score: float
    weighted_score: Optional[float] = None
    letter_grade: Optional[str] = None
    gpa_point: Optional[float] = None
    remarks: Optional[str] = None
    graded_by: Optional[int] = None
    graded_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class SectionGradebookEntriesResponse(BaseModel):
    """Saved marks for a section, so the grade-entry matrix can pre-load.

    `entries` contains ONLY marks that were actually recorded. A student with
    no entry for an assessment simply has no row here -- there is deliberately
    no zero-filled placeholder, because on a report card "no mark yet" and
    "scored 0" mean opposite things and must stay distinguishable.
    """

    section_id: int
    assessment_plan_ids: List[int]
    entries: List["GradebookEntryRead"] = Field(default_factory=list)


class CourseGradeSummary(BaseModel):
    course_id: int
    course_name: Optional[str] = None
    credits: float = 3.0
    total_raw_percentage: float
    total_weighted_percentage: float
    letter_grade: str
    gpa_point: float
    # False when nothing has been marked for this course yet. Such a course
    # must be EXCLUDED from the cumulative GPA rather than counted as 0.0
    # quality points over its credits, which silently dragged every average
    # down and made unmarked coursework look like failed coursework.
    has_grades: bool = True
    assessment_breakdown: List[Dict[str, Any]] = Field(default_factory=list)


class ReportCardStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"


class StudentTermReportCardResponse(BaseModel):
    student_id: int
    section_id: int
    academic_term_id: int
    total_credits: float
    # None when the student has no graded credits. NOT 0.0 and NOT "F": a
    # student with nothing marked yet has no grade, and reporting one as a
    # measured value put a fabricated F in front of parents.
    cumulative_gpa: Optional[float] = None
    overall_letter_grade: Optional[str] = None
    remarks: Optional[str] = None
    courses: List[CourseGradeSummary]
    generated_at: datetime.datetime
    # The persisted record this computation was upserted into. Callers need it
    # to reach the send/PDF endpoints, which key on a report-card id: without
    # it the only source of an id was the draft POST response, so a card sent
    # in an earlier session was unreachable and displayed as "not generated
    # yet". TermReportCard is unique on (student_id, academic_term_id), so one
    # lookup resolves it -- no list endpoint required.
    report_card_id: Optional[int] = None
    report_card_status: Optional["ReportCardStatus"] = None


# ---------------------------------------------------------------------------
# Report-card draft -> sent distribution lifecycle (Phase 4, Part A.4)
# ---------------------------------------------------------------------------

class GenerateReportCardDraftRequest(BaseModel):
    section_id: int
    academic_term_id: int
    # Whether to (re)generate the AI-assisted narrative comment alongside the
    # GPA/grade recalculation. False lets a teacher refresh grade data without
    # spending an AI call / clobbering a narrative they already hand-edited.
    generate_narrative: bool = True


class ReportCardDraftUpdate(BaseModel):
    """Teacher edits to a still-DRAFT report card. Both fields optional so a
    PATCH can touch just one."""
    ai_narrative: Optional[str] = None
    remarks: Optional[str] = None


class TermReportCardRecordRead(BaseModel):
    """The persisted report-card record, including its draft/sent lifecycle
    state -- distinct from `StudentTermReportCardResponse`, which is the
    on-the-fly GPA-calculation preview returned by the pre-existing
    GET /report-card/student/{student_id} endpoint."""
    id: int
    student_id: int
    section_id: int
    academic_term_id: int
    status: ReportCardStatus
    total_credits: float
    # None when total_credits is 0. The stored TermReportCard.gpa column is
    # NOT NULL so it holds 0.0 for an ungraded student; that is a storage
    # artefact, not a measured grade, and must not surface as one.
    cumulative_gpa: Optional[float] = None
    overall_letter_grade: Optional[str] = None
    remarks: Optional[str] = None
    ai_narrative: Optional[str] = None
    courses: List[CourseGradeSummary] = Field(default_factory=list)
    calculated_at: datetime.datetime
    sent_at: Optional[datetime.datetime] = None
    sent_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Whole-section term-end operations
# ---------------------------------------------------------------------------


class BatchReportCardDraftRequest(BaseModel):
    section_id: int
    academic_term_id: int
    generate_narrative: bool = True


class BatchReportCardSendRequest(BaseModel):
    """Explicit ids, never a section -- see the endpoint docstring for why a
    section-wide blind send is the one thing that cannot be recalled."""

    report_card_ids: List[int] = Field(..., min_length=1)


class RecalculateReportCardsRequest(BaseModel):
    section_id: int
    academic_term_id: int


class BatchReportCardOutcome(BaseModel):
    """What actually happened to one student's card in a batch run.

    An outcome string rather than a success count: at term end a teacher needs
    to know WHICH students were skipped and why, not that "27 of 30 succeeded".
    `drafted_ungraded` is deliberately distinct from `drafted` -- a student
    with nothing marked has no grade, and that must be visible before anybody
    presses send.
    """

    student_id: Optional[int] = None
    report_card_id: Optional[int] = None
    outcome: str
    detail: Optional[str] = None
    # Present only on a recalculation, so a teacher can see what moved.
    previous_cumulative_gpa: Optional[float] = None
    cumulative_gpa: Optional[float] = None


class BatchReportCardResponse(BaseModel):
    results: List[BatchReportCardOutcome] = Field(default_factory=list)


class GradeChangeEventRead(BaseModel):
    """One append-only entry in a mark's audit trail.

    `previous_raw_score` is None on a "created" row -- there was no previous
    mark. That is deliberately distinct from 0.0, which is a real score.
    """

    id: int
    gradebook_entry_id: int
    student_id: int
    assessment_plan_id: int
    section_id: Optional[int] = None
    action: str
    previous_raw_score: Optional[float] = None
    new_raw_score: float
    previous_letter_grade: Optional[str] = None
    new_letter_grade: Optional[str] = None
    max_score: float
    changed_by_user_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class GradeHistoryResponse(BaseModel):
    """Full change history for one gradebook entry, oldest first.

    Oldest-first because an audit trail is read as a narrative: what it was
    first, then what happened to it.
    """

    gradebook_entry_id: int
    student_id: int
    assessment_plan_id: int
    events: List[GradeChangeEventRead] = Field(default_factory=list)
