"""
Full Vision Integration Test Suite for CSG-LMS Pillars (M05, M08, M16, M21, M22, M35, M44, M48, M50).
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, get_current_user_principal
from src.routers.sms_cognia import router as cognia_router
from src.routers.sms_gradebook import router as gradebook_router
from src.routers.sms_fees import router as fees_router
from src.routers.sms_revops import router as revops_router
from src.routers.ai_knowledge_graph import router as knowledge_graph_router
from src.routers.ai_parent_digest import router as parent_digest_router
from src.routers.live_classes import router as live_classes_router
from src.security.features_utils.dependencies import (
    require_sms_gradebook_feature,
    require_sms_fees_feature,
    require_revops_feature,
)


@pytest.fixture
def test_principal():
    return KeycloakUserPrincipal(
        sub="test-user-sub-123",
        email="admin@csg.dev",
        username="admin",
        roles={"SUPER_ADMIN", "SCHOOL_ADMIN", "TEACHER"},
        org_id=1,
    )


@pytest.fixture
def app(db, test_principal):
    app = FastAPI()
    app.include_router(cognia_router, prefix="/api/v1/sms/cognia")
    app.include_router(gradebook_router, prefix="/api/v1/sms/gradebook")
    app.include_router(fees_router, prefix="/api/v1/sms/fees")
    app.include_router(revops_router, prefix="/api/v1/revops")
    app.include_router(knowledge_graph_router, prefix="/api/v1/ai/knowledge-graph")
    app.include_router(parent_digest_router, prefix="/api/v1/ai/parent")
    app.include_router(live_classes_router, prefix="/api/v1/live")

    # Dependency overrides
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_current_user_principal] = lambda: test_principal
    app.dependency_overrides[require_sms_gradebook_feature] = lambda: True
    app.dependency_overrides[require_sms_fees_feature] = lambda: True
    app.dependency_overrides[require_revops_feature] = lambda: True

    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


class TestCogniaAccreditationM16:
    async def test_get_standards_framework(self, client):
        response = await client.get("/api/v1/sms/cognia/standards")
        assert response.status_code == 200
        data = response.json()
        assert "domains" in data
        assert "STD_1" in data["domains"]
        assert "STD_2" in data["domains"]
        assert "STD_3" in data["domains"]

    async def test_log_and_list_evidence(self, client):
        payload = {
            "standard_code": "2.2",
            "title": "Curriculum Alignment Review",
            "description": "STEM Syllabus mapped to international standards",
            "evidence_type": "rubric",
            "academic_year": "2025-2026",
            "performance_score": 3.5,
        }
        res_create = await client.post("/api/v1/sms/cognia/evidence", json=payload)
        assert res_create.status_code == 201
        evidence_item = res_create.json()
        assert evidence_item["title"] == "Curriculum Alignment Review"
        assert evidence_item["domain"] == "Learning Capacity"

        res_list = await client.get("/api/v1/sms/cognia/evidence?standard_code=2.2")
        assert res_list.status_code == 200
        items = res_list.json()
        assert len(items) >= 1

    async def test_get_summary_and_export_binder(self, client):
        res_summary = await client.get("/api/v1/sms/cognia/summary")
        assert res_summary.status_code == 200
        summary = res_summary.json()
        assert "domain_scores" in summary
        assert "overall_compliance_score" in summary

        res_binder = await client.get("/api/v1/sms/cognia/binder/export")
        assert res_binder.status_code == 200
        binder = res_binder.json()
        assert binder["accreditation_body"] == "Cognia / AdvancED Global"
        # The export must NOT carry a verification seal. It previously emitted
        # the hardcoded constant "COGNIA-VERIFIED-CSG-LMS-2026" -- copyable
        # onto any document, asserting a real accreditation body had endorsed
        # it. It now states plainly that it is an unverified self-report.
        assert "verification_seal" not in binder
        assert "not independently verified" in binder["attestation"].lower()


class TestGradebookGPATranscriptM05:
    async def test_calculate_gpa_empty(self, client):
        """A student with no marks has NO GPA -- not a perfect one.

        This test previously asserted `unweighted_gpa == 4.0` for a student
        with zero gradebook entries, pinning the endpoint's fabrication in
        place: it reported a flawless 4.0, "Good Standing" and
        `honor_roll: True` for a child who had never been graded. The test
        asserting it is why the bug survived earlier fabrication sweeps.

        Inverted: absence of coursework must read as absence.
        """
        response = await client.get("/api/v1/sms/gradebook/students/999/gpa")
        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == 999
        assert data["unweighted_gpa"] is None, (
            "A student with no graded coursework must have no GPA -- 4.0 is a "
            "fabricated perfect record."
        )
        assert data["honor_roll"] is None, "Nobody makes the honour roll without a grade."
        assert data["academic_standing"] is None
        assert data["total_credits"] == 0.0
        assert "no graded coursework" in data["detail"].lower()

    async def test_transcript_does_not_carry_a_forgeable_seal(self, client):
        """The transcript must not claim to be verified when it is not.

        It used to return a "verification_seal" that was an unkeyed sha256
        over student_id and GPA -- both printed on the document -- so anyone
        could recompute it for any student and any GPA. Asserting its ABSENCE
        keeps it from being reintroduced as a convincing-looking but
        unverifiable stamp.
        """
        response = await client.get("/api/v1/sms/gradebook/students/999/transcript")
        assert response.status_code == 200
        data = response.json()
        assert "verification_seal" not in data
        assert data["document_type"] == "ACADEMIC_TRANSCRIPT_EXPORT"
        assert data["status"] == "UNVERIFIED_EXPORT"
        assert "verification_note" in data


class TestFeesInstallmentsM08:
    async def test_receipt_details_not_found(self, client):
        response = await client.get("/api/v1/sms/fees/receipts/NONEXISTENT/details")
        assert response.status_code == 404


WEBHOOK_TEST_SECRET = "test-revops-webhook-secret"


@pytest.fixture
def webhook_secret(monkeypatch):
    """Configure the inbound-lead shared secret for the duration of a test.

    The endpoint reads the env var per request and fails closed when it is
    unset, so tests must supply it explicitly rather than rely on ambient
    configuration.
    """
    monkeypatch.setenv("REVOPS_WEBHOOK_SECRET", WEBHOOK_TEST_SECRET)
    return WEBHOOK_TEST_SECRET


class TestRevOpsGrowthEngineM21_M22_M35:
    async def test_inbound_lead_webhook(self, client, webhook_secret):
        payload = {
            "parent_name": "Sarah Jenkins",
            "student_name": "Leo Jenkins",
            "email": "sarah.j@example.com",
            "phone": "+15551234567",
            "target_grade": "Grade 10",
        }
        response = await client.post(
            "/api/v1/revops/webhook/meta",
            json=payload,
            headers={"X-Webhook-Secret": webhook_secret},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ingested"
        assert data["channel"] == "meta"
        lead_id = data["lead_id"]

        # Test AI Lead Qualification Scoring (M22)
        res_qualify = await client.post(f"/api/v1/revops/leads/{lead_id}/ai-qualify")
        assert res_qualify.status_code == 200
        qual_data = res_qualify.json()
        assert qual_data["lead_score"] > 0
        assert qual_data["intent_level"] in {"HOT", "WARM", "COLD", "NURTURE"}
        assert qual_data["breakdown"]
        assert qual_data["recommended_next_action"]

        # NOTE: M35 autonomous follow-up sequence generation is NOT implemented.
        # This test previously asserted POST /leads/{id}/generate-sequence
        # returned exactly three touchpoints beginning with WhatsApp. No such
        # route has ever existed in sms_revops.py -- the assertion described a
        # canned itinerary rather than a behaviour, and satisfying it would have
        # meant writing a generator that invents a contact plan it has no basis
        # for. The gap is left open and visible here instead of being papered
        # over with a stub that passes.
        res_seq = await client.post(f"/api/v1/revops/leads/{lead_id}/generate-sequence")
        assert res_seq.status_code == 404, (
            "M35 sequence generation now exists -- replace this with real assertions."
        )

    async def test_webhook_rejects_a_wrong_secret(self, client, webhook_secret):
        """A caller who guesses wrong must not be able to write into the CRM."""
        response = await client.post(
            "/api/v1/revops/webhook/meta",
            json={"email": "intruder@example.com"},
            headers={"X-Webhook-Secret": "not-the-secret"},
        )
        assert response.status_code == 403

    async def test_webhook_fails_closed_when_unconfigured(self, client, monkeypatch):
        """An unconfigured deployment rejects rather than accepting anonymous writes.

        This is the failure mode that matters: a secret nobody set must not
        degrade into "no secret required".
        """
        monkeypatch.delenv("REVOPS_WEBHOOK_SECRET", raising=False)
        response = await client.post(
            "/api/v1/revops/webhook/meta",
            json={"email": "anon@example.com"},
            headers={"X-Webhook-Secret": ""},
        )
        assert response.status_code == 403

    async def test_webhook_rejects_a_lead_with_no_way_to_contact_it(
        self, client, webhook_secret
    ):
        response = await client.post(
            "/api/v1/revops/webhook/meta",
            json={"parent_name": "No Contact Details"},
            headers={"X-Webhook-Secret": webhook_secret},
        )
        assert response.status_code == 422


class TestAIStudentCoachM44_M48_M50:
    async def test_curriculum_graph_refuses_instead_of_serving_a_demo_curriculum(self, client):
        """This endpoint returned a hardcoded six-node Maths graph to every
        school, campus and grade. The previous version of this test asserted
        `total_nodes >= 5` -- it was pinning the fixture in place. The real
        concept catalogue is GET /api/v1/ai/concepts, backed by ConceptNode.
        """
        response = await client.get("/api/v1/ai/knowledge-graph/graph?subject=math_high_school")
        assert response.status_code == 501
        assert "ai/concepts" in response.json()["detail"]

    async def test_student_mastery_refuses_instead_of_simulating_scores(self, client):
        """The endpoint held `scores = [95.0, 88.0, 72.0, 84.0, 45.0, 10.0]`
        under the comment "Dynamic simulation for demo" and never queried the
        database, so every student -- including ones who do not exist --
        returned 65.7% and "2/6 mastered". A teacher would have been shown
        "95% mastered" for a child never assessed.

        The previous version of this test asserted
        `len(data["mastery_nodes"]) >= 5`, which required the fabrication to
        keep working. It now asserts the refusal, and specifically that no
        score survives anywhere in the response -- refusing with zeros would
        be the same lie in a quieter voice.
        """
        response = await client.get("/api/v1/ai/knowledge-graph/students/123/mastery")
        assert response.status_code == 501
        body = response.text
        assert "mastery_nodes" not in body
        assert "95.0" not in body and "65.7" not in body
        assert "mastery-radar" in response.json()["detail"]

    async def test_parent_weekly_digest_reports_absence_of_data_honestly(self, client):
        """A student with no records this week gets "Not recorded", not 96%.

        This endpoint used to return the same flattering hardcoded figures for
        every student regardless of student_id. The assertions below deliberately
        pin the honest behaviour: no attendance rows means no attendance rate,
        and no tutor activity means an empty topic list -- never a default that
        would read to a parent as a real measurement of their own child.
        """
        response = await client.get("/api/v1/ai/parent/students/123/digest")
        assert response.status_code == 200
        data = response.json()
        assert data["attendance_rate"] == "Not recorded"
        assert data["total_classes"] == 0
        assert data["classes_attended"] == 0
        assert data["tutor_sessions"] == 0
        assert data["ai_tutor_topics_explored"] == []
        # Fields that had no data source were removed outright rather than
        # emptied -- an empty list still implies "we looked and found none".
        assert "top_strengths" not in data
        assert "average_weekly_score" not in data
        assert "teacher_praise" not in data
        assert "96" not in data["conversational_summary"]
