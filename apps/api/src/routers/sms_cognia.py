"""
Cognia Accreditation & Continuous Improvement Evidence Management Router (M16).

Provides standards mapping, evidence artifact logging, performance indicator evaluation,
and accreditation binder compilation for international school accreditation (Cognia / AdvancED).

TWO DEFECTS THIS MODULE USED TO CARRY
-------------------------------------
1. Evidence lived in a module-level Python list, so it died on restart and
   differed per worker (production runs WORKERS=4). It is now a real table --
   see `db/sms_cognia.py` and migration `c4f81a7d2e93`.

2. The readiness summary seeded its own answers. `domain_scores` started at
   {"Leadership Capacity": 3.2, "Learning Capacity": 3.4, "Resource Capacity": 3.1}
   and every standard at `average_score: 3.0`, and those seeds were only
   overwritten where evidence happened to exist. A school that had submitted
   NOTHING was told its compliance score was 3.23 and that it was
   "Accreditation Ready (Effective)".

   That is the same defect class as the gradebook endpoint that reported a 4.0
   GPA and honour roll for a student with zero grades. On an accreditation
   surface it is worse: the figure is about the institution's own compliance,
   and a head teacher could act on it.

   Every figure here is now a `Metric` (schemas/sms_reports.py), which cannot
   hold a value without also holding the sample size it came from, and cannot
   be absent without a stated reason.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SCHOOL_ADMIN,
    STAFF,
    SUPER_ADMIN,
    TEACHER,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_cognia import CogniaEvidenceItem, CogniaEvidenceStatus
from src.schemas.sms_reports import Metric
from src.security.features_utils.dependencies import require_sms_gradebook_feature
from src.security.school_ownership import (
    require_org_id,
    require_user_id,
    resolve_scoped_campus_id,
)

router = APIRouter(dependencies=[Depends(require_sms_gradebook_feature)])

# Who may do what with an institution's accreditation record.
#
# Every endpoint here previously took a bare `get_current_user_principal`, so
# any authenticated account -- a STUDENT, a PARENT -- could file evidence into
# the school's accreditation binder, read the whole binder, and export it. An
# accreditation submission is an institutional compliance record; the people
# who contribute to it are staff.
#
# `/standards` is the exception and stays open to any authenticated user: it
# returns Cognia's published framework, which is reference material, not this
# school's data.
_EVIDENCE_AUTHORS = [SUPER_ADMIN, SCHOOL_ADMIN, STAFF, TEACHER]
_EVIDENCE_READERS = [SUPER_ADMIN, SCHOOL_ADMIN, STAFF, TEACHER]
_SUMMARY_READERS = [SUPER_ADMIN, SCHOOL_ADMIN, STAFF]
_BINDER_EXPORTERS = [SUPER_ADMIN, SCHOOL_ADMIN]

# ---------------------------------------------------------------------------
# Cognia Standards Framework Reference
# ---------------------------------------------------------------------------
COGNIA_STANDARDS = {
    "STD_1": {
        "id": "STD_1",
        "domain": "Leadership Capacity",
        "standards": [
            {"code": "1.1", "name": "Shared Vision & Purpose", "description": "The institution commits to a purpose reflecting high expectations for learning."},
            {"code": "1.2", "name": "Governance & Leadership Autonomy", "description": "The governing authority operates responsibly and autonomously."},
            {"code": "1.3", "name": "Continuous Improvement Process", "description": "The leadership engages stakeholders in continuous improvement."},
        ],
    },
    "STD_2": {
        "id": "STD_2",
        "domain": "Learning Capacity",
        "standards": [
            {"code": "2.1", "name": "Learner Engagement & Equity", "description": "Learners have equitable opportunities to engage in rich learning experiences."},
            {"code": "2.2", "name": "Curriculum Alignment & Rigor", "description": "Curriculum is systematically aligned, rigorous, and personalized."},
            {"code": "2.3", "name": "Assessment & Evidence System", "description": "A comprehensive assessment system monitors learner progress."},
        ],
    },
    "STD_3": {
        "id": "STD_3",
        "domain": "Resource Capacity",
        "standards": [
            {"code": "3.1", "name": "Qualified Staff & PD", "description": "Staff are highly qualified and engage in ongoing professional learning."},
            {"code": "3.2", "name": "Learning Environment & Safety", "description": "The institution provides safe, healthy, and supportive learning environments."},
            {"code": "3.3", "name": "Resource Management & Tech", "description": "Resources, technology, and materials effectively support instructional goals."},
        ],
    },
}

_ALL_DOMAINS = [d["domain"] for d in COGNIA_STANDARDS.values()]


def _domain_for_standard(standard_code: str) -> Optional[str]:
    """The domain a standard code belongs to, or None if the code is unknown.

    Returns None rather than guessing. The previous implementation defaulted to
    "Learning Capacity" for any unrecognised code, so a typo silently filed an
    artifact under the wrong domain and shifted that domain's average.
    """
    for dom in COGNIA_STANDARDS.values():
        if any(std["code"] == standard_code for std in dom["standards"]):
            return dom["domain"]
    return None


def _valid_standard_codes() -> List[str]:
    return [std["code"] for dom in COGNIA_STANDARDS.values() for std in dom["standards"]]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class EvidenceItemCreate(BaseModel):
    standard_code: str = Field(..., description="Cognia standard code e.g. 1.1, 2.2")
    title: str = Field(..., max_length=255)
    description: str
    evidence_type: str = Field(default="policy", description="policy | rubric | student_work | survey | assessment")
    artifact_url: Optional[str] = None
    academic_year: str = Field(default="2025-2026")
    performance_score: float = Field(..., ge=1.0, le=4.0, description="1.0: Ineffective, 2.0: Developing, 3.0: Effective, 4.0: Exemplary")
    tags: List[str] = Field(default_factory=list)


class EvidenceItemResponse(BaseModel):
    id: str
    org_id: int
    campus_id: Optional[int] = None
    standard_code: str
    domain: str
    title: str
    description: str
    evidence_type: str
    artifact_url: Optional[str]
    academic_year: str
    performance_score: float
    status: str
    submitted_by: str
    created_at: str
    verified: bool

    @classmethod
    def from_row(cls, row: CogniaEvidenceItem) -> "EvidenceItemResponse":
        return cls(
            id=f"cog_ev_{row.id}",
            org_id=row.org_id,
            campus_id=row.campus_id,
            standard_code=row.standard_code,
            domain=row.domain,
            title=row.title,
            description=row.description,
            evidence_type=row.evidence_type,
            artifact_url=row.artifact_url,
            academic_year=row.academic_year,
            performance_score=row.performance_score,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            submitted_by=row.submitted_by_sub,
            created_at=row.created_at.isoformat(),
            verified=(row.status == CogniaEvidenceStatus.VERIFIED),
        )


class StandardCoverage(BaseModel):
    """How one Cognia standard is evidenced. `average_score` is absent, not 3.0,
    when nothing has been filed against it."""

    name: str
    domain: str
    evidence_count: int
    average_score: Metric


class CogniaSummaryResponse(BaseModel):
    org_id: int
    academic_year: str
    total_evidence_count: int

    # Per domain. A domain with no evidence carries an absent Metric with a
    # reason, never a seeded number.
    domain_scores: Dict[str, Metric]

    # How much of the framework has been evidenced at all. Makes a score
    # computed from one domain out of three impossible to mistake for a
    # complete picture.
    domains_assessed: int
    domains_total: int

    overall_compliance_score: Metric

    # None until every domain has at least one artifact. A readiness LEVEL is
    # the claim a head teacher acts on; it is not emitted from partial coverage.
    overall_readiness_level: Optional[str] = None
    readiness_no_data_reason: Optional[str] = None

    standards_coverage: Dict[str, StandardCoverage]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _mean_score(scores: List[float]) -> Metric:
    """The mean of the scores given, or an absent Metric when there are none.

    Deliberately a statement-form guard rather than `... if scores else 0.0`.
    An empty collection was never measured, so its mean is not a number -- and
    `src/tests/security/test_no_fabricated_averages.py` exists precisely to
    catch the literal-fallback form.
    """
    if not scores:
        return Metric.absent("No evidence has been submitted against this yet.", unit="score")
    return Metric.of(round(sum(scores) / len(scores), 2), sample_size=len(scores), unit="score")


def _readiness_level(score: float) -> str:
    if score >= 3.5:
        return "Accreditation Ready (Exemplary)"
    if score >= 2.8:
        return "Accreditation Ready (Effective)"
    return "Developing (Action Plan Required)"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "/standards",
    summary="Get Cognia Accreditation Standards Framework",
    response_model=Dict[str, Any],
)
async def get_cognia_standards(
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> Dict[str, Any]:
    """Returns the full Cognia performance standards hierarchy and evaluation rubric.

    Open to any authenticated user: this is Cognia's published framework, not
    the school's own data.
    """
    return {
        "framework": "Cognia Performance Standards 2026",
        "domains": COGNIA_STANDARDS,
        "performance_levels": {
            "4.0": {"level": "Exemplary", "description": "Substantial, sustained evidence of high quality across all indicators"},
            "3.0": {"level": "Effective", "description": "Clear evidence meeting standard expectations with positive impact"},
            "2.0": {"level": "Developing", "description": "Emerging evidence, in-progress implementation"},
            "1.0": {"level": "Ineffective", "description": "Insufficient or missing evidence requiring immediate intervention"},
        },
    }


@router.post(
    "/evidence",
    response_model=EvidenceItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log Cognia Evidence Artifact",
)
async def log_cognia_evidence(
    payload: EvidenceItemCreate,
    principal: KeycloakUserPrincipal = Depends(require_roles(_EVIDENCE_AUTHORS)),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceItemResponse:
    """Submit an evidence artifact linked to a specific Cognia standard indicator."""
    org_id = require_org_id(principal)
    campus_id = resolve_scoped_campus_id(principal, None)

    domain = _domain_for_standard(payload.standard_code)
    if domain is None:
        # Refuse rather than filing it under a guessed domain. A misfiled
        # artifact silently moves that domain's average.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unknown Cognia standard code {payload.standard_code!r}. "
                f"Valid codes: {', '.join(_valid_standard_codes())}."
            ),
        )

    # A school admin filing evidence has it accepted immediately; anyone else
    # files a submission for review. This preserves the workflow that was here
    # before. Worth noting for a later pass: it means an admin's own artifact is
    # self-verified, which an external panel may not regard as review.
    is_verifier = principal.has_role(SUPER_ADMIN) or principal.has_role(SCHOOL_ADMIN)
    user_id = require_user_id(principal)
    now = datetime.now(timezone.utc)

    row = CogniaEvidenceItem(
        org_id=org_id,
        campus_id=campus_id,
        standard_code=payload.standard_code,
        domain=domain,
        title=payload.title,
        description=payload.description,
        evidence_type=payload.evidence_type,
        artifact_url=payload.artifact_url,
        academic_year=payload.academic_year,
        performance_score=payload.performance_score,
        status=CogniaEvidenceStatus.VERIFIED if is_verifier else CogniaEvidenceStatus.SUBMITTED,
        submitted_by_user_id=user_id,
        submitted_by_sub=principal.sub,
        verified_by_user_id=user_id if is_verifier else None,
        verified_at=now if is_verifier else None,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return EvidenceItemResponse.from_row(row)


async def _load_evidence(
    session: AsyncSession,
    org_id: int,
    academic_year: Optional[str],
    standard_code: Optional[str] = None,
) -> List[CogniaEvidenceItem]:
    stmt = select(CogniaEvidenceItem).where(CogniaEvidenceItem.org_id == org_id)
    if academic_year is not None:
        stmt = stmt.where(CogniaEvidenceItem.academic_year == academic_year)
    if standard_code is not None:
        stmt = stmt.where(CogniaEvidenceItem.standard_code == standard_code)
    result = await session.exec(stmt.order_by(CogniaEvidenceItem.id))
    return list(result.all())


@router.get(
    "/evidence",
    response_model=List[EvidenceItemResponse],
    summary="List Cognia Evidence Artifacts",
)
async def list_cognia_evidence(
    standard_code: Optional[str] = Query(None, description="Filter by standard code"),
    academic_year: Optional[str] = Query("2025-2026", description="Filter by academic year"),
    principal: KeycloakUserPrincipal = Depends(require_roles(_EVIDENCE_READERS)),
    session: AsyncSession = Depends(get_db_session),
) -> List[EvidenceItemResponse]:
    """List evidence artifacts for the caller's organisation."""
    org_id = require_org_id(principal)
    rows = await _load_evidence(session, org_id, academic_year, standard_code)
    return [EvidenceItemResponse.from_row(r) for r in rows]


@router.get(
    "/summary",
    response_model=CogniaSummaryResponse,
    summary="Get Cognia Accreditation Readiness Summary",
)
async def get_cognia_summary(
    academic_year: Optional[str] = Query("2025-2026"),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SUMMARY_READERS)),
    session: AsyncSession = Depends(get_db_session),
) -> CogniaSummaryResponse:
    """Domain compliance and accreditation readiness, computed only from evidence.

    A school with no evidence gets absent metrics and no readiness level, not a
    passing score.
    """
    org_id = require_org_id(principal)
    rows = await _load_evidence(session, org_id, academic_year)

    by_domain: Dict[str, List[float]] = {d: [] for d in _ALL_DOMAINS}
    by_standard: Dict[str, List[float]] = {c: [] for c in _valid_standard_codes()}

    for ev in rows:
        if ev.domain in by_domain:
            by_domain[ev.domain].append(ev.performance_score)
        if ev.standard_code in by_standard:
            by_standard[ev.standard_code].append(ev.performance_score)

    domain_scores = {domain: _mean_score(scores) for domain, scores in by_domain.items()}

    standards_coverage: Dict[str, StandardCoverage] = {}
    for dom_val in COGNIA_STANDARDS.values():
        for std in dom_val["standards"]:
            scores = by_standard[std["code"]]
            standards_coverage[std["code"]] = StandardCoverage(
                name=std["name"],
                domain=dom_val["domain"],
                evidence_count=len(scores),
                average_score=_mean_score(scores),
            )

    assessed = [m for m in domain_scores.values() if m.has_data]
    unassessed_names = [d for d, m in domain_scores.items() if not m.has_data]

    if assessed:
        # Mean of the domain means that HAVE data -- domains are weighted
        # equally, matching Cognia's own framing, and an unevidenced domain is
        # excluded rather than counted as anything. sample_size is the number of
        # domains behind the figure, so a score built on one domain is legible
        # as such.
        values = [m.value for m in assessed if m.value is not None]
        overall = Metric.of(
            round(sum(values) / len(values), 2), sample_size=len(values), unit="score"
        )
    else:
        overall = Metric.absent(
            "No evidence has been submitted for this academic year.", unit="score"
        )

    readiness_level: Optional[str] = None
    readiness_reason: Optional[str] = None
    if unassessed_names:
        readiness_reason = (
            "Readiness is not reported until every domain has evidence. "
            f"Still unevidenced: {', '.join(unassessed_names)}."
        )
    elif overall.value is not None:
        readiness_level = _readiness_level(overall.value)

    return CogniaSummaryResponse(
        org_id=org_id,
        academic_year=academic_year or "2025-2026",
        total_evidence_count=len(rows),
        domain_scores=domain_scores,
        domains_assessed=len(assessed),
        domains_total=len(_ALL_DOMAINS),
        overall_compliance_score=overall,
        overall_readiness_level=readiness_level,
        readiness_no_data_reason=readiness_reason,
        standards_coverage=standards_coverage,
    )


@router.get(
    "/binder/export",
    summary="Export Cognia Digital Evidence Binder",
)
async def export_cognia_binder(
    academic_year: Optional[str] = Query("2025-2026"),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BINDER_EXPORTERS)),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Generates an index bundle suitable for Cognia external review panels."""
    summary = await get_cognia_summary(
        academic_year=academic_year, principal=principal, session=session
    )
    evidence = await list_cognia_evidence(
        academic_year=academic_year, principal=principal, session=session
    )

    return {
        "institution_id": f"org_{require_org_id(principal)}",
        "academic_year": academic_year,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": principal.sub,
        "accreditation_body": "Cognia / AdvancED Global",
        "executive_summary": summary.model_dump(),
        "artifacts_catalog": [e.model_dump() for e in evidence],
        # NO verification seal. This previously emitted the hardcoded constant
        # "COGNIA-VERIFIED-CSG-LMS-2026" on every export -- a fixed string that
        # anyone could copy onto any document, asserting that Cognia (a real
        # accreditation body) had endorsed it. It verified nothing while
        # implying verification, which is worse than carrying no seal at all.
        # A genuine seal needs a server-side signature AND a verification
        # endpoint an accreditor can check against; until that exists, this
        # export is what it actually is: an unsigned self-report.
        "attestation": (
            "Self-reported export generated by CSG-LMS. Not independently "
            "verified or endorsed by Cognia / AdvancED Global."
        ),
    }


# ---------------------------------------------------------------------------
# Cognia Evidence Engine & Real-Time AMI (Phase 5)
# ---------------------------------------------------------------------------

@router.post(
    "/harvest/lesson-plan",
    response_model=EvidenceItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Harvest Lesson Plan Evidence with SHA-256 Dual Checksum",
)
async def harvest_lesson_plan_endpoint(
    payload: Dict[str, Any],
    academic_year: str = Query("2025-2026"),
    principal: KeycloakUserPrincipal = Depends(require_roles(_EVIDENCE_AUTHORS)),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceItemResponse:
    from src.services.sms import cognia_engine
    row = await cognia_engine.harvest_lesson_plan(session, principal, payload, academic_year)
    return EvidenceItemResponse.from_row(row)


@router.post(
    "/harvest/rubric",
    response_model=EvidenceItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Harvest Assessment Rubric Evidence with SHA-256 Dual Checksum",
)
async def harvest_rubric_endpoint(
    payload: Dict[str, Any],
    academic_year: str = Query("2025-2026"),
    principal: KeycloakUserPrincipal = Depends(require_roles(_EVIDENCE_AUTHORS)),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceItemResponse:
    from src.services.sms import cognia_engine
    row = await cognia_engine.harvest_rubric(session, principal, payload, academic_year)
    return EvidenceItemResponse.from_row(row)


@router.post(
    "/harvest/psychometrics",
    response_model=EvidenceItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Harvest Exam Psychometrics with SHA-256 Dual Checksum",
)
async def harvest_psychometrics_endpoint(
    payload: Dict[str, Any],
    academic_year: str = Query("2025-2026"),
    principal: KeycloakUserPrincipal = Depends(require_roles(_EVIDENCE_AUTHORS)),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceItemResponse:
    from src.services.sms import cognia_engine
    row = await cognia_engine.harvest_exam_psychometrics(session, principal, payload, academic_year)
    return EvidenceItemResponse.from_row(row)


@router.post(
    "/harvest/attendance",
    response_model=EvidenceItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Harvest Attendance Log Evidence with SHA-256 Dual Checksum",
)
async def harvest_attendance_endpoint(
    payload: Dict[str, Any],
    academic_year: str = Query("2025-2026"),
    principal: KeycloakUserPrincipal = Depends(require_roles(_EVIDENCE_AUTHORS)),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceItemResponse:
    from src.services.sms import cognia_engine
    row = await cognia_engine.harvest_attendance_logs(session, principal, payload, academic_year)
    return EvidenceItemResponse.from_row(row)


@router.post(
    "/harvest/policy",
    response_model=EvidenceItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Harvest Governance Policy Evidence with SHA-256 Dual Checksum",
)
async def harvest_policy_endpoint(
    payload: Dict[str, Any],
    academic_year: str = Query("2025-2026"),
    principal: KeycloakUserPrincipal = Depends(require_roles(_EVIDENCE_AUTHORS)),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceItemResponse:
    from src.services.sms import cognia_engine
    row = await cognia_engine.harvest_governance_policy(session, principal, payload, academic_year)
    return EvidenceItemResponse.from_row(row)


@router.get(
    "/ami",
    summary="Get Real-Time Accreditation Maturity Index (AMI)",
)
async def get_realtime_ami_endpoint(
    academic_year: str = Query("2025-2026"),
    principal: KeycloakUserPrincipal = Depends(require_roles(_SUMMARY_READERS)),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    from src.services.sms import cognia_engine
    org_id = require_org_id(principal)
    return await cognia_engine.calculate_realtime_ami(session, org_id, academic_year)


@router.get(
    "/dossier/export",
    summary="One-Click Export of Cognia Self-Study Dossier",
)
async def export_self_study_dossier_endpoint(
    academic_year: str = Query("2025-2026"),
    principal: KeycloakUserPrincipal = Depends(require_roles(_BINDER_EXPORTERS)),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    from src.services.sms import cognia_engine
    return await cognia_engine.generate_self_study_dossier(session, principal, academic_year)

