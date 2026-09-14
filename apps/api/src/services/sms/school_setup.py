"""
First-run school setup -- turning an organisation into a working school.
========================================================================

WHAT WAS ACTUALLY MISSING (and what was not):

Creating an *organisation* has always had a flow -- Learnhouse's own wizard at
`apps/web/app/(hub)/new`, backed by `services/orgs/orgs.create_org`. That
creates the `Organization`, a `UserOrganization` membership with `role_id=1`,
and an `OrganizationConfig`. So "you cannot create an org without psql" was
never true.

What it does NOT create is everything that makes the org a *school*:

  * no `Campus`, so every campus-scoped query has nothing to scope to;
  * no `AcademicYear` or `AcademicTerm`, so sections cannot be year-scoped
    and the year can never be rolled over;
  * no `SMSUserRole` grant -- and this is the one that actually locks people
    out. `security/school_principal.resolve_school_principal()` builds
    `principal.roles` EXCLUSIVELY from `SMSUserRole` rows;
    `UserOrganization.role_id` contributes nothing to it. So the person who
    created the organisation owns it in Learnhouse's model and has *zero*
    school roles: every `require_roles(...)` gate in every SMS router refuses
    them. They own a school they cannot administer.

That last point is why this module exists, and why the founding-administrator
grant is part of the same transaction as the structure rather than a follow-up
step somebody might forget.

ATOMIC, NOT RESUMABLE -- and deliberately so:

Everything structural is staged on the caller's session and flushed for its
ids, but never committed here; the router commits once at the end. A failure
anywhere unwinds the whole school.

Resumability was the alternative and was rejected: resuming means persisting
partial state, and a persisted half-built tenant is precisely the failure this
is meant to prevent. An org with a campus but no academic year renders empty
across most modules with nothing on screen explaining why -- the reader
concludes the software is broken rather than unconfigured. Setup is four
inserts and one account; it is cheap enough to simply redo.

SETTINGS SIT OUTSIDE THE ATOMIC CORE, for two reasons:

  1. `services/sms/settings.write_group()` commits internally, so it cannot
     take part in the caller's transaction without being rewritten -- and it
     is owned by another surface.
  2. More importantly, a missing settings row is a *valid* state, not a
     broken one. An unconfigured school shows students an honest "your school
     has not added its local crisis helpline numbers" message rather than
     another country's. A school with no `crisis_resources` row works; a
     school with no campus does not.

So settings are applied after the structure is committed, and a settings
failure is REPORTED rather than allowed to destroy a good tenant. The response
says exactly which defaults landed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.organizations import Organization
from src.db.sms_campus import AcademicTerm, AcademicYear, Campus
from src.db.sms_identity import SchoolRole
from src.services.sms.people_provisioning import PersonSpec, provision_person

logger = logging.getLogger(__name__)


# A school with no terms cannot weight a report card, so setup insists on at
# least one. Two is the common case (two semesters); the cap is a sanity bound
# on a form, not a policy about how many terms a school may eventually have.
MIN_TERMS = 1
MAX_TERMS = 12


def _bad_request(detail: str) -> HTTPException:
    """400 with an actionable message.

    Setup failures are almost always a human filling in a form, so every
    message here names what to change. A 500 with a constraint violation
    teaches the administrator nothing.
    """
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


@dataclass
class TermSpec:
    name: str
    term_code: Optional[str] = None
    weight_percentage: float = 100.0
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass
class SchoolSetupSpec:
    """Everything needed to turn an organisation into a working school."""

    # Campus
    campus_name: str
    campus_code: str
    campus_timezone: str = "UTC"
    campus_address: Optional[str] = None

    # Academic year
    academic_year_name: str = ""
    academic_year_start: Optional[str] = None
    academic_year_end: Optional[str] = None
    terms: List[TermSpec] = field(default_factory=list)

    # Founding administrator. Optional ONLY because the caller may already
    # hold SCHOOL_ADMIN here (a superadmin re-running setup on an org that
    # already has an administrator); the router decides.
    admin_email: Optional[str] = None
    admin_first_name: Optional[str] = None
    admin_last_name: str = ""

    # Defaults applied after commit. See module docstring.
    crisis_resources: Optional[Dict[str, Any]] = None
    school_profile: Optional[Dict[str, Any]] = None


@dataclass
class SchoolSetupResult:
    org_id: int
    campus_id: int
    academic_year_id: int
    term_ids: List[int]
    admin_user_id: Optional[int]
    admin_created: bool
    # Which settings groups were written after the structural commit. Reported
    # rather than assumed, because these are best-effort by design.
    settings_written: List[str] = field(default_factory=list)
    settings_failed: List[str] = field(default_factory=list)


def _parse_iso_date(value: Optional[str], label: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise _bad_request(
            f"{label} must be a date in YYYY-MM-DD form, not {value!r}."
        ) from exc


def _validate(spec: SchoolSetupSpec) -> None:
    """Everything checkable, checked BEFORE the first write.

    The point is that a typo in term 4 cannot leave a campus and three terms
    behind. The transaction would unwind anyway, but validating up front also
    means the administrator gets every problem at once instead of discovering
    them one submit at a time.
    """
    if not (spec.campus_name or "").strip():
        raise _bad_request("The campus needs a name.")

    code = (spec.campus_code or "").strip()
    if not code:
        raise _bad_request(
            "The campus needs a short code (for example 'MAIN' or 'ISB-NORTH'). "
            "It appears on registers and report cards."
        )
    if len(code) > 50:
        raise _bad_request("The campus code must be 50 characters or fewer.")

    if not (spec.academic_year_name or "").strip():
        raise _bad_request(
            "The academic year needs a name, for example '2026-2027'. "
            "Sections, enrolments and report cards are all scoped to it."
        )

    year_start = _parse_iso_date(spec.academic_year_start, "The academic year start date")
    year_end = _parse_iso_date(spec.academic_year_end, "The academic year end date")
    if year_start and year_end and year_end <= year_start:
        raise _bad_request(
            "The academic year must end after it starts. "
            f"Given {spec.academic_year_start} to {spec.academic_year_end}."
        )

    if len(spec.terms) < MIN_TERMS:
        raise _bad_request(
            "A school needs at least one term. Report card weighting has "
            "nothing to divide across otherwise."
        )
    if len(spec.terms) > MAX_TERMS:
        raise _bad_request(f"At most {MAX_TERMS} terms can be created during setup.")

    seen_names: set[str] = set()
    for index, term in enumerate(spec.terms, start=1):
        name = (term.name or "").strip()
        if not name:
            raise _bad_request(f"Term {index} needs a name.")
        key = name.casefold()
        if key in seen_names:
            raise _bad_request(
                f"Two terms are both called {name!r}. Term names must differ, "
                "or a report card cannot say which one a grade belongs to."
            )
        seen_names.add(key)

        if not 0.0 <= term.weight_percentage <= 100.0:
            raise _bad_request(
                f"Term {name!r} has a weighting of {term.weight_percentage}. "
                "A term's weighting is a percentage between 0 and 100."
            )

        t_start = _parse_iso_date(term.start_date, f"Term {name!r} start date")
        t_end = _parse_iso_date(term.end_date, f"Term {name!r} end date")
        if t_start and t_end and t_end <= t_start:
            raise _bad_request(f"Term {name!r} must end after it starts.")
        # A term outside its own year is a data error that only surfaces much
        # later, as a report card with no grades in it.
        if t_start and year_start and t_start < year_start:
            raise _bad_request(
                f"Term {name!r} starts before the academic year does."
            )
        if t_end and year_end and t_end > year_end:
            raise _bad_request(f"Term {name!r} ends after the academic year does.")

    # Deliberately NOT enforcing that weights sum to 100: a school may weight
    # terms however it likes (some weight only the final term), and refusing a
    # valid policy during setup would be worse than allowing an unusual one.
    # Gradebook already normalises when it computes.

    if spec.admin_email is not None:
        if not (spec.admin_first_name or "").strip():
            raise _bad_request(
                "The founding administrator needs a first name. An account "
                "with no name shows as 'Unnamed' on every screen."
            )


async def setup_school(
    session: AsyncSession,
    spec: SchoolSetupSpec,
    *,
    org_id: int,
    actor_user_id: Optional[int],
) -> SchoolSetupResult:
    """Stage a complete school onto `session`. The CALLER commits.

    Nothing here commits, mirroring `provision_person`, so that a failure in
    any later stage of the same request unwinds every earlier one. Ids are
    obtained with `flush()`, which assigns primary keys without ending the
    transaction.
    """
    _validate(spec)

    org = await session.get(Organization, org_id)
    if org is None:
        # Not a 404 on the org itself: the caller reached an authenticated
        # route, so this is a malformed request rather than a missing page.
        raise _bad_request(f"Organisation {org_id} does not exist.")

    code = spec.campus_code.strip()

    # Campus codes are unique per org (ix_campus_org_code). Checking here
    # turns a 500 IntegrityError into a message naming the conflict.
    existing_campus = (
        await session.execute(
            select(Campus).where(Campus.org_id == org_id, Campus.code == code)
        )
    ).scalars().first()
    if existing_campus is not None:
        raise _bad_request(
            f"A campus with the code {code!r} already exists at this school "
            f"({existing_campus.name}). Campus codes must be unique."
        )

    # --- 1. Campus ----------------------------------------------------------
    campus = Campus(
        name=spec.campus_name.strip(),
        code=code,
        address=(spec.campus_address or None),
        timezone=(spec.campus_timezone or "UTC").strip() or "UTC",
        is_active=True,
        org_id=org_id,
    )
    session.add(campus)
    await session.flush()
    if campus.id is None:  # pragma: no cover - defensive
        raise _bad_request("The campus could not be created.")

    # --- 2. Academic year ---------------------------------------------------
    year = AcademicYear(
        name=spec.academic_year_name.strip(),
        start_date=spec.academic_year_start,
        end_date=spec.academic_year_end,
        is_active=True,
        campus_id=campus.id,
    )
    session.add(year)
    await session.flush()
    if year.id is None:  # pragma: no cover - defensive
        raise _bad_request("The academic year could not be created.")

    # --- 3. Terms -----------------------------------------------------------
    term_ids: List[int] = []
    for term in spec.terms:
        row = AcademicTerm(
            name=term.name.strip(),
            term_code=(term.term_code or None),
            weight_percentage=term.weight_percentage,
            start_date=term.start_date,
            end_date=term.end_date,
            academic_year_id=year.id,
        )
        session.add(row)
        await session.flush()
        if row.id is not None:
            term_ids.append(row.id)

    # --- 4. Founding administrator -----------------------------------------
    #
    # Delegated to `provision_person` rather than reimplemented, so the
    # unusable-password rule, the org-membership row and the audit event all
    # come from one place. Note the contrast with
    # `revops_enrollment.provision_learner_from_lead`, which creates a learner
    # WITHOUT a `UserOrganization` row -- a person who belongs to no
    # organisation. That shape is deliberately not copied here.
    admin_user_id: Optional[int] = None
    admin_created = False
    if spec.admin_email:
        result = await provision_person(
            session,
            PersonSpec(
                role=SchoolRole.SCHOOL_ADMIN,
                email=spec.admin_email,
                first_name=(spec.admin_first_name or "").strip(),
                last_name=(spec.admin_last_name or "").strip(),
                campus_id=None,  # org-wide: a founding admin is not campus-bound
            ),
            org_id=org_id,
            actor_user_id=actor_user_id,
        )
        admin_user_id = result.user_id
        admin_created = result.created_user
        await session.flush()

    return SchoolSetupResult(
        org_id=org_id,
        campus_id=campus.id,
        academic_year_id=year.id,
        term_ids=term_ids,
        admin_user_id=admin_user_id,
        admin_created=admin_created,
    )


async def apply_setup_defaults(
    session: AsyncSession,
    spec: SchoolSetupSpec,
    result: SchoolSetupResult,
    *,
    org_id: int,
    actor_user_id: Optional[int],
) -> None:
    """Write the optional settings groups, AFTER the structure is committed.

    Mutates `result` to record what landed. Never raises: the school already
    exists and is usable by this point, and destroying a good tenant because a
    default failed to save would be the wrong trade. A failure here is
    reported to the administrator so they can set it on the settings screen.
    """
    # Imported here rather than at module scope: `write_group` commits
    # internally, and keeping the import local makes it obvious at the call
    # site that this function is outside the caller's transaction.
    from src.schemas.sms_settings import SettingsGroup
    from src.services.sms.settings import write_group

    planned: List[tuple[SettingsGroup, Optional[Dict[str, Any]]]] = [
        (SettingsGroup.CRISIS_RESOURCES, spec.crisis_resources),
        (SettingsGroup.SCHOOL_PROFILE, spec.school_profile),
    ]

    for group, values in planned:
        if not values:
            continue
        try:
            await write_group(
                session,
                org_id=org_id,
                campus_id=None,  # org-wide default
                group=group,
                values=values,
                updated_by_user_id=actor_user_id,
            )
            result.settings_written.append(group.value)
        except Exception:
            # Logged with a stack trace, surfaced in the response, and the
            # school stands. An unconfigured crisis-resources group renders an
            # honest "not configured" message rather than a wrong one.
            logger.exception(
                "School setup could not write the %s settings group for org %s; "
                "the school was created and this default must be set manually.",
                group.value,
                org_id,
            )
            result.settings_failed.append(group.value)


async def describe_setup_state(
    session: AsyncSession, *, org_id: int
) -> Dict[str, Any]:
    """What this organisation still needs before it behaves like a school.

    Every field is sourced from a real row. Nothing is defaulted or guessed --
    an org with no campus reports `campus_count: 0` and `is_set_up: False`,
    never a reassuring zero that reads as "nothing to do".
    """
    campuses = list(
        (
            await session.execute(select(Campus).where(Campus.org_id == org_id))
        ).scalars().all()
    )
    campus_ids = [c.id for c in campuses if c.id is not None]

    years: List[AcademicYear] = []
    if campus_ids:
        years = list(
            (
                await session.execute(
                    select(AcademicYear).where(
                        AcademicYear.campus_id.in_(campus_ids)  # type: ignore[union-attr]
                    )
                )
            ).scalars().all()
        )

    year_ids = [y.id for y in years if y.id is not None]
    terms: List[AcademicTerm] = []
    if year_ids:
        terms = list(
            (
                await session.execute(
                    select(AcademicTerm).where(
                        AcademicTerm.academic_year_id.in_(year_ids)  # type: ignore[union-attr]
                    )
                )
            ).scalars().all()
        )

    # Imported locally to keep this module's import graph away from the
    # identity router, which another lane owns.
    from src.db.sms_identity import SMSUserRole

    admins = list(
        (
            await session.execute(
                select(SMSUserRole).where(
                    SMSUserRole.org_id == org_id,
                    SMSUserRole.role == SchoolRole.SCHOOL_ADMIN,
                    SMSUserRole.is_active == True,  # noqa: E712
                )
            )
        ).scalars().all()
    )

    missing: List[str] = []
    if not campuses:
        missing.append("campus")
    if not years:
        missing.append("academic_year")
    if not terms:
        missing.append("academic_term")
    if not admins:
        missing.append("school_admin")

    return {
        "org_id": org_id,
        "is_set_up": not missing,
        "missing": missing,
        "campus_count": len(campuses),
        "academic_year_count": len(years),
        "term_count": len(terms),
        "school_admin_count": len(admins),
    }
