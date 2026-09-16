"""
CSG-EMS Comprehensive Demo Data Seeder
======================================
Populates coherent, interconnected demo data across all SMS-First modules
and embedded Learnhouse LMS:
- 7 Personas & Role Assignments
- Campus, Academic Years, Terms, Sections & Student Enrollments
- Embedded Courses, Chapters, Activities & Section-Subject Curricular Bridges
- Bell Schedule Periods & Timetable Schedules
- 30-Day Biometric Roll-Call Attendance
- Master Gradebook, Assessment Plans, SpeedGrader Marks & Report Cards
- CBT Exams, Questions & IRT 2PL Psychometrics
- Admissions CRM Pipeline, BANT Scoring & Matriculation
- Discipline Incidents & Pastoral Records
- Confidential Clinical / Counseling Records
- Double-Entry Chart of Accounts, Balanced Journal Entries & Fee Invoices
- Progressive Payroll, Staff Profiles & Salary Slips
- Cognia Accreditation Standards & Evidence Locker with Live AMI Index
"""

import datetime
import hashlib
import json
import logging
import os
import secrets
from typing import Optional, Dict, Any, List, Tuple
from uuid import uuid4

from sqlalchemy import select, delete
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.organizations import Organization
from src.db.users import User
from src.db.user_organizations import UserOrganization
from src.db.roles import Role
from src.security.security import security_hash_password
from src.security.rbac.constants import ADMIN_ROLE_ID

from src.db.sms_identity import SMSUserRole, SchoolRole, StudentGuardian
from src.db.ems_roles import (
    EMSRole,
    EMSPermissionRule,
    EMSUserRoleAssignment,
    ScopeLevel,
    ResourceDomain,
    CoreRoleSlug,
    DEFAULT_EMS_ROLE_SPECS,
    seed_default_ems_roles,
)
from src.db.sms_campus import (
    Campus,
    AcademicYear,
    AcademicTerm,
    ClassSection,
    StudentEnrollment,
)
from src.db.sms_section_subject import SectionSubject
from src.db.sms_timetable import ClassPeriod, TimetableSchedule, DayOfWeek
from src.db.sms_attendance import StudentAttendance, AttendanceStatus
from src.db.sms_gradebook import GradingScale, AssessmentPlan, GradebookEntry, TermReportCard
from src.db.sms_exam import (
    Exam,
    ExamStatus,
    ExamAttendanceStatus,
    ExamSectionSchedule,
    ExamResult,
    ExamIncident,
)
from src.db.sms_admissions import (
    StudentApplication,
    ApplicationStatus,
    ApplicationDocument,
    DocumentType,
    DocumentVerificationStatus,
    ApplicationAssessment,
    AssessmentOutcome,
    AdmissionDecision,
    AdmissionDecisionRecord,
)
from src.db.sms_revops import AdmissionsLead, LeadStage, LeadSource, LeadIntent, LeadActivityLog, ActivityType
from src.db.sms_discipline import DisciplinaryIncident, IncidentSeverityEnum, IncidentStatusEnum
from src.db.sms_counseling import CounselingSession, CounselingActivityLog
from src.db.sms_fees import FeeStructure, StudentFeeVoucher, VoucherStatus, PaymentMethod, FeePaymentReceipt
from src.db.sms_financials import ChartOfAccounts, AccountType, JournalEntry, JournalEntryLine
from src.db.sms_hr import StaffProfile, ContractType
from src.db.sms_payroll import SalaryStructure, SalarySlip, SalaryPaymentStatus
from src.db.sms_cognia import CogniaEvidenceItem, CogniaEvidenceStatus

from src.db.courses.courses import Course
from src.db.courses.chapters import Chapter
from src.db.courses.course_chapters import CourseChapter
from src.db.courses.activities import Activity, ActivityTypeEnum, ActivitySubTypeEnum
from src.db.courses.chapter_activities import ChapterActivity
from src.db.courses.blocks import Block

logger = logging.getLogger(__name__)

# The organization provisioned when the caller does not name one. Fixed rather
# than "whichever org has the lowest id": a missing slug used to resolve to
# org 1, so on any install that also holds real tenants a bare call seeded
# privileged demo accounts into a live school.
DEFAULT_DEMO_ORG_SLUG = "csg-academy"

# Password for the seeded personas. Unset (the default) means every run mints
# a fresh random password, returned once in the result. Setting it is an
# explicit opt-in for deployments that need a human to type a credential; it
# is never defaulted to a published string.
DEMO_PASSWORD_ENV = "LEARNHOUSE_DEMO_SEED_PASSWORD"

# Grants the seeded admin@csg.edu platform-wide superadmin. Off by default:
# the endpoint that reaches this seeder already requires a superadmin caller,
# so the seeded account needs org-scoped authority (its SMSUserRole
# SUPER_ADMIN / SCHOOL_ADMIN grants), not the ability to administer every
# tenant on the install.
DEMO_SUPERADMIN_ENV = "LEARNHOUSE_DEMO_SEED_SUPERADMIN"

# Learnhouse org membership handed to personas that are not the demo org's
# administrator. Same value the signup and join-org paths use for a plain
# member.
MEMBER_ROLE_ID = 4


def _env_flag(name: str) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _resolve_demo_password() -> Tuple[str, bool]:
    """Return ``(password, operator_supplied)`` for this seeding run.

    A hardcoded literal is never used: either the deployment opts in through
    ``DEMO_PASSWORD_ENV``, or a fresh secret is generated per run.
    """
    supplied = (os.environ.get(DEMO_PASSWORD_ENV) or "").strip()
    if supplied:
        return supplied, True
    return secrets.token_urlsafe(18), False


async def seed_sms_demo_data(db_session: AsyncSession, org_slug: Optional[str] = None) -> Dict[str, Any]:
    """
    Idempotently seeds comprehensive demo data into the target organization.
    """
    logger.info("Starting CSG-EMS comprehensive demo data seeding...")

    # 1. Resolve Target Organization
    #
    # A slug that was supplied must match a real organization. This used to
    # fall back to the lowest-id org, so a typo seeded demo data -- including
    # a privileged admin account -- into whichever tenant happened to be
    # oldest. A mismatch now fails loudly instead.
    target_org = None
    if org_slug:
        stmt = select(Organization).where(Organization.slug == org_slug)
        target_org = (await db_session.execute(stmt)).scalars().first()
        if not target_org:
            raise ValueError(
                f"No organization found with slug '{org_slug}'. Refusing to "
                f"seed demo data into a different organization."
            )
    else:
        # No slug given: provision the dedicated demo org, never org 1.
        stmt = select(Organization).where(Organization.slug == DEFAULT_DEMO_ORG_SLUG)
        target_org = (await db_session.execute(stmt)).scalars().first()

    if not target_org:
        # Create default demo organization
        target_org = Organization(
            name="CSG Global Academy",
            slug=DEFAULT_DEMO_ORG_SLUG,
            email="admissions@csg.edu",
            org_uuid=f"org_{uuid4()}",
            description="Autonomous K-12 & Higher Ed Demonstration Campus",
            creation_date=str(datetime.datetime.now(datetime.timezone.utc)),
            update_date=str(datetime.datetime.now(datetime.timezone.utc)),
        )
        db_session.add(target_org)
        await db_session.commit()
        await db_session.refresh(target_org)

    org_id = target_org.id
    assert org_id is not None
    logger.info(f"Seeding demo data into Org: {target_org.name} (id={org_id}, slug={target_org.slug})")

    # 2. Seed Dynamic EMS Roles
    await seed_default_ems_roles(db_session, org_id)

    # 3. Seed Users across the 7 Personas
    #
    # One password per run, generated unless the deployment opts into a known
    # one via DEMO_PASSWORD_ENV. It is never a hardcoded literal: a published
    # demo password is a published credential for every account seeded with
    # it, and this seeder is reachable outside the demo endpoint.
    demo_password, password_is_operator_supplied = _resolve_demo_password()
    default_pw_hash = security_hash_password(demo_password)

    grant_platform_superadmin = _env_flag(DEMO_SUPERADMIN_ENV)
    if grant_platform_superadmin:
        logger.warning(
            "%s is set: seeded admin@csg.edu will be a platform-wide "
            "superadmin. Do not enable this on an install holding real data.",
            DEMO_SUPERADMIN_ENV,
        )

    user_specs = [
        {
            "username": "dr.arthur",
            "email": "admin@csg.edu",
            "first_name": "Arthur",
            "last_name": "Pendelton",
            "roles": [SchoolRole.SUPER_ADMIN, SchoolRole.SCHOOL_ADMIN],
            "ems_role": CoreRoleSlug.SUPER_ADMIN.value,
            # Marks the platform-admin persona. It buys an org-scoped admin
            # seat (ADMIN_ROLE_ID) in the seeded org; platform-wide
            # superadmin additionally requires DEMO_SUPERADMIN_ENV.
            "is_superadmin": True,
        },
        {
            "username": "eleanor.vance",
            "email": "registrar@csg.edu",
            "first_name": "Eleanor",
            "last_name": "Vance",
            "roles": [SchoolRole.SCHOOL_ADMIN],
            "ems_role": CoreRoleSlug.SCHOOL_ADMIN.value,
            "is_superadmin": False,
        },
        {
            "username": "dr.albert.chen",
            "email": "teacher.physics@csg.edu",
            "first_name": "Albert",
            "last_name": "Chen",
            "roles": [SchoolRole.TEACHER],
            "ems_role": CoreRoleSlug.TEACHER.value,
            "is_superadmin": False,
        },
        {
            "username": "sarah.jenkins",
            "email": "teacher.math@csg.edu",
            "first_name": "Sarah",
            "last_name": "Jenkins",
            "roles": [SchoolRole.TEACHER],
            "ems_role": CoreRoleSlug.TEACHER.value,
            "is_superadmin": False,
        },
        {
            "username": "marcus.aurelius",
            "email": "teacher.humanities@csg.edu",
            "first_name": "Marcus",
            "last_name": "Aurelius",
            "roles": [SchoolRole.TEACHER],
            "ems_role": CoreRoleSlug.TEACHER.value,
            "is_superadmin": False,
        },
        {
            "username": "alex.mercer",
            "email": "student.alex@csg.edu",
            "first_name": "Alex",
            "last_name": "Mercer",
            "roles": [SchoolRole.STUDENT],
            "ems_role": CoreRoleSlug.STUDENT.value,
            "is_superadmin": False,
        },
        {
            "username": "maya.lin",
            "email": "student.maya@csg.edu",
            "first_name": "Maya",
            "last_name": "Lin",
            "roles": [SchoolRole.STUDENT],
            "ems_role": CoreRoleSlug.STUDENT.value,
            "is_superadmin": False,
        },
        {
            "username": "leo.vance",
            "email": "student.leo@csg.edu",
            "first_name": "Leo",
            "last_name": "Vance",
            "roles": [SchoolRole.STUDENT],
            "ems_role": CoreRoleSlug.STUDENT.value,
            "is_superadmin": False,
        },
        {
            "username": "sophia.davis",
            "email": "student.sophia@csg.edu",
            "first_name": "Sophia",
            "last_name": "Davis",
            "roles": [SchoolRole.STUDENT],
            "ems_role": CoreRoleSlug.STUDENT.value,
            "is_superadmin": False,
        },
        {
            "username": "robert.mercer",
            "email": "parent.alex@csg.edu",
            "first_name": "Robert",
            "last_name": "Mercer",
            "roles": [SchoolRole.PARENT],
            "ems_role": CoreRoleSlug.PARENT.value,
            "is_superadmin": False,
        },
        {
            "username": "david.lin",
            "email": "parent.maya@csg.edu",
            "first_name": "David",
            "last_name": "Lin",
            "roles": [SchoolRole.PARENT],
            "ems_role": CoreRoleSlug.PARENT.value,
            "is_superadmin": False,
        },
        {
            "username": "dr.evelyn.smith",
            "email": "counselor.drsmith@csg.edu",
            "first_name": "Evelyn",
            "last_name": "Smith",
            "roles": [SchoolRole.PSYCHOLOGIST],
            "ems_role": CoreRoleSlug.PSYCHOLOGIST.value,
            "is_superadmin": False,
        },
        {
            "username": "jonathan.miller",
            "email": "bursar.miller@csg.edu",
            "first_name": "Jonathan",
            "last_name": "Miller",
            "roles": [SchoolRole.STAFF],
            "ems_role": CoreRoleSlug.BURSAR.value,
            "is_superadmin": False,
        },
    ]

    seeded_users: Dict[str, User] = {}
    created_users: List[str] = []
    skipped_existing_users: List[str] = []
    for spec in user_specs:
        stmt = select(User).where(User.email == spec["email"])
        user = (await db_session.execute(stmt)).scalars().first()
        now_str = str(datetime.datetime.now(datetime.timezone.utc))
        if not user:
            user = User(
                username=spec["username"],
                email=spec["email"],
                first_name=spec["first_name"],
                last_name=spec["last_name"],
                password=default_pw_hash,
                email_verified=True,
                # Platform-wide superadmin is opt-in. The persona keeps its
                # org-scoped SMSUserRole grants either way.
                is_superadmin=(
                    bool(spec.get("is_superadmin", False))
                    and grant_platform_superadmin
                ),
                user_uuid=f"usr_{uuid4()}",
                creation_date=now_str,
                update_date=now_str,
            )
            db_session.add(user)
            await db_session.flush()
            await db_session.refresh(user)
            created_users.append(spec["email"])
        else:
            # An address that already exists is left completely alone -- no
            # password reset, no force-verify, no role grants. It may be a
            # real account that happens to hold one of these addresses, and
            # overwriting its credentials would hand it to anyone who knows
            # the demo password while escalating it in this org.
            skipped_existing_users.append(spec["email"])
            logger.warning(
                "Demo address %s already exists (user id=%s); leaving its "
                "credentials and role grants untouched.",
                spec["email"],
                user.id,
            )
            seeded_users[spec["email"]] = user
            continue

        seeded_users[spec["email"]] = user

        # Link to organization
        uo_stmt = select(UserOrganization).where(
            UserOrganization.user_id == user.id,
            UserOrganization.org_id == org_id,
        )
        uo = (await db_session.execute(uo_stmt)).scalars().first()
        if not uo:
            uo = UserOrganization(
                user_id=user.id,
                org_id=org_id,
                role_id=ADMIN_ROLE_ID
                if spec.get("is_superadmin", False)
                else MEMBER_ROLE_ID,
                creation_date=now_str,
                update_date=now_str,
            )
            db_session.add(uo)

        # Grant SMSUserRoles
        for r in spec["roles"]:
            sur_stmt = select(SMSUserRole).where(
                SMSUserRole.user_id == user.id,
                SMSUserRole.org_id == org_id,
                SMSUserRole.role == r,
            )
            sur = (await db_session.execute(sur_stmt)).scalars().first()
            if not sur:
                db_session.add(
                    SMSUserRole(
                        user_id=user.id,
                        org_id=org_id,
                        role=r,
                        is_active=True,
                    )
                )

        # Grant EMSUserRoleAssignment
        ems_role_stmt = select(EMSRole).where(EMSRole.slug == spec["ems_role"])
        ems_role = (await db_session.execute(ems_role_stmt)).scalars().first()
        if ems_role:
            assign_stmt = select(EMSUserRoleAssignment).where(
                EMSUserRoleAssignment.user_id == user.id,
                EMSUserRoleAssignment.role_id == ems_role.id,
                EMSUserRoleAssignment.org_id == org_id,
            )
            assign = (await db_session.execute(assign_stmt)).scalars().first()
            if not assign:
                db_session.add(
                    EMSUserRoleAssignment(
                        user_id=user.id,
                        role_id=ems_role.id,
                        org_id=org_id,
                    )
                )

    await db_session.flush()

    # 4. Guardian-Student Links
    alex_user = seeded_users["student.alex@csg.edu"]
    maya_user = seeded_users["student.maya@csg.edu"]
    parent_alex = seeded_users["parent.alex@csg.edu"]
    parent_maya = seeded_users["parent.maya@csg.edu"]

    guard_pairs = [
        (parent_alex.id, alex_user.id, "father"),
        (parent_maya.id, maya_user.id, "father"),
    ]
    for g_id, s_id, rel in guard_pairs:
        g_stmt = select(StudentGuardian).where(
            StudentGuardian.guardian_user_id == g_id,
            StudentGuardian.student_id == s_id,
        )
        if not (await db_session.execute(g_stmt)).scalars().first():
            db_session.add(
                StudentGuardian(
                    guardian_user_id=g_id,
                    student_id=s_id,
                    relationship=rel,
                    is_primary_contact=True,
                )
            )

    await db_session.flush()

    # 5. Campus, Academic Year, Terms & Sections
    campus_stmt = select(Campus).where(Campus.org_id == org_id, Campus.code == "MAIN-01")
    campus = (await db_session.execute(campus_stmt)).scalars().first()
    if not campus:
        campus = Campus(
            org_id=org_id,
            name="Innovation Campus (Main)",
            code="MAIN-01",
            address="100 Science Parkway, Cambridge, MA",
            timezone="America/New_York",
            is_active=True,
        )
        db_session.add(campus)
        await db_session.flush()
        await db_session.refresh(campus)

    year_stmt = select(AcademicYear).where(AcademicYear.campus_id == campus.id, AcademicYear.name == "2025-2026 Academic Year")
    acad_year = (await db_session.execute(year_stmt)).scalars().first()
    if not acad_year:
        acad_year = AcademicYear(
            campus_id=campus.id,
            name="2025-2026 Academic Year",
            start_date="2025-08-15",
            end_date="2026-06-15",
            is_active=True,
        )
        db_session.add(acad_year)
        await db_session.flush()
        await db_session.refresh(acad_year)

    term_stmt = select(AcademicTerm).where(AcademicTerm.academic_year_id == acad_year.id, AcademicTerm.name == "Fall Semester 2025")
    fall_term = (await db_session.execute(term_stmt)).scalars().first()
    if not fall_term:
        fall_term = AcademicTerm(
            academic_year_id=acad_year.id,
            name="Fall Semester 2025",
            term_code="FALL-25",
            weight_percentage=50.0,
            start_date="2025-08-15",
            end_date="2025-12-20",
        )
        db_session.add(fall_term)
        await db_session.flush()
        await db_session.refresh(fall_term)

    term_stmt_sp = select(AcademicTerm).where(AcademicTerm.academic_year_id == acad_year.id, AcademicTerm.name == "Spring Semester 2026")
    spring_term = (await db_session.execute(term_stmt_sp)).scalars().first()
    if not spring_term:
        spring_term = AcademicTerm(
            academic_year_id=acad_year.id,
            name="Spring Semester 2026",
            term_code="SPRING-26",
            weight_percentage=50.0,
            start_date="2026-01-10",
            end_date="2026-06-15",
        )
        db_session.add(spring_term)
        await db_session.flush()
        await db_session.refresh(spring_term)

    # Sections
    teacher_chen = seeded_users["teacher.physics@csg.edu"]
    teacher_jenkins = seeded_users["teacher.math@csg.edu"]
    teacher_aurelius = seeded_users["teacher.humanities@csg.edu"]

    section_specs = [
        {"grade": "Grade 10", "name": "Section 10-A (STEM Advanced)", "room": "Lab 201", "teacher_id": teacher_chen.id, "cap": 30},
        {"grade": "Grade 10", "name": "Section 10-B (Humanities & Arts)", "room": "Room 105", "teacher_id": teacher_aurelius.id, "cap": 28},
        {"grade": "Grade 9", "name": "Section 9-A (Foundations)", "room": "Room 102", "teacher_id": teacher_jenkins.id, "cap": 32},
    ]

    seeded_sections: Dict[str, ClassSection] = {}
    for s_spec in section_specs:
        sec_stmt = select(ClassSection).where(
            ClassSection.campus_id == campus.id,
            ClassSection.section_name == s_spec["name"],
        )
        sec = (await db_session.execute(sec_stmt)).scalars().first()
        if not sec:
            sec = ClassSection(
                campus_id=campus.id,
                academic_year_id=acad_year.id,
                grade_level=s_spec["grade"],
                section_name=s_spec["name"],
                room_number=s_spec["room"],
                max_capacity=s_spec["cap"],
                class_teacher_id=s_spec["teacher_id"],
                is_active=True,
            )
            db_session.add(sec)
            await db_session.flush()
            await db_session.refresh(sec)
        seeded_sections[s_spec["name"]] = sec

    # Student Enrollments
    sec_10a = seeded_sections["Section 10-A (STEM Advanced)"]
    sec_10b = seeded_sections["Section 10-B (Humanities & Arts)"]
    sec_9a = seeded_sections["Section 9-A (Foundations)"]

    enroll_specs = [
        (seeded_users["student.alex@csg.edu"].id, sec_10a.id, "STEM-101"),
        (seeded_users["student.maya@csg.edu"].id, sec_10a.id, "STEM-102"),
        (seeded_users["student.leo@csg.edu"].id, sec_10b.id, "HUM-201"),
        (seeded_users["student.sophia@csg.edu"].id, sec_9a.id, "FND-001"),
    ]
    for st_id, s_id, roll in enroll_specs:
        enr_stmt = select(StudentEnrollment).where(
            StudentEnrollment.student_id == st_id,
            StudentEnrollment.section_id == s_id,
        )
        if not (await db_session.execute(enr_stmt)).scalars().first():
            db_session.add(
                StudentEnrollment(
                    student_id=st_id,
                    section_id=s_id,
                    academic_year_id=acad_year.id,
                    enrollment_status="ACTIVE",
                    roll_number=roll,
                )
            )

    await db_session.flush()

    # 6. Embedded Learnhouse Courses & Curricular Bridge
    course_specs = [
        {
            "title": "AP Physics C: Mechanics & Electromagnetism",
            "slug": "ap-physics-c",
            "code": "PHY-301",
            "desc": "Rigorous calculus-based physics covering Newtonian mechanics and field theory.",
            "teacher": teacher_chen,
            "section": sec_10a,
            "credits": 4.0,
        },
        {
            "title": "Advanced Calculus & Linear Algebra",
            "slug": "adv-calculus-math",
            "code": "MATH-401",
            "desc": "Multivariable integration, vector spaces, and differential systems.",
            "teacher": teacher_jenkins,
            "section": sec_10a,
            "credits": 4.0,
        },
        {
            "title": "World History & Global Perspectives",
            "slug": "world-history-perspectives",
            "code": "HIST-201",
            "desc": "Comparative analysis of civilization dynamics and economic revolutions.",
            "teacher": teacher_aurelius,
            "section": sec_10b,
            "credits": 3.0,
        },
    ]

    seeded_courses: Dict[str, Course] = {}
    for c_spec in course_specs:
        c_stmt = select(Course).where(Course.org_id == org_id, Course.name == c_spec["title"])
        course = (await db_session.execute(c_stmt)).scalars().first()
        now_str = str(datetime.datetime.now(datetime.timezone.utc))
        if not course:
            course = Course(
                org_id=org_id,
                name=c_spec["title"],
                description=c_spec["desc"],
                about=c_spec["desc"],
                learnings=c_spec["desc"],
                public=True,
                published=True,
                open_to_contributors=False,
                course_uuid=f"crs_{uuid4()}",
                creation_date=now_str,
                update_date=now_str,
            )
            db_session.add(course)
            await db_session.flush()
            await db_session.refresh(course)

        seeded_courses[c_spec["slug"]] = course

        # Curricular Bridge (SectionSubject)
        ss_stmt = select(SectionSubject).where(
            SectionSubject.section_id == c_spec["section"].id,
            SectionSubject.course_id == course.id,
        )
        if not (await db_session.execute(ss_stmt)).scalars().first():
            db_session.add(
                SectionSubject(
                    section_id=c_spec["section"].id,
                    course_id=course.id,
                    teacher_id=c_spec["teacher"].id,
                    subject_name=c_spec["title"],
                    subject_code=c_spec["code"],
                    academic_year_id=acad_year.id,
                    credit_hours=c_spec["credits"],
                    is_elective=False,
                )
            )

    await db_session.flush()

    # 7. Bell Schedule Periods & Timetable Schedules
    period_specs = [
        (1, "08:30:00", "09:15:00", "Period 1: Morning Advisory & STEM"),
        (2, "09:20:00", "10:15:00", "Period 2: Advanced Physics"),
        (3, "10:25:00", "11:20:00", "Period 3: Calculus & Mathematics"),
        (4, "11:30:00", "12:25:00", "Period 4: World History"),
        (5, "13:15:00", "14:10:00", "Period 5: Laboratory Practicum"),
        (6, "14:15:00", "15:10:00", "Period 6: Socratic Seminar"),
    ]

    seeded_periods: Dict[int, ClassPeriod] = {}
    for p_num, s_time, e_time, p_name in period_specs:
        p_stmt = select(ClassPeriod).where(ClassPeriod.campus_id == campus.id, ClassPeriod.period_number == p_num)
        period = (await db_session.execute(p_stmt)).scalars().first()
        if not period:
            period = ClassPeriod(
                campus_id=campus.id,
                period_number=p_num,
                start_time=s_time,
                end_time=e_time,
                name=p_name,
            )
            db_session.add(period)
            await db_session.flush()
            await db_session.refresh(period)
        seeded_periods[p_num] = period

    # Timetable Slots for Section 10-A
    phy_course = seeded_courses["ap-physics-c"]
    math_course = seeded_courses["adv-calculus-math"]
    hist_course = seeded_courses["world-history-perspectives"]

    timetable_slots = [
        (DayOfWeek.MONDAY, 2, phy_course.id, teacher_chen.id, sec_10a.id, "Lab 201"),
        (DayOfWeek.MONDAY, 3, math_course.id, teacher_jenkins.id, sec_10a.id, "Lab 201"),
        (DayOfWeek.TUESDAY, 2, phy_course.id, teacher_chen.id, sec_10a.id, "Lab 201"),
        (DayOfWeek.TUESDAY, 3, math_course.id, teacher_jenkins.id, sec_10a.id, "Lab 201"),
        (DayOfWeek.WEDNESDAY, 2, phy_course.id, teacher_chen.id, sec_10a.id, "Lab 201"),
        (DayOfWeek.THURSDAY, 2, phy_course.id, teacher_chen.id, sec_10a.id, "Lab 201"),
        (DayOfWeek.THURSDAY, 3, math_course.id, teacher_jenkins.id, sec_10a.id, "Lab 201"),
        (DayOfWeek.FRIDAY, 2, phy_course.id, teacher_chen.id, sec_10a.id, "Lab 201"),
        (DayOfWeek.FRIDAY, 4, hist_course.id, teacher_aurelius.id, sec_10b.id, "Room 105"),
    ]

    for dow, p_num, c_id, t_id, s_id, room in timetable_slots:
        p_obj = seeded_periods[p_num]
        tt_stmt = select(TimetableSchedule).where(
            TimetableSchedule.section_id == s_id,
            TimetableSchedule.day_of_week == dow,
            TimetableSchedule.period_id == p_obj.id,
            TimetableSchedule.academic_term_id == fall_term.id,
        )
        if not (await db_session.execute(tt_stmt)).scalars().first():
            # TimetableSchedule has no is_active column. On SQLModel versions
            # that reject unknown kwargs the old is_active=True was a hard
            # TypeError at seed time; on this one it is silently dropped, so
            # the "active" intent was simply lost. A slot is live by belonging
            # to a term: academic_term_id is what every timetable read scopes
            # on, so binding these to the fall term is what activates them.
            db_session.add(
                TimetableSchedule(
                    section_id=s_id,
                    course_id=c_id,
                    teacher_id=t_id,
                    day_of_week=dow,
                    period_id=p_obj.id,
                    room_number=room,
                    academic_term_id=fall_term.id,
                )
            )

    await db_session.flush()

    # 8. 30-Day Biometric Roll-Call Attendance
    today = datetime.date.today()
    students_10a = [seeded_users["student.alex@csg.edu"], seeded_users["student.maya@csg.edu"]]

    for day_offset in range(30, -1, -1):
        att_date = today - datetime.timedelta(days=day_offset)
        if att_date.weekday() >= 5:  # Skip weekends
            continue

        for student in students_10a:
            # Deterministic realistic attendance: Maya 100%, Alex 96%
            if student.email == "student.alex@csg.edu" and day_offset == 7:
                status = AttendanceStatus.LATE
                remarks = "Late arrival due to transit delay"
            elif student.email == "student.alex@csg.edu" and day_offset == 14:
                status = AttendanceStatus.EXCUSED
                remarks = "Medical appointment verified"
            else:
                status = AttendanceStatus.PRESENT
                remarks = "Biometric scan verified"

            att_stmt = select(StudentAttendance).where(
                StudentAttendance.student_id == student.id,
                StudentAttendance.section_id == sec_10a.id,
                StudentAttendance.date == att_date,
            )
            if not (await db_session.execute(att_stmt)).scalars().first():
                db_session.add(
                    StudentAttendance(
                        student_id=student.id,
                        section_id=sec_10a.id,
                        date=att_date,
                        status=status,
                        remarks=remarks,
                        recorded_by=teacher_chen.id,
                    )
                )

    await db_session.flush()

    # 9. Master Gradebook, Assessment Plans & SpeedGrader Marks
    scale_stmt = select(GradingScale).where(GradingScale.name == "Standard 4.0 GPA Scale")
    scale = (await db_session.execute(scale_stmt)).scalars().first()
    if not scale:
        scale = GradingScale(
            name="Standard 4.0 GPA Scale",
            description="Institutional standard 4.0 scale with plus/minus distinctions",
            intervals=[
                {"letter": "A+", "min_percent": 97.0, "max_percent": 100.0, "gpa_point": 4.0},
                {"letter": "A", "min_percent": 93.0, "max_percent": 96.9, "gpa_point": 4.0},
                {"letter": "A-", "min_percent": 90.0, "max_percent": 92.9, "gpa_point": 3.7},
                {"letter": "B+", "min_percent": 87.0, "max_percent": 89.9, "gpa_point": 3.3},
                {"letter": "B", "min_percent": 83.0, "max_percent": 86.9, "gpa_point": 3.0},
                {"letter": "B-", "min_percent": 80.0, "max_percent": 82.9, "gpa_point": 2.7},
                {"letter": "C+", "min_percent": 77.0, "max_percent": 79.9, "gpa_point": 2.3},
                {"letter": "C", "min_percent": 73.0, "max_percent": 76.9, "gpa_point": 2.0},
                {"letter": "F", "min_percent": 0.0, "max_percent": 72.9, "gpa_point": 0.0},
            ],
            is_default=True,
        )
        db_session.add(scale)
        await db_session.flush()

    # Assessment Plans for AP Physics
    plan_specs = [
        {"name": "Continuous Laboratory & SpeedGrader Work", "weight": 30.0, "max": 100.0},
        {"name": "Midterm CBT Examination", "weight": 30.0, "max": 100.0},
        {"name": "Final Capstone Research & Defense", "weight": 40.0, "max": 100.0},
    ]

    seeded_plans: List[AssessmentPlan] = []
    for p_spec in plan_specs:
        plan_stmt = select(AssessmentPlan).where(
            AssessmentPlan.course_id == phy_course.id,
            AssessmentPlan.section_id == sec_10a.id,
            AssessmentPlan.assessment_name == p_spec["name"],
        )
        plan = (await db_session.execute(plan_stmt)).scalars().first()
        if not plan:
            plan = AssessmentPlan(
                course_id=phy_course.id,
                section_id=sec_10a.id,
                academic_term_id=fall_term.id,
                assessment_name=p_spec["name"],
                weight_percentage=p_spec["weight"],
                max_score=p_spec["max"],
            )
            db_session.add(plan)
            await db_session.flush()
            await db_session.refresh(plan)
        seeded_plans.append(plan)

    # Gradebook Entries
    # Alex: Lab=95, Midterm=92, Capstone=96 -> Weighted Total ~94.5 (A)
    # Maya: Lab=98, Midterm=96, Capstone=99 -> Weighted Total ~97.8 (A+)
    scores = {
        alex_user.id: [95.0, 92.0, 96.0],
        maya_user.id: [98.0, 96.0, 99.0],
    }

    for s_id, score_list in scores.items():
        for i, plan in enumerate(seeded_plans):
            raw = score_list[i]
            weighted = (raw / plan.max_score) * plan.weight_percentage
            letter = "A+" if raw >= 97 else ("A" if raw >= 93 else "A-")
            gpa = 4.0 if raw >= 93 else 3.7

            ge_stmt = select(GradebookEntry).where(
                GradebookEntry.student_id == s_id,
                GradebookEntry.assessment_plan_id == plan.id,
            )
            if not (await db_session.execute(ge_stmt)).scalars().first():
                db_session.add(
                    GradebookEntry(
                        student_id=s_id,
                        assessment_plan_id=plan.id,
                        raw_score=raw,
                        max_score=plan.max_score,
                        weighted_score=weighted,
                        letter_grade=letter,
                        gpa_point=gpa,
                        remarks="Exemplary analytic rigor and lab execution.",
                        graded_by=teacher_chen.id,
                    )
                )

    await db_session.flush()

    # Term Report Cards
    for s_id, (gpa, letter, remarks) in [
        (alex_user.id, (3.92, "A", "Outstanding analytical capabilities and positive leadership in group physics projects.")),
        (maya_user.id, (4.00, "A+", "Top of cohort across theoretical derivations and lab implementations. Exemplary work.")),
    ]:
        rc_stmt = select(TermReportCard).where(
            TermReportCard.student_id == s_id,
            TermReportCard.academic_term_id == fall_term.id,
        )
        if not (await db_session.execute(rc_stmt)).scalars().first():
            db_session.add(
                TermReportCard(
                    student_id=s_id,
                    section_id=sec_10a.id,
                    academic_term_id=fall_term.id,
                    gpa=gpa,
                    letter_grade=letter,
                    attendance_percentage=96.5 if s_id == alex_user.id else 100.0,
                    remarks=remarks,
                    status="SENT",
                    sent_at=datetime.datetime.now(datetime.timezone.utc),
                )
            )

    await db_session.flush()

    # 10. School Examinations & Results
    exam_stmt = select(Exam).where(Exam.course_id == phy_course.id, Exam.title == "Physics Midterm: Quantum & Classical Mechanics")
    exam = (await db_session.execute(exam_stmt)).scalars().first()
    if not exam:
        exam = Exam(
            campus_id=campus.id,
            academic_term_id=fall_term.id,
            course_id=phy_course.id,
            title="Physics Midterm: Quantum & Classical Mechanics",
            exam_type="Midterm",
            exam_date=today - datetime.timedelta(days=15),
            start_time="09:00",
            duration_minutes=90,
            total_marks=100.0,
            pass_marks=40.0,
            assessment_plan_id=seeded_plans[1].id if len(seeded_plans) > 1 else None,
            status=ExamStatus.RESULTS_POSTED,
            instructions="Calculator and formula sheet permitted. Show all working clearly.",
            created_by=teacher_chen.id,
        )
        db_session.add(exam)
        await db_session.flush()
        await db_session.refresh(exam)

        # Section schedule
        db_session.add(
            ExamSectionSchedule(
                exam_id=exam.id,
                section_id=sec_10a.id,
                room_number="Lab 201",
                invigilator_id=teacher_chen.id,
                actual_start_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=15, hours=2),
                actual_end_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=15, hours=0, minutes=30),
            )
        )

        # Student Exam Results
        db_session.add(
            ExamResult(
                exam_id=exam.id,
                student_id=alex_user.id,
                marks_obtained=92.0,
                attendance_status=ExamAttendanceStatus.PRESENT,
                remarks="Strong theoretical understanding, minor calculation error on relativistic momentum.",
                marked_by=teacher_chen.id,
                marked_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14),
                posted_to_gradebook_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14),
            )
        )
        db_session.add(
            ExamResult(
                exam_id=exam.id,
                student_id=maya_user.id,
                marks_obtained=96.0,
                attendance_status=ExamAttendanceStatus.PRESENT,
                remarks="Flawless derivation of harmonic oscillations and relativistic dynamics.",
                marked_by=teacher_chen.id,
                marked_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14),
                posted_to_gradebook_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14),
            )
        )
        await db_session.flush()

    # 11. Admissions & RevOps CRM Pipeline
    leads_data = [
        {"name": "Elena Rostova", "email": "elena.parent@example.com", "phone": "+1 555-0192", "grade": "Grade 10", "stage": LeadStage.NEW_INQUIRY, "score": 85, "intent": LeadIntent.HOT},
        {"name": "Tariq Mansoor", "email": "tariq.family@example.com", "phone": "+1 555-0144", "grade": "Grade 10", "stage": LeadStage.TOUR_BOOKED, "score": 78, "intent": LeadIntent.WARM},
        {"name": "Chloe Dupont", "email": "dupont.chloe@example.com", "phone": "+1 555-0188", "grade": "Grade 11", "stage": LeadStage.CONTACTED, "score": 92, "intent": LeadIntent.HOT},
        {"name": "Lucas Wright", "email": "wright.lucas@example.com", "phone": "+1 555-0133", "grade": "Grade 9", "stage": LeadStage.ASSESSMENT_SCHEDULED, "score": 82, "intent": LeadIntent.HOT},
        {"name": "Isabella Martinez", "email": "martinez.isa@example.com", "phone": "+1 555-0177", "grade": "Grade 10", "stage": LeadStage.OFFER_SENT, "score": 95, "intent": LeadIntent.HOT},
        {"name": "Alex Mercer", "email": "robert.mercer@example.com", "phone": "+1 555-0111", "grade": "Grade 10", "stage": LeadStage.ENROLLED, "score": 98, "intent": LeadIntent.HOT},
    ]

    for ld in leads_data:
        l_stmt = select(AdmissionsLead).where(AdmissionsLead.student_name == ld["name"], AdmissionsLead.email == ld["email"])
        lead = (await db_session.execute(l_stmt)).scalars().first()
        if not lead:
            lead = AdmissionsLead(
                campus_id=campus.id,
                parent_name=f"Parent of {ld['name']}",
                email=ld["email"],
                phone=ld["phone"],
                student_name=ld["name"],
                grade_applying_for=ld["grade"],
                academic_year_id=acad_year.id,
                stage=ld["stage"],
                source=LeadSource.WEBSITE_FORM,
                lead_score=ld["score"],
                intent_level=ld["intent"],
                budget_range="$15,000 - $20,000",
                notes="Family interested in rigorous STEM curriculum and AP coursework.",
            )
            db_session.add(lead)
            await db_session.flush()
            await db_session.refresh(lead)

            # Log initial LeadActivity
            db_session.add(
                LeadActivityLog(
                    lead_id=lead.id,
                    activity_type=ActivityType.NOTE,
                    summary=f"Admissions Discovery: Initial evaluation score {ld['score']}/100. High alignment with STEM track.",
                )
            )

            # Map to StudentApplication
            app_status_map = {
                LeadStage.NEW_INQUIRY: ApplicationStatus.SUBMITTED,
                LeadStage.CONTACTED: ApplicationStatus.UNDER_REVIEW,
                LeadStage.TOUR_BOOKED: ApplicationStatus.DOCUMENTS_PENDING,
                LeadStage.ASSESSMENT_SCHEDULED: ApplicationStatus.ASSESSMENT_SCHEDULED,
                LeadStage.OFFER_SENT: ApplicationStatus.OFFERED,
                LeadStage.ENROLLED: ApplicationStatus.ENROLLED,
            }
            app_num = f"APP-2025-{lead.id:04d}"
            app_stmt = select(StudentApplication).where(StudentApplication.application_number == app_num)
            if not (await db_session.execute(app_stmt)).scalars().first():
                db_session.add(
                    StudentApplication(
                        application_number=app_num,
                        org_id=org_id,
                        campus_id=campus.id,
                        lead_id=lead.id,
                        student_name=ld["name"],
                        guardian_name=f"Parent of {ld['name']}",
                        guardian_email=ld["email"],
                        guardian_phone=ld["phone"],
                        grade_applying_for=ld["grade"],
                        academic_year_id=acad_year.id,
                        status=app_status_map.get(ld["stage"], ApplicationStatus.SUBMITTED),
                        submitted_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10),
                        enrolled_student_id=alex_user.id if ld["name"] == "Alex Mercer" else None,
                        notes="Candidate demonstrates strong analytical potential and high motivation.",
                    )
                )

    await db_session.flush()

    # 12. Discipline & Pastoral Records
    disc_stmt = select(DisciplinaryIncident).where(DisciplinaryIncident.student_id == alex_user.id)
    if not (await db_session.execute(disc_stmt)).scalars().first():
        db_session.add(
            DisciplinaryIncident(
                org_id=org_id,
                campus_id=campus.id,
                student_id=alex_user.id,
                reporter_id=teacher_chen.id,
                incident_date=str(today - datetime.timedelta(days=12)),
                title="Academic Distinction & Regional Physics Olympiad Finalist",
                description="Alex achieved 1st place in the Northeast regional physics theoretical exam, representing CSG Academy.",
                location="Physics Lab",
                severity=IncidentSeverityEnum.MINOR,
                status=IncidentStatusEnum.RESOLVED,
                action_taken="Institutional commendation logged and certificate awarded.",
                parent_notified=True,
                parent_acknowledgement=True,
            )
        )

    # 13. Confidential Counseling / Clinical Desk Records
    clin_user = seeded_users["counselor.drsmith@csg.edu"]
    csess_stmt = select(CounselingSession).where(CounselingSession.student_id == alex_user.id)
    if not (await db_session.execute(csess_stmt)).scalars().first():
        db_session.add(
            CounselingSession(
                student_id=alex_user.id,
                psychologist_id=str(clin_user.id),
                psychologist_user_id=clin_user.id,
                session_date=today - datetime.timedelta(days=10),
                duration_minutes=45,
                notes="CONFIDENTIAL: Regular academic pacing and stress management check-in during AP examination prep. Student exhibits healthy coping mechanisms.",
                follow_up_plan="Bi-weekly advisory check-in.",
                parent_visible_summary="Routine academic wellness and time-management consultation conducted.",
                share_summary_with_parent=True,
            )
        )
        db_session.add(
            CounselingActivityLog(
                student_id=alex_user.id,
                psychologist_id=str(clin_user.id),
                psychologist_user_id=clin_user.id,
                signal_type="WELLNESS_SURVEY",
                description="High cognitive engagement and positive self-efficacy score on term wellness survey.",
                severity="low",
            )
        )

    await db_session.flush()

    # 14. Double-Entry General Ledger & Chart of Accounts
    coa_specs = [
        ("1010", "Cash & Operating Bank Account", AccountType.ASSET, 450000.0),
        ("1020", "Tuition Fees Receivable", AccountType.ASSET, 25000.0),
        ("2010", "Accounts Payable & Accruals", AccountType.LIABILITY, 18500.0),
        ("3010", "Institutional Retained Earnings", AccountType.EQUITY, 380000.0),
        ("4010", "Tuition & Academic Program Revenue", AccountType.REVENUE, 125000.0),
        ("5010", "Faculty & Instructional Salaries", AccountType.EXPENSE, 38500.0),
        ("5020", "STEM Laboratory & Equipment Expense", AccountType.EXPENSE, 10000.0),
    ]

    seeded_coa: Dict[str, ChartOfAccounts] = {}
    for code, name, acct_type, init_bal in coa_specs:
        coa_stmt = select(ChartOfAccounts).where(ChartOfAccounts.campus_id == campus.id, ChartOfAccounts.account_code == code)
        account = (await db_session.execute(coa_stmt)).scalars().first()
        if not account:
            account = ChartOfAccounts(
                campus_id=campus.id,
                account_code=code,
                account_name=name,
                account_type=acct_type,
                balance=init_bal,
                is_active=True,
            )
            db_session.add(account)
            await db_session.flush()
            await db_session.refresh(account)
        seeded_coa[code] = account

    # Balanced Journal Entry
    j_stmt = select(JournalEntry).where(JournalEntry.reference_no == "JV-2025-Q1-TUITION")
    if not (await db_session.execute(j_stmt)).scalars().first():
        j_entry = JournalEntry(
            campus_id=campus.id,
            entry_date=today - datetime.timedelta(days=20),
            reference_no="JV-2025-Q1-TUITION",
            description="Q1 Tuition Invoicing & Fee Collection Recognition",
            total_debit=25000.0,
            total_credit=25000.0,
        )
        db_session.add(j_entry)
        await db_session.flush()
        await db_session.refresh(j_entry)

        # Lines: Debit Cash (1010) $25,000 / Credit Revenue (4010) $25,000
        db_session.add(
            JournalEntryLine(
                entry_id=j_entry.id,
                account_id=seeded_coa["1010"].id,
                debit_amount=25000.0,
                credit_amount=0.0,
                description="Cash received from Q1 tuition fee settlements",
            )
        )
        db_session.add(
            JournalEntryLine(
                entry_id=j_entry.id,
                account_id=seeded_coa["4010"].id,
                debit_amount=0.0,
                credit_amount=25000.0,
                description="Earned tuition revenue for Fall 2025 semester",
            )
        )

    await db_session.flush()

    # 15. Fee Structure & Student Fee Vouchers
    fee_struct_stmt = select(FeeStructure).where(FeeStructure.campus_id == campus.id, FeeStructure.name == "Grade 10 STEM Standard Fee")
    fee_struct = (await db_session.execute(fee_struct_stmt)).scalars().first()
    if not fee_struct:
        fee_struct = FeeStructure(
            campus_id=campus.id,
            name="Grade 10 STEM Standard Fee",
            tuition_fee=3000.0,
            lab_fee=500.0,
            transport_fee=250.0,
            other_fee=150.0,
            total_amount=3900.0,
        )
        db_session.add(fee_struct)
        await db_session.flush()
        await db_session.refresh(fee_struct)

    # Vouchers for Alex & Maya
    v_specs = [
        (alex_user.id, "VOUCH-2025-001", VoucherStatus.PAID, today - datetime.timedelta(days=45), today - datetime.timedelta(days=15)),
        (alex_user.id, "VOUCH-2025-002", VoucherStatus.UNPAID, today - datetime.timedelta(days=5), today + datetime.timedelta(days=25)),
        (maya_user.id, "VOUCH-2025-003", VoucherStatus.PAID, today - datetime.timedelta(days=45), today - datetime.timedelta(days=15)),
    ]

    for s_id, v_no, v_status, iss_date, d_date in v_specs:
        v_stmt = select(StudentFeeVoucher).where(StudentFeeVoucher.voucher_no == v_no)
        if not (await db_session.execute(v_stmt)).scalars().first():
            db_session.add(
                StudentFeeVoucher(
                    student_id=s_id,
                    fee_structure_id=fee_struct.id,
                    voucher_no=v_no,
                    issue_date=iss_date,
                    due_date=d_date,
                    tuition_fee=3000.0,
                    lab_fee=500.0,
                    transport_fee=250.0,
                    other_fee=150.0,
                    total_amount=3900.0,
                    paid_amount=3900.0 if v_status == VoucherStatus.PAID else 0.0,
                    balance_amount=0.0 if v_status == VoucherStatus.PAID else 3900.0,
                    status=v_status,
                )
            )

    await db_session.flush()

    # 16. Staff Profiles & Progressive Payroll
    staff_specs = [
        {"user": teacher_chen, "code": "FAC-001", "name": "Dr. Albert Chen", "dept": "Science & STEM", "desig": "Lead Physics Faculty", "salary": 8500.0},
        {"user": teacher_jenkins, "code": "FAC-002", "name": "Ms. Sarah Jenkins", "dept": "Mathematics", "desig": "Senior Mathematics Faculty", "salary": 7200.0},
        {"user": teacher_aurelius, "code": "FAC-003", "name": "Mr. Marcus Aurelius", "dept": "Humanities", "desig": "Senior History Faculty", "salary": 7000.0},
    ]

    for sp in staff_specs:
        st_prof_stmt = select(StaffProfile).where(StaffProfile.employee_code == sp["code"])
        profile = (await db_session.execute(st_prof_stmt)).scalars().first()
        if not profile:
            profile = StaffProfile(
                user_id=sp["user"].id,
                campus_id=campus.id,
                employee_code=sp["code"],
                full_name=sp["name"],
                designation=sp["desig"],
                department=sp["dept"],
                joining_date=datetime.date(2023, 8, 1),
                contract_type=ContractType.PERMANENT,
                basic_salary=sp["salary"],
                email=sp["user"].email,
                is_active=True,
            )
            db_session.add(profile)
            await db_session.flush()
            await db_session.refresh(profile)

        # Salary Structure & Monthly Slip
        s_struct_stmt = select(SalaryStructure).where(SalaryStructure.staff_id == profile.id)
        if not (await db_session.execute(s_struct_stmt)).scalars().first():
            basic = sp["salary"] * 0.70
            housing = sp["salary"] * 0.20
            medical = sp["salary"] * 0.10
            tax = sp["salary"] * 0.15
            net = sp["salary"] - tax

            db_session.add(
                SalaryStructure(
                    staff_id=profile.id,
                    basic=basic,
                    housing_allowance=housing,
                    medical_allowance=medical,
                    other_allowances=0.0,
                    tax_deduction=tax,
                    provident_fund=0.0,
                    other_deductions=0.0,
                    gross_salary=sp["salary"],
                    total_deductions=tax,
                    net_salary=net,
                )
            )

            # Slip for current month
            slip_no = f"PAY-{profile.employee_code}-{today.strftime('%Y%m')}"
            slip_stmt = select(SalarySlip).where(SalarySlip.slip_no == slip_no)
            if not (await db_session.execute(slip_stmt)).scalars().first():
                db_session.add(
                    SalarySlip(
                        slip_no=slip_no,
                        staff_id=profile.id,
                        month=today.month,
                        year=today.year,
                        basic=basic,
                        housing_allowance=housing,
                        medical_allowance=medical,
                        tax_deduction=tax,
                        gross_salary=sp["salary"],
                        total_deductions=tax,
                        net_salary=net,
                        payment_status=SalaryPaymentStatus.PAID,
                        payment_date=today - datetime.timedelta(days=2),
                        payment_method="BANK_TRANSFER",
                        remarks="Monthly direct deposit processed.",
                    )
                )

    await db_session.flush()

    # 17. Cognia Accreditation Standards & Evidence Locker
    cognia_specs = [
        ("1.1", "Leadership Capacity", "Standard 1.1: Mission, Strategic Vision & Leadership Capacity", "policy", 3.9),
        ("2.2", "Learning Capacity", "Standard 2.2: Curriculum Alignment, Rubric Integrity & SpeedGrader Delivery", "rubric", 3.8),
        ("3.1", "Resource Capacity", "Standard 3.1: Resource Allocation, Financial Soundness & Governance", "assessment", 3.7),
    ]

    for code, domain, title, ev_type, score in cognia_specs:
        std_stmt = select(CogniaEvidenceItem).where(
            CogniaEvidenceItem.org_id == org_id,
            CogniaEvidenceItem.standard_code == code,
        )
        if not (await db_session.execute(std_stmt)).scalars().first():
            evidence_body = f"Evidence dossier verifying compliance with Cognia Standard {code} for CSG Global Academy."
            sha_hash = hashlib.sha256(evidence_body.encode("utf-8")).hexdigest()

            admin_user = seeded_users["admin@csg.edu"]
            db_session.add(
                CogniaEvidenceItem(
                    org_id=org_id,
                    campus_id=campus.id,
                    standard_code=code,
                    domain=domain,
                    title=title,
                    description="Standard Operating Procedures, Curricular Maps, Rubrics and Psychometrics evidence verified under ISO 27001.",
                    evidence_type=ev_type,
                    artifact_url=f"/artifacts/cognia-std-{code.replace('.', '-')}.pdf",
                    academic_year="2025-2026",
                    performance_score=score,
                    status=CogniaEvidenceStatus.VERIFIED,
                    submitted_by_user_id=admin_user.id,
                    submitted_by_sub=admin_user.user_uuid,
                )
            )

    await db_session.commit()
    logger.info("CSG-EMS comprehensive demo data successfully seeded and committed!")

    result: Dict[str, Any] = {
        "status": "success",
        "organization": target_org.name,
        "org_slug": target_org.slug,
        "users_seeded": len(seeded_users),
        "users_created": len(created_users),
        "users_skipped_existing": skipped_existing_users,
        "campus": campus.name,
        "sections": len(seeded_sections),
        "courses": len(seeded_courses),
        "ami_index": 3.82,
    }

    # The generated password is surfaced exactly once, here, because only its
    # hash is stored and it is unrecoverable afterwards. Omitted when the
    # password came from the environment (the operator already holds it) and
    # when no account was actually created with it -- an empty or echoed value
    # would be worse than none.
    if created_users and not password_is_operator_supplied:
        result["demo_password"] = demo_password
        logger.info(
            "Seeded %s demo user(s) with a generated password (returned once "
            "in the result; set %s to use a known one).",
            len(created_users),
            DEMO_PASSWORD_ENV,
        )

    return result
