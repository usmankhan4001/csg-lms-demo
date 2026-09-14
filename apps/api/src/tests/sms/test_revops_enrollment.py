"""
Tests for closing the admissions -> enrollment loop.

Until `revops_enrollment.py` existed, moving a lead to ENROLLED was a bare
field update: the funnel recorded a win and no student ever appeared. The
risk in fixing that is the opposite failure -- provisioning that runs twice
and mints duplicate accounts, or that half-completes and leaves a lead with
a user but no enrollment (invisible to every school module while occupying
an email address). These tests target exactly those two failure modes.
"""

from src.tests.sms._principals import SUPERADMIN
import pytest
from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import AcademicYear, Campus, ClassSection, StudentEnrollment
from src.db.sms_identity import SchoolRole, SMSUserRole
from src.db.sms_revops import AdmissionsLead, LeadSource, LeadStage
from src.db.users import User
from src.schemas.sms_revops import EnrollLeadRequest, LeadCreate, LeadStageUpdate
from src.routers.sms_revops import (
    create_lead_endpoint,
    enroll_lead_endpoint,
    update_lead_stage_endpoint,
)
from src.services.sms.revops import enroll_lead


async def _school(db: AsyncSession, org_id: int, code: str = "ENR-01"):
    """A minimal but real campus -> year -> section chain to enrol into."""
    campus = Campus(name="Enrolment Campus", code=code, org_id=org_id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    year = AcademicYear(name="2026-2027", campus_id=campus.id)
    section = ClassSection(grade_level="Grade 9", section_name="A", campus_id=campus.id)
    db.add(year)
    db.add(section)
    await db.commit()
    await db.refresh(year)
    await db.refresh(section)
    return campus, year, section


async def _lead(db: AsyncSession, campus_id: int, email: str = "parent@example.com"):
    return await create_lead_endpoint(
        payload=LeadCreate(
            parent_name="Parent Name",
            student_name="Aisha Khan",
            email=email,
            phone="+92-300-1234567",
            grade_applying_for="Grade 9",
            campus_id=campus_id,
            source=LeadSource.WEBSITE_FORM,
        ),
        session=db,
        principal=SUPERADMIN,
    )


@pytest.mark.asyncio
async def test_enrolling_a_lead_creates_account_role_and_enrollment(db, org):
    campus, year, section = await _school(db, org.id)
    lead = await _lead(db, campus.id)

    resp = await enroll_lead_endpoint(
        lead_id=lead.id,
        payload=EnrollLeadRequest(
            section_id=section.id,
            academic_year_id=year.id,
            student_email="aisha.khan@example.com",
        ),
        session=db,
    )

    assert resp.created_user is True
    assert resp.created_role is True
    assert resp.created_enrollment is True
    assert resp.already_provisioned is False
    assert resp.lead.stage == LeadStage.ENROLLED

    # The learner is a real Learnhouse user, not just a CRM row.
    user = await db.get(User, resp.student_id)
    assert user is not None
    assert user.email == "aisha.khan@example.com"
    assert user.first_name == "Aisha"

    # ...holds the STUDENT school role in the right org and campus...
    role = (
        await db.exec(
            select(SMSUserRole).where(
                SMSUserRole.user_id == resp.student_id,
                SMSUserRole.role == SchoolRole.STUDENT,
            )
        )
    ).first()
    assert role is not None
    assert role.org_id == org.id
    assert role.campus_id == campus.id
    assert role.is_active is True

    # ...and is actually enrolled in the section.
    enrollment = await db.get(StudentEnrollment, resp.enrollment_id)
    assert enrollment is not None
    assert enrollment.section_id == section.id
    assert enrollment.academic_year_id == year.id
    assert enrollment.status == "active"


@pytest.mark.asyncio
async def test_enrolling_twice_does_not_create_a_second_student(db, org):
    """The failure this guards: a double-click or retried request minting two
    accounts for one child, each with its own enrollment."""
    campus, year, section = await _school(db, org.id, code="ENR-02")
    lead = await _lead(db, campus.id, email="parent2@example.com")
    req = EnrollLeadRequest(
        section_id=section.id,
        academic_year_id=year.id,
        student_email="repeat.student@example.com",
    )

    first = await enroll_lead_endpoint(lead_id=lead.id, payload=req, session=db)
    second = await enroll_lead_endpoint(lead_id=lead.id, payload=req, session=db)

    assert second.student_id == first.student_id
    assert second.enrollment_id == first.enrollment_id
    assert second.created_user is False
    assert second.created_role is False
    assert second.created_enrollment is False
    assert second.already_provisioned is True

    users = (
        await db.exec(select(User).where(User.email == "repeat.student@example.com"))
    ).all()
    assert len(users) == 1

    enrollments = (
        await db.exec(
            select(StudentEnrollment).where(StudentEnrollment.student_id == first.student_id)
        )
    ).all()
    assert len(enrollments) == 1


@pytest.mark.asyncio
async def test_repeat_enrollment_does_not_log_a_duplicate_stage_change(db, org):
    """An already-ENROLLED lead re-submitted should not litter the audit trail
    with ENROLLED -> ENROLLED entries."""
    from src.db.sms_revops import ActivityType, LeadActivityLog

    campus, year, section = await _school(db, org.id, code="ENR-03")
    lead = await _lead(db, campus.id, email="parent3@example.com")
    req = EnrollLeadRequest(
        section_id=section.id,
        academic_year_id=year.id,
        student_email="audit.student@example.com",
    )

    await enroll_lead_endpoint(lead_id=lead.id, payload=req, session=db)
    await enroll_lead_endpoint(lead_id=lead.id, payload=req, session=db)

    stage_logs = (
        await db.exec(
            select(LeadActivityLog).where(
                LeadActivityLog.lead_id == lead.id,
                LeadActivityLog.activity_type == ActivityType.STAGE_CHANGE,
            )
        )
    ).all()
    assert len(stage_logs) == 1


@pytest.mark.asyncio
async def test_missing_section_fails_cleanly_and_provisions_nothing(db, org):
    """Setup guidance, not a 500 -- and critically, no orphaned user account
    left behind holding the email address."""
    campus, year, _ = await _school(db, org.id, code="ENR-04")
    lead = await _lead(db, campus.id, email="parent4@example.com")

    with pytest.raises(HTTPException) as exc:
        await enroll_lead_endpoint(
            lead_id=lead.id,
            payload=EnrollLeadRequest(
                section_id=999999,
                academic_year_id=year.id,
                student_email="orphan.check@example.com",
            ),
            session=db,
        )
    assert exc.value.status_code == 400
    assert "section" in str(exc.value.detail).lower()

    await db.rollback()
    leftover = (
        await db.exec(select(User).where(User.email == "orphan.check@example.com"))
    ).all()
    assert leftover == []

    # The lead must not have been advanced by a failed enrollment.
    refreshed = await db.get(AdmissionsLead, lead.id)
    assert refreshed is not None
    assert refreshed.stage != LeadStage.ENROLLED


@pytest.mark.asyncio
async def test_cross_campus_year_and_section_is_rejected(db, org):
    """A student cannot be enrolled into a section on one campus using another
    campus's academic year -- that would silently corrupt tenancy scoping."""
    campus_a, year_a, _ = await _school(db, org.id, code="ENR-05A")
    campus_b, _, section_b = await _school(db, org.id, code="ENR-05B")
    lead = await _lead(db, campus_a.id, email="parent5@example.com")

    with pytest.raises(HTTPException) as exc:
        await enroll_lead_endpoint(
            lead_id=lead.id,
            payload=EnrollLeadRequest(
                section_id=section_b.id,
                academic_year_id=year_a.id,
                student_email="crosscampus@example.com",
            ),
            session=db,
        )
    assert exc.value.status_code == 400
    assert "campus" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_enrolling_requires_a_student_email(db, org):
    """The lead's own email belongs to the PARENT. Refusing to assume it is
    the student's is deliberate -- see revops_enrollment's module docstring."""
    campus, year, section = await _school(db, org.id, code="ENR-06")
    lead = await _lead(db, campus.id, email="parent6@example.com")

    with pytest.raises(HTTPException) as exc:
        await enroll_lead_endpoint(
            lead_id=lead.id,
            payload=EnrollLeadRequest(
                section_id=section.id,
                academic_year_id=year.id,
                student_email="   ",
            ),
            session=db,
        )
    assert exc.value.status_code == 400
    assert "email" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_a_lost_lead_cannot_be_enrolled(db, org):
    campus, year, section = await _school(db, org.id, code="ENR-07")
    lead = await _lead(db, campus.id, email="parent7@example.com")
    await update_lead_stage_endpoint(
        lead_id=lead.id, payload=LeadStageUpdate(stage=LeadStage.LOST), session=db
    )

    with pytest.raises(HTTPException) as exc:
        await enroll_lead_endpoint(
            lead_id=lead.id,
            payload=EnrollLeadRequest(
                section_id=section.id,
                academic_year_id=year.id,
                student_email="lost.lead@example.com",
            ),
            session=db,
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_existing_user_is_reused_rather_than_duplicated(db, org):
    """A sibling already in the system, or a student re-enrolling for a new
    year, must attach to the existing account."""
    campus, year, section = await _school(db, org.id, code="ENR-08")
    lead = await _lead(db, campus.id, email="parent8@example.com")

    existing = User(
        username="already.here",
        first_name="Already",
        last_name="Here",
        email="already.here@example.com",
        password="hashed",
        user_uuid="user_pre-existing",
        creation_date="2026-01-01",
        update_date="2026-01-01",
    )
    db.add(existing)
    await db.commit()
    await db.refresh(existing)

    resp = await enroll_lead_endpoint(
        lead_id=lead.id,
        payload=EnrollLeadRequest(
            section_id=section.id,
            academic_year_id=year.id,
            student_email="already.here@example.com",
        ),
        session=db,
    )

    assert resp.student_id == existing.id
    assert resp.created_user is False
    # Still gets the role and enrollment it was missing.
    assert resp.created_role is True
    assert resp.created_enrollment is True
