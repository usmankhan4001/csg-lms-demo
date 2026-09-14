"""Schemas for staff offboarding, appraisal and payroll approval."""

import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.db.sms_hr_extended import (
    AppraisalOutcome,
    AppraisalStatus,
    OffboardingReason,
    PayrollActionType,
)


# ── Offboarding ──


class StaffOffboardingRequest(BaseModel):
    """Offboard one staff member.

    `successor_user_id` is optional and NOT inferred. Picking a replacement
    teacher automatically would mean guessing who inherits a class, which is a
    staffing decision a school makes deliberately. Omitted, sections are
    released to unassigned and reported; timetable slots cannot be released at
    all (teacher_id is NOT NULL) so they are reported as outstanding.
    """

    effective_date: datetime.date
    reason: OffboardingReason
    notes: Optional[str] = None
    successor_user_id: Optional[int] = Field(
        default=None,
        description=(
            "Learnhouse user id inheriting this staff member's class sections "
            "and timetable slots. Omit to leave them for manual reassignment."
        ),
    )
    revoke_roles: bool = Field(
        default=True,
        description=(
            "Deactivate the person's school role grants. Default true: a "
            "departed employee retaining access is the whole point of this "
            "operation."
        ),
    )


class StaffOffboardingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    staff_id: int
    staff_user_id: Optional[int]
    campus_id: Optional[int]
    effective_date: datetime.date
    reason: OffboardingReason
    notes: Optional[str]
    roles_revoked: int
    sections_released: int
    sections_reassigned: int
    timetable_slots_reassigned: int
    timetable_slots_outstanding: int
    initiated_by_user_id: Optional[int]
    created_at: datetime.datetime


class OffboardingOutcome(BaseModel):
    """What the cascade did, returned to the caller.

    `timetable_slots_outstanding` is surfaced separately from the counts that
    succeeded because it is WORK REMAINING, not a result. A departed teacher
    still attached to live timetable rows must be visible, not buried in a
    success message.
    """

    offboarding: StaffOffboardingRead
    outstanding_timetable_slot_ids: List[int] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ── Appraisal ──


class StaffAppraisalCreate(BaseModel):
    staff_id: int
    period_start: datetime.date
    period_end: datetime.date
    outcome: Optional[AppraisalOutcome] = None
    strengths: Optional[str] = None
    development_areas: Optional[str] = None
    objectives: Optional[str] = None


class StaffAppraisalUpdate(BaseModel):
    outcome: Optional[AppraisalOutcome] = None
    strengths: Optional[str] = None
    development_areas: Optional[str] = None
    objectives: Optional[str] = None


class StaffAppraisalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    staff_id: int
    campus_id: Optional[int]
    period_start: datetime.date
    period_end: datetime.date
    outcome: Optional[AppraisalOutcome]
    strengths: Optional[str]
    development_areas: Optional[str]
    objectives: Optional[str]
    status: AppraisalStatus
    reviewer_user_id: int
    shared_at: Optional[datetime.datetime]
    acknowledged_at: Optional[datetime.datetime]
    created_at: datetime.datetime


# ── Payroll approval ──


class PayrollActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slip_id: int
    staff_id: int
    campus_id: Optional[int]
    action: PayrollActionType
    net_salary_at_action: Optional[float]
    note: Optional[str]
    actor_user_id: Optional[int]
    actor_label: Optional[str]
    created_at: datetime.datetime


class PayrollApprovalRequest(BaseModel):
    slip_ids: List[int] = Field(
        ...,
        min_length=1,
        description=(
            "Explicit slip ids, never a whole run by filter. A payroll batch "
            "is a moving target and approving by filter could sweep in a slip "
            "generated after the reviewer last looked."
        ),
    )
    note: Optional[str] = None


class PayrollApprovalOutcome(BaseModel):
    """Per-slip result. A bad slip is reported, not raised, so one failure
    cannot abort an entire payroll review half-way through."""

    slip_id: int
    outcome: str
    detail: Optional[str] = None


class PayrollApprovalResponse(BaseModel):
    results: List[PayrollApprovalOutcome]
