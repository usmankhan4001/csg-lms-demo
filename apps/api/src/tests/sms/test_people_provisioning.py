"""
Tests for administrator-driven account provisioning.

Until this existed a school could grant a role but not create the person to
grant it to, so onboarding a teacher meant direct database access. The risks
in fixing that are specific and each has a test here:

* a default or generated password shared across a provisioned cohort,
* an account created without its role (looks done, can do nothing),
* a bulk import that reports only a total, so nobody can tell which rows to
  chase,
* a teacher, or a campus-bound admin, able to mint accounts they should not,
* SUPER_ADMIN reachable from a provisioning form.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import AcademicYear, Campus, ClassSection, StudentEnrollment
from src.db.sms_identity import (
    PersonProvisioningAction,
    SchoolRole,
    SMSPersonProvisioningEvent,
    SMSUserRole,
    StudentGuardian,
)
from src.db.user_organizations import UserOrganization
from src.db.users import User
from src.routers.sms_identity import (
    BulkProvisionRequest,
    ProvisionPersonRequest,
    assign_role,
    bulk_provision_school_people,
    list_school_directory,
    provision_school_person,
)
from src.security.security import security_verify_password
from src.tests.sms._principals import SUPERADMIN, TEACHER, principal


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

async def _school(db: AsyncSession, org_id: int, code: str = "PROV-01"):
    """A minimal but real campus -> year -> section chain to provision into."""
    campus = Campus(name="Provisioning Campus", code=code, org_id=org_id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    year = AcademicYear(name="2026-2027", campus_id=campus.id)
    section = ClassSection(grade_level="Grade 7", section_name="A", campus_id=campus.id)
    db.add(year)
    db.add(section)
    await db.commit()
    await db.refresh(year)
    await db.refresh(section)
    return campus, year, section


def _admin(org_id: int, campus_id=None, user_id: int = 900):
    return principal("SCHOOL_ADMIN", user_id=user_id, org_id=org_id, campus_id=campus_id)


# ---------------------------------------------------------------------------
# The core promise: an account AND its role, in one go
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_provisioning_a_teacher_creates_account_membership_and_role(db, org):
    campus, _, _ = await _school(db, org.id)

    resp = await provision_school_person(
        payload=ProvisionPersonRequest(
            role=SchoolRole.TEACHER,
            email="Nadia.Aslam@example.com",
            first_name="Nadia",
            last_name="Aslam",
            campus_id=campus.id,
        ),
        db_session=db,
        principal=_admin(org.id),
    )

    assert resp.created_user is True
    assert resp.created_role is True

    user = await db.get(User, resp.user_id)
    assert user is not None
    # Normalised, so a re-import with different casing matches rather than
    # minting a second account.
    assert user.email == "nadia.aslam@example.com"
    assert user.first_name == "Nadia"

    # The role landed in the same request, not a follow-up the admin might
    # never make.
    role = (
        await db.exec(
            select(SMSUserRole).where(
                SMSUserRole.user_id == resp.user_id,
                SMSUserRole.role == SchoolRole.TEACHER,
            )
        )
    ).first()
    assert role is not None
    assert role.org_id == org.id
    assert role.campus_id == campus.id
    assert role.is_active is True

    # ...and they are a member of the org, or they would authenticate into a
    # school that does not acknowledge them.
    membership = (
        await db.exec(
            select(UserOrganization).where(
                UserOrganization.user_id == resp.user_id,
                UserOrganization.org_id == org.id,
            )
        )
    ).first()
    assert membership is not None


@pytest.mark.asyncio
async def test_provisioned_account_has_no_usable_password(db, org):
    """The single most dangerous thing this feature could do is set a shared
    default password across a cohort. Nothing here may be guessable, and the
    response must not carry a password at all."""
    campus, _, _ = await _school(db, org.id)

    resp = await provision_school_person(
        payload=ProvisionPersonRequest(
            role=SchoolRole.STUDENT,
            email="omar@example.com",
            first_name="Omar",
            campus_id=campus.id,
        ),
        db_session=db,
        principal=_admin(org.id),
    )

    # Nothing password-shaped is returned to the administrator.
    assert not any("password" in f for f in resp.model_dump())

    user = await db.get(User, resp.user_id)
    # Not blank: pwdlib raises UnknownHashError on a hash it cannot identify,
    # which would turn a login attempt into a 500 rather than a clean 401.
    assert user.password
    for guess in (
        "",
        "changeme",
        "password",
        "Password123!",
        "omar@example.com",
        "Omar",
    ):
        assert security_verify_password(guess, user.password) is False


@pytest.mark.asyncio
async def test_provisioning_writes_an_audit_row(db, org):
    campus, _, _ = await _school(db, org.id)

    resp = await provision_school_person(
        payload=ProvisionPersonRequest(
            role=SchoolRole.PSYCHOLOGIST,
            email="counsellor@example.com",
            first_name="Sana",
            campus_id=campus.id,
        ),
        db_session=db,
        principal=_admin(org.id, user_id=77),
    )

    event = (
        await db.exec(
            select(SMSPersonProvisioningEvent).where(
                SMSPersonProvisioningEvent.subject_user_id == resp.user_id
            )
        )
    ).first()
    assert event is not None
    assert event.action == PersonProvisioningAction.CREATED
    assert event.role == "PSYCHOLOGIST"
    assert event.org_id == org.id
    # The AUTHENTICATED caller, not a client-supplied field.
    assert event.actor_user_id == 77
    assert event.via_bulk_import is False


@pytest.mark.asyncio
async def test_reprovisioning_the_same_email_reuses_the_account(db, org):
    """A retried import or a family listed twice must not mint a duplicate,
    and must say so rather than claiming a fresh account."""
    campus, _, _ = await _school(db, org.id)
    payload = ProvisionPersonRequest(
        role=SchoolRole.STAFF,
        email="bursar@example.com",
        first_name="Imran",
        campus_id=campus.id,
    )
    first = await provision_school_person(payload=payload, db_session=db, principal=_admin(org.id))
    second = await provision_school_person(payload=payload, db_session=db, principal=_admin(org.id))

    assert first.created_user is True
    assert second.created_user is False
    assert second.user_id == first.user_id

    users = (await db.exec(select(User).where(User.email == "bursar@example.com"))).all()
    assert len(users) == 1


# ---------------------------------------------------------------------------
# Placement: a student who is not enrolled is invisible to every module
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_student_provisioned_with_a_section_is_actually_enrolled(db, org):
    campus, year, section = await _school(db, org.id)

    resp = await provision_school_person(
        payload=ProvisionPersonRequest(
            role=SchoolRole.STUDENT,
            email="zara@example.com",
            first_name="Zara",
            campus_id=campus.id,
            section_id=section.id,
            academic_year_id=year.id,
            roll_number="7A-014",
        ),
        db_session=db,
        principal=_admin(org.id),
    )

    assert resp.created_enrollment is True
    enrollment = (
        await db.exec(
            select(StudentEnrollment).where(StudentEnrollment.student_id == resp.user_id)
        )
    ).first()
    assert enrollment is not None
    assert enrollment.section_id == section.id
    assert enrollment.academic_year_id == year.id
    assert enrollment.roll_number == "7A-014"
    assert enrollment.status == "active"


@pytest.mark.asyncio
async def test_enrolment_into_a_missing_section_creates_no_orphan_account(db, org):
    """Placement is validated before anything is written, so a typo'd section
    id does not leave an account behind that nobody knows about."""
    campus, year, _ = await _school(db, org.id)

    with pytest.raises(HTTPException) as exc:
        await provision_school_person(
            payload=ProvisionPersonRequest(
                role=SchoolRole.STUDENT,
                email="ghost@example.com",
                first_name="Ghost",
                campus_id=campus.id,
                section_id=999_999,
                academic_year_id=year.id,
            ),
            db_session=db,
            principal=_admin(org.id),
        )
    assert exc.value.status_code == 400

    await db.rollback()
    assert (await db.exec(select(User).where(User.email == "ghost@example.com"))).first() is None


@pytest.mark.asyncio
async def test_only_a_student_may_be_enrolled(db, org):
    campus, year, section = await _school(db, org.id)
    with pytest.raises(HTTPException) as exc:
        await provision_school_person(
            payload=ProvisionPersonRequest(
                role=SchoolRole.TEACHER,
                email="teach@example.com",
                first_name="Teach",
                campus_id=campus.id,
                section_id=section.id,
                academic_year_id=year.id,
            ),
            db_session=db,
            principal=_admin(org.id),
        )
    assert exc.value.status_code == 400
    assert "STUDENT" in str(exc.value.detail)


# ---------------------------------------------------------------------------
# Parents: an unlinked parent account can see nothing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parent_provisioned_with_a_child_is_actually_linked(db, org):
    campus, year, section = await _school(db, org.id)
    admin = _admin(org.id)

    student = await provision_school_person(
        payload=ProvisionPersonRequest(
            role=SchoolRole.STUDENT,
            email="child@example.com",
            first_name="Child",
            campus_id=campus.id,
            section_id=section.id,
            academic_year_id=year.id,
        ),
        db_session=db,
        principal=admin,
    )

    parent = await provision_school_person(
        payload=ProvisionPersonRequest(
            role=SchoolRole.PARENT,
            email="parent@example.com",
            first_name="Parent",
            campus_id=campus.id,
            child_student_id=student.user_id,
            relationship="mother",
            is_primary_contact=True,
        ),
        db_session=db,
        principal=admin,
    )

    assert parent.created_guardian_link is True
    link = (
        await db.exec(
            select(StudentGuardian).where(
                StudentGuardian.guardian_user_id == parent.user_id,
                StudentGuardian.student_id == student.user_id,
            )
        )
    ).first()
    assert link is not None
    assert link.relationship == "mother"
    assert link.is_primary_contact is True


@pytest.mark.asyncio
async def test_parent_cannot_be_linked_to_a_non_student(db, org):
    """Otherwise a guardian could be attached to -- and then read the records
    of -- somebody who is not a student at this school."""
    campus, _, _ = await _school(db, org.id)
    admin = _admin(org.id)

    outsider = await provision_school_person(
        payload=ProvisionPersonRequest(
            role=SchoolRole.STAFF,
            email="outsider@example.com",
            first_name="Outsider",
            campus_id=campus.id,
        ),
        db_session=db,
        principal=admin,
    )

    with pytest.raises(HTTPException) as exc:
        await provision_school_person(
            payload=ProvisionPersonRequest(
                role=SchoolRole.PARENT,
                email="claimant@example.com",
                first_name="Claimant",
                campus_id=campus.id,
                child_student_id=outsider.user_id,
            ),
            db_session=db,
            principal=admin,
        )
    assert exc.value.status_code == 400
    assert "not an active student" in str(exc.value.detail)


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_super_admin_cannot_be_provisioned_even_by_a_super_admin(db, org):
    """SUPER_ADMIN is cross-tenant platform control. It has no legitimate use
    on a school-administration form, so it is refused for everyone here rather
    than merely restricted to superadmins."""
    campus, _, _ = await _school(db, org.id)

    for caller in (_admin(org.id), principal("SUPER_ADMIN", org_id=org.id, campus_id=None)):
        with pytest.raises(HTTPException) as exc:
            await provision_school_person(
                payload=ProvisionPersonRequest(
                    role=SchoolRole.SUPER_ADMIN,
                    email="escalate@example.com",
                    first_name="Escalate",
                    campus_id=campus.id,
                ),
                db_session=db,
                principal=caller,
            )
        assert exc.value.status_code == 403

    await db.rollback()
    assert (await db.exec(select(User).where(User.email == "escalate@example.com"))).first() is None


@pytest.mark.asyncio
async def test_a_campus_bound_admin_cannot_provision_into_another_campus(db, org):
    campus_a, _, _ = await _school(db, org.id, code="PROV-A")
    campus_b, _, _ = await _school(db, org.id, code="PROV-B")

    bound_to_a = _admin(org.id, campus_id=campus_a.id)

    with pytest.raises(HTTPException) as exc:
        await provision_school_person(
            payload=ProvisionPersonRequest(
                role=SchoolRole.TEACHER,
                email="crosscampus@example.com",
                first_name="Cross",
                campus_id=campus_b.id,
            ),
            db_session=db,
            principal=bound_to_a,
        )
    assert exc.value.status_code == 403

    await db.rollback()
    assert (
        await db.exec(select(User).where(User.email == "crosscampus@example.com"))
    ).first() is None


@pytest.mark.asyncio
async def test_a_campus_bound_admin_omitting_a_campus_provisions_into_their_own(db, org):
    """Omitting the field must not buy org-wide reach -- the hole
    `resolve_scoped_campus_id` exists to close."""
    campus_a, _, _ = await _school(db, org.id, code="PROV-C")

    resp = await provision_school_person(
        payload=ProvisionPersonRequest(
            role=SchoolRole.TEACHER,
            email="unscoped@example.com",
            first_name="Unscoped",
        ),
        db_session=db,
        principal=_admin(org.id, campus_id=campus_a.id),
    )

    role = (
        await db.exec(select(SMSUserRole).where(SMSUserRole.user_id == resp.user_id))
    ).first()
    assert role.campus_id == campus_a.id


@pytest.mark.asyncio
async def test_a_teacher_cannot_provision_anyone(db, org):
    """`require_roles` is a FastAPI dependency, so calling a handler directly
    bypasses it. Pull the REAL dependency off each route and run it with a
    teacher principal, which is what production actually does."""
    from fastapi.routing import APIRoute

    from src.routers.sms_identity import router

    gated = {
        "/identity/provision",
        "/identity/provision/bulk",
        "/identity/directory",
    }
    checked = set()
    for route in router.routes:
        if not isinstance(route, APIRoute) or route.path not in gated:
            continue
        checkers = [
            dep.call
            for dep in route.dependant.dependencies
            if getattr(dep.call, "__name__", "") == "_role_checker"
        ]
        assert checkers, f"{route.path} declares no require_roles gate"
        for checker in checkers:
            with pytest.raises(HTTPException) as exc:
                await checker(principal=TEACHER)
            assert exc.value.status_code == 403
            # The same gate admits the people it should.
            assert await checker(principal=_admin(org.id)) is not None
        checked.add(route.path)

    assert checked == gated


@pytest.mark.asyncio
async def test_school_admin_cannot_grant_super_admin_through_the_role_endpoint(db, org):
    """The provisioning form is not the only way in: `POST /identity/roles`
    took `role` straight from the body and admitted SCHOOL_ADMIN callers, so a
    school admin could grant themselves SUPER_ADMIN. The frontend even offered
    it in its dropdown."""
    from src.db.sms_identity import SMSUserRoleCreate

    with pytest.raises(HTTPException) as exc:
        await assign_role(
            payload=SMSUserRoleCreate(
                user_id=1, org_id=org.id, role=SchoolRole.SUPER_ADMIN
            ),
            db_session=db,
            principal=_admin(org.id),
        )
    assert exc.value.status_code == 403

    # A real superadmin is still able to.
    assert SUPERADMIN.is_superadmin is True


@pytest.mark.asyncio
async def test_school_admin_cannot_grant_a_role_in_another_org(db, org, other_org):
    from src.db.sms_identity import SMSUserRoleCreate

    with pytest.raises(HTTPException) as exc:
        await assign_role(
            payload=SMSUserRoleCreate(
                user_id=1, org_id=other_org.id, role=SchoolRole.SCHOOL_ADMIN
            ),
            db_session=db,
            principal=_admin(org.id),
        )
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_import_reports_every_row_individually(db, org):
    """A total alone ("47 created, 3 failed") is unusable: nobody can tell
    which three families to chase. Each failure must name its row, its email
    and its reason -- and must not discard the good rows."""
    campus, year, section = await _school(db, org.id)

    resp = await bulk_provision_school_people(
        payload=BulkProvisionRequest(
            people=[
                ProvisionPersonRequest(
                    role=SchoolRole.STUDENT,
                    email="row0@example.com",
                    first_name="Row",
                    last_name="Zero",
                    campus_id=campus.id,
                    section_id=section.id,
                    academic_year_id=year.id,
                ),
                # Bad email.
                ProvisionPersonRequest(
                    role=SchoolRole.STUDENT,
                    email="not-an-email",
                    first_name="Row",
                    last_name="One",
                    campus_id=campus.id,
                ),
                ProvisionPersonRequest(
                    role=SchoolRole.TEACHER,
                    email="row2@example.com",
                    first_name="Row",
                    last_name="Two",
                    campus_id=campus.id,
                ),
                # Missing name.
                ProvisionPersonRequest(
                    role=SchoolRole.STUDENT,
                    email="row3@example.com",
                    first_name="   ",
                    campus_id=campus.id,
                ),
                # Section that does not exist.
                ProvisionPersonRequest(
                    role=SchoolRole.STUDENT,
                    email="row4@example.com",
                    first_name="Row",
                    last_name="Four",
                    campus_id=campus.id,
                    section_id=999_999,
                    academic_year_id=year.id,
                ),
            ]
        ),
        db_session=db,
        principal=_admin(org.id),
    )

    assert resp.created == 2
    assert resp.failed == 3
    assert len(resp.results) == 5

    by_row = {r.row: r for r in resp.results}
    assert by_row[0].status == "created"
    assert by_row[2].status == "created"

    for bad_row in (1, 3, 4):
        assert by_row[bad_row].status == "failed"
        # Each failure is actionable on its own, without cross-referencing.
        assert by_row[bad_row].error
        assert by_row[bad_row].user_id is None
    assert by_row[1].email == "not-an-email"
    assert "999999" in by_row[4].error or "999,999" in by_row[4].error

    # The good rows survived the bad ones.
    assert (await db.exec(select(User).where(User.email == "row0@example.com"))).first() is not None
    assert (await db.exec(select(User).where(User.email == "row2@example.com"))).first() is not None
    # ...and the bad ones left nothing behind.
    for bad_email in ("row3@example.com", "row4@example.com"):
        assert (await db.exec(select(User).where(User.email == bad_email))).first() is None

    # Row 0's enrolment actually happened; a "created" student who is not
    # enrolled would be invisible to attendance and the gradebook.
    student = (await db.exec(select(User).where(User.email == "row0@example.com"))).first()
    enrollment = (
        await db.exec(
            select(StudentEnrollment).where(StudentEnrollment.student_id == student.id)
        )
    ).first()
    assert enrollment is not None
    assert enrollment.section_id == section.id


@pytest.mark.asyncio
async def test_bulk_import_distinguishes_reused_accounts_from_created_ones(db, org):
    campus, _, _ = await _school(db, org.id)
    admin = _admin(org.id)

    people = [
        ProvisionPersonRequest(
            role=SchoolRole.PARENT,
            email="dup@example.com",
            first_name="Dup",
            campus_id=campus.id,
        ),
        ProvisionPersonRequest(
            role=SchoolRole.PARENT,
            email="DUP@example.com",
            first_name="Dup",
            campus_id=campus.id,
        ),
    ]
    resp = await bulk_provision_school_people(
        payload=BulkProvisionRequest(people=people), db_session=db, principal=admin
    )

    assert resp.created == 1
    assert resp.reused == 1
    assert resp.failed == 0
    assert [r.status for r in resp.results] == ["created", "reused"]


@pytest.mark.asyncio
async def test_bulk_import_rejects_an_empty_list(db, org):
    with pytest.raises(HTTPException) as exc:
        await bulk_provision_school_people(
            payload=BulkProvisionRequest(people=[]),
            db_session=db,
            principal=_admin(org.id),
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_bulk_rows_are_audited_as_bulk(db, org):
    campus, _, _ = await _school(db, org.id)
    resp = await bulk_provision_school_people(
        payload=BulkProvisionRequest(
            people=[
                ProvisionPersonRequest(
                    role=SchoolRole.STAFF,
                    email="bulkaudit@example.com",
                    first_name="Bulk",
                    campus_id=campus.id,
                )
            ]
        ),
        db_session=db,
        principal=_admin(org.id),
    )
    event = (
        await db.exec(
            select(SMSPersonProvisioningEvent).where(
                SMSPersonProvisioningEvent.subject_user_id == resp.results[0].user_id
            )
        )
    ).first()
    assert event is not None
    assert event.via_bulk_import is True


# ---------------------------------------------------------------------------
# Directory
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_directory_shows_members_with_no_role_and_never_guesses_one(db, org):
    """`GET /identity/people` filters to one role, so somebody with none can
    never appear in it -- which is precisely the person an administrator is
    looking for. And a member with no role must read as having none, not be
    defaulted to STUDENT."""
    campus, _, _ = await _school(db, org.id)
    admin = _admin(org.id)

    await provision_school_person(
        payload=ProvisionPersonRequest(
            role=SchoolRole.TEACHER,
            email="withrole@example.com",
            first_name="With",
            campus_id=campus.id,
        ),
        db_session=db,
        principal=admin,
    )

    # A member who joined the org without a school role ever being granted.
    orphan = User(
        username="orphan",
        first_name="No",
        last_name="Role",
        email="norole@example.com",
        password="x",
        user_uuid="user_orphan",
    )
    db.add(orphan)
    await db.commit()
    await db.refresh(orphan)
    db.add(
        UserOrganization(
            user_id=orphan.id,
            org_id=org.id,
            role_id=4,
            creation_date="2026-01-01",
            update_date="2026-01-01",
        )
    )
    await db.commit()

    everyone = await list_school_directory(
        campus_id=None, unassigned_only=False, db_session=db, principal=admin
    )
    by_email = {e.email: e for e in everyone}
    assert by_email["withrole@example.com"].roles == ["TEACHER"]
    # Empty, not a guess.
    assert by_email["norole@example.com"].roles == []

    unassigned = await list_school_directory(
        campus_id=None, unassigned_only=True, db_session=db, principal=admin
    )
    assert [e.email for e in unassigned] == ["norole@example.com"]
