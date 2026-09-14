"""
RevOps Admin Config (M30) and Knowledge Base (M34).

The load-bearing guarantee is the same one school settings carries: a school
with NO config rows behaves exactly as it did before this module existed. Lead
scoring weights and nurture cadence were hardcoded constants, and if resolution
ever returned a zero for an unconfigured school, every lead would silently
score 0 and be disqualified. `test_missing_row_yields_the_real_constants_not_zero`
and `test_default_weights_reproduce_the_engine_exactly` pin that.

The scoping tests cover the case that is easy to get wrong: campus_id=None is
not "no campus claimed", it is the ORG-WIDE row every campus inherits, so a
campus-bound admin writing it would change scoring policy for every other
campus.
"""

import pytest
from fastapi import HTTPException

from src.db.sms_revops_config import KnowledgeEntryStatus
from src.routers.sms_revops_config import (
    _assert_may_write_scope,
    create_knowledge_entry,
    KnowledgeEntryWrite,
    update_revops_config_group,
)
from src.schemas.sms_revops_config import (
    BASELINE_FACTOR_MAX,
    ConsentPolicySettings,
    LeadScoringSettings,
    RevOpsConfigGroup,
    RevOpsConfigSource,
    RevOpsConfigUpdate,
)
from src.services.sms import revops_kb
from src.services.sms.revops_config import (
    InvalidRevOpsConfigPayload,
    apply_scoring_weights,
    consent_blocks_channel,
    get_lead_scoring,
    get_nurture,
    resolve_group,
    write_group,
)
from src.tests.sms._principals import principal

# The engine constants these defaults must keep mirroring.
from src.services.ai.revops_lead_scoring import (
    HIGH_DEMAND_GRADES,
    MODERATE_DEMAND_GRADES,
    calculate_lead_score,
)


# ---------------------------------------------------------------------------
# Fallback: campus -> org -> code default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_row_yields_the_real_constants_not_zero(db):
    """No row must mean "use the built-in policy", never 0.

    A scoring weight of 0.0 and "no scoring policy configured" are different
    things: the first silently scores every lead at zero and disqualifies the
    school's entire intake.
    """
    values, source, updated = await resolve_group(
        db, org_id=1, campus_id=None, group=RevOpsConfigGroup.LEAD_SCORING
    )
    assert source is RevOpsConfigSource.DEFAULT
    assert updated is None
    assert values.weight_completeness == BASELINE_FACTOR_MAX["completeness"]
    assert values.weight_completeness != 0.0
    assert values.hot_threshold == 75.0
    assert values.warm_threshold == 45.0


@pytest.mark.asyncio
async def test_defaults_still_match_the_engine_constants(db):
    """Turning this feature on must change nothing for an existing school."""
    scoring = await get_lead_scoring(db, org_id=1)

    # Factor caps mirror the engine's documented maxima.
    assert scoring.weight_completeness == BASELINE_FACTOR_MAX["completeness"]
    assert scoring.weight_responsiveness == BASELINE_FACTOR_MAX["responsiveness"]
    assert scoring.weight_grade_demand == BASELINE_FACTOR_MAX["grade_demand"]
    assert scoring.weight_budget_fit == BASELINE_FACTOR_MAX["budget_fit"]
    assert scoring.weight_timeline == BASELINE_FACTOR_MAX["timeline"]

    # And the demand-grade sets are the engine's, not a paraphrase of them.
    assert set(scoring.high_demand_grades) == HIGH_DEMAND_GRADES
    assert set(scoring.moderate_demand_grades) == MODERATE_DEMAND_GRADES

    nurture = await get_nurture(db, org_id=1)
    assert [s.day for s in nurture.stages] == [1, 3, 7, 14]
    assert [s.channel for s in nurture.stages] == [
        "email_whatsapp",
        "whatsapp_email",
        "email_sms",
        "phone_whatsapp",
    ]
    assert all(s.enabled for s in nurture.stages)


@pytest.mark.asyncio
async def test_default_weights_reproduce_the_engine_exactly(db):
    """Re-weighting with the defaults must be a no-op on a real lead.

    This is the drift guard: if someone edits a DEFAULT weight without
    intending a product change, a real lead's score and intent band move and
    this fails.
    """
    lead = {
        "student_name": "A",
        "parent_name": "B",
        "email": "b@example.com",
        "phone": "1234567",
        "grade": "grade 9",
        "budget_fit": "high",
        "start_timeline": "immediate",
        "interactions_count": 5,
    }
    raw = calculate_lead_score(lead)
    scoring = await get_lead_scoring(db, org_id=1)
    reweighted = apply_scoring_weights(raw["breakdown"], scoring)

    assert reweighted["intent"] == raw["intent"]
    assert abs(reweighted["score"] - raw["score"]) < 0.15
    assert reweighted["total_possible"] == 100.0


@pytest.mark.asyncio
async def test_campus_row_overrides_org_row(db):
    """campus -> org -> default, in that order."""
    await write_group(
        db, org_id=1, campus_id=None,
        group=RevOpsConfigGroup.LEAD_SCORING,
        values={"hot_threshold": 60.0},
    )
    org_values, org_source, _ = await resolve_group(
        db, org_id=1, campus_id=None, group=RevOpsConfigGroup.LEAD_SCORING
    )
    assert org_source is RevOpsConfigSource.ORG
    assert org_values.hot_threshold == 60.0

    # A campus with no row of its own inherits the org row.
    inherited, source, _ = await resolve_group(
        db, org_id=1, campus_id=7, group=RevOpsConfigGroup.LEAD_SCORING
    )
    assert source is RevOpsConfigSource.ORG
    assert inherited.hot_threshold == 60.0

    # Its own row wins once written.
    await write_group(
        db, org_id=1, campus_id=7,
        group=RevOpsConfigGroup.LEAD_SCORING,
        values={"hot_threshold": 90.0},
    )
    campus_values, campus_source, _ = await resolve_group(
        db, org_id=1, campus_id=7, group=RevOpsConfigGroup.LEAD_SCORING
    )
    assert campus_source is RevOpsConfigSource.CAMPUS
    assert campus_values.hot_threshold == 90.0

    # And the org row is untouched.
    still_org, _, _ = await resolve_group(
        db, org_id=1, campus_id=None, group=RevOpsConfigGroup.LEAD_SCORING
    )
    assert still_org.hot_threshold == 60.0


@pytest.mark.asyncio
async def test_invalid_values_are_refused_not_silently_dropped(db):
    """An admin who mistypes a weight must be told, not ignored."""
    with pytest.raises(InvalidRevOpsConfigPayload):
        await write_group(
            db, org_id=1, campus_id=None,
            group=RevOpsConfigGroup.LEAD_SCORING,
            values={"hot_threshold": 500.0},  # ge=0 le=100
        )


# ---------------------------------------------------------------------------
# Write scoping -- the org-wide row is the privileged one
# ---------------------------------------------------------------------------


def test_campus_bound_admin_cannot_write_the_org_level_row():
    """campus_id=None is every campus, not "no campus claimed"."""
    with pytest.raises(HTTPException) as exc:
        _assert_may_write_scope(principal("SCHOOL_ADMIN", campus_id=2), None)
    assert exc.value.status_code == 403


def test_campus_bound_admin_cannot_write_another_campus():
    with pytest.raises(HTTPException):
        _assert_may_write_scope(principal("SCHOOL_ADMIN", campus_id=2), 9)


def test_campus_bound_admin_may_write_their_own_campus():
    _assert_may_write_scope(principal("SCHOOL_ADMIN", campus_id=2), 2)


def test_org_level_admin_may_write_the_org_row():
    """An admin with no campus of their own is an org-level administrator."""
    _assert_may_write_scope(principal("SCHOOL_ADMIN", campus_id=None), None)


def test_superadmin_may_write_any_scope():
    _assert_may_write_scope(principal("SUPER_ADMIN", campus_id=None), 9)


@pytest.mark.asyncio
async def test_endpoint_refuses_a_campus_bound_admin_writing_org_defaults(db):
    """End-to-end through the handler, not just the helper."""
    with pytest.raises(HTTPException) as exc:
        await update_revops_config_group(
            group=RevOpsConfigGroup.LEAD_SCORING,
            payload=RevOpsConfigUpdate(values={"hot_threshold": 10.0}),
            campus_id=None,
            session=db,
            principal=principal("SCHOOL_ADMIN", campus_id=2),
        )
    assert exc.value.status_code == 403


def test_the_scope_assertion_discriminates():
    """Guard against the scoping tests passing vacuously.

    If `_assert_may_write_scope` ever became a no-op, the refusal tests above
    would silently pass. This asserts the permissive case really is permitted,
    so the helper must be making a decision rather than always raising.
    """
    _assert_may_write_scope(principal("SCHOOL_ADMIN", campus_id=2), 2)
    with pytest.raises(HTTPException):
        _assert_may_write_scope(principal("SCHOOL_ADMIN", campus_id=2), None)


# ---------------------------------------------------------------------------
# Consent policy
# ---------------------------------------------------------------------------


def test_default_consent_policy_reproduces_explicit_opt_out_only():
    """Default must match `_stage_consent_blocked`: only an explicit False blocks."""
    policy = ConsentPolicySettings()
    assert policy.require_explicit_opt_in is False

    assert consent_blocks_channel({"email_consent": False}, "email", policy) is True
    # Unknown consent does NOT block under the default policy.
    assert consent_blocks_channel({}, "email", policy) is False
    assert consent_blocks_channel({"email_consent": True}, "email", policy) is False
    # Untracked channels never gate a stage on their own.
    assert consent_blocks_channel({}, "phone", policy) is False


def test_opt_in_policy_only_narrows_who_can_be_contacted():
    """Stricter mode blocks unknown consent; it can never permit more."""
    strict = ConsentPolicySettings(require_explicit_opt_in=True)
    assert consent_blocks_channel({}, "email", strict) is True
    assert consent_blocks_channel({"email_consent": False}, "email", strict) is True
    # An explicit yes is still a yes.
    assert consent_blocks_channel({"email_consent": True}, "email", strict) is False


# ---------------------------------------------------------------------------
# Human review gate
# ---------------------------------------------------------------------------


def test_human_review_gate_is_off_by_default():
    """Enabling this module must not start holding leads back on its own."""
    scoring = LeadScoringSettings()
    assert scoring.human_review_below_score == 0.0
    out = apply_scoring_weights(
        {"completeness_score": 0.0, "responsiveness_score": 0.0,
         "grade_demand_score": 0.0, "budget_fit_score": 0.0, "timeline_score": 0.0},
        scoring,
    )
    assert out["awaiting_human_review"] is False


def test_human_review_gate_holds_low_confidence_leads_when_enabled():
    scoring = LeadScoringSettings(human_review_below_score=50.0)
    low = apply_scoring_weights(
        {"completeness_score": 5.0, "responsiveness_score": 0.0,
         "grade_demand_score": 0.0, "budget_fit_score": 0.0, "timeline_score": 0.0},
        scoring,
    )
    assert low["awaiting_human_review"] is True

    high = apply_scoring_weights(
        {"completeness_score": 25.0, "responsiveness_score": 20.0,
         "grade_demand_score": 15.0, "budget_fit_score": 20.0, "timeline_score": 20.0},
        scoring,
    )
    assert high["awaiting_human_review"] is False


def test_reweighting_reports_total_possible_when_weights_do_not_sum_to_100():
    """A score must never be presented as "out of 100" when it is not."""
    scoring = LeadScoringSettings(weight_budget_fit=5.0)
    out = apply_scoring_weights(
        {"completeness_score": 25.0, "responsiveness_score": 20.0,
         "grade_demand_score": 15.0, "budget_fit_score": 20.0, "timeline_score": 20.0},
        scoring,
    )
    assert out["total_possible"] == 85.0
    assert out["score"] == 85.0


# ---------------------------------------------------------------------------
# M34 -- Knowledge base
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entry_without_a_source_is_stored_sourceless_not_given_one(db):
    """A synthesised citation would be worse than none."""
    entry = await revops_kb.create_entry(
        db, org_id=1, title="Fee instalments", body="Payable in three terms."
    )
    assert entry.source_label is None
    assert entry.source_url is None
    assert revops_kb.is_sourceless(entry) is True


@pytest.mark.asyncio
async def test_entry_with_a_source_is_not_sourceless(db):
    entry = await revops_kb.create_entry(
        db, org_id=1, title="Uniform policy", body="Blazers required.",
        source_label="Parent Handbook 2026, p.12",
    )
    assert revops_kb.is_sourceless(entry) is False


@pytest.mark.asyncio
async def test_create_endpoint_does_not_invent_a_source(db):
    """Through the handler, since that is where a default could creep in."""
    read = await create_knowledge_entry(
        payload=KnowledgeEntryWrite(title="Bus routes", body="Two routes."),
        session=db,
        principal=principal("SCHOOL_ADMIN", campus_id=None),
    )
    assert read.source_label is None
    assert read.source_url is None
    assert read.is_sourceless is True


@pytest.mark.asyncio
async def test_search_excludes_drafts_by_default(db):
    """A draft is a human's working note and must not be quoted at a parent."""
    await revops_kb.create_entry(
        db, org_id=1, title="Draft scholarship note", body="Merit award details",
        status=KnowledgeEntryStatus.DRAFT.value,
    )
    await revops_kb.create_entry(
        db, org_id=1, title="Published scholarship note", body="Merit award details",
        status=KnowledgeEntryStatus.PUBLISHED.value,
    )

    published = await revops_kb.search_entries(db, org_id=1, query="merit award")
    titles = [e.title for e in published]
    assert "Published scholarship note" in titles
    assert "Draft scholarship note" not in titles

    everything = await revops_kb.search_entries(
        db, org_id=1, query="merit award", published_only=False
    )
    assert len([e for e in everything if "scholarship note" in e.title]) == 2


@pytest.mark.asyncio
async def test_search_is_scoped_to_the_callers_org(db):
    """An entry from another organisation must never surface."""
    await revops_kb.create_entry(
        db, org_id=99, title="Other school policy", body="Confidential",
        status=KnowledgeEntryStatus.PUBLISHED.value,
    )
    results = await revops_kb.search_entries(db, org_id=1, query="confidential")
    assert results == []


@pytest.mark.asyncio
async def test_get_entry_from_another_org_reads_as_not_found(db):
    other = await revops_kb.create_entry(
        db, org_id=99, title="Theirs", body="Not yours."
    )
    assert await revops_kb.get_entry(db, org_id=1, entry_id=other.id or 0) is None
