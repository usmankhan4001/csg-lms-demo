"""
School Setup Router -- first-run tenant scaffolding.
====================================================

Turns an organisation into a working school: campus, academic year, terms and
the founding administrator, in one transaction. See
`services/sms/school_setup.py` for why the organisation itself is NOT created
here (Learnhouse's own wizard already does that) and why the administrator's
`SMSUserRole` grant is the part that actually matters.

AUTHORISATION -- the bootstrap problem, and how it is bounded
------------------------------------------------------------

`resolve_school_principal()` builds `principal.roles` exclusively from
`SMSUserRole` rows. A person who has just created an organisation through
Learnhouse's wizard therefore holds NO school roles at all, and
`principal.org_id` is `None`. Gating setup on `require_roles([SCHOOL_ADMIN])`
would lock every new school out of its own setup screen forever -- the role
can only be granted by running the setup that the missing role forbids.

So two callers may run setup:

  * a SUPER_ADMIN, for any organisation; or
  * the organisation's own Learnhouse owner (`UserOrganization.role_id == 1`),
    and only while the organisation has no campus yet.

The second is a genuine self-grant of SCHOOL_ADMIN, so its blast radius was
checked rather than assumed:

  * it is bounded to an organisation the caller already owns in Learnhouse's
    own model -- they can already rebrand it, change its settings and delete
    it, so administering it as a school is not a widening of their reach;
  * SCHOOL_ADMIN cannot escape its organisation: `_assert_may_grant` in
    `sms_identity.py` refuses a grant into another org and refuses
    SUPER_ADMIN outright, and `PROVISIONABLE_ROLES` omits SUPER_ADMIN for
    everyone;
  * it is one-shot. Setup refuses once the organisation has a campus, so it
    cannot be re-run later to mint further administrators.

**`principal.org_id` is deliberately not consulted to decide WHICH org is set
up.** For the bootstrap caller it is `None`, and the codebase's existing
`principal.org_id or 1` fallback (18 occurrences, being removed by another
lane) would have silently pointed setup at organisation 1 -- configuring
somebody else's school. The organisation is named explicitly in the request
and the caller's membership of it is verified below.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
)
from src.db.user_organizations import UserOrganization
from src.services.sms.school_setup import (
    SchoolSetupSpec,
    TermSpec,
    apply_setup_defaults,
    describe_setup_state,
    setup_school,
)

router = APIRouter()


# Learnhouse's own owner role id, as written by `services/orgs/orgs.create_org`
# when somebody creates an organisation. Named rather than inlined so the
# bootstrap rule below reads as a rule instead of a magic number.
LEARNHOUSE_ORG_OWNER_ROLE_ID = 1


class TermPayload(SQLModel):
    name: str
    term_code: Optional[str] = None
    weight_percentage: float = 100.0
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class SchoolSetupRequest(SQLModel):
    org_id: int

    campus_name: str
    campus_code: str
    campus_timezone: str = "UTC"
    campus_address: Optional[str] = None

    academic_year_name: str
    academic_year_start: Optional[str] = None
    academic_year_end: Optional[str] = None
    terms: List[TermPayload] = []

    admin_email: Optional[str] = None
    admin_first_name: Optional[str] = None
    admin_last_name: str = ""

    crisis_resources: Optional[Dict[str, Any]] = None
    school_profile: Optional[Dict[str, Any]] = None


class SchoolSetupResponse(SQLModel):
    org_id: int
    campus_id: int
    academic_year_id: int
    term_ids: List[int]
    admin_user_id: Optional[int]
    # "We created this account" and "this person already existed and is now an
    # administrator" are different facts and the screen says which.
    admin_created: bool
    settings_written: List[str]
    settings_failed: List[str]


class SchoolSetupStatusResponse(SQLModel):
    org_id: int
    is_set_up: bool
    missing: List[str]
    campus_count: int
    academic_year_count: int
    term_count: int
    school_admin_count: int
    may_run_setup: bool


async def _is_org_owner(
    db_session: AsyncSession, *, user_id: Optional[int], org_id: int
) -> bool:
    """Does this user own this organisation in Learnhouse's own model?"""
    if user_id is None:
        return False
    row = (
        await db_session.execute(
            select(UserOrganization).where(
                UserOrganization.user_id == user_id,
                UserOrganization.org_id == org_id,
                UserOrganization.role_id == LEARNHOUSE_ORG_OWNER_ROLE_ID,
            )
        )
    ).scalars().first()
    return row is not None


def _actor_user_id(principal: KeycloakUserPrincipal) -> Optional[int]:
    """The real integer user id, which lives in `raw_claims`.

    `principal.sub` is a UUID string and cannot be used where an integer user
    id is required -- the two identifier systems in this codebase are not
    interchangeable.
    """
    raw = getattr(principal, "raw_claims", None) or {}
    value = raw.get("lh_user_id")
    return int(value) if isinstance(value, int) else None


async def _assert_may_set_up(
    db_session: AsyncSession,
    principal: KeycloakUserPrincipal,
    org_id: int,
    *,
    already_set_up: bool,
) -> None:
    """Who may scaffold this school. See the module docstring for the reasoning."""
    if already_set_up:
        # Refused for everyone, superadmin included. Setup is first-run only;
        # adding a second campus or a further administrator is what the campus
        # and people screens are for, and keeping this one-shot removes it as
        # a route to minting administrators later.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This school has already been set up. Add further campuses, "
                "years and staff from the school settings screens."
            ),
        )

    if principal.is_superadmin:
        return

    if await _is_org_owner(
        db_session, user_id=_actor_user_id(principal), org_id=org_id
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Only a super admin, or the owner of this organisation, can set up "
            "a school here."
        ),
    )


@router.get(
    "/school-setup/status",
    response_model=SchoolSetupStatusResponse,
    summary="What this organisation still needs to work as a school",
)
async def get_school_setup_status(
    org_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> SchoolSetupStatusResponse:
    """Read-only, and readable by anyone who belongs to the organisation.

    A member who cannot run setup still benefits from being told the school is
    unconfigured -- otherwise every module simply looks broken to them.
    """
    is_owner = await _is_org_owner(
        db_session, user_id=_actor_user_id(principal), org_id=org_id
    )
    if not principal.is_superadmin and not is_owner and principal.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this organisation.",
        )

    state = await describe_setup_state(db_session, org_id=org_id)
    may_run = (not state["is_set_up"]) and (principal.is_superadmin or is_owner)
    return SchoolSetupStatusResponse(**state, may_run_setup=may_run)


@router.post(
    "/school-setup",
    response_model=SchoolSetupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set up a school: campus, academic year, terms and founding admin",
)
async def run_school_setup(
    payload: SchoolSetupRequest,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> SchoolSetupResponse:
    org_id = payload.org_id

    state = await describe_setup_state(db_session, org_id=org_id)
    await _assert_may_set_up(
        db_session, principal, org_id, already_set_up=bool(state["is_set_up"])
    )

    spec = SchoolSetupSpec(
        campus_name=payload.campus_name,
        campus_code=payload.campus_code,
        campus_timezone=payload.campus_timezone,
        campus_address=payload.campus_address,
        academic_year_name=payload.academic_year_name,
        academic_year_start=payload.academic_year_start,
        academic_year_end=payload.academic_year_end,
        terms=[
            TermSpec(
                name=t.name,
                term_code=t.term_code,
                weight_percentage=t.weight_percentage,
                start_date=t.start_date,
                end_date=t.end_date,
            )
            for t in payload.terms
        ],
        admin_email=payload.admin_email,
        admin_first_name=payload.admin_first_name,
        admin_last_name=payload.admin_last_name,
        crisis_resources=payload.crisis_resources,
        school_profile=payload.school_profile,
    )

    actor = _actor_user_id(principal)

    try:
        result = await setup_school(
            db_session, spec, org_id=org_id, actor_user_id=actor
        )
        await db_session.commit()
    except Exception:
        # Explicit rather than implied. Setup stages a campus, a year, several
        # terms and an account on one session; without this rollback a later
        # failure could leave earlier rows pending on a session that something
        # else commits, which is exactly the half-built tenant this endpoint
        # exists to prevent.
        await db_session.rollback()
        raise

    # Outside the transaction by design -- see the service module docstring.
    # A settings failure is reported, never fatal.
    await apply_setup_defaults(
        db_session, spec, result, org_id=org_id, actor_user_id=actor
    )

    return SchoolSetupResponse(
        org_id=result.org_id,
        campus_id=result.campus_id,
        academic_year_id=result.academic_year_id,
        term_ids=result.term_ids,
        admin_user_id=result.admin_user_id,
        admin_created=result.admin_created,
        settings_written=result.settings_written,
        settings_failed=result.settings_failed,
    )
