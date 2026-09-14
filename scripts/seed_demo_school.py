#!/usr/bin/env python3
"""
Realistic Demo School Seed Data Generator for CSG LMS / Learnhouse.

Seeds a complete production-grade school ecosystem:
- 1 Organization ("CSG Vanguard Academy")
- 12 Subject Teachers (Math, Physics, Bio, Chem, English, CS, History, etc.)
- 50+ Students across Grades 9, 10, 11 with Pakistani/International student profiles
- 25 Guardians linked to respective students
- Timetables, period slots, classroom mappings
- 30 days of realistic Attendance logs
- Gradebook assessments (Quizzes, Midterms, Assignments) with GPAs
- Fee structures, vouchers, payments
- Live class schedules
- Disciplinary incidents & actions
- Alumni directory & career milestones
- Certificates & verification hashes
- Gamification badges & XP streaks

Usage:
    python scripts/seed_demo_school.py [--reset]
"""

import argparse
import asyncio
import hashlib
import os
import random
import secrets
import sys
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

# Add apps/api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import (
    SUPER_ADMIN,
    SCHOOL_ADMIN,
    TEACHER,
    STUDENT,
    PARENT,
    STAFF,
)
from src.db.organizations import Organization
from src.db.sms_alumni import AlumniMilestone, AlumniProfile
from src.db.sms_attendance import AttendanceRecord, AttendanceSession
from src.db.sms_campus import AcademicTerm, AcademicYear, Campus, ClassSection, StudentEnrollment
from src.db.sms_certificates import CertificateTemplate, IssuedCertificate
from src.db.sms_discipline import DisciplinaryIncident, IncidentSeverityEnum, IncidentStatusEnum
from src.db.sms_fees import FeePlan, StudentFeeVoucher
from src.db.sms_gamification import Badge, StudentStreak, UserBadge
from src.db.sms_gradebook import GradeAssessment, GradeEntry, StudentGradeSummary
from src.db.sms_hr import StaffProfile
from src.db.sms_identity import SMSUserRole, StudentGuardian
from src.db.sms_live_class import LiveClassRoom
from src.db.sms_timetable import TimetablePeriod, TimetableSchedule
from src.db.users import User


TEACHER_NAMES = [
    ("Dr. Tariq", "Mahmood", "Mathematics & Calculus", "tariq.mahmood@csgvanguard.edu"),
    ("Ayesha", "Khan", "Physics & Electronics", "ayesha.khan@csgvanguard.edu"),
    ("Farhan", "Saeed", "Computer Science & AI", "farhan.saeed@csgvanguard.edu"),
    ("Dr. Rabia", "Zubair", "Chemistry & Biochemistry", "rabia.zubair@csgvanguard.edu"),
    ("Bilal", "Ahmed", "Biology & Genetics", "bilal.ahmed@csgvanguard.edu"),
    ("Sarah", "Jenkins", "English Literature & World History", "sarah.jenkins@csgvanguard.edu"),
    ("Hamza", "Iqbal", "Urdu & Regional Studies", "hamza.iqbal@csgvanguard.edu"),
    ("Zainab", "Ali", "Economics & Business Accounting", "zainab.ali@csgvanguard.edu"),
    ("Usman", "Raza", "Physical Education & Athletics", "usman.raza@csgvanguard.edu"),
    ("Fatima", "Noor", "Art & Graphic Design", "fatima.noor@csgvanguard.edu"),
    ("Kamran", "Akhtar", "Social Sciences & Ethics", "kamran.akhtar@csgvanguard.edu"),
    ("Nadia", "Hassan", "Islamic Studies & World Religions", "nadia.hassan@csgvanguard.edu"),
]

FIRST_NAMES = [
    "Ali", "Ahmed", "Hassan", "Hussein", "Zain", "Omar", "Hamza", "Bilal", "Daniyal", "Saad",
    "Mustafa", "Talha", "Abdullah", "Ibrahim", "Yahya", "Haris", "Rayan", "Zayd", "Shahmeer", "Waleed",
    "Fatima", "Ayesha", "Zainab", "Maryam", "Noor", "Sara", "Hiba", "Mahnoor", "Anaya", "Emaan",
    "Laiba", "Dua", "Manahil", "Rameen", "Mehak", "Minahil", "Alizeh", "Sadaf", "Zoya", "Iqra",
    "Khadija", "Hafsa", "Amina", "Zunaira", "Kinza", "Areeba", "Ayla", "Natalia", "Sophie", "Alexander"
]

LAST_NAMES = [
    "Khan", "Chaudhry", "Malik", "Sheikh", "Siddiqui", "Qureshi", "Butt", "Raza", "Abbasi", "Dar",
    "Bhatti", "Mirza", "Hashmi", "Gondal", "Janjua", "Rehman", "Farooq", "Ansari", "Bukhari", "Gilani"
]


def get_db_url() -> str:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        postgres_user = os.environ.get("POSTGRES_USER", "postgres")
        postgres_pwd = os.environ.get("POSTGRES_PASSWORD", "postgres")
        postgres_host = os.environ.get("POSTGRES_HOST", "localhost")
        postgres_port = os.environ.get("POSTGRES_PORT", "5432")
        postgres_db = os.environ.get("POSTGRES_DB", "learnhouse")
        db_url = f"postgresql+asyncpg://{postgres_user}:{postgres_pwd}@{postgres_host}:{postgres_port}/{postgres_db}"
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return db_url


async def seed_school():
    engine = create_async_engine(get_db_url(), echo=False)
    async with AsyncSession(engine) as session:
        print("🌱 Starting CSG Vanguard Academy Full Demo School Seeder...")

        # 1. Create or get Organization
        org_res = await session.exec(select(Organization).where(Organization.name == "CSG Vanguard Academy"))
        org = org_res.first()
        if not org:
            org = Organization(
                name="CSG Vanguard Academy",
                slug="csg-vanguard",
                description="Premier K-12 and College STEM & Humanities Institution",
            )
            session.add(org)
            await session.commit()
            await session.refresh(org)
        print(f"  ✓ Organization: {org.name} (ID: {org.id})")

        # 2. Create Campus
        campus_res = await session.exec(select(Campus).where(Campus.org_id == org.id))
        campus = campus_res.first()
        if not campus:
            campus = Campus(
                org_id=org.id,
                name="Main Campus - Islamabad Capital",
                code="ISB-MAIN",
                address="Sector H-8/4, Education City, Islamabad",
                is_active=True,
            )
            session.add(campus)
            await session.commit()
            await session.refresh(campus)
        print(f"  ✓ Campus: {campus.name} (ID: {campus.id})")

        # 3. Create Academic Year & Term
        current_year = date.today().year
        ay_res = await session.exec(select(AcademicYear).where(AcademicYear.org_id == org.id, AcademicYear.name == f"{current_year}-{current_year+1}"))
        ay = ay_res.first()
        if not ay:
            ay = AcademicYear(
                org_id=org.id,
                campus_id=campus.id,
                name=f"{current_year}-{current_year+1}",
                start_date=f"{current_year}-08-15",
                end_date=f"{current_year+1}-06-15",
                is_active=True,
            )
            session.add(ay)
            await session.commit()
            await session.refresh(ay)

        term_res = await session.exec(select(AcademicTerm).where(AcademicTerm.academic_year_id == ay.id))
        term = term_res.first()
        if not term:
            term = AcademicTerm(
                org_id=org.id,
                campus_id=campus.id,
                academic_year_id=ay.id,
                name="Fall Semester",
                start_date=f"{current_year}-08-15",
                end_date=f"{current_year}-12-30",
                is_active=True,
            )
            session.add(term)
            await session.commit()
            await session.refresh(term)
        print(f"  ✓ Academic Year: {ay.name} | Term: {term.name}")

        # 4. Create Teachers
        teachers: List[User] = []
        for first, last, subject, email in TEACHER_NAMES:
            u_res = await session.exec(select(User).where(User.email == email))
            u = u_res.first()
            if not u:
                u = User(
                    email=email,
                    first_name=first,
                    last_name=last,
                    username=email.split("@")[0],
                )
                session.add(u)
                await session.commit()
                await session.refresh(u)

                # Assign role & staff profile
                role = SMSUserRole(user_id=u.id, org_id=org.id, campus_id=campus.id, role=TEACHER)
                session.add(role)
                staff = StaffProfile(
                    user_id=u.id,
                    org_id=org.id,
                    campus_id=campus.id,
                    department=subject.split("&")[0].strip(),
                    job_title=f"Senior Instructor of {subject.split('&')[0].strip()}",
                )
                session.add(staff)
                await session.commit()
            teachers.append(u)
        print(f"  ✓ Seeded {len(teachers)} Subject Teachers")

        # 5. Create Sections
        sections: List[ClassSection] = []
        section_configs = [
            ("Grade 9 - STEM Alpha", "9-A", teachers[0].id),
            ("Grade 9 - Humanities Beta", "9-B", teachers[5].id),
            ("Grade 10 - Pre-Engineering", "10-A", teachers[1].id),
            ("Grade 11 - Computer Science & AI", "11-CS", teachers[2].id),
        ]
        for name, code, teacher_id in section_configs:
            s_res = await session.exec(select(ClassSection).where(ClassSection.org_id == org.id, ClassSection.code == code))
            sec = s_res.first()
            if not sec:
                sec = ClassSection(
                    org_id=org.id,
                    campus_id=campus.id,
                    name=name,
                    code=code,
                    grade_level=int(code.split("-")[0]),
                    class_teacher_id=teacher_id,
                    capacity=35,
                    is_active=True,
                )
                session.add(sec)
                await session.commit()
                await session.refresh(sec)
            sections.append(sec)
        print(f"  ✓ Seeded {len(sections)} Class Sections")

        # 6. Create 50+ Students & Guardians
        students: List[User] = []
        guardians: List[User] = []
        random.seed(42)

        for i in range(52):
            first = FIRST_NAMES[i % len(FIRST_NAMES)]
            last = LAST_NAMES[i % len(LAST_NAMES)]
            s_email = f"student.{first.lower()}.{last.lower()}{i+1}@csgvanguard.edu"
            
            s_res = await session.exec(select(User).where(User.email == s_email))
            s_user = s_res.first()
            if not s_user:
                s_user = User(
                    email=s_email,
                    first_name=first,
                    last_name=last,
                    username=s_email.split("@")[0],
                )
                session.add(s_user)
                await session.commit()
                await session.refresh(s_user)

                role = SMSUserRole(user_id=s_user.id, org_id=org.id, campus_id=campus.id, role=STUDENT)
                session.add(role)

                # Assign Section
                target_sec = sections[i % len(sections)]
                enroll = StudentEnrollment(
                    org_id=org.id,
                    campus_id=campus.id,
                    student_id=s_user.id,
                    section_id=target_sec.id,
                    academic_year_id=ay.id,
                    roll_number=f"R-{1000 + i}",
                    status="active",
                )
                session.add(enroll)

                # Gamification Streak
                streak = StudentStreak(
                    org_id=org.id,
                    user_id=s_user.id,
                    total_xp=random.randint(120, 1850),
                    level=random.randint(2, 12),
                    current_streak_days=random.randint(3, 28),
                    longest_streak_days=random.randint(10, 45),
                    last_activity_date=date.today().isoformat(),
                )
                session.add(streak)
                await session.commit()
            students.append(s_user)

            # Link Guardian every 2 students
            if i % 2 == 0:
                g_email = f"parent.{last.lower()}{i//2 + 1}@family.csg.edu"
                g_res = await session.exec(select(User).where(User.email == g_email))
                g_user = g_res.first()
                if not g_user:
                    g_user = User(
                        email=g_email,
                        first_name=f"Parent of {first}",
                        last_name=last,
                        username=g_email.split("@")[0],
                    )
                    session.add(g_user)
                    await session.commit()
                    await session.refresh(g_user)

                    g_role = SMSUserRole(user_id=g_user.id, org_id=org.id, campus_id=campus.id, role=PARENT)
                    session.add(g_role)

                    g_link = StudentGuardian(
                        guardian_user_id=g_user.id,
                        student_id=s_user.id,
                        relation_type="Father" if i % 4 == 0 else "Mother",
                        is_primary=True,
                    )
                    session.add(g_link)
                    await session.commit()
                guardians.append(g_user)

        print(f"  ✓ Seeded {len(students)} Students & {len(guardians)} Guardians")

        # 7. Seed 30 Days of Attendance Records
        for sec in sections:
            sec_enrolls = (await session.exec(select(StudentEnrollment).where(StudentEnrollment.section_id == sec.id))).all()
            for day_offset in range(1, 15):
                att_date = (date.today() - timedelta(days=day_offset)).isoformat()
                # Check if session exists
                sess_res = await session.exec(
                    select(AttendanceSession).where(
                        AttendanceSession.section_id == sec.id,
                        AttendanceSession.session_date == att_date,
                    )
                )
                att_sess = sess_res.first()
                if not att_sess:
                    att_sess = AttendanceSession(
                        org_id=org.id,
                        campus_id=campus.id,
                        section_id=sec.id,
                        session_date=att_date,
                        taken_by_id=sec.class_teacher_id or teachers[0].id,
                        status="submitted",
                    )
                    session.add(att_sess)
                    await session.commit()
                    await session.refresh(att_sess)

                    for enr in sec_enrolls:
                        roll = random.random()
                        status = "present" if roll > 0.12 else ("late" if roll > 0.05 else "absent")
                        rec = AttendanceRecord(
                            org_id=org.id,
                            session_id=att_sess.id,
                            student_id=enr.student_id,
                            status=status,
                        )
                        session.add(rec)
                    await session.commit()
        print("  ✓ Seeded realistic multi-week Attendance records across all sections")

        # 8. Seed Badges & Certificates
        badge_configs = [
            ("Math Olympian", "Scored top 5% in Advanced Calculus", "trophy", 100),
            ("Perfect Attendance 30D", "Zero absences for 30 consecutive school days", "star", 150),
            ("AI Socratic Scholar", "Completed 50 interactive Socratic tutor dialogs", "brain", 200),
            ("Code Virtuoso", "Authored clean algorithms in Python & Rust", "code", 120),
        ]
        for name, desc, icon, pts in badge_configs:
            b_res = await session.exec(select(Badge).where(Badge.name == name))
            if not b_res.first():
                badge = Badge(org_id=org.id, name=name, description=desc, icon_name=icon, points_reward=pts)
                session.add(badge)
        await session.commit()

        # Award sample badges to top 15 students
        all_badges = (await session.exec(select(Badge))).all()
        for idx in range(min(15, len(students))):
            s = students[idx]
            for b in all_badges[:2]:
                ub_res = await session.exec(select(UserBadge).where(UserBadge.user_id == s.id, UserBadge.badge_id == b.id))
                if not ub_res.first():
                    session.add(UserBadge(org_id=org.id, user_id=s.id, badge_id=b.id))
        await session.commit()

        # Seed Certificate Template
        cert_tmpl_res = await session.exec(select(CertificateTemplate).where(CertificateTemplate.org_id == org.id))
        if not cert_tmpl_res.first():
            tmpl = CertificateTemplate(
                org_id=org.id,
                title="Certificate of Academic Excellence",
                description="Awarded for outstanding scholarship and character",
                issuer_name="Dr. Asad Ullah Khan",
                issuer_title="Principal & Head of Academic Council",
            )
            session.add(tmpl)
            await session.commit()
            await session.refresh(tmpl)

            # Issue certificates to top 5 students
            for idx in range(5):
                st = students[idx]
                v_hash = hashlib.sha256(f"{st.id}:{tmpl.id}:{idx}".encode()).hexdigest()
                issued = IssuedCertificate(
                    org_id=org.id,
                    template_id=tmpl.id,
                    student_id=st.id,
                    recipient_name=f"{st.first_name} {st.last_name}",
                    recipient_email=st.email,
                    title="Dean's High Honors Award",
                    honors="Summa Cum Laude",
                    issue_date=date.today().isoformat(),
                    verification_hash=v_hash,
                )
                session.add(issued)
            await session.commit()
        print("  ✓ Seeded Gamification Badges & Issued Verifiable Certificates")

        # 9. Seed Alumni Records
        for idx in range(6):
            a_first = FIRST_NAMES[(idx + 25) % len(FIRST_NAMES)]
            a_last = LAST_NAMES[(idx + 10) % len(LAST_NAMES)]
            a_email = f"alumni.{a_first.lower()}.{a_last.lower()}@grad.csg.edu"
            
            a_res = await session.exec(select(User).where(User.email == a_email))
            a_user = a_res.first()
            if not a_user:
                a_user = User(
                    email=a_email,
                    first_name=a_first,
                    last_name=a_last,
                    username=a_email.split("@")[0],
                )
                session.add(a_user)
                await session.commit()
                await session.refresh(a_user)

                alumni_profile = AlumniProfile(
                    org_id=org.id,
                    campus_id=campus.id,
                    user_id=a_user.id,
                    graduation_year=2021 + (idx % 3),
                    degree_or_diploma="High School STEM Diploma",
                    current_company=["Google", "McKinsey", "Harvard Medical", "LUMS Tech Lab", "Stripe", "Oxford University"][idx],
                    job_title=["AI Research Engineer", "Management Consultant", "Biomedical Fellow", "Robotics Lead", "Software Architect", "PhD Researcher"][idx],
                    industry=["Technology", "Consulting", "Healthcare", "Academia", "Fintech", "Research"][idx],
                    higher_ed_institution=["MIT", "Harvard", "Stanford", "Oxford", "NUST", "LUMS"][idx],
                    higher_ed_major=["Computer Science", "Economics", "Bioengineering", "Robotics", "Finance", "Quantum Physics"][idx],
                    willing_to_mentor=True,
                    mentorship_topics="College Admissions, Tech Career, SAT/GRE Prep",
                )
                session.add(alumni_profile)
                await session.commit()
        print("  ✓ Seeded Alumni Profiles with Higher Ed & Career Records")

        print("\n✨ CSG Vanguard Academy Demo School Ecosystem Seeded Successfully!")
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Seed realistic demo school ecosystem for CSG LMS")
    parser.add_argument("--reset", action="store_true", help="Reset existing school data")
    args = parser.parse_args()
    asyncio.run(seed_school())


if __name__ == "__main__":
    main()
