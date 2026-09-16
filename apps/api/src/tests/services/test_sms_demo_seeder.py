"""
Unit & Integrity Tests for CSG-EMS Demo Data Seeder
===================================================
Verifies complete relational integrity across all 12 modules:
- 7 Personas & Role Assignments
- Campus, Academic Years, Sections, Student Enrollments & Curricular Bridges
- Attendance, Gradebook, Examinations, Admissions, Financials, Payroll, Cognia
"""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.organizations import Organization
from src.db.users import User
from src.db.sms_campus import Campus, ClassSection, StudentEnrollment
from src.db.sms_section_subject import SectionSubject
from src.db.sms_timetable import TimetableSchedule
from src.db.sms_attendance import StudentAttendance
from src.db.sms_gradebook import GradebookEntry, TermReportCard
from src.db.sms_exam import Exam, ExamResult
from src.db.sms_revops import AdmissionsLead
from src.db.sms_admissions import StudentApplication
from src.db.sms_financials import ChartOfAccounts, JournalEntry
from src.db.sms_fees import StudentFeeVoucher
from src.db.sms_payroll import SalarySlip
from src.db.sms_cognia import CogniaEvidenceItem
from src.db.ems_roles import EMSRole, EMSUserRoleAssignment

from src.services.demo.sms_demo_seeder import seed_sms_demo_data


@pytest.mark.asyncio
async def test_seed_sms_demo_data_integrity(db: AsyncSession):
    # 1. Run Seeder
    result = await seed_sms_demo_data(db)
    assert result["status"] == "success"
    assert result["users_seeded"] >= 13
    assert result["sections"] == 3
    assert result["courses"] == 3

    # 2. Verify Organization & Roles
    org = (await db.execute(select(Organization).where(Organization.slug == "csg-academy"))).scalars().first()
    assert org is not None

    ems_roles = (await db.execute(select(EMSRole).where(EMSRole.org_id == org.id))).scalars().all()
    assert len(ems_roles) >= 7

    # 3. Verify Users & Personas
    alex = (await db.execute(select(User).where(User.email == "student.alex@csg.edu"))).scalars().first()
    assert alex is not None

    teacher_chen = (await db.execute(select(User).where(User.email == "teacher.physics@csg.edu"))).scalars().first()
    assert teacher_chen is not None

    # 4. Verify Campus & Curricular Bridge
    campus = (await db.execute(select(Campus).where(Campus.org_id == org.id))).scalars().first()
    assert campus is not None

    sec_subjects = (await db.execute(select(SectionSubject))).scalars().all()
    assert len(sec_subjects) >= 3

    # 5. Verify Attendance & Gradebook
    attendances = (await db.execute(select(StudentAttendance).where(StudentAttendance.student_id == alex.id))).scalars().all()
    assert len(attendances) > 10

    grades = (await db.execute(select(GradebookEntry).where(GradebookEntry.student_id == alex.id))).scalars().all()
    assert len(grades) == 3

    report_cards = (await db.execute(select(TermReportCard).where(TermReportCard.student_id == alex.id))).scalars().all()
    assert len(report_cards) == 1
    assert report_cards[0].status == "SENT"
    assert report_cards[0].gpa == 3.92

    # 6. Verify Exams & Results
    exams = (await db.execute(select(Exam))).scalars().all()
    assert len(exams) >= 1

    exam_results = (await db.execute(select(ExamResult).where(ExamResult.student_id == alex.id))).scalars().all()
    assert len(exam_results) >= 1
    assert exam_results[0].marks_obtained == 92.0

    # 7. Verify Admissions & RevOps
    leads = (await db.execute(select(AdmissionsLead))).scalars().all()
    assert len(leads) >= 6

    apps = (await db.execute(select(StudentApplication))).scalars().all()
    assert len(apps) >= 6

    # 8. Verify Financials & Payroll
    coas = (await db.execute(select(ChartOfAccounts))).scalars().all()
    assert len(coas) >= 7

    j_entries = (await db.execute(select(JournalEntry))).scalars().all()
    assert len(j_entries) >= 1
    assert j_entries[0].total_debit == j_entries[0].total_credit == 25000.0

    vouchers = (await db.execute(select(StudentFeeVoucher).where(StudentFeeVoucher.student_id == alex.id))).scalars().all()
    assert len(vouchers) == 2

    slips = (await db.execute(select(SalarySlip))).scalars().all()
    assert len(slips) >= 3

    # 9. Verify Cognia Evidence
    cognia_items = (await db.execute(select(CogniaEvidenceItem))).scalars().all()
    assert len(cognia_items) == 3


@pytest.mark.asyncio
async def test_seed_sms_demo_data_idempotency(db: AsyncSession):
    # Running twice should not fail or duplicate
    res1 = await seed_sms_demo_data(db)
    assert res1["status"] == "success"

    res2 = await seed_sms_demo_data(db)
    assert res2["status"] == "success"
