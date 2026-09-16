import pytest
from sqlmodel import select
from src.db.api_tokens import APIToken, VALID_API_SCOPES
from src.db.users import APITokenUser, AnonymousUser, PublicUser
from src.security.api_token_utils import token_has_scope
from src.services.webhooks.events import WEBHOOK_EVENTS, validate_event_data


def test_valid_api_scopes_catalog_structure():
    """Verify VALID_API_SCOPES covers all required domains."""
    assert len(VALID_API_SCOPES) >= 25
    expected_scopes = [
        "academic:read", "academic:write",
        "attendance:read", "attendance:bulk",
        "gradebook:read", "gradebook:write",
        "exams:read", "exams:psychometrics",
        "admissions:read", "admissions:matriculate",
        "fees:read", "fees:collect",
        "financials:read", "financials:write",
        "payroll:read", "payroll:approve",
        "crisis:alert",
        "cognia:read", "cognia:verify",
        "clinical:restricted",
    ]
    for scope in expected_scopes:
        assert scope in VALID_API_SCOPES
        assert "category" in VALID_API_SCOPES[scope]
        assert "description" in VALID_API_SCOPES[scope]


def test_token_has_scope_wildcard_matching():
    """Verify exact, domain-wildcard, action-wildcard, and full-wildcard evaluation."""
    # 1. Full wildcard
    super_token = APITokenUser(org_id=1, scopes=["*"])
    assert token_has_scope(super_token, "academic:read") is True
    assert token_has_scope(super_token, "fees:collect") is True
    assert token_has_scope(super_token, "crisis:alert") is True

    # 2. Domain wildcard
    academic_token = APITokenUser(org_id=1, scopes=["academic:*"])
    assert token_has_scope(academic_token, "academic:read") is True
    assert token_has_scope(academic_token, "academic:write") is True
    assert token_has_scope(academic_token, "attendance:read") is False

    # 3. Action wildcard
    readonly_token = APITokenUser(org_id=1, scopes=["*:read"])
    assert token_has_scope(readonly_token, "academic:read") is True
    assert token_has_scope(readonly_token, "fees:read") is True
    assert token_has_scope(readonly_token, "fees:write") is False

    # 4. Exact scopes
    finance_token = APITokenUser(org_id=1, scopes=["fees:read", "fees:collect", "financials:read"])
    assert token_has_scope(finance_token, "fees:collect") is True
    assert token_has_scope(finance_token, "fees:write") is False
    assert token_has_scope(finance_token, "admissions:read") is False

    # 5. Session users (PublicUser) automatically pass token scope checks
    session_user = PublicUser(id=1, user_uuid="user_123", username="admin", email="admin@csg.edu", first_name="A", last_name="B")
    assert token_has_scope(session_user, "any:scope") is True


    # 6. Anonymous users fail
    anon_user = AnonymousUser()
    assert token_has_scope(anon_user, "any:scope") is False


def test_webhook_events_catalog_coverage():
    """Verify all 32+ webhook events exist with valid schemas."""
    assert len(WEBHOOK_EVENTS) >= 40
    required_events = [
        "lead.created", "lead.stage_changed", "lead.matriculated",
        "section.created", "student.enrolled", "student.transferred", "timetable.published",
        "attendance.recorded", "attendance.truancy_alert", "attendance.excuse_submitted",
        "coursework.graded", "speedgrader.evaluated", "report_card.published",
        "exam.scheduled", "exam.submitted", "exam.psychometrics_calculated",
        "fee.voucher_created", "fee.payment_received", "fee.overdue",
        "journal.posted", "payroll.processed", "payroll.approved",
        "crisis.escalated", "discipline.incident_logged",
        "cognia.evidence_submitted", "cognia.evidence_verified", "cognia.ami_updated",
    ]
    for ev in required_events:
        assert ev in WEBHOOK_EVENTS, f"Event {ev} missing from WEBHOOK_EVENTS"
        assert "category" in WEBHOOK_EVENTS[ev]
        assert "data_schema" in WEBHOOK_EVENTS[ev]


def test_webhook_event_data_validation():
    """Verify validate_event_data catches schema compliance."""
    # Valid matriculation payload
    valid_data = {
        "lead_id": 101,
        "student_user_id": 12,
        "student_email": "student@csg.edu",
        "parent_user_id": 13,
        "parent_email": "parent@csg.edu",
        "campus_id": 1,
        "section_id": 2,
        "section_name": "Section 10-A",
        "enrollment_date": "2026-09-16",
        "initial_voucher_id": 55,
        "total_tuition_due": 12000.0,
    }
    # Should not raise
    validate_event_data("lead.matriculated", valid_data)
