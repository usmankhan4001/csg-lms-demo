"""
Unit tests for Phase 5 Psychological Clinical Desk & Cognia Evidence Engine.
=============================================================================
Covers:
- Client-side AES-256-GCM envelope encryption & decryption
- Strict 404-Never-403 rule enforcement
- Anonymized pastoral escalation without clinical notes leak
- SHA-256 dual checksum evidence harvesting (lesson plans, rubrics, psychometrics, attendance, policy)
- Real-time Accreditation Maturity Index (AMI) calculation across Leadership, Learning, and Resource standards
- One-click Cognia Self-Study Dossier compilation and integrity manifest
"""

import pytest
from cryptography.exceptions import InvalidTag
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import KeycloakUserPrincipal
from src.schemas.sms_counseling import (
    ClinicalCaseNoteCreate,
    CrisisTriageItemCreate,
    DiagnosticAssessmentCreate,
    PastoralEscalationCreate,
)
from src.services.sms import clinical_desk, cognia_engine


def _principal(roles, sub="user-1", org_id=1, campus_id=1, user_id=101):
    return KeycloakUserPrincipal(
        sub=sub,
        org_id=org_id,
        campus_id=campus_id,
        roles=set(roles),
        attributes={"user_id": [str(user_id)]},
    )


# ===========================================================================
# 1. Psychological Clinical Desk Tests
# ===========================================================================

class TestClinicalDeskEncryption:
    def test_aes_256_gcm_encryption_roundtrip(self):
        key = clinical_desk.generate_aes256_key()
        assert len(key) == 32

        plaintext = "Confidential psychological assessment: Patient reports anxiety triggers."
        envelope = clinical_desk.encrypt_clinical_envelope(plaintext, key, key_id="vault-key-01")

        assert envelope.algorithm == "AES-256-GCM"
        assert envelope.key_id == "vault-key-01"
        assert envelope.ciphertext != plaintext
        assert len(envelope.iv) > 0
        assert len(envelope.tag) > 0

        decrypted = clinical_desk.decrypt_clinical_envelope(envelope, key)
        assert decrypted == plaintext

    def test_tampered_ciphertext_fails_decryption(self):
        key = clinical_desk.generate_aes256_key()
        plaintext = "Sensitive therapeutic notes."
        envelope = clinical_desk.encrypt_clinical_envelope(plaintext, key)

        # Corrupt ciphertext
        tampered_envelope = envelope.model_copy(update={"ciphertext": "dGFtcGVyZWQ="})
        with pytest.raises(Exception):
            clinical_desk.decrypt_clinical_envelope(tampered_envelope, key)

    def test_invalid_key_length_rejected(self):
        short_key = b"too_short_key_16"
        with pytest.raises(ValueError, match="32-byte"):
            clinical_desk.encrypt_clinical_envelope("test", short_key)


class TestClinicalDeskAccessControl:
    @pytest.mark.asyncio
    async def test_non_psychologist_gets_404_never_403(self, db: AsyncSession):
        teacher = _principal(["TEACHER"], sub="teacher-1")
        school_admin = _principal(["SCHOOL_ADMIN"], sub="admin-1")

        # 404 on psychologist check
        with pytest.raises(HTTPException) as exc:
            clinical_desk.require_psychologist_role_or_404(teacher)
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc2:
            clinical_desk.require_psychologist_role_or_404(school_admin)
        assert exc2.value.status_code == 404

        # Listing notes returns empty list for non-psychologists (never 403)
        notes = await clinical_desk.list_encrypted_case_notes_for_student(db, teacher, student_id=101)
        assert notes == []

        # Triage queue returns empty list for non-psychologists
        triage = await clinical_desk.list_crisis_triage_queue(db, teacher)
        assert triage == []

    @pytest.mark.asyncio
    async def test_psychologist_can_create_and_read_encrypted_notes(self, db: AsyncSession):
        psych = _principal(["PSYCHOLOGIST"], sub="psych-007", user_id=701)
        key = clinical_desk.generate_aes256_key()
        envelope = clinical_desk.encrypt_clinical_envelope("Therapeutic notes content", key)

        payload = ClinicalCaseNoteCreate(
            student_id=505,
            category="therapeutic_note",
            risk_level="medium",
            envelope=envelope,
        )

        saved = await clinical_desk.save_encrypted_case_note(db, psych, payload)
        assert saved.id is not None
        assert saved.student_id == 505
        assert saved.psychologist_id == "psych-007"
        assert saved.envelope_ciphertext == envelope.ciphertext

        # Fetch notes for student
        notes = await clinical_desk.list_encrypted_case_notes_for_student(db, psych, student_id=505)
        assert len(notes) == 1
        assert notes[0].id == saved.id

        # Another psychologist gets empty list (strict author isolation)
        psych_other = _principal(["PSYCHOLOGIST"], sub="psych-999", user_id=799)
        other_notes = await clinical_desk.list_encrypted_case_notes_for_student(db, psych_other, student_id=505)
        assert other_notes == []


class TestPastoralEscalation:
    @pytest.mark.asyncio
    async def test_anonymized_escalation_contains_no_clinical_notes(self, db: AsyncSession):
        psych = _principal(["PSYCHOLOGIST"], sub="psych-007", org_id=1, user_id=701)
        
        payload = PastoralEscalationCreate(
            student_id=505,
            risk_level="high",
            category="crisis_triage",
            action_required="Initiate immediate pastoral welfare check and notify head of house.",
        )

        escalation = await clinical_desk.emit_pastoral_escalation(db, psych, payload)
        assert escalation.id is not None
        assert escalation.student_anon_token.startswith("STU-ANON-")
        assert escalation.risk_level == "high"
        assert escalation.action_required == payload.action_required
        # Assure no clinical notes exist in model attributes
        assert not hasattr(escalation, "notes")
        assert not hasattr(escalation, "diagnostic_narrative")

        # Leadership can list the escalation
        admin = _principal(["SCHOOL_ADMIN"], sub="admin-1", org_id=1)
        alerts = await clinical_desk.list_pastoral_escalations_for_leadership(db, admin)
        assert len(alerts) >= 1
        assert alerts[0].student_anon_token == escalation.student_anon_token


# ===========================================================================
# 2. Cognia Evidence Locker & Real-Time AMI Tests
# ===========================================================================

class TestCogniaDualChecksumAndHarvesting:
    def test_dual_checksum_computation(self):
        payload = {"lesson_id": 101, "topic": "Photosynthesis", "rigor_tier": 3}
        metadata = {
            "standard_code": "2.2",
            "domain": "Learning Capacity",
            "academic_year": "2025-2026",
            "submitted_by": "teacher-1",
            "timestamp": "2026-09-15T12:00:00Z",
        }

        checksums = cognia_engine.compute_dual_checksum(payload, metadata)
        assert "content_hash" in checksums
        assert "audit_signature_hash" in checksums
        assert len(checksums["content_hash"]) == 64
        assert len(checksums["audit_signature_hash"]) == 64
        assert checksums["verification_badge"].startswith("SHA256:")

        # Verification helper
        assert cognia_engine.verify_evidence_dual_checksum(
            payload, metadata, checksums["content_hash"], checksums["audit_signature_hash"]
        ) is True

    @pytest.mark.asyncio
    async def test_automated_evidence_harvesters(self, db: AsyncSession):
        teacher = _principal(["TEACHER"], sub="teacher-42", org_id=1, user_id=42)

        # 1. Harvest Lesson Plan (STD 2.2)
        lp = await cognia_engine.harvest_lesson_plan(
            db, teacher,
            {"title": "Quantum Mechanics Intro", "grade_level": "12", "differentiated_instruction": True},
        )
        assert lp.standard_code == "2.2"
        assert lp.domain == "Learning Capacity"
        assert lp.performance_score == 3.5
        assert "Content-SHA256:" in lp.description

        # 2. Harvest Rubric (STD 2.3)
        rubric = await cognia_engine.harvest_rubric(
            db, teacher,
            {"title": "Argumentative Essay Rubric", "criteria": ["Thesis", "Evidence", "Structure", "Conventions"]},
        )
        assert rubric.standard_code == "2.3"
        assert rubric.performance_score == 3.5

        # 3. Harvest Psychometrics (STD 2.3)
        psychometrics = await cognia_engine.harvest_exam_psychometrics(
            db, teacher,
            {"exam_code": "PHYS-101", "cronbach_alpha": 0.88, "mean_discrimination": 0.45},
        )
        assert psychometrics.standard_code == "2.3"
        assert psychometrics.performance_score == 4.0

        # 4. Harvest Attendance (STD 3.2)
        attendance = await cognia_engine.harvest_attendance_logs(
            db, teacher,
            {"term": "Term 1", "attendance_rate_pct": 96.5, "pastoral_resolution_pct": 99.0},
        )
        assert attendance.standard_code == "3.2"
        assert attendance.domain == "Resource Capacity"
        assert attendance.performance_score == 3.8

        # 5. Harvest Governance Policy (STD 1.1)
        policy = await cognia_engine.harvest_governance_policy(
            db, teacher,
            {"title": "Stakeholder Continuous Improvement Charter", "evaluated_score": 3.6},
        )
        assert policy.standard_code == "1.1"
        assert policy.domain == "Leadership Capacity"
        assert policy.performance_score == 3.6


class TestRealTimeAMIAndDossierExport:
    @pytest.mark.asyncio
    async def test_ami_calculation_and_tier_classification(self, db: AsyncSession):
        admin = _principal(["SCHOOL_ADMIN"], sub="admin-1", org_id=2, user_id=1)

        # Before evidence: unassessed
        initial_ami = await cognia_engine.calculate_realtime_ami(db, org_id=2)
        assert initial_ami["ami_score"] is None
        assert initial_ami["domains_assessed"] == 0
        assert initial_ami["is_fully_evidenced"] is False

        # Add evidence for all 3 domains
        await cognia_engine.harvest_governance_policy(
            db, admin, {"title": "Vision", "evaluated_score": 3.6}
        )
        await cognia_engine.harvest_lesson_plan(
            db, admin, {"title": "Calculus", "differentiated_instruction": True}
        )
        await cognia_engine.harvest_attendance_logs(
            db, admin, {"term": "Term 1", "attendance_rate_pct": 95.0}
        )

        ami_result = await cognia_engine.calculate_realtime_ami(db, org_id=2)
        assert ami_result["ami_score"] is not None
        assert 3.5 <= ami_result["ami_score"] <= 4.0
        assert ami_result["domains_assessed"] == 3
        assert ami_result["is_fully_evidenced"] is True
        assert "Exemplary" in ami_result["maturity_tier"]

    @pytest.mark.asyncio
    async def test_self_study_dossier_generation(self, db: AsyncSession):
        admin = _principal(["SCHOOL_ADMIN"], sub="admin-1", org_id=3, user_id=1)

        await cognia_engine.harvest_governance_policy(db, admin, {"title": "Charter", "evaluated_score": 3.8})
        await cognia_engine.harvest_rubric(db, admin, {"title": "STEM Rubric", "criteria": ["A", "B", "C", "D"]})
        await cognia_engine.harvest_attendance_logs(db, admin, {"term": "Term 2", "attendance_rate_pct": 97.0})

        dossier = await cognia_engine.generate_self_study_dossier(db, admin)
        assert dossier["dossier_type"] == "Cognia Continuous Improvement Self-Study Dossier"
        assert dossier["institution_id"] == "org_3"
        assert len(dossier["evidence_locker_manifest"]) >= 3
        assert "tamper_evident_seal" in dossier["digital_attestation"]
        assert len(dossier["strategic_improvement_initiatives"]) > 0
