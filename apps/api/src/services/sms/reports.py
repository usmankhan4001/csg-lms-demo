"""
M19 cross-module reporting.

Aggregates what four separate modules already record -- attendance, grades,
fees, admissions -- into the one view a principal actually opens. It OWNS no
data and computes no grades of its own: `resolve_letter_and_gpa` is imported
from services/sms/gradebook.py so there is exactly one grading engine. Two
engines that can disagree would be far worse than one gap.

Every function here returns `Metric.absent(...)` rather than 0.0 when there is
nothing to compute from. See schemas/sms_reports.py for why that distinction
is load-bearing.
"""

import datetime
import logging
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_attendance import AttendanceStatus, StudentAttendance
from src.db.sms_campus import Campus, ClassSection, StudentEnrollment
from src.db.sms_fees import StudentFeeVoucher, VoucherStatus
from src.db.sms_gradebook import AssessmentPlan, GradebookEntry
from src.db.sms_revops import AdmissionsLead, LeadStage
from src.schemas.sms_reports import (
    AdmissionsFunnelReport,
    AttendanceReport,
    FeeCollectionReport,
    GradeDistributionReport,
    Metric,
    SchoolOverviewReport,
)
from src.services.sms.gradebook import resolve_letter_and_gpa

logger = logging.getLogger(__name__)


async def _campus_section_ids(db_session: AsyncSession, campus_id: Optional[int]) -> Optional[List[int]]:
    """Section ids for a campus, or None meaning "do not filter by campus".

    Returning None rather than [] for the unscoped case matters: an empty list
    is a real answer (a campus with no sections) and must narrow the query to
    nothing, whereas None must not narrow it at all.
    """
    if campus_id is None:
        return None
    rows = await db_session.execute(
        select(ClassSection.id).where(ClassSection.campus_id == campus_id)
    )
    return list(rows.scalars().all())


async def _campus_student_ids(db_session: AsyncSession, campus_id: Optional[int]) -> Optional[List[int]]:
    """Distinct enrolled student ids for a campus, or None when unscoped."""
    if campus_id is None:
        return None
    rows = await db_session.execute(
        select(StudentEnrollment.student_id)
        .join(ClassSection, ClassSection.id == StudentEnrollment.section_id)
        .where(ClassSection.campus_id == campus_id)
        .distinct()
    )
    return list(rows.scalars().all())


async def compute_attendance_report(
    db_session: AsyncSession,
    *,
    campus_id: Optional[int] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
) -> AttendanceReport:
    """Attendance rate = (present + late) / marked records, over the range.

    LATE counts as attending: the student was in the room. EXCUSED is excluded
    from the numerator AND the denominator -- an authorised absence should
    neither flatter nor penalise the rate.
    """
    stmt = select(StudentAttendance.status, func.count()).group_by(StudentAttendance.status)

    section_ids = await _campus_section_ids(db_session, campus_id)
    if section_ids is not None:
        if not section_ids:
            return AttendanceReport(
                attendance_rate=Metric.absent(
                    "This campus has no class sections yet, so no attendance can have been taken."
                )
            )
        stmt = stmt.where(StudentAttendance.section_id.in_(section_ids))
    if date_from is not None:
        stmt = stmt.where(StudentAttendance.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(StudentAttendance.date <= date_to)

    counts: Dict[str, int] = {}
    for status_value, count in (await db_session.execute(stmt)).all():
        key = status_value.value if hasattr(status_value, "value") else str(status_value)
        counts[key] = int(count)

    present = counts.get(AttendanceStatus.PRESENT.value, 0)
    absent = counts.get(AttendanceStatus.ABSENT.value, 0)
    late = counts.get(AttendanceStatus.LATE.value, 0)
    excused = counts.get(AttendanceStatus.EXCUSED.value, 0)
    total_marked = present + absent + late + excused

    countable = present + absent + late
    if countable == 0:
        reason = (
            "No roll-call has been taken in this period."
            if total_marked == 0
            else "Every record in this period is an excused absence, which is not counted either way."
        )
        rate = Metric.absent(reason)
    else:
        rate = Metric.of(round((present + late) / countable * 100.0, 1), countable)

    return AttendanceReport(
        attendance_rate=rate,
        present_count=present,
        absent_count=absent,
        late_count=late,
        excused_count=excused,
        records_counted=total_marked,
    )


async def compute_grade_distribution(
    db_session: AsyncSession,
    *,
    campus_id: Optional[int] = None,
    academic_term_id: Optional[int] = None,
) -> GradeDistributionReport:
    """Grade spread across recorded gradebook entries.

    Letter and GPA come from the gradebook's own `resolve_letter_and_gpa`, not
    from a second scale defined here.
    """
    stmt = select(GradebookEntry.raw_score, GradebookEntry.max_score).join(
        AssessmentPlan, AssessmentPlan.id == GradebookEntry.assessment_plan_id
    )

    section_ids = await _campus_section_ids(db_session, campus_id)
    if section_ids is not None:
        if not section_ids:
            reason = "This campus has no class sections yet."
            return GradeDistributionReport(
                average_percentage=Metric.absent(reason),
                average_gpa=Metric.absent(reason, unit="gpa"),
            )
        stmt = stmt.where(AssessmentPlan.section_id.in_(section_ids))
    if academic_term_id is not None:
        stmt = stmt.where(AssessmentPlan.academic_term_id == academic_term_id)

    rows = (await db_session.execute(stmt)).all()
    if not rows:
        reason = "No marks have been recorded for this selection yet."
        return GradeDistributionReport(
            average_percentage=Metric.absent(reason),
            average_gpa=Metric.absent(reason, unit="gpa"),
        )

    percentages: List[float] = []
    gpa_points: List[float] = []
    distribution: Dict[str, int] = {}
    for raw_score, max_score in rows:
        if not max_score:
            # A zero/absent max score cannot yield a percentage. Skip it rather
            # than dividing by zero or inventing a denominator.
            continue
        pct = float(raw_score) / float(max_score) * 100.0
        letter, gpa = resolve_letter_and_gpa(pct)
        percentages.append(pct)
        gpa_points.append(gpa)
        distribution[letter] = distribution.get(letter, 0) + 1

    if not percentages:
        reason = "Marks exist but none carry a usable maximum score, so no percentage can be computed."
        return GradeDistributionReport(
            average_percentage=Metric.absent(reason),
            average_gpa=Metric.absent(reason, unit="gpa"),
            entries_counted=len(rows),
        )

    n = len(percentages)
    return GradeDistributionReport(
        average_percentage=Metric.of(round(sum(percentages) / n, 1), n),
        average_gpa=Metric.of(round(sum(gpa_points) / n, 2), n, unit="gpa"),
        letter_distribution=distribution,
        entries_counted=n,
    )


async def compute_fee_collection(
    db_session: AsyncSession,
    *,
    campus_id: Optional[int] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
) -> FeeCollectionReport:
    """Collected vs invoiced. CANCELLED vouchers are excluded from both sides."""
    stmt = select(
        StudentFeeVoucher.total_amount,
        StudentFeeVoucher.paid_amount,
        StudentFeeVoucher.status,
    ).where(StudentFeeVoucher.status != VoucherStatus.CANCELLED)

    student_ids = await _campus_student_ids(db_session, campus_id)
    if student_ids is not None:
        if not student_ids:
            return FeeCollectionReport(
                collection_rate=Metric.absent(
                    "No students are enrolled at this campus, so nothing has been invoiced."
                )
            )
        stmt = stmt.where(StudentFeeVoucher.student_id.in_(student_ids))
    if date_from is not None:
        stmt = stmt.where(StudentFeeVoucher.issue_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(StudentFeeVoucher.issue_date <= date_to)

    rows = (await db_session.execute(stmt)).all()
    if not rows:
        return FeeCollectionReport(
            collection_rate=Metric.absent("No fee vouchers have been issued for this selection.")
        )

    invoiced = sum(float(r[0] or 0.0) for r in rows)
    collected = sum(float(r[1] or 0.0) for r in rows)
    breakdown: Dict[str, int] = {}
    for _, _, status_value in rows:
        key = status_value.value if hasattr(status_value, "value") else str(status_value)
        breakdown[key] = breakdown.get(key, 0) + 1

    if invoiced <= 0:
        # Vouchers exist but bill nothing: a rate would divide by zero, and
        # "0% collected" would wrongly read as a collections failure.
        rate = Metric.absent(
            "Vouchers exist for this selection but none carry an amount, so there is nothing to collect."
        )
    else:
        rate = Metric.of(round(collected / invoiced * 100.0, 1), len(rows))

    return FeeCollectionReport(
        collection_rate=rate,
        total_invoiced=round(invoiced, 2),
        total_collected=round(collected, 2),
        total_outstanding=round(invoiced - collected, 2),
        voucher_count=len(rows),
        status_breakdown=breakdown,
    )


async def compute_admissions_funnel(
    db_session: AsyncSession,
    *,
    campus_id: Optional[int] = None,
) -> AdmissionsFunnelReport:
    """Funnel occupancy and conversion.

    Conversion = enrolled / (leads that reached an outcome). Leads still moving
    through the funnel are excluded from the denominator: counting them as
    not-yet-converted would understate conversion purely because the funnel is
    still working.
    """
    stmt = select(AdmissionsLead.stage, func.count()).group_by(AdmissionsLead.stage)
    if campus_id is not None:
        stmt = stmt.where(AdmissionsLead.campus_id == campus_id)

    stage_counts: Dict[str, int] = {}
    for stage_value, count in (await db_session.execute(stmt)).all():
        key = stage_value.value if hasattr(stage_value, "value") else str(stage_value)
        stage_counts[key] = int(count)

    total = sum(stage_counts.values())
    if total == 0:
        return AdmissionsFunnelReport(
            conversion_rate=Metric.absent(
                "No admissions inquiries have been recorded for this selection."
            )
        )

    enrolled = stage_counts.get(LeadStage.ENROLLED.value, 0)
    lost = stage_counts.get(LeadStage.LOST.value, 0)
    stalled = stage_counts.get(LeadStage.STALLED.value, 0)

    decided = enrolled + lost
    if decided == 0:
        rate = Metric.absent(
            "Every inquiry is still in progress, so no conversion rate can be computed yet."
        )
    else:
        rate = Metric.of(round(enrolled / decided * 100.0, 1), decided)

    return AdmissionsFunnelReport(
        conversion_rate=rate,
        stage_counts=stage_counts,
        total_leads=total,
        enrolled_count=enrolled,
        lost_count=lost,
        stalled_count=stalled,
    )


async def compute_school_overview(
    db_session: AsyncSession,
    *,
    campus_id: Optional[int] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
    academic_term_id: Optional[int] = None,
) -> SchoolOverviewReport:
    """The four reports in one payload, plus what could not be answered."""
    campus_name: Optional[str] = None
    if campus_id is not None:
        campus_name = (
            await db_session.execute(select(Campus.name).where(Campus.id == campus_id))
        ).scalar_one_or_none()

    attendance = await compute_attendance_report(
        db_session, campus_id=campus_id, date_from=date_from, date_to=date_to
    )
    grades = await compute_grade_distribution(
        db_session, campus_id=campus_id, academic_term_id=academic_term_id
    )
    fees = await compute_fee_collection(
        db_session, campus_id=campus_id, date_from=date_from, date_to=date_to
    )
    admissions = await compute_admissions_funnel(db_session, campus_id=campus_id)

    section_ids = await _campus_section_ids(db_session, campus_id)
    student_ids = await _campus_student_ids(db_session, campus_id)
    if section_ids is None:
        section_ids = list(
            (await db_session.execute(select(ClassSection.id))).scalars().all()
        )
    if student_ids is None:
        student_ids = list(
            (await db_session.execute(select(StudentEnrollment.student_id).distinct()))
            .scalars()
            .all()
        )

    # Surfaced rather than left as a silent blank: a missing section reads as a
    # zero if nobody says why it is missing.
    warnings = [
        m.no_data_reason
        for m in (
            attendance.attendance_rate,
            grades.average_percentage,
            fees.collection_rate,
            admissions.conversion_rate,
        )
        if not m.has_data and m.no_data_reason
    ]

    return SchoolOverviewReport(
        campus_id=campus_id,
        campus_name=campus_name,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        attendance=attendance,
        grades=grades,
        fees=fees,
        admissions=admissions,
        sections_covered=len(section_ids),
        students_covered=len(student_ids),
        warnings=warnings,
    )
