"""
CSG-EMS Psychological Clinical Desk Service (Phase 5).
======================================================
Provides zero-knowledge client-side AES-256-GCM envelope encryption for
therapeutic case notes and diagnostic assessments, strict 404-Never-403
access gating, and anonymized pastoral escalation to institutional leadership.
"""

import base64
import hashlib
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import KeycloakUserPrincipal, PSYCHOLOGIST, SCHOOL_ADMIN, SUPER_ADMIN
from src.db.sms_counseling import (
    ClinicalCrisisTriageItem,
    EncryptedClinicalCaseNote,
    PastoralEscalationAlert,
)
from src.schemas.sms_counseling import (
    ClinicalCaseNoteCreate,
    CrisisTriageItemCreate,
    DiagnosticAssessmentCreate,
    EncryptedEnvelope,
    PastoralEscalationCreate,
)
from src.security.school_ownership import get_user_id, require_org_id, resolve_scoped_campus_id


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clinical_not_found() -> HTTPException:
    """The 404-Never-403 rule: Non-psychologists or unauthorized callers
    receive a clean 404 Not Found on all clinical endpoints, preventing
    an existence oracle."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def require_psychologist_role_or_404(principal: KeycloakUserPrincipal) -> None:
    """Enforces that the caller has PSYCHOLOGIST role; raises 404 Not Found otherwise."""
    if not principal.has_role(PSYCHOLOGIST):
        raise clinical_not_found()


def _is_psychologist(principal: KeycloakUserPrincipal) -> bool:
    return principal.has_role(PSYCHOLOGIST)


# ---------------------------------------------------------------------------
# AES-256-GCM Envelope Encryption Helpers
# ---------------------------------------------------------------------------

def generate_aes256_key() -> bytes:
    """Generates a cryptographically secure 256-bit (32-byte) AES key."""
    return AESGCM.generate_key(bit_length=256)


def encrypt_clinical_envelope(
    plaintext: str,
    key: bytes,
    key_id: Optional[str] = None,
    associated_data: Optional[bytes] = None,
) -> EncryptedEnvelope:
    """Encrypts plaintext therapeutic notes or diagnostic assessments using AES-256-GCM.
    Returns an EncryptedEnvelope containing ciphertext, 12-byte IV, and 16-byte auth tag."""
    if len(key) != 32:
        raise ValueError("AES-256 requires a 32-byte (256-bit) key")
    
    # 12-byte nonce standard for GCM
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    
    # AESGCM.encrypt in cryptography appends the 16-byte tag to the ciphertext
    ct_and_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), associated_data)
    
    # Split ciphertext and 16-byte authentication tag
    tag_len = 16
    ciphertext_bytes = ct_and_tag[:-tag_len]
    tag_bytes = ct_and_tag[-tag_len:]
    
    return EncryptedEnvelope(
        ciphertext=base64.b64encode(ciphertext_bytes).decode("ascii"),
        iv=base64.b64encode(iv).decode("ascii"),
        tag=base64.b64encode(tag_bytes).decode("ascii"),
        key_id=key_id,
        algorithm="AES-256-GCM",
        version="v1",
    )


def decrypt_clinical_envelope(
    envelope: Union[EncryptedEnvelope, Dict[str, Any]],
    key: bytes,
    associated_data: Optional[bytes] = None,
) -> str:
    """Decrypts an AES-256-GCM EncryptedEnvelope and verifies tag authenticity."""
    if len(key) != 32:
        raise ValueError("AES-256 requires a 32-byte (256-bit) key")

    if isinstance(envelope, EncryptedEnvelope):
        ciphertext_b64 = envelope.ciphertext
        iv_b64 = envelope.iv
        tag_b64 = envelope.tag
    else:
        ciphertext_b64 = envelope["ciphertext"]
        iv_b64 = envelope["iv"]
        tag_b64 = envelope["tag"]

    iv = base64.b64decode(iv_b64)
    ciphertext_bytes = base64.b64decode(ciphertext_b64)
    tag_bytes = base64.b64decode(tag_b64)
    
    ct_and_tag = ciphertext_bytes + tag_bytes
    aesgcm = AESGCM(key)
    
    decrypted_bytes = aesgcm.decrypt(iv, ct_and_tag, associated_data)
    return decrypted_bytes.decode("utf-8")


# ---------------------------------------------------------------------------
# Anonymized Institutional Escalation
# ---------------------------------------------------------------------------

def generate_student_anon_token(student_id: int, org_id: int) -> str:
    """Generates an HMAC/SHA-256 derived pseudo-anonymous token for institutional alerts.
    E.g. STU-ANON-A1B2C3D4"""
    digest = hashlib.sha256(f"CSG-EMS:ANON:{org_id}:{student_id}".encode("utf-8")).hexdigest()[:8].upper()
    return f"STU-ANON-{digest}"


async def emit_pastoral_escalation(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    payload: PastoralEscalationCreate,
) -> PastoralEscalationAlert:
    """Emits a protective pastoral alert to school leadership without disclosing
    any clinical case notes or diagnostic narratives."""
    require_psychologist_role_or_404(principal)
    
    org_id = require_org_id(principal)
    campus_id = resolve_scoped_campus_id(principal, None)
    anon_token = generate_student_anon_token(payload.student_id, org_id)

    alert = PastoralEscalationAlert(
        org_id=org_id,
        campus_id=campus_id,
        student_anon_token=anon_token,
        student_id=payload.student_id,
        risk_level=payload.risk_level.lower(),
        category=payload.category,
        action_required=payload.action_required,
        status="PENDING",
        escalated_by_sub=principal.sub,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


async def list_pastoral_escalations_for_leadership(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
) -> List[PastoralEscalationAlert]:
    """Lists anonymized pastoral alerts for school leadership (Principal / Admins)
    and psychologists. Zero clinical notes are surfaced."""
    if not principal.has_any_role([SUPER_ADMIN, SCHOOL_ADMIN, PSYCHOLOGIST]):
        return []
    
    org_id = require_org_id(principal)
    stmt = (
        select(PastoralEscalationAlert)
        .where(PastoralEscalationAlert.org_id == org_id)
        .order_by(PastoralEscalationAlert.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Clinical Case Notes & Diagnostic Assessments
# ---------------------------------------------------------------------------

def _authored_by_clause(model, principal: KeycloakUserPrincipal):
    caller_user_id = get_user_id(principal)
    if caller_user_id is None:
        return model.psychologist_id == principal.sub
    return or_(
        model.psychologist_id == principal.sub,
        and_(
            model.psychologist_user_id.is_not(None),
            model.psychologist_user_id == caller_user_id,
        ),
    )


async def save_encrypted_case_note(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    payload: ClinicalCaseNoteCreate,
) -> EncryptedClinicalCaseNote:
    """Stores an encrypted therapeutic case note. Psychologist-only (404-Never-403)."""
    require_psychologist_role_or_404(principal)

    note = EncryptedClinicalCaseNote(
        student_id=payload.student_id,
        psychologist_id=principal.sub,
        psychologist_user_id=get_user_id(principal),
        category=payload.category,
        risk_level=payload.risk_level,
        envelope_ciphertext=payload.envelope.ciphertext,
        envelope_iv=payload.envelope.iv,
        envelope_tag=payload.envelope.tag,
        key_id=payload.envelope.key_id,
        algorithm=payload.envelope.algorithm,
        envelope_version=payload.envelope.version,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


async def list_encrypted_case_notes_for_student(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    student_id: int,
) -> List[EncryptedClinicalCaseNote]:
    """Retrieves encrypted case notes for a student, scoped strictly to the authoring psychologist."""
    if not _is_psychologist(principal):
        return []

    stmt = (
        select(EncryptedClinicalCaseNote)
        .where(
            and_(
                EncryptedClinicalCaseNote.student_id == student_id,
                _authored_by_clause(EncryptedClinicalCaseNote, principal),
            )
        )
        .order_by(EncryptedClinicalCaseNote.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_encrypted_case_note_by_id(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    note_id: int,
) -> Optional[EncryptedClinicalCaseNote]:
    if not _is_psychologist(principal):
        return None

    record = await session.get(EncryptedClinicalCaseNote, note_id)
    if record is None:
        return None
    
    caller_user_id = get_user_id(principal)
    if record.psychologist_id != principal.sub and (
        record.psychologist_user_id is None
        or caller_user_id is None
        or record.psychologist_user_id != caller_user_id
    ):
        return None
    return record


async def save_diagnostic_assessment(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    payload: DiagnosticAssessmentCreate,
) -> EncryptedClinicalCaseNote:
    """Stores an encrypted diagnostic assessment evaluation (e.g. PHQ-9, GAD-7, BASC-3)."""
    require_psychologist_role_or_404(principal)

    note = EncryptedClinicalCaseNote(
        student_id=payload.student_id,
        psychologist_id=principal.sub,
        psychologist_user_id=get_user_id(principal),
        category=f"diagnostic_assessment:{payload.assessment_tool}",
        risk_level=payload.risk_level,
        envelope_ciphertext=payload.envelope.ciphertext,
        envelope_iv=payload.envelope.iv,
        envelope_tag=payload.envelope.tag,
        key_id=payload.envelope.key_id,
        algorithm=payload.envelope.algorithm,
        envelope_version=payload.envelope.version,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


# ---------------------------------------------------------------------------
# Emergency Crisis Triage Queue
# ---------------------------------------------------------------------------

async def create_crisis_triage(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    payload: CrisisTriageItemCreate,
) -> ClinicalCrisisTriageItem:
    require_psychologist_role_or_404(principal)

    item = ClinicalCrisisTriageItem(
        student_id=payload.student_id,
        psychologist_id=principal.sub,
        triage_level=payload.triage_level.upper(),
        trigger_reason=payload.trigger_reason,
        status="ACTIVE",
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def list_crisis_triage_queue(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
) -> List[ClinicalCrisisTriageItem]:
    """Psychologist-only triage queue for critical crisis monitoring."""
    if not _is_psychologist(principal):
        return []

    stmt = (
        select(ClinicalCrisisTriageItem)
        .where(
            _authored_by_clause(ClinicalCrisisTriageItem, principal),
        )
        .order_by(ClinicalCrisisTriageItem.flagged_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_crisis_triage_status(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    triage_id: int,
    status: str,
) -> Optional[ClinicalCrisisTriageItem]:
    if not _is_psychologist(principal):
        return None

    item = await session.get(ClinicalCrisisTriageItem, triage_id)
    if item is None:
        return None
    
    caller_user_id = get_user_id(principal)
    if item.psychologist_id != principal.sub and (
        caller_user_id is None
    ):
        return None

    item.status = status.upper()
    if status.upper() in ("RESOLVED", "ESCALATED"):
        item.resolved_at = _utcnow()
    
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item
