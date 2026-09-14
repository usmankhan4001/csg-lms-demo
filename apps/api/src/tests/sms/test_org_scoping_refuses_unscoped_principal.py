"""A principal with no organisation must be refused, not served school #1.

These four routers resolved their tenant as `principal.org_id or 1`. A caller
whose account carries no organisation was therefore handed whichever school
holds the lowest id -- reading its settings and accreditation evidence, and
writing into them.

`resolve_school_principal` produces exactly that principal in two real cases:

  * an authenticated user holding zero `SMSUserRole` grants. Every `sms_cognia`
    endpoint gates on a bare `get_current_user_principal` with no role
    requirement, so such a user reached all four of its defaulting sites.
  * a SUPER_ADMIN on an instance where `_get_default_org_id` finds no
    organisation at all. `require_roles` short-circuits for a superadmin
    *before* evaluating any role, so the fourteen sites behind it were reachable
    this way even though a roleless user is rejected there.

The handlers are called directly as coroutines, which is why the principal is
passed explicitly -- FastAPI's dependency injection does not run here. See
`_principals.py`.
"""

import pytest
from fastapi import HTTPException, status

from src.routers.sms_cognia import (
    EvidenceItemCreate,
    export_cognia_binder,
    get_cognia_summary,
    list_cognia_evidence,
    log_cognia_evidence,
)
from src.routers.sms_gradebook import generate_official_transcript
from src.routers.sms_revops_config import (
    delete_knowledge_entry,
    get_revops_config,
    list_knowledge_entries,
)
from src.routers.sms_settings import get_school_settings, update_settings_group
from src.schemas.sms_settings import SettingsGroup, SettingsGroupUpdate
from src.security.school_ownership import require_org_id
from src.tests.sms._principals import principal


def unscoped(*roles: str):
    """An authenticated principal attached to no school."""
    return principal(*roles, org_id=None, campus_id=None)


class TestHelper:
    def test_returns_the_org_when_present(self):
        assert require_org_id(principal("SCHOOL_ADMIN", org_id=7)) == 7

    def test_refuses_rather_than_defaulting(self):
        with pytest.raises(HTTPException) as exc:
            require_org_id(unscoped("SCHOOL_ADMIN"))
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    def test_never_returns_organisation_one(self):
        """The specific regression: the old code returned 1 here."""
        with pytest.raises(HTTPException):
            require_org_id(unscoped("SUPER_ADMIN"))

    def test_org_zero_is_not_treated_as_absent(self):
        """`or 1` also swallowed a falsy-but-present 0. Only None is absent."""
        assert require_org_id(principal("SCHOOL_ADMIN", org_id=0)) == 0


class TestCognia:
    """Reachable by any authenticated user -- these four were live."""

    @pytest.mark.asyncio
    async def test_logging_evidence_is_refused(self, db):
        payload = EvidenceItemCreate(
            standard_code="1.1", title="Policy", description="x"
        )
        with pytest.raises(HTTPException) as exc:
            await log_cognia_evidence(
                payload=payload, principal=unscoped("STUDENT"), session=db
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_listing_evidence_is_refused(self):
        with pytest.raises(HTTPException) as exc:
            await list_cognia_evidence(
                standard_code=None,
                academic_year="2025-2026",
                principal=unscoped("STUDENT"),
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_summary_is_refused(self):
        with pytest.raises(HTTPException) as exc:
            await get_cognia_summary(
                academic_year="2025-2026", principal=unscoped("STUDENT")
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_binder_export_is_refused(self):
        """The binder stamped `institution_id: org_1` onto an external export."""
        with pytest.raises(HTTPException) as exc:
            await export_cognia_binder(
                academic_year="2025-2026", principal=unscoped("STUDENT")
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN


class TestSettings:
    @pytest.mark.asyncio
    async def test_reading_settings_is_refused(self, db):
        with pytest.raises(HTTPException) as exc:
            await get_school_settings(
                campus_id=None, session=db, principal=unscoped("SCHOOL_ADMIN")
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_writing_settings_is_refused(self, db):
        """The worst of the eighteen: this wrote another school's fee policy."""
        with pytest.raises(HTTPException) as exc:
            await update_settings_group(
                group=SettingsGroup.FEE_POLICY,
                payload=SettingsGroupUpdate(values={}),
                campus_id=None,
                session=db,
                principal=unscoped("SUPER_ADMIN"),
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN


class TestRevOpsConfig:
    @pytest.mark.asyncio
    async def test_reading_config_is_refused(self, db):
        with pytest.raises(HTTPException) as exc:
            await get_revops_config(
                campus_id=None, session=db, principal=unscoped("SUPER_ADMIN")
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_listing_knowledge_entries_is_refused(self, db):
        with pytest.raises(HTTPException) as exc:
            await list_knowledge_entries(
                session=db, principal=unscoped("SUPER_ADMIN")
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_deleting_a_knowledge_entry_is_refused(self, db):
        """This one deleted another school's records."""
        with pytest.raises(HTTPException) as exc:
            await delete_knowledge_entry(
                entry_id=1, session=db, principal=unscoped("SUPER_ADMIN")
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN


class TestGradebook:
    @pytest.mark.asyncio
    async def test_transcript_export_is_refused(self, db):
        """An "OFFICIAL" transcript must not be stamped with a guessed school."""
        with pytest.raises(HTTPException) as exc:
            await generate_official_transcript(
                student_id=1, session=db, principal=unscoped("SUPER_ADMIN")
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN
