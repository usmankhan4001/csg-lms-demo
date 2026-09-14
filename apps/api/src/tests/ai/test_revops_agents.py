"""
Unit tests for the AI RevOps agents (M23 Research, M25 Marketing, M26 Copywriting).

The two behaviours worth guarding here are the ones with real-world
consequences: that the research brief reports gaps instead of inventing
detail about a family, and that a lead without explicit consent never lands
in an outbound campaign segment.
"""

import pytest

from src.services.ai.revops_copywriting_agent import (
    generate_outreach_copy,
    refine_copy_with_model,
)
from src.services.ai.revops_marketing_agent import (
    has_explicit_consent,
    plan_campaign,
    segment_leads,
)
from src.services.ai.revops_research_agent import (
    build_lead_research_brief,
    classify_grade_demand,
    summarise_engagement,
)


def _lead(**overrides):
    base = {
        "id": 1,
        "parent_name": "Sadia Rahman",
        "student_name": "Ayaan",
        "email": "sadia@example.com",
        "phone": "+92 300 1234567",
        "grade_applying_for": "Grade 9",
        "stage": "NEW_INQUIRY",
        "source": "WEBSITE_FORM",
        "lead_score": 60,
        "whatsapp_consent": False,
        "email_consent": False,
    }
    base.update(overrides)
    return base


# ===========================================================================
# M23 -- Research Agent
# ===========================================================================

class TestResearchAgent:
    def test_missing_fields_are_reported_not_invented(self):
        """The core anti-fabrication guarantee."""
        brief = build_lead_research_brief(_lead())

        # These were never supplied, so they must be declared unknown...
        assert "Current / previous school" in brief["unknown_fields"]
        assert "Budget expectation" in brief["unknown_fields"]
        assert "Curriculum preference" in brief["unknown_fields"]

        # ...and must NOT have been filled in with a plausible-looking value.
        assert "Current / previous school" not in brief["known_facts"]
        assert "Budget expectation" not in brief["known_facts"]

        # Nothing anywhere in the brief should assert a previous school.
        blob = str(brief).lower()
        assert "little explorers" not in blob

    def test_known_fields_are_carried_through_verbatim(self):
        brief = build_lead_research_brief(_lead())
        assert brief["known_facts"]["Student's name"] == "Ayaan"
        assert brief["known_facts"]["Grade applying for"] == "Grade 9"

    def test_each_gap_produces_a_question_to_close_it(self):
        brief = build_lead_research_brief(_lead())
        questions = " ".join(brief["questions_to_ask"]).lower()
        assert "school" in questions  # previous school gap
        assert "curriculum" in questions  # curriculum gap
        # A supplied field must not generate a question.
        assert "best number to reach" not in questions

    def test_supplied_field_generates_no_question(self):
        brief = build_lead_research_brief(
            _lead(previous_school="Beaconhouse", curriculum_preference="Cambridge")
        )
        questions = " ".join(brief["questions_to_ask"]).lower()
        assert "attending at the moment" not in questions
        assert "Current / previous school" not in brief["unknown_fields"]

    def test_grade_demand_bands(self):
        assert classify_grade_demand("Grade 9")["band"] == "high"
        assert classify_grade_demand("Grade 4")["band"] == "moderate"
        assert classify_grade_demand("")["band"] == "unknown"
        # An unrecognised grade is flagged, not silently treated as normal.
        assert classify_grade_demand("Grade 47")["band"] == "unlisted"

    def test_no_activity_is_reported_as_no_record_not_low_engagement(self):
        summary = summarise_engagement([])
        assert summary["recorded_touchpoints"] == 0
        assert "No contact recorded" in summary["summary"]

    def test_engagement_counts_only_logged_activity(self):
        summary = summarise_engagement(
            [{"activity_type": "CALL"}, {"activity_type": "EMAIL"}]
        )
        assert summary["recorded_touchpoints"] == 2
        assert summary["last_activity_type"] == "CALL"
        assert "off-system" in summary["summary"]

    def test_brief_states_no_external_lookup_was_done(self):
        brief = build_lead_research_brief(_lead())
        assert "No external lookup" in brief["disclaimer"]
        assert brief["sources"] == ["CRM lead record", "CRM activity log (empty)"]

    def test_handles_garbage_input_without_raising(self):
        brief = build_lead_research_brief(None)  # type: ignore[arg-type]
        assert brief["lead_id"] is None
        assert len(brief["unknown_fields"]) > 0


# ===========================================================================
# M25 -- Marketing Agent
# ===========================================================================

class TestMarketingAgentConsent:
    def test_non_consenting_lead_is_excluded_from_segment(self):
        """The required guarantee: no consent, no outbound."""
        leads = [
            _lead(id=1, whatsapp_consent=True),
            _lead(id=2, whatsapp_consent=False),
        ]
        segment = segment_leads(leads, channel="whatsapp")

        assert segment["eligible_count"] == 1
        assert [l["id"] for l in segment["eligible"]] == [1]
        assert segment["excluded_no_consent"] == 1
        assert segment["excluded_no_consent_ids"] == [2]

    def test_unknown_consent_is_not_treated_as_permission(self):
        """Outbound is opt-in: absent consent must not be read as a yes."""
        lead_without_field = {
            "id": 3,
            "stage": "NEW_INQUIRY",
            "grade_applying_for": "Grade 9",
            "lead_score": 50,
        }
        segment = segment_leads([lead_without_field], channel="whatsapp")
        assert segment["eligible_count"] == 0
        assert segment["excluded_no_consent"] == 1

    def test_consent_is_per_channel(self):
        lead = _lead(id=4, email_consent=True, whatsapp_consent=False)
        assert has_explicit_consent(lead, "email") is True
        assert has_explicit_consent(lead, "whatsapp") is False

        assert segment_leads([lead], channel="email")["eligible_count"] == 1
        assert segment_leads([lead], channel="whatsapp")["eligible_count"] == 0

    def test_channel_without_consent_field_is_never_eligible(self):
        # There is no phone_consent field, so phone can't be evidenced.
        assert has_explicit_consent(_lead(whatsapp_consent=True), "phone") is False

    def test_exclusions_are_counted_with_reasons_not_silently_dropped(self):
        leads = [
            _lead(id=1, whatsapp_consent=True),
            _lead(id=2, whatsapp_consent=False),
            _lead(id=3, whatsapp_consent=False),
        ]
        segment = segment_leads(leads, channel="whatsapp")
        assert segment["excluded_no_consent"] == 2
        assert "2 lead(s) matched the targeting" in segment["reasons"]["no_explicit_consent"]

    def test_enrolled_and_lost_are_never_targeted(self):
        leads = [
            _lead(id=1, stage="ENROLLED", whatsapp_consent=True),
            _lead(id=2, stage="LOST", whatsapp_consent=True),
            _lead(id=3, stage="CONTACTED", whatsapp_consent=True),
        ]
        segment = segment_leads(leads, channel="whatsapp")
        assert segment["eligible_count"] == 1
        assert segment["eligible"][0]["id"] == 3
        assert segment["excluded_by_stage"] == 2

    def test_score_and_grade_filters_apply(self):
        leads = [
            _lead(id=1, lead_score=90, whatsapp_consent=True),
            _lead(id=2, lead_score=20, whatsapp_consent=True),
        ]
        segment = segment_leads(leads, channel="whatsapp", min_score=50)
        assert segment["eligible_count"] == 1
        assert segment["excluded_by_filter"] == 1


class TestMarketingAgentPlanning:
    def test_plan_reports_empty_audience_rather_than_pretending(self):
        plan = plan_campaign([_lead(whatsapp_consent=False)], channel="whatsapp")
        assert plan["audience"]["eligible_count"] == 0
        assert plan["audience"]["excluded_no_consent"] == 1
        assert any("No lead in this pool" in w for w in plan["warnings"])

    def test_plan_never_sends_and_is_marked_proposed(self):
        plan = plan_campaign([_lead(whatsapp_consent=True)], channel="whatsapp")
        assert plan["status"] == "PROPOSED"
        assert "Nothing has been sent" in plan["note"]

    def test_angle_and_timing_follow_the_dominant_stage(self):
        leads = [_lead(id=i, stage="OFFER_SENT", email_consent=True) for i in range(3)]
        plan = plan_campaign(leads, channel="email")
        assert plan["dominant_stage"] == "OFFER_SENT"
        assert "deadline" in plan["angle"].lower()

    def test_mixed_stage_segment_is_flagged(self):
        leads = [
            _lead(id=1, stage="NEW_INQUIRY", email_consent=True),
            _lead(id=2, stage="OFFER_SENT", email_consent=True),
        ]
        plan = plan_campaign(leads, channel="email")
        assert any("several funnel stages" in w for w in plan["warnings"])

    def test_channel_mismatch_with_stage_playbook_is_warned(self):
        leads = [_lead(id=1, stage="NEW_INQUIRY", email_consent=True)]
        plan = plan_campaign(leads, channel="email")
        # NEW_INQUIRY's playbook prefers whatsapp.
        assert plan["recommended_channel"] == "whatsapp"
        assert any("respond better on whatsapp" in w for w in plan["warnings"])


# ===========================================================================
# M26 -- Copywriting Agent
# ===========================================================================

class TestCopywritingAgent:
    def test_copy_is_always_a_draft(self):
        copy = generate_outreach_copy(_lead())
        assert copy["status"] == "DRAFT"
        assert copy["refined"] is False
        assert "nothing has been sent" in copy["note"].lower()

    def test_email_has_subject_whatsapp_does_not(self):
        email = generate_outreach_copy(_lead(), channel="email")
        whatsapp = generate_outreach_copy(_lead(), channel="whatsapp")
        assert email["subject"]
        assert whatsapp["subject"] is None

    def test_tone_differs_by_stage(self):
        cold = generate_outreach_copy(_lead(stage="NEW_INQUIRY"))
        offer = generate_outreach_copy(_lead(stage="OFFER_SENT"))
        assert cold["tone"] != offer["tone"]
        assert cold["body"] != offer["body"]
        assert "delighted" in offer["body"].lower()

    def test_student_name_is_used_when_known(self):
        copy = generate_outreach_copy(_lead(student_name="Ayaan"))
        assert "Ayaan" in copy["body"]

    def test_missing_names_degrade_gracefully_without_placeholders(self):
        copy = generate_outreach_copy({"stage": "NEW_INQUIRY"})
        assert "your child" in copy["body"]
        # No template artefacts leaked.
        assert "{" not in copy["body"]
        assert "None" not in copy["body"]

    def test_whatsapp_copy_stays_short(self):
        copy = generate_outreach_copy(_lead(), channel="whatsapp")
        assert len(copy["body"]) <= 700

    def test_stage_override_writes_for_a_different_stage(self):
        copy = generate_outreach_copy(_lead(stage="NEW_INQUIRY"), stage_override="OFFER_SENT")
        assert copy["stage"] == "OFFER_SENT"

    @pytest.mark.asyncio
    async def test_refinement_falls_back_to_draft_when_model_unavailable(self, monkeypatch):
        """A dead provider must yield the usable draft, never an error or
        invented copy."""
        monkeypatch.setattr(
            "src.services.ai.revops_copywriting_agent.resolve_provider_chain",
            lambda _: (_ for _ in ()).throw(RuntimeError("no provider configured")),
        )
        draft = generate_outreach_copy(_lead())
        result = await refine_copy_with_model(draft, org_id=1)

        assert result["refined"] is False
        assert result["body"] == draft["body"]
        assert "unavailable" in result["refinement_note"]

    @pytest.mark.asyncio
    async def test_refinement_skipped_when_org_over_token_budget(self, monkeypatch):
        from src.services.ai.revops_model_router import TokenBudgetResult

        monkeypatch.setattr(
            "src.services.ai.revops_copywriting_agent.check_token_budget",
            lambda org_id, limit=0: TokenBudgetResult(
                is_allowed=False, current_spend=limit, limit=limit, remaining=0
            ),
        )
        draft = generate_outreach_copy(_lead())
        result = await refine_copy_with_model(draft, org_id=1)

        assert result["refined"] is False
        assert result["body"] == draft["body"]
        assert "budget" in result["refinement_note"].lower()
