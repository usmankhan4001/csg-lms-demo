"""
Unit Tests for RevOps AI Services (Modules M22, M24, M25, M26, M27)
===================================================================
Tests for:
1. AI Lead Scoring Engine (revops_lead_scoring.py)
2. Conversational Admissions SDR Agent (revops_sdr_agent.py)
3. Automated Marketing Drip Generator (revops_drip_engine.py)
4. Dynamic Scholarship & Offer Letter Generator (revops_offer_generator.py)
"""

import pytest

from src.services.ai.revops_lead_scoring import calculate_lead_score
from src.services.ai.revops_sdr_agent import (
    extract_entities_from_text,
    detect_inquiry_intent,
    handle_admissions_inquiry,
)
from src.services.ai.revops_drip_engine import generate_nurture_sequence
from src.services.ai.revops_offer_generator import generate_personalized_offer_copy


# ===========================================================================
# 1. Tests for AI Lead Scoring Engine (M22, M24)
# ===========================================================================

class TestLeadScoringEngine:
    def test_hot_lead_high_conversion(self):
        lead_data = {
            "id": "lead_101",
            "student_name": "Alexander Vance",
            "parent_name": "Eleanor Vance",
            "email": "eleanor.vance@example.com",
            "phone": "+1-555-019-2834",
            "grade": "Grade 1",
            "previous_school": "Little Explorers Early Years",
            "curriculum_preference": "Cambridge Primary",
            "interactions_count": 6,
            "replied_whatsapp": True,
            "attended_event": True,
            "requested_callback": True,
            "budget_fit": "high",
            "start_timeline": "immediate",
        }

        result = calculate_lead_score(lead_data)

        assert result["score"] >= 75.0
        assert result["intent"] == "HOT"
        assert result["lead_id"] == "lead_101"
        assert len(result["key_conversion_factors"]) >= 3
        assert "Priority Admissions Outreach" in result["recommended_next_action"]

        # Check breakdown
        breakdown = result["breakdown"]
        assert breakdown["completeness_score"] == 25.0
        assert breakdown["responsiveness_score"] == 20.0
        assert breakdown["grade_demand_score"] == 15.0
        assert breakdown["budget_fit_score"] == 20.0
        assert breakdown["timeline_score"] == 20.0
        assert result["score"] == 100.0

    def test_warm_lead_moderate_engagement(self):
        lead_data = {
            "id": "lead_102",
            "student_name": "Lucas Grey",
            "parent_name": "Mark Grey",
            "email": "mark.grey@example.com",
            "phone": "555-4432-111",
            "grade": "Grade 4",
            "interactions_count": 2,
            "opened_email": True,
            "budget_fit": "standard",
            "start_timeline": "next term",
        }

        result = calculate_lead_score(lead_data)

        assert 45.0 <= result["score"] < 75.0
        assert result["intent"] == "WARM"
        assert "Send Personalized Curriculum & Fee Guide" in result["recommended_next_action"]

    def test_cold_lead_minimal_data(self):
        lead_data = {
            "id": "lead_103",
            "email": "inquiry@random.com",
            "interactions_count": 0,
            "start_timeline": "next year",
        }

        result = calculate_lead_score(lead_data)

        assert result["score"] < 45.0
        assert result["intent"] == "COLD"
        assert "Enroll in 14-Day Value-Add" in result["recommended_next_action"]

    def test_empty_or_malformed_input(self):
        # Empty dict
        res_empty = calculate_lead_score({})
        assert isinstance(res_empty["score"], float)
        assert res_empty["score"] >= 0.0
        assert res_empty["intent"] == "COLD"

        # Non-dict input
        res_none = calculate_lead_score(None)  # type: ignore
        assert res_none["intent"] == "COLD"

    def test_budget_fit_with_numeric_values(self):
        lead_data = {
            "stated_budget": 15000,
            "expected_fee": 12000,
            "grade": "Grade 9",
            "start_timeline": "immediate",
        }
        res = calculate_lead_score(lead_data)
        assert res["breakdown"]["budget_fit_score"] == 20.0


# ===========================================================================
# 2. Tests for Conversational Admissions SDR Agent (M25, M26)
# ===========================================================================

class TestAdmissionsSDRAgent:
    def test_entity_extraction_complete_sentence(self):
        text = (
            "Hi, my name is Sarah Jenkins. I am looking for Grade 5 admission for my son "
            "Adam who is 10 years old. You can reach me at sarah.jenkins@gmail.com or +1 555-839-2041."
        )
        entities = extract_entities_from_text(text)

        assert entities["parent_name"] == "Sarah Jenkins"
        assert entities["student_name"] == "Adam"
        assert entities["student_age"] == 10
        assert entities["grade"] == "Grade 5"
        assert entities["email"] == "sarah.jenkins@gmail.com"
        assert entities["phone"] == "+1 555-839-2041"

    def test_tour_intent_detection(self):
        message = "Can we book a campus tour this Friday to see the STEAM labs and classrooms?"
        intent_data = detect_inquiry_intent(message)

        assert intent_data["tour_intent_detected"] is True
        assert intent_data["primary_intent"] == "book_tour"

    def test_fee_inquiry_handling(self):
        message = "What are the annual tuition fees for Grade 3 and do you offer installment payment plans?"
        result = handle_admissions_inquiry(message)

        assert result["intent"] == "fee_inquiry"
        assert "Tuition & Flexible Payment Plans" in result["response"]
        assert "send_fee_schedule" in result["suggested_actions"]

    def test_curriculum_inquiry_handling(self):
        message = "Tell me about your Cambridge IGCSE and robotics curriculum for high school."
        result = handle_admissions_inquiry(message)

        assert result["intent"] == "curriculum_inquiry"
        assert "Curriculum & Academic Excellence" in result["response"]
        assert "send_curriculum_guide" in result["suggested_actions"]

    def test_transport_inquiry_handling(self):
        message = "Do your buses have real-time GPS tracking and female bus attendants?"
        result = handle_admissions_inquiry(message)

        assert result["intent"] == "transport_inquiry"
        assert "Safe Campus Transport" in result["response"]
        assert "send_transport_routes" in result["suggested_actions"]

    def test_admissions_criteria_inquiry(self):
        message = "What are the admission requirements and entrance exam criteria for new students?"
        result = handle_admissions_inquiry(message)

        assert result["intent"] == "admissions_criteria"
        assert "Admissions Criteria & Process" in result["response"]
        assert "send_application_checklist" in result["suggested_actions"]

    def test_full_sdr_flow_with_lead_context_merge(self):
        lead_ctx = {
            "student_name": "Maya",
            "grade": "Kindergarten",
            "parent_name": "David Miller",
            "phone": "+1-555-999-8888",
        }
        message = "We would love to schedule a visit to the school next Tuesday morning."
        result = handle_admissions_inquiry(message, lead_context=lead_ctx)

        assert result["tour_intent_detected"] is True
        assert "Maya" in result["response"]
        assert "David Miller" in result["response"]
        assert "schedule_campus_tour" in result["suggested_actions"]
        assert result["parent_contact"]["phone"] == "+1-555-999-8888"


# ===========================================================================
# 3. Tests for Automated Marketing Drip Generator (M27)
# ===========================================================================

class TestMarketingDripGenerator:
    def test_four_stage_sequence_structure(self):
        lead = {
            "id": "lead_555",
            "parent_name": "Rachel Zane",
            "student_name": "Sophia",
            "grade": "Grade 7",
            "curriculum": "International Baccalaureate (IB)",
        }
        campus = {
            "name": "CSG Horizon Academy",
            "city": "Singapore",
            "principal_name": "Dr. Helena Thorne",
            "admissions_phone": "+65 6789 0123",
        }

        drip = generate_nurture_sequence(lead, campus)

        assert len(drip) == 4
        
        # Verify days and sequencing
        assert [stage["stage"] for stage in drip] == [1, 2, 3, 4]
        assert [stage["day"] for stage in drip] == [1, 3, 7, 14]

        # Stage 1: Welcome
        assert drip[0]["day"] == 1
        assert "Rachel Zane" in drip[0]["content"]
        assert "Sophia" in drip[0]["content"]
        assert "CSG Horizon Academy" in drip[0]["content"]

        # Stage 2: Campus 360 Tour
        assert drip[1]["day"] == 3
        assert "Virtual Campus Tour" in drip[1]["subject"]
        assert "Book an In-Person Guided Campus Tour" in drip[1]["call_to_action"]

        # Stage 3: Scholarship
        assert drip[2]["day"] == 7
        assert "Scholarship Opportunity" in drip[2]["subject"]
        assert "Apply for Merit & Leadership Scholarship" in drip[2]["call_to_action"]

        # Stage 4: Personal Officer Consultation
        assert drip[3]["day"] == 14
        assert "Dr. Helena Thorne" in drip[3]["content"]
        assert "Confirm 1-on-1 Executive Consultation" in drip[3]["call_to_action"]

    def test_drip_graceful_defaults(self):
        drip = generate_nurture_sequence({}, {})
        assert len(drip) == 4
        assert drip[0]["stage"] == 1
        assert drip[3]["stage"] == 4


# ===========================================================================
# 4. Tests for Dynamic Scholarship & Offer Letter Generator (M24, M27)
# ===========================================================================

class TestOfferGenerator:
    def test_scholarship_offer_with_discount(self):
        letter = generate_personalized_offer_copy(
            student_name="Ethan Wright",
            grade="Grade 9",
            discount_pct=25.0,
            campus_name="CSG Cambridge Academy",
            parent_name="Dr. & Mrs. Wright",
            annual_tuition=20000.0,
            academic_year="2026-2027",
            validity_days=10,
        )

        assert "ETHAN WRIGHT" in letter.upper()
        assert "GRADE 9" in letter.upper()
        assert "CSG Cambridge Academy" in letter
        assert "25% Annual Tuition Scholarship" in letter
        assert "$20,000.00" in letter
        assert "-$5,000.00" in letter
        assert "$15,000.00" in letter
        assert "within **10 days**" in letter

    def test_standard_offer_zero_discount(self):
        letter = generate_personalized_offer_copy(
            student_name="Oliver Queen",
            grade="Kindergarten",
            discount_pct=0.0,
            campus_name="CSG Early Years Campus",
            annual_tuition=10000.0,
        )

        assert "Oliver Queen" in letter
        assert "Standard Annual Tuition" in letter
        assert "$10,000.00" in letter
        # Should not include scholarship award heading
        assert "Merit & Academic Scholarship Award" not in letter

    def test_edge_case_and_boundary_discounts(self):
        # 100% full scholarship
        full_scholarship = generate_personalized_offer_copy(
            student_name="Amina Khan",
            grade="Grade 11",
            discount_pct=100.0,
            campus_name="CSG Scholars Campus",
            annual_tuition=15000.0,
        )
        assert "100% Annual Tuition Scholarship" in full_scholarship
        assert "$0.00" in full_scholarship

        # Graceful fallback for empty names
        fallback_letter = generate_personalized_offer_copy("", "", 0.0, "")
        assert "Candidate" in fallback_letter
        assert "CSG International Academy" in fallback_letter
