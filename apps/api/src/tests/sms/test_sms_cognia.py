"""Accreditation readiness must be earned, not seeded.

`sms_cognia.py` previously started every summary from
{"Leadership Capacity": 3.2, "Learning Capacity": 3.4, "Resource Capacity": 3.1}
with each standard at 3.0, and only overwrote those seeds where evidence
happened to exist. A school that had submitted NOTHING was told its compliance
score was 3.23 and that it was "Accreditation Ready (Effective)".

It also kept the evidence in a module-level Python list, so it died on restart
and differed across the four production workers.

These tests pin both: evidence is durable and org-scoped, and no figure is
reported that no artifact supports.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_cognia import CogniaEvidenceItem, CogniaEvidenceStatus
from src.routers.sms_cognia import (
    EvidenceItemCreate,
    get_cognia_summary,
    list_cognia_evidence,
    log_cognia_evidence,
)
from src.tests.sms._principals import principal

ADMIN = principal("SCHOOL_ADMIN", user_id=7, org_id=1)
TEACH = principal("TEACHER", user_id=8, org_id=1)
OTHER_SCHOOL = principal("SCHOOL_ADMIN", user_id=9, org_id=2)


def _evidence(standard_code: str, score: float, title: str = "Artifact") -> EvidenceItemCreate:
    return EvidenceItemCreate(
        standard_code=standard_code,
        title=title,
        description="Evidence description",
        evidence_type="policy",
        academic_year="2025-2026",
        performance_score=score,
    )


class TestASchoolWithNoEvidence:
    """The defect that made this module dangerous."""

    @pytest.mark.asyncio
    async def test_no_evidence_yields_no_readiness_level(self, db: AsyncSession):
        summary = await get_cognia_summary(
            academic_year="2025-2026", principal=ADMIN, session=db
        )

        assert summary.total_evidence_count == 0
        # The claim a head teacher would act on is simply not made.
        assert summary.overall_readiness_level is None
        assert summary.readiness_no_data_reason is not None

    @pytest.mark.asyncio
    async def test_no_evidence_yields_no_compliance_score(self, db: AsyncSession):
        summary = await get_cognia_summary(
            academic_year="2025-2026", principal=ADMIN, session=db
        )

        assert summary.overall_compliance_score.has_data is False
        assert summary.overall_compliance_score.value is None
        assert summary.overall_compliance_score.no_data_reason
        # Specifically NOT the old seeded answer.
        assert summary.overall_compliance_score.value != pytest.approx(3.23, abs=0.05)

    @pytest.mark.asyncio
    async def test_every_domain_is_absent_not_seeded(self, db: AsyncSession):
        summary = await get_cognia_summary(
            academic_year="2025-2026", principal=ADMIN, session=db
        )

        assert summary.domains_assessed == 0
        assert summary.domains_total == 3
        for domain, metric in summary.domain_scores.items():
            assert metric.has_data is False, f"{domain} reported a score with no evidence"
            assert metric.value is None, f"{domain} was seeded with {metric.value}"

    @pytest.mark.asyncio
    async def test_every_standard_is_absent_not_three_point_zero(self, db: AsyncSession):
        summary = await get_cognia_summary(
            academic_year="2025-2026", principal=ADMIN, session=db
        )

        assert len(summary.standards_coverage) == 9
        for code, cov in summary.standards_coverage.items():
            assert cov.evidence_count == 0
            assert cov.average_score.has_data is False, f"{code} claimed a score"
            assert cov.average_score.value is None, f"{code} was seeded with {cov.average_score.value}"


class TestEvidenceIsDurableAndScoped:
    @pytest.mark.asyncio
    async def test_submitted_evidence_is_readable_back(self, db: AsyncSession):
        created = await log_cognia_evidence(
            payload=_evidence("1.1", 4.0, title="Vision statement"), principal=ADMIN, session=db
        )
        assert created.domain == "Leadership Capacity"

        listed = await list_cognia_evidence(
            standard_code=None, academic_year="2025-2026", principal=ADMIN, session=db
        )
        assert [e.title for e in listed] == ["Vision statement"]

    @pytest.mark.asyncio
    async def test_it_is_a_table_not_a_module_global(self, db: AsyncSession):
        """Read through the ORM, not the router, so this fails if storage ever
        moves back into process memory."""
        await log_cognia_evidence(
            payload=_evidence("2.1", 3.0), principal=ADMIN, session=db
        )
        row = (await db.exec(select(CogniaEvidenceItem))).first()
        assert row is not None
        assert row.org_id == 1
        assert row.submitted_by_user_id == 7

    @pytest.mark.asyncio
    async def test_another_school_sees_none_of_it(self, db: AsyncSession):
        await log_cognia_evidence(
            payload=_evidence("1.1", 4.0, title="Ours"), principal=ADMIN, session=db
        )

        theirs = await list_cognia_evidence(
            standard_code=None, academic_year="2025-2026", principal=OTHER_SCHOOL, session=db
        )
        assert theirs == []

        summary = await get_cognia_summary(
            academic_year="2025-2026", principal=OTHER_SCHOOL, session=db
        )
        assert summary.total_evidence_count == 0
        assert summary.overall_readiness_level is None

    @pytest.mark.asyncio
    async def test_a_teachers_submission_is_not_self_verified(self, db: AsyncSession):
        created = await log_cognia_evidence(
            payload=_evidence("3.1", 3.0), principal=TEACH, session=db
        )
        assert created.verified is False
        assert created.status == CogniaEvidenceStatus.SUBMITTED.value


class TestScoringUsesOnlyRealEvidence:
    @pytest.mark.asyncio
    async def test_a_domain_scores_only_from_its_own_evidence(self, db: AsyncSession):
        await log_cognia_evidence(payload=_evidence("1.1", 4.0), principal=ADMIN, session=db)
        await log_cognia_evidence(payload=_evidence("1.2", 2.0), principal=ADMIN, session=db)

        summary = await get_cognia_summary(
            academic_year="2025-2026", principal=ADMIN, session=db
        )

        leadership = summary.domain_scores["Leadership Capacity"]
        assert leadership.value == pytest.approx(3.0)
        assert leadership.sample_size == 2

        # The two untouched domains must remain absent, not inherit the mean.
        assert summary.domain_scores["Learning Capacity"].has_data is False
        assert summary.domain_scores["Resource Capacity"].has_data is False
        assert summary.domains_assessed == 1

    @pytest.mark.asyncio
    async def test_readiness_is_withheld_until_every_domain_has_evidence(self, db: AsyncSession):
        await log_cognia_evidence(payload=_evidence("1.1", 4.0), principal=ADMIN, session=db)
        await log_cognia_evidence(payload=_evidence("2.1", 4.0), principal=ADMIN, session=db)

        summary = await get_cognia_summary(
            academic_year="2025-2026", principal=ADMIN, session=db
        )
        # Two strong domains would have scored "Exemplary" on the old code.
        assert summary.overall_readiness_level is None
        assert "Resource Capacity" in (summary.readiness_no_data_reason or "")

    @pytest.mark.asyncio
    async def test_readiness_is_reported_once_all_domains_are_evidenced(self, db: AsyncSession):
        for code in ("1.1", "2.1", "3.1"):
            await log_cognia_evidence(payload=_evidence(code, 4.0), principal=ADMIN, session=db)

        summary = await get_cognia_summary(
            academic_year="2025-2026", principal=ADMIN, session=db
        )
        assert summary.domains_assessed == 3
        assert summary.overall_compliance_score.value == pytest.approx(4.0)
        assert summary.overall_readiness_level == "Accreditation Ready (Exemplary)"
        assert summary.readiness_no_data_reason is None

    @pytest.mark.asyncio
    async def test_weak_evidence_is_reported_as_weak(self, db: AsyncSession):
        for code in ("1.1", "2.1", "3.1"):
            await log_cognia_evidence(payload=_evidence(code, 1.0), principal=ADMIN, session=db)

        summary = await get_cognia_summary(
            academic_year="2025-2026", principal=ADMIN, session=db
        )
        assert summary.overall_readiness_level == "Developing (Action Plan Required)"


class TestWhoMayTouchTheAccreditationRecord:
    """Every endpoint here previously took a bare `get_current_user_principal`,
    so any authenticated account could file evidence into the school's
    accreditation binder, read it, and export it.

    These exercise the real `require_roles` dependency rather than the handler,
    because calling a handler directly bypasses FastAPI's dependency injection
    entirely -- which is exactly how a gate can look attached and do nothing.
    """

    @pytest.mark.asyncio
    async def test_a_student_cannot_file_evidence(self):
        from src.routers.sms_cognia import _EVIDENCE_AUTHORS
        from src.core.keycloak_auth import require_roles

        gate = require_roles(_EVIDENCE_AUTHORS)
        with pytest.raises(HTTPException) as exc:
            await gate(principal=principal("STUDENT", user_id=40, org_id=1))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_a_parent_cannot_export_the_binder(self):
        from src.routers.sms_cognia import _BINDER_EXPORTERS
        from src.core.keycloak_auth import require_roles

        gate = require_roles(_BINDER_EXPORTERS)
        with pytest.raises(HTTPException) as exc:
            await gate(principal=principal("PARENT", user_id=41, org_id=1))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_a_teacher_may_file_but_not_export(self):
        from src.routers.sms_cognia import _BINDER_EXPORTERS, _EVIDENCE_AUTHORS
        from src.core.keycloak_auth import require_roles

        teacher = principal("TEACHER", user_id=42, org_id=1)
        assert await require_roles(_EVIDENCE_AUTHORS)(principal=teacher) is teacher

        with pytest.raises(HTTPException):
            await require_roles(_BINDER_EXPORTERS)(principal=teacher)


class TestUnknownStandardCodes:
    @pytest.mark.asyncio
    async def test_an_unknown_code_is_refused_not_guessed(self, db: AsyncSession):
        """The old code defaulted any unrecognised code to "Learning Capacity",
        so a typo silently moved that domain's average."""
        with pytest.raises(HTTPException) as exc:
            await log_cognia_evidence(
                payload=_evidence("9.9", 4.0), principal=ADMIN, session=db
            )
        assert exc.value.status_code == 422

        summary = await get_cognia_summary(
            academic_year="2025-2026", principal=ADMIN, session=db
        )
        assert summary.domain_scores["Learning Capacity"].has_data is False
