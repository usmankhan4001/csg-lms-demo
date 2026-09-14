"""
Tests for M19 cross-module reports.

The central thing under test is NOT arithmetic -- it is that a report over an
empty school says "nothing recorded" rather than "0%". This codebase has had
fabricated reporting torn out three times (a 4.0 GPA for a student with zero
grades; a parent digest inventing attendance; outbound copy naming a school
that does not exist), and a principal reading a fabricated 0% would act on it.
"""

import datetime

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import KeycloakUserPrincipal
from src.db.sms_attendance import AttendanceStatus, StudentAttendance
from src.db.sms_campus import Campus, ClassSection, StudentEnrollment
from src.db.sms_fees import StudentFeeVoucher, VoucherStatus
from src.db.sms_gradebook import AssessmentPlan, GradebookEntry
from src.db.sms_revops import AdmissionsLead, LeadSource, LeadStage
from src.routers.sms_reports import (
    _effective_campus_id,
    get_admissions_funnel,
    get_attendance_report,
    get_fee_collection,
    get_grade_distribution,
    get_school_overview,
)


def _principal(*, superadmin: bool = False, campus_id: int | None = 1) -> KeycloakUserPrincipal:
    roles = {"SUPER_ADMIN"} if superadmin else {"SCHOOL_ADMIN"}
    return KeycloakUserPrincipal(sub="u-report", org_id=1, campus_id=campus_id, roles=roles)


async def _make_campus(db: AsyncSession, name: str = "Lighthouse Main") -> Campus:
    campus = Campus(org_id=1, name=name, code=f"C-{name[:4]}", timezone="Asia/Karachi")
    db.add(campus)
    await db.commit()
    await db.refresh(campus)
    return campus


async def _make_section(db: AsyncSession, campus_id: int) -> ClassSection:
    section = ClassSection(
        campus_id=campus_id, grade_level="Grade 9", section_name="A", max_capacity=30
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section


# ---------------------------------------------------------------------------
# The rule: no data is not zero.
# ---------------------------------------------------------------------------


async def test_empty_school_reports_no_data_never_zero(db: AsyncSession):
    """A school with nothing recorded must not report 0% anything."""
    campus = await _make_campus(db)
    principal = _principal(campus_id=campus.id)

    overview = await get_school_overview(
        campus_id=campus.id,
        date_from=None,
        date_to=None,
        academic_term_id=None,
        session=db,
        principal=principal,
    )

    for metric in (
        overview.attendance.attendance_rate,
        overview.grades.average_percentage,
        overview.grades.average_gpa,
        overview.fees.collection_rate,
        overview.admissions.conversion_rate,
    ):
        assert metric.value is None, "a rate over no data must be null, not 0.0"
        assert metric.has_data is False
        assert metric.no_data_reason, "every absent metric must say why"
        assert metric.sample_size == 0

    # And the reasons are surfaced, so an empty panel is never read as a bad result.
    assert len(overview.warnings) == 4


async def test_zero_is_reported_as_zero_when_it_is_real(db: AsyncSession):
    """A genuine 0% (all absent) is a real answer and must NOT be nulled."""
    campus = await _make_campus(db, "Zero Campus")
    section = await _make_section(db, campus.id)
    today = datetime.date.today()
    for student_id in (101, 102):
        db.add(
            StudentAttendance(
                student_id=student_id,
                section_id=section.id,
                date=today,
                status=AttendanceStatus.ABSENT,
            )
        )
    await db.commit()

    report = await get_attendance_report(
        campus_id=campus.id,
        date_from=None,
        date_to=None,
        session=db,
        principal=_principal(campus_id=campus.id),
    )

    assert report.attendance_rate.has_data is True
    assert report.attendance_rate.value == 0.0, "everyone absent really is 0%"
    assert report.attendance_rate.sample_size == 2
    assert report.absent_count == 2


async def test_excused_only_is_not_zero_percent(db: AsyncSession):
    """Excused absences alone leave the rate uncomputable, not 0%."""
    campus = await _make_campus(db, "Excused Campus")
    section = await _make_section(db, campus.id)
    db.add(
        StudentAttendance(
            student_id=201,
            section_id=section.id,
            date=datetime.date.today(),
            status=AttendanceStatus.EXCUSED,
        )
    )
    await db.commit()

    report = await get_attendance_report(
        campus_id=campus.id,
        date_from=None,
        date_to=None,
        session=db,
        principal=_principal(campus_id=campus.id),
    )
    assert report.attendance_rate.value is None
    assert report.excused_count == 1
    assert "excused" in (report.attendance_rate.no_data_reason or "").lower()


# ---------------------------------------------------------------------------
# Real figures, and reuse of the gradebook's own scale.
# ---------------------------------------------------------------------------


async def test_attendance_rate_counts_late_as_attending(db: AsyncSession):
    campus = await _make_campus(db, "Attend Campus")
    section = await _make_section(db, campus.id)
    today = datetime.date.today()
    rows = [
        (301, AttendanceStatus.PRESENT),
        (302, AttendanceStatus.PRESENT),
        (303, AttendanceStatus.LATE),
        (304, AttendanceStatus.ABSENT),
    ]
    for student_id, status in rows:
        db.add(
            StudentAttendance(
                student_id=student_id, section_id=section.id, date=today, status=status
            )
        )
    await db.commit()

    report = await get_attendance_report(
        campus_id=campus.id,
        date_from=None,
        date_to=None,
        session=db,
        principal=_principal(campus_id=campus.id),
    )
    # (2 present + 1 late) / 4 countable = 75%
    assert report.attendance_rate.value == 75.0
    assert report.attendance_rate.sample_size == 4
    assert report.late_count == 1


async def test_grade_distribution_uses_the_gradebook_scale(db: AsyncSession):
    """Letters must match resolve_letter_and_gpa, not a second scale."""
    from src.services.sms.gradebook import resolve_letter_and_gpa

    campus = await _make_campus(db, "Grade Campus")
    section = await _make_section(db, campus.id)
    plan = AssessmentPlan(
        course_id=1,
        section_id=section.id,
        assessment_name="Midterm",
        weight_percentage=100.0,
        max_score=100.0,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    db.add(GradebookEntry(student_id=401, assessment_plan_id=plan.id, raw_score=95.0, max_score=100.0))
    db.add(GradebookEntry(student_id=402, assessment_plan_id=plan.id, raw_score=85.0, max_score=100.0))
    await db.commit()

    report = await get_grade_distribution(
        campus_id=campus.id,
        academic_term_id=None,
        session=db,
        principal=_principal(campus_id=campus.id),
    )
    assert report.average_percentage.value == 90.0
    assert report.entries_counted == 2
    expected_top = resolve_letter_and_gpa(95.0)[0]
    assert expected_top in report.letter_distribution


async def test_fee_collection_excludes_cancelled(db: AsyncSession):
    campus = await _make_campus(db, "Fee Campus")
    section = await _make_section(db, campus.id)
    db.add(StudentEnrollment(student_id=501, section_id=section.id, academic_year_id=1))
    await db.commit()

    today = datetime.date.today()
    db.add(
        StudentFeeVoucher(
            student_id=501,
            voucher_no="V-REPORT-001",
            issue_date=today,
            due_date=today,
            total_amount=1000.0,
            paid_amount=250.0,
            status=VoucherStatus.PARTIAL,
        )
    )
    db.add(
        StudentFeeVoucher(
            student_id=501,
            voucher_no="V-REPORT-002",
            issue_date=today,
            due_date=today,
            total_amount=9999.0,
            paid_amount=0.0,
            status=VoucherStatus.CANCELLED,
        )
    )
    await db.commit()

    report = await get_fee_collection(
        campus_id=campus.id,
        date_from=None,
        date_to=None,
        session=db,
        principal=_principal(campus_id=campus.id),
    )
    assert report.total_invoiced == 1000.0, "cancelled voucher must not inflate invoiced"
    assert report.total_collected == 250.0
    assert report.total_outstanding == 750.0
    assert report.collection_rate.value == 25.0
    assert VoucherStatus.CANCELLED.value not in report.status_breakdown


async def test_admissions_conversion_excludes_in_progress_leads(db: AsyncSession):
    """An active pipeline must not depress the conversion rate."""
    campus = await _make_campus(db, "Funnel Campus")
    stages = [
        LeadStage.ENROLLED,
        LeadStage.LOST,
        LeadStage.CONTACTED,
        LeadStage.TOUR_BOOKED,
    ]
    for i, stage in enumerate(stages):
        db.add(
            AdmissionsLead(
                parent_name=f"Parent {i}",
                student_name=f"Lead {i}",
                email=f"lead{i}@example.com",
                phone=f"0300000000{i}",
                grade_applying_for="Grade 9",
                source=LeadSource.WALK_IN,
                stage=stage,
                campus_id=campus.id,
            )
        )
    await db.commit()

    report = await get_admissions_funnel(
        campus_id=campus.id, session=db, principal=_principal(campus_id=campus.id)
    )
    # 1 enrolled / (1 enrolled + 1 lost) = 50%, the two in-progress excluded.
    assert report.conversion_rate.value == 50.0
    assert report.conversion_rate.sample_size == 2
    assert report.total_leads == 4


async def test_all_leads_in_progress_gives_no_rate(db: AsyncSession):
    campus = await _make_campus(db, "InProgress Campus")
    db.add(
        AdmissionsLead(
            parent_name="Undecided Parent",
            student_name="Still Deciding",
            email="wip@example.com",
            phone="03001234567",
            grade_applying_for="Grade 1",
            source=LeadSource.WALK_IN,
            stage=LeadStage.CONTACTED,
            campus_id=campus.id,
        )
    )
    await db.commit()

    report = await get_admissions_funnel(
        campus_id=campus.id, session=db, principal=_principal(campus_id=campus.id)
    )
    assert report.conversion_rate.value is None
    assert report.total_leads == 1
    assert "still in progress" in (report.conversion_rate.no_data_reason or "").lower()


# ---------------------------------------------------------------------------
# Campus scoping.
# ---------------------------------------------------------------------------


async def test_campus_scoping_isolates_data(db: AsyncSession):
    """Campus A's attendance must not appear in Campus B's report."""
    campus_a = await _make_campus(db, "Alpha")
    campus_b = await _make_campus(db, "Beta")
    section_a = await _make_section(db, campus_a.id)
    db.add(
        StudentAttendance(
            student_id=601,
            section_id=section_a.id,
            date=datetime.date.today(),
            status=AttendanceStatus.PRESENT,
        )
    )
    await db.commit()

    report_b = await get_attendance_report(
        campus_id=campus_b.id,
        date_from=None,
        date_to=None,
        session=db,
        principal=_principal(superadmin=True, campus_id=None),
    )
    assert report_b.attendance_rate.value is None
    assert report_b.present_count == 0


def test_unscoped_request_falls_back_to_own_campus():
    """A campus-bound admin omitting campus_id must not silently see all campuses."""
    bound = _principal(campus_id=7)
    assert _effective_campus_id(bound, None) == 7

    # Only a super-admin, who has no single campus, sees everything.
    assert _effective_campus_id(_principal(superadmin=True, campus_id=None), None) is None


def test_campus_bound_admin_cannot_retarget_another_campus():
    bound = _principal(campus_id=7)
    assert _effective_campus_id(bound, 9) == 7, "must not honour a foreign campus_id"
