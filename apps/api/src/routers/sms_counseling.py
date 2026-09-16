"""
CSG-LMS Counseling / Wellbeing / Career Guidance router (Phase 4, Part B).

Mount pattern matches the other SMS routers exactly (see
src/routers/sms_attendance.py): router-level
`dependencies=[Depends(require_tutor_counseling_feature)]` plus a per-handler
`Depends(get_current_user_principal)`. Mounted in src/router.py WITHOUT any
router-mount-level Learnhouse-native auth dependency, to avoid reintroducing
the double-auth-gate bug fixed for the other 8 SMS routers (see
src/tests/routers/test_sms_router_mount_auth.py).

CONFIDENTIALITY (DESIGN-SYSTEM.md §4/§10 — mandatory): every activity-log and
session endpoint below returns an EMPTY result (200 empty list, or 404) to an
unauthorized caller — NEVER a 403. A 403 would itself confirm to a
TEACHER/SCHOOL_ADMIN that a counseling record exists for this student. This
rule is scoped to THIS module only (see src/services/sms/counseling.py
module docstring for the full rationale and the explicit contrast with
src/services/users/usergroups.py:301-304, which is left untouched).

Career guidance (§3) is NOT a confidential clinical record and uses ordinary
403s for role checks, like the rest of the app.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    PSYCHOLOGIST,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    TEACHER,
    get_current_user_principal,
)
from src.db.sms_gradebook import TermReportCard
from src.schemas.sms_counseling import (
    ActivityLogCreate,
    ActivityLogRead,
    CareerGuidanceGenerateRequest,
    CareerGuidancePlanRead,
    ClinicalCaseNoteCreate,
    ClinicalCaseNoteRead,
    CounselingSessionCreate,
    CounselingSessionRead,
    CounselingSessionUpdate,
    CrisisTriageItemCreate,
    CrisisTriageItemRead,
    CrisisTriageUpdate,
    DiagnosticAssessmentCreate,
    EncryptedEnvelope,
    ParentVisibleSessionSummary,
    PastoralEscalationCreate,
    PastoralEscalationRead,
)
from src.security.ems_rbac import require_permission
from src.security.features_utils.dependencies import require_tutor_counseling_feature
from src.services.ai.llm import AINotConfiguredError
from src.services.sms import clinical_desk as clinical_desk_service
from src.services.sms import counseling as counseling_service

router = APIRouter(dependencies=[Depends(require_tutor_counseling_feature)])

# Staff roles permitted to generate a (non-confidential) career guidance plan.
CAREER_GUIDANCE_STAFF_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, PSYCHOLOGIST]

# --- Dynamic RBAC (src/security/ems_rbac.py) -------------------------------
#
# Fine-grained second gate. Every key below is inside the `clinical` domain of
# `ResourceDomain` (src/db/ems_roles.py), which is what makes the engine's
# 404-Never-403 guardrail fire: a caller who is not a clinical specialist gets
# a bare 404, never a 403 -- the same contract this module already enforces by
# hand with `_confidential_not_found()`.
#
# Applied ONLY to endpoints whose existing unauthorised outcome is already a
# refusal (404/403). The list endpoints in this module deliberately answer an
# unauthorised caller with an EMPTY LIST, and a dependency cannot produce that
# -- so they are left to the service layer's per-psychologist scoping, which is
# where that contract actually lives. See the module docstring.
CLINICAL_SESSIONS = "clinical.sessions"
CLINICAL_ACTIVITY_LOGS = "clinical.activity_logs"
CLINICAL_CASE_NOTES = "clinical.case_notes"
CLINICAL_TRIAGE = "clinical.triage"
CLINICAL_ESCALATIONS = "clinical.escalations"
CAREER_GUIDANCE = "academic.career_guidance"

def _confidential_not_found() -> HTTPException:
    """A generic 404, deliberately indistinguishable from 'record does not
    exist' -- never a 403. See module docstring."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# ---------------------------------------------------------------------------
# 1. Psychologist activity tracking
# ---------------------------------------------------------------------------

@router.post(
    "/activity-logs",
    response_model=ActivityLogRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log a Counseling-Relevant Activity Signal",
    description="PSYCHOLOGIST-only. Any other role gets a generic 404, never a 403.",
    dependencies=[Depends(require_permission(CLINICAL_ACTIVITY_LOGS, "create"))],
)
async def create_activity_log_endpoint(
    payload: ActivityLogCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> ActivityLogRead:
    if not principal.has_role(PSYCHOLOGIST):
        raise _confidential_not_found()
    record = await counseling_service.create_activity_log(session, principal, payload)
    return ActivityLogRead.model_validate(record)


@router.get(
    "/activity-logs/student/{student_id}",
    response_model=List[ActivityLogRead],
    summary="List a Student's Counseling Activity Signals",
    description=(
        "PSYCHOLOGIST-only, scoped to signals THEY logged. Every other role "
        "(TEACHER, SCHOOL_ADMIN, a different PSYCHOLOGIST, ...) gets an "
        "empty list -- never a 403 -- so existence can never be inferred."
    ),
)
async def list_activity_logs_endpoint(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ActivityLogRead]:
    records = await counseling_service.list_activity_logs_for_viewer(session, principal, student_id)
    return [ActivityLogRead.model_validate(r) for r in records]


# ---------------------------------------------------------------------------
# 2. Structured 1:1 session logging + parent involvement
# ---------------------------------------------------------------------------

@router.post(
    "/sessions",
    response_model=CounselingSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log a 1:1 Counseling Session",
    description="PSYCHOLOGIST-only. Any other role gets a generic 404, never a 403.",
    dependencies=[Depends(require_permission(CLINICAL_SESSIONS, "create"))],
)
async def create_session_endpoint(
    payload: CounselingSessionCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CounselingSessionRead:
    if not principal.has_role(PSYCHOLOGIST):
        raise _confidential_not_found()
    record = await counseling_service.create_session(session, principal, payload)
    return CounselingSessionRead.model_validate(record)


@router.get(
    "/sessions/student/{student_id}",
    response_model=List[CounselingSessionRead],
    summary="List a Student's Full Counseling Sessions",
    description=(
        "PSYCHOLOGIST-only full record, scoped to sessions THEY logged. "
        "Every other role gets an empty list -- never a 403. PARENT/STUDENT "
        "use GET .../parent-summary instead for the narrow shared slice."
    ),
)
async def list_sessions_endpoint(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[CounselingSessionRead]:
    records = await counseling_service.list_sessions_for_viewer(session, principal, student_id)
    return [CounselingSessionRead.model_validate(r) for r in records]


@router.get(
    "/sessions/{session_id}",
    response_model=CounselingSessionRead,
    summary="Get a Counseling Session by ID",
    description="PSYCHOLOGIST-only (the author). Every other caller gets a generic 404.",
    dependencies=[Depends(require_permission(CLINICAL_SESSIONS, "read"))],
)
async def get_session_endpoint(
    session_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CounselingSessionRead:
    record = await counseling_service.get_session_for_psychologist(session, principal, session_id)
    if record is None:
        raise _confidential_not_found()
    return CounselingSessionRead.model_validate(record)


@router.patch(
    "/sessions/{session_id}",
    response_model=CounselingSessionRead,
    summary="Edit a Counseling Session",
    description="PSYCHOLOGIST-only (the author). Every other caller gets a generic 404.",
    dependencies=[Depends(require_permission(CLINICAL_SESSIONS, "update"))],
)
async def update_session_endpoint(
    session_id: int,
    payload: CounselingSessionUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CounselingSessionRead:
    record = await counseling_service.update_session(session, principal, session_id, payload)
    if record is None:
        raise _confidential_not_found()
    return CounselingSessionRead.model_validate(record)


@router.get(
    "/sessions/student/{student_id}/parent-summary",
    response_model=List[ParentVisibleSessionSummary],
    summary="Parent-Visible Session Summaries",
    description=(
        "The parent-involvement slice: only sessions the psychologist "
        "explicitly flagged share_summary_with_parent. Visible to the "
        "STUDENT/PARENT role; every other role gets an empty list."
    ),
)
async def list_parent_visible_sessions_endpoint(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ParentVisibleSessionSummary]:
    records = await counseling_service.list_parent_visible_sessions(session, principal, student_id)
    return [ParentVisibleSessionSummary.model_validate(r) for r in records]


# ---------------------------------------------------------------------------
# 3. Career guidance -- structured plan, not open chat (not confidential)
# ---------------------------------------------------------------------------

async def _build_academic_summary(session: AsyncSession, student_id: int) -> str:
    """Grounds the career-guidance generation in the student's real academic
    profile by reusing the existing gradebook data (Part A.4's
    TermReportCard) rather than inventing a parallel data source."""
    stmt = (
        select(TermReportCard)
        .where(TermReportCard.student_id == student_id)
        .order_by(TermReportCard.calculated_at.desc())
    )
    record = (await session.execute(stmt)).scalars().first()
    if record is None:
        return "No academic record on file yet."

    lines = [f"Cumulative GPA: {record.gpa}", f"Overall grade: {record.letter_grade or 'N/A'}"]
    for c in record.course_summaries or []:
        lines.append(
            f"- {c.get('course_name') or c.get('course_id')}: "
            f"{c.get('letter_grade')} ({c.get('total_weighted_percentage')}%)"
        )
    return "\n".join(lines)


@router.post(
    "/career-guidance/generate",
    response_model=CareerGuidancePlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a Structured Career Guidance Plan",
    description=(
        "Generates a structured CareerGuidancePlan (pathways, reasoning, next "
        "steps) grounded in the student's academic profile. A single "
        "generate-and-store operation, not a conversational agent."
    ),
    dependencies=[Depends(require_permission(CAREER_GUIDANCE, "create"))],
)
async def generate_career_guidance_endpoint(
    payload: CareerGuidanceGenerateRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CareerGuidancePlanRead:
    if not principal.has_any_role(CAREER_GUIDANCE_STAFF_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only counseling/teaching staff can generate a career guidance plan.",
        )
    academic_summary = await _build_academic_summary(session, payload.student_id)
    try:
        record = await counseling_service.generate_career_guidance_plan(
            session=session,
            principal=principal,
            payload=payload,
            academic_summary=academic_summary,
        )
    except AINotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Career guidance plan generation failed. Please try again.",
        )
    return CareerGuidancePlanRead.model_validate(record)


@router.get(
    "/career-guidance/student/{student_id}",
    response_model=List[CareerGuidancePlanRead],
    summary="List a Student's Career Guidance Plans",
    description="Not confidential -- visible to school staff and to the student/parent themselves.",
    dependencies=[Depends(require_permission(CAREER_GUIDANCE, "read"))],
)
async def list_career_guidance_endpoint(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[CareerGuidancePlanRead]:
    records = await counseling_service.list_career_plans(session, student_id)
    return [CareerGuidancePlanRead.model_validate(r) for r in records]


# ---------------------------------------------------------------------------
# 4. Psychological Clinical Desk (Phase 5)
# ---------------------------------------------------------------------------

@router.post(
    "/clinical/notes",
    response_model=ClinicalCaseNoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Store Encrypted Clinical Case Note",
    description="PSYCHOLOGIST-only. Enforces 404-Never-403 for non-psychologists.",
    dependencies=[Depends(require_permission(CLINICAL_CASE_NOTES, "create"))],
)
async def create_encrypted_case_note_endpoint(
    payload: ClinicalCaseNoteCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> ClinicalCaseNoteRead:
    if not principal.has_role(PSYCHOLOGIST):
        raise _confidential_not_found()
    record = await clinical_desk_service.save_encrypted_case_note(session, principal, payload)
    return ClinicalCaseNoteRead(
        id=record.id,
        student_id=record.student_id,
        psychologist_id=record.psychologist_id,
        category=record.category,
        risk_level=record.risk_level,
        envelope=EncryptedEnvelope(
            ciphertext=record.envelope_ciphertext,
            iv=record.envelope_iv,
            tag=record.envelope_tag,
            key_id=record.key_id,
            algorithm=record.algorithm,
            version=record.envelope_version,
        ),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "/clinical/notes/student/{student_id}",
    response_model=List[ClinicalCaseNoteRead],
    summary="List Student Encrypted Clinical Case Notes",
    description="PSYCHOLOGIST-only (author). Every other role gets an empty list -- never a 403.",
)
async def list_encrypted_case_notes_endpoint(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ClinicalCaseNoteRead]:
    records = await clinical_desk_service.list_encrypted_case_notes_for_student(
        session, principal, student_id
    )
    return [
        ClinicalCaseNoteRead(
            id=r.id,
            student_id=r.student_id,
            psychologist_id=r.psychologist_id,
            category=r.category,
            risk_level=r.risk_level,
            envelope=EncryptedEnvelope(
                ciphertext=r.envelope_ciphertext,
                iv=r.envelope_iv,
                tag=r.envelope_tag,
                key_id=r.key_id,
                algorithm=r.algorithm,
                version=r.envelope_version,
            ),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in records
    ]


@router.post(
    "/clinical/diagnostic-assessments",
    response_model=ClinicalCaseNoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record Encrypted Diagnostic Assessment",
    description="PSYCHOLOGIST-only. Enforces 404-Never-403.",
    dependencies=[Depends(require_permission(CLINICAL_CASE_NOTES, "create"))],
)
async def create_diagnostic_assessment_endpoint(
    payload: DiagnosticAssessmentCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> ClinicalCaseNoteRead:
    if not principal.has_role(PSYCHOLOGIST):
        raise _confidential_not_found()
    record = await clinical_desk_service.save_diagnostic_assessment(session, principal, payload)
    return ClinicalCaseNoteRead(
        id=record.id,
        student_id=record.student_id,
        psychologist_id=record.psychologist_id,
        category=record.category,
        risk_level=record.risk_level,
        envelope=EncryptedEnvelope(
            ciphertext=record.envelope_ciphertext,
            iv=record.envelope_iv,
            tag=record.envelope_tag,
            key_id=record.key_id,
            algorithm=record.algorithm,
            version=record.envelope_version,
        ),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post(
    "/clinical/escalate",
    response_model=PastoralEscalationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Emit Anonymized Pastoral Escalation",
    description=(
        "Emits protective pastoral alert to school principal / leadership. "
        "Zero clinical notes or diagnostic narratives are leaked."
    ),
    dependencies=[Depends(require_permission(CLINICAL_ESCALATIONS, "create"))],
)
async def emit_pastoral_escalation_endpoint(
    payload: PastoralEscalationCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> PastoralEscalationRead:
    if not principal.has_role(PSYCHOLOGIST):
        raise _confidential_not_found()
    record = await clinical_desk_service.emit_pastoral_escalation(session, principal, payload)
    return PastoralEscalationRead.model_validate(record)


@router.get(
    "/clinical/escalations",
    response_model=List[PastoralEscalationRead],
    summary="List Pastoral Escalation Alerts",
    description="Accessible to school leadership (Principal/SuperAdmin) and psychologists. Stripped of clinical details.",
)
async def list_pastoral_escalations_endpoint(
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[PastoralEscalationRead]:
    records = await clinical_desk_service.list_pastoral_escalations_for_leadership(session, principal)
    return [PastoralEscalationRead.model_validate(r) for r in records]


@router.post(
    "/clinical/triage",
    response_model=CrisisTriageItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Flag Crisis Triage Item",
    description="PSYCHOLOGIST-only. Enforces 404-Never-403.",
    dependencies=[Depends(require_permission(CLINICAL_TRIAGE, "create"))],
)
async def create_crisis_triage_endpoint(
    payload: CrisisTriageItemCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CrisisTriageItemRead:
    if not principal.has_role(PSYCHOLOGIST):
        raise _confidential_not_found()
    record = await clinical_desk_service.create_crisis_triage(session, principal, payload)
    return CrisisTriageItemRead.model_validate(record)


@router.get(
    "/clinical/triage",
    response_model=List[CrisisTriageItemRead],
    summary="List Crisis Triage Queue",
    description="PSYCHOLOGIST-only. Enforces 404-Never-403.",
)
async def list_crisis_triage_endpoint(
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[CrisisTriageItemRead]:
    records = await clinical_desk_service.list_crisis_triage_queue(session, principal)
    return [CrisisTriageItemRead.model_validate(r) for r in records]


@router.patch(
    "/clinical/triage/{triage_id}",
    response_model=CrisisTriageItemRead,
    summary="Update Crisis Triage Status",
    description="PSYCHOLOGIST-only. Enforces 404-Never-403.",
    dependencies=[Depends(require_permission(CLINICAL_TRIAGE, "update"))],
)
async def update_crisis_triage_endpoint(
    triage_id: int,
    payload: CrisisTriageUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CrisisTriageItemRead:
    if not principal.has_role(PSYCHOLOGIST):
        raise _confidential_not_found()
    record = await clinical_desk_service.update_crisis_triage_status(
        session, principal, triage_id, payload.status
    )
    if record is None:
        raise _confidential_not_found()
    return CrisisTriageItemRead.model_validate(record)

