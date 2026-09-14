"""
M19 Reports & Analytics (cross-module).

The one place that answers "how is the school doing" across attendance,
grades, fees and admissions, instead of four modules each showing a slice.

Two things worth knowing before editing:

1. **This module owns no data and computes no grades.** Everything is derived
   in services/sms/reports.py from the source modules' own tables, and the
   grade scale comes from the gradebook's `resolve_letter_and_gpa`. Do not add
   a second computation here.

2. **A report over no data reports no data.** Rates come back as `null` with a
   `no_data_reason`, never 0.0 -- see schemas/sms_reports.py. "0% attendance"
   and "no roll-call taken" lead a principal to opposite decisions.
"""

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    require_roles,
)
from src.schemas.sms_reports import (
    AdmissionsFunnelReport,
    AttendanceReport,
    FeeCollectionReport,
    GradeDistributionReport,
    SchoolOverviewReport,
)
from src.security.features_utils.dependencies import require_sms_reports_feature
from src.services.sms.reports import (
    compute_admissions_funnel,
    compute_attendance_report,
    compute_fee_collection,
    compute_grade_distribution,
    compute_school_overview,
)

# School-admin and above only. Deliberately NOT teacher-wide: this aggregates
# fee collection and admissions alongside academics, which is principal/office
# data rather than something every class teacher should read.
router = APIRouter(dependencies=[Depends(require_sms_reports_feature)])

_REPORT_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN]


def _effective_campus_id(
    principal: KeycloakUserPrincipal, requested: Optional[int]
) -> Optional[int]:
    """Resolve which campus a report covers.

    `require_campus_access` only rejects an explicit mismatch, so an UNSCOPED
    request would otherwise let a campus-bound school admin read every campus
    in the org. A request with no campus therefore falls back to the caller's
    own campus; only a SUPER_ADMIN (who has no single campus) sees all of them.
    """
    if requested is not None:
        if not principal.is_superadmin and principal.campus_id is not None:
            # A mismatch here is already a 403 from require_campus_access; this
            # is belt-and-braces for callers mounted without it.
            return principal.campus_id if principal.campus_id != requested else requested
        return requested
    if principal.is_superadmin:
        return None
    return principal.campus_id


@router.get(
    "/overview",
    response_model=SchoolOverviewReport,
    summary="Whole-school overview across attendance, grades, fees and admissions",
    description=(
        "The principal's single view. Each section names the module it came "
        "from. Any figure that cannot be computed comes back as null with a "
        "stated reason rather than as zero, and those reasons are collected "
        "into `warnings` so an empty section is never mistaken for a bad result."
    ),
)
async def get_school_overview(
    campus_id: Optional[int] = Query(
        default=None,
        description="Campus to report on. Defaults to the caller's own campus; only a super-admin may omit it to see all.",
    ),
    date_from: Optional[datetime.date] = Query(default=None, description="Start of the reporting window (inclusive)."),
    date_to: Optional[datetime.date] = Query(default=None, description="End of the reporting window (inclusive)."),
    academic_term_id: Optional[int] = Query(default=None, description="Restrict grade figures to one term."),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_REPORT_ROLES)),
) -> SchoolOverviewReport:
    return await compute_school_overview(
        session,
        campus_id=_effective_campus_id(principal, campus_id),
        date_from=date_from,
        date_to=date_to,
        academic_term_id=academic_term_id,
    )


@router.get(
    "/attendance",
    response_model=AttendanceReport,
    summary="Attendance rate over a period",
    description=(
        "Rate is (present + late) / (present + absent + late). LATE counts as "
        "attending because the student was in the room; EXCUSED is excluded "
        "from both sides so an authorised absence neither flatters nor "
        "penalises the rate."
    ),
)
async def get_attendance_report(
    campus_id: Optional[int] = Query(default=None),
    date_from: Optional[datetime.date] = Query(default=None),
    date_to: Optional[datetime.date] = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_REPORT_ROLES)),
) -> AttendanceReport:
    return await compute_attendance_report(
        session,
        campus_id=_effective_campus_id(principal, campus_id),
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/grades",
    response_model=GradeDistributionReport,
    summary="Grade distribution and averages",
    description=(
        "Letter grades and GPA come from the gradebook's own scale resolver, "
        "so this can never disagree with a report card."
    ),
)
async def get_grade_distribution(
    campus_id: Optional[int] = Query(default=None),
    academic_term_id: Optional[int] = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_REPORT_ROLES)),
) -> GradeDistributionReport:
    return await compute_grade_distribution(
        session,
        campus_id=_effective_campus_id(principal, campus_id),
        academic_term_id=academic_term_id,
    )


@router.get(
    "/fees",
    response_model=FeeCollectionReport,
    summary="Fee collection vs outstanding",
    description="Cancelled vouchers are excluded from both invoiced and collected.",
)
async def get_fee_collection(
    campus_id: Optional[int] = Query(default=None),
    date_from: Optional[datetime.date] = Query(default=None),
    date_to: Optional[datetime.date] = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_REPORT_ROLES)),
) -> FeeCollectionReport:
    return await compute_fee_collection(
        session,
        campus_id=_effective_campus_id(principal, campus_id),
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/admissions",
    response_model=AdmissionsFunnelReport,
    summary="Admissions funnel occupancy and conversion",
    description=(
        "Conversion is enrolled / (enrolled + lost). Inquiries still moving "
        "through the funnel are excluded from the denominator, so an active "
        "pipeline does not depress the rate."
    ),
)
async def get_admissions_funnel(
    campus_id: Optional[int] = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_REPORT_ROLES)),
) -> AdmissionsFunnelReport:
    return await compute_admissions_funnel(
        session, campus_id=_effective_campus_id(principal, campus_id)
    )
