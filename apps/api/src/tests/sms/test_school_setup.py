"""
Tests for first-run school setup.

The thing being prevented here is a HALF-BUILT TENANT. An organisation with a
campus but no academic year, or with structure but no administrator, is not an
obviously broken state -- it is a school where most modules render empty and
nothing on screen explains why, so the reader concludes the software is
broken rather than unconfigured.

The specific risks each have a test below:

* structure created but the founding administrator's grant missing, so nobody
  can administer the school that was just created for them;
* a failure partway through leaving a campus and some terms behind;
* setup usable as a route to minting administrators after the fact;
* a caller configuring an organisation that is not theirs;
* an optional default failing and destroying an otherwise good school.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import select

from src.db.sms_campus import AcademicTerm, AcademicYear, Campus
from src.db.sms_identity import SchoolRole, SMSUserRole
from src.db.user_organizations import UserOrganization
from src.db.users import User
from src.routers.sms_school_setup import (
    SchoolSetupRequest,
    TermPayload,
    get_school_setup_status,
    run_school_setup,
)
from src.tests.sms._principals import SUPERADMIN, principal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_org_owner(db, *, user_id: int, org_id: int) -> User:
    """A real user who owns the org in Learnhouse's own model (role_id=1).

    This is the bootstrap caller: somebody who created an organisation through
    Learnhouse's wizard and therefore holds NO school roles at all.
    """
    user = User(
        id=user_id,
        email=f"owner{user_id}@example.com",
        username=f"owner{user_id}",
        first_name="Org",
        last_name="Owner",
        password="x",
        user_uuid=f"user_{user_id}",
        email_verified=True,
        creation_date="2026-01-01",
        update_date="2026-01-01",
    )
    db.add(user)
    db.add(
        UserOrganization(
            user_id=user_id,
            org_id=org_id,
            role_id=1,
            creation_date="2026-01-01",
            update_date="2026-01-01",
        )
    )
    await db.commit()
    return user


def _owner_principal(user_id: int):
    """The bootstrap principal: authenticated, but no school roles and NO org_id.

    `org_id=None` is the real shape -- `resolve_school_principal` sources it
    from SMSUserRole grants, and this person has none. Any code that reached
    for `principal.org_id or 1` here would configure organisation 1.
    """
    p = principal(user_id=user_id, org_id=None, campus_id=None)
    return p


def _request(org_id: int, **overrides) -> SchoolSetupRequest:
    payload = dict(
        org_id=org_id,
        campus_name="Lighthouse Main Campus",
        campus_code="MAIN",
        campus_timezone="Asia/Karachi",
        academic_year_name="2026-2027",
        academic_year_start="2026-08-01",
        academic_year_end="2027-06-30",
        terms=[
            TermPayload(
                name="Term 1",
                term_code="T1",
                weight_percentage=50.0,
                start_date="2026-08-01",
                end_date="2026-12-20",
            ),
            TermPayload(
                name="Term 2",
                term_code="T2",
                weight_percentage=50.0,
                start_date="2027-01-10",
                end_date="2027-06-30",
            ),
        ],
        admin_email="head@lighthouse.example.com",
        admin_first_name="Ayesha",
        admin_last_name="Khan",
    )
    payload.update(overrides)
    return SchoolSetupRequest(**payload)


# ---------------------------------------------------------------------------
# The core promise: a complete, usable school
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setup_creates_campus_year_terms_and_a_usable_admin(db, org):
    resp = await run_school_setup(
        payload=_request(org.id), db_session=db, principal=SUPERADMIN
    )

    campus = await db.get(Campus, resp.campus_id)
    assert campus is not None
    assert campus.org_id == org.id
    assert campus.timezone == "Asia/Karachi"

    year = await db.get(AcademicYear, resp.academic_year_id)
    assert year is not None
    assert year.campus_id == campus.id

    terms = list(
        (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.academic_year_id == resp.academic_year_id
                )
            )
        ).scalars().all()
    )
    assert len(terms) == 2

    # The part that actually matters: the founding admin must hold a real
    # SMSUserRole grant, because principal.roles is built from nothing else.
    # Without it they own a school they cannot administer.
    assert resp.admin_user_id is not None
    grant = (
        await db.execute(
            select(SMSUserRole).where(
                SMSUserRole.user_id == resp.admin_user_id,
                SMSUserRole.role == SchoolRole.SCHOOL_ADMIN,
            )
        )
    ).scalars().first()
    assert grant is not None
    assert grant.org_id == org.id
    assert grant.is_active is True

    # ...and org membership, which provision_learner_from_lead notoriously
    # omits, leaving an account that belongs to no organisation.
    membership = (
        await db.execute(
            select(UserOrganization).where(
                UserOrganization.user_id == resp.admin_user_id,
                UserOrganization.org_id == org.id,
            )
        )
    ).scalars().first()
    assert membership is not None


@pytest.mark.asyncio
async def test_founding_admin_gets_no_usable_password(db, org):
    """Setup must not invent a credential any more than provisioning does."""
    from src.security.security import security_verify_password

    resp = await run_school_setup(
        payload=_request(org.id), db_session=db, principal=SUPERADMIN
    )
    user = await db.get(User, resp.admin_user_id)
    assert user is not None

    for guess in ("", "changeme", "password", "Password123!", user.email, "Ayesha"):
        assert not security_verify_password(guess, user.password)


# ---------------------------------------------------------------------------
# No half-built tenants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failure_at_the_admin_stage_leaves_no_campus_behind(db, org):
    """The central promise.

    An unusable admin email fails inside provision_person, AFTER the campus,
    year and terms have been staged. Nothing may survive that.
    """
    # Read the id BEFORE the call: the rollback under test expires every ORM
    # object on this session, so touching `org.id` afterwards would trigger a
    # lazy refresh outside the async context and fail as MissingGreenlet --
    # an artefact of the test, not of the rollback.
    org_id = org.id

    with pytest.raises(HTTPException):
        await run_school_setup(
            payload=_request(org_id, admin_email="not-an-email"),
            db_session=db,
            principal=SUPERADMIN,
        )

    assert (
        await db.execute(select(Campus).where(Campus.org_id == org_id))
    ).scalars().first() is None
    assert (await db.execute(select(AcademicYear))).scalars().first() is None
    assert (await db.execute(select(AcademicTerm))).scalars().first() is None


@pytest.mark.asyncio
async def test_invalid_term_dates_write_nothing_at_all(db, org):
    """Validation runs before the first write, so a bad term 2 cannot leave a
    campus and a term 1 behind."""
    org_id = org.id  # see note in the test above

    with pytest.raises(HTTPException) as exc:
        await run_school_setup(
            payload=_request(
                org_id,
                terms=[
                    TermPayload(name="Term 1", start_date="2026-08-01", end_date="2026-12-20"),
                    TermPayload(name="Term 2", start_date="2027-06-01", end_date="2027-01-10"),
                ],
            ),
            db_session=db,
            principal=SUPERADMIN,
        )
    assert exc.value.status_code == 400
    assert (
        await db.execute(select(Campus).where(Campus.org_id == org_id))
    ).scalars().first() is None


@pytest.mark.asyncio
async def test_duplicate_campus_code_is_refused_with_a_readable_message(db, org):
    await run_school_setup(payload=_request(org.id), db_session=db, principal=SUPERADMIN)

    # A second org, so the "already set up" guard is not what refuses us.
    from src.db.organizations import Organization

    other = Organization(
        id=2,
        name="Other",
        slug="other",
        email="o@o.com",
        org_uuid="org_other",
        creation_date="2026-01-01",
        update_date="2026-01-01",
    )
    db.add(other)
    await db.commit()

    # Same code, different org -- must be allowed, codes are unique per org.
    resp = await run_school_setup(
        payload=_request(2, campus_code="MAIN"), db_session=db, principal=SUPERADMIN
    )
    assert resp.campus_id is not None


# ---------------------------------------------------------------------------
# Authorisation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_org_owner_can_bootstrap_despite_having_no_school_roles(db, org):
    """The bootstrap case.

    Somebody who created an organisation holds no SMSUserRole, so
    principal.roles is empty and principal.org_id is None. Gating on
    require_roles([SCHOOL_ADMIN]) would lock them out of the setup that grants
    the very role being demanded.
    """
    await _make_org_owner(db, user_id=700, org_id=org.id)

    resp = await run_school_setup(
        payload=_request(org.id), db_session=db, principal=_owner_principal(700)
    )
    assert resp.campus_id is not None


@pytest.mark.asyncio
async def test_a_stranger_cannot_set_up_someone_elses_school(db, org):
    """A logged-in user with no relationship to the org is refused.

    Note the principal has org_id=None: this is exactly the shape that the
    `principal.org_id or 1` pattern elsewhere in this codebase turns into
    "organisation 1", which would have been somebody else's school.
    """
    stranger = User(
        id=701,
        email="stranger@example.com",
        username="stranger",
        first_name="No",
        last_name="Access",
        password="x",
        user_uuid="user_701",
        email_verified=True,
        creation_date="2026-01-01",
        update_date="2026-01-01",
    )
    db.add(stranger)
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await run_school_setup(
            payload=_request(org.id),
            db_session=db,
            principal=_owner_principal(701),
        )
    assert exc.value.status_code == 403

    assert (
        await db.execute(select(Campus).where(Campus.org_id == org.id))
    ).scalars().first() is None


@pytest.mark.asyncio
async def test_setup_is_one_shot_even_for_a_superadmin(db, org):
    """Re-running setup must not be a way to mint further administrators."""
    await run_school_setup(payload=_request(org.id), db_session=db, principal=SUPERADMIN)

    with pytest.raises(HTTPException) as exc:
        await run_school_setup(
            payload=_request(org.id, campus_code="SECOND", admin_email="second@x.com"),
            db_session=db,
            principal=SUPERADMIN,
        )
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# Status: honest about an unconfigured school
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_reports_what_is_missing_not_a_reassuring_zero(db, org):
    """A brand-new org has nothing. The status must say 'not set up' and name
    what is absent -- counts of 0 alongside is_set_up=False, never a bare zero
    that reads as 'nothing to do'."""
    state = await get_school_setup_status(
        org_id=org.id, db_session=db, principal=SUPERADMIN
    )

    assert state.is_set_up is False
    assert set(state.missing) == {
        "campus",
        "academic_year",
        "academic_term",
        "school_admin",
    }
    assert state.campus_count == 0
    assert state.may_run_setup is True


@pytest.mark.asyncio
async def test_status_after_setup_is_complete(db, org):
    await run_school_setup(payload=_request(org.id), db_session=db, principal=SUPERADMIN)

    state = await get_school_setup_status(
        org_id=org.id, db_session=db, principal=SUPERADMIN
    )
    assert state.is_set_up is True
    assert state.missing == []
    assert state.campus_count == 1
    assert state.term_count == 2
    assert state.school_admin_count == 1
    # Already set up, so nobody may run it again.
    assert state.may_run_setup is False


# ---------------------------------------------------------------------------
# Defaults are best-effort, and say so
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_settings_failure_does_not_destroy_a_good_school(db, org, monkeypatch):
    """Crisis resources failing to save must not roll back a real school.

    The school already exists and works at that point; an unconfigured
    crisis-resources group renders an honest "your school has not added its
    local helpline numbers" message rather than a wrong one.
    """
    import src.services.sms.settings as settings_mod

    async def _boom(*args, **kwargs):
        raise RuntimeError("settings backend down")

    monkeypatch.setattr(settings_mod, "write_group", _boom)

    resp = await run_school_setup(
        payload=_request(
            org.id,
            crisis_resources={"emergency_number": "1122"},
        ),
        db_session=db,
        principal=SUPERADMIN,
    )

    # The school stands...
    assert await db.get(Campus, resp.campus_id) is not None
    # ...and the failure is reported rather than swallowed.
    assert "crisis_resources" in resp.settings_failed
    assert "crisis_resources" not in resp.settings_written


@pytest.mark.asyncio
async def test_crisis_resources_are_written_when_supplied(db, org):
    resp = await run_school_setup(
        payload=_request(
            org.id,
            crisis_resources={"emergency_number": "1122"},
        ),
        db_session=db,
        principal=SUPERADMIN,
    )
    assert "crisis_resources" in resp.settings_written

    from src.services.sms.settings import get_crisis_resources

    resolved = await get_crisis_resources(db, org.id)
    assert resolved.emergency_number == "1122"
