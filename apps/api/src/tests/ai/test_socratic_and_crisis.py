"""
Unit Tests for Socratic AI Engine, SM-2 Spaced Repetition, Knowledge Graph DAG, and Crisis Escalation SLA
(Phase 4 / M39, M42, M44, M45, M47)
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.services.ai.socratic_engine import (
    BloomTaxonomyLevel,
    HintTier,
    CognitiveState,
    SocraticPedagogicEngine,
)
from src.services.ai.sm2_learning_engine import (
    SM2ReviewState,
    calculate_sm2_interval,
    estimate_retention_probability,
    DAGNode,
    KnowledgeGraphDAG,
)
from src.services.ai.crisis_escalation import (
    UniversalCrisisEscalationEngine,
    CRISIS_ESCALATION_SLA_SECONDS,
)
from src.db.ai_models import AISafetyCategory, AISafetySeverity


# ===========================================================================
# 1. Socratic Pedagogic Engine & Bloom's Taxonomy Progression Tests
# ===========================================================================

def test_direct_answer_refusal():
    """Verify that direct answer requests for homework/exams are strictly refused."""
    cheating_prompts = [
        "give me the answer to question 4",
        "solve this test question for me completely",
        "what is the exact answer to this problem",
        "do my homework for me",
        "write my entire essay on Hamlet",
        "just give me the solution without explaining",
    ]

    for p in cheating_prompts:
        result = SocraticPedagogicEngine.check_direct_answer_refusal(p)
        assert result.is_direct_answer_request is True, f"Failed to refuse: {p}"
        assert result.refusal_message is not None
        assert result.pedagogic_pivot_question is not None

    legit_query = "Can you help me understand how angular momentum is conserved?"
    legit_result = SocraticPedagogicEngine.check_direct_answer_refusal(legit_query)
    assert legit_result.is_direct_answer_request is False


def test_blooms_taxonomy_cognitive_progression():
    """Verify that student cognitive state promotes on repeated success and scaffolds on struggle."""
    state = CognitiveState(student_id="test_student_1")
    assert state.current_bloom_level == BloomTaxonomyLevel.REMEMBER

    # 1st success -> still REMEMBER
    level, note = SocraticPedagogicEngine.advance_cognitive_level(state, student_response_quality=0.85)
    assert level == BloomTaxonomyLevel.REMEMBER
    assert state.consecutive_successes == 1

    # 2nd success -> promotes to UNDERSTAND
    level, note = SocraticPedagogicEngine.advance_cognitive_level(state, student_response_quality=0.90)
    assert level == BloomTaxonomyLevel.UNDERSTAND
    assert state.consecutive_successes == 0

    # Promote to APPLY
    SocraticPedagogicEngine.advance_cognitive_level(state, student_response_quality=0.80)
    level, note = SocraticPedagogicEngine.advance_cognitive_level(state, student_response_quality=0.85)
    assert level == BloomTaxonomyLevel.APPLY

    # Struggle 1 -> still APPLY
    level, note = SocraticPedagogicEngine.advance_cognitive_level(state, student_response_quality=0.20)
    assert level == BloomTaxonomyLevel.APPLY
    assert state.consecutive_struggles == 1

    # Struggle 2 -> scaffolds back to UNDERSTAND
    level, note = SocraticPedagogicEngine.advance_cognitive_level(state, student_response_quality=0.30)
    assert level == BloomTaxonomyLevel.UNDERSTAND
    assert state.consecutive_struggles == 0


def test_hint_ladder_generation_and_prompt_building():
    """Verify 3-tier progressive hint directives and prompt assembling."""
    hint1 = SocraticPedagogicEngine.generate_hint_guidance(HintTier.TIER_1_CLUE, concept_title="Newton's Laws")
    assert hint1["tier"] == 1
    assert "Conceptual Clue" in hint1["name"]

    hint2 = SocraticPedagogicEngine.generate_hint_guidance(HintTier.TIER_2_PROCESS, concept_title="Newton's Laws")
    assert hint2["tier"] == 2
    assert "Process" in hint2["name"]

    hint3 = SocraticPedagogicEngine.generate_hint_guidance(HintTier.TIER_3_GUIDED_STEP, concept_title="Newton's Laws")
    assert hint3["tier"] == 3
    assert "Analogous" in hint3["name"]

    state = CognitiveState(student_id="test_student", current_bloom_level=BloomTaxonomyLevel.APPLY)
    sys_prompt, user_prompt = SocraticPedagogicEngine.build_socratic_prompt(
        student_query="How do I find tension in the string?",
        cognitive_state=state,
        hint_tier=HintTier.TIER_2_PROCESS,
        context="Textbook chapter 4: Tension and pulley systems.",
    )
    assert "Bloom's Taxonomy level 'APPLY'" in sys_prompt
    assert "HINT SCAFFOLDING TIER 2" in sys_prompt
    assert "NEVER GIVE DIRECT ANSWERS" in sys_prompt
    assert "Textbook chapter 4" in sys_prompt
    assert user_prompt == "How do I find tension in the string?"


# ===========================================================================
# 2. SuperMemo SM-2 & Knowledge Graph DAG Tests
# ===========================================================================

def test_sm2_spaced_repetition_calculation():
    """Verify SM-2 ease factor updates, interval progression, and reset on failure."""
    now = datetime.now(timezone.utc)
    initial_state = SM2ReviewState(concept_id=1, student_id="student_1", ease_factor=2.5)

    # 1st successful review (q=5) -> interval 1 day
    s1 = calculate_sm2_interval(initial_state, quality=5, review_time=now)
    assert s1.repetitions == 1
    assert s1.interval_days == 1
    assert s1.ease_factor == 2.6  # 2.5 + (0.1 - 0) = 2.6

    # 2nd successful review (q=4) -> interval 6 days
    s2 = calculate_sm2_interval(s1, quality=4, review_time=now)
    assert s2.repetitions == 2
    assert s2.interval_days == 6
    assert round(s2.ease_factor, 2) == 2.6  # 2.6 + (0.1 - 1 * 0.10) = 2.6

    # 3rd successful review (q=4) -> interval round(6 * 2.6) = 16 days
    s3 = calculate_sm2_interval(s2, quality=4, review_time=now)
    assert s3.repetitions == 3
    assert s3.interval_days == 16

    # Failed review (q=1) -> repetitions reset to 0, interval 1 day
    s_failed = calculate_sm2_interval(s3, quality=1, review_time=now)
    assert s_failed.repetitions == 0
    assert s_failed.interval_days == 1
    assert s_failed.consecutive_correct == 0

    # Ease factor cannot drop below 1.3
    low_ef_state = SM2ReviewState(concept_id=1, student_id="student_1", ease_factor=1.35)
    s_low = calculate_sm2_interval(low_ef_state, quality=0, review_time=now)
    assert s_low.ease_factor >= 1.3


def test_ebbinghaus_retention_curve():
    """Verify memory retention probability decays smoothly over time."""
    now = datetime.now(timezone.utc)
    state = SM2ReviewState(
        concept_id=1,
        student_id="student_1",
        interval_days=10,
        ease_factor=2.5,
        last_reviewed_at=now,
    )

    r_0 = estimate_retention_probability(state, as_of=now)
    assert r_0 == 1.0

    r_5 = estimate_retention_probability(state, as_of=now + timedelta(days=5))
    assert 0.0 < r_5 < 1.0
    assert r_5 < r_0

    r_20 = estimate_retention_probability(state, as_of=now + timedelta(days=20))
    assert r_20 < r_5


def test_knowledge_graph_dag_and_cycle_detection():
    """Verify DAG validation, cycle detection, and topological sorting."""
    dag = KnowledgeGraphDAG()
    dag.add_node(DAGNode(id=1, title="Algebraic Expressions", subject="Math", topic_code="ALG-01", difficulty_level=1))
    dag.add_node(DAGNode(id=2, title="Linear Equations", subject="Math", topic_code="ALG-02", difficulty_level=2))
    dag.add_node(DAGNode(id=3, title="Quadratic Equations", subject="Math", topic_code="ALG-03", difficulty_level=3))

    dag.add_edge(concept_id=2, prerequisite_id=1)
    dag.add_edge(concept_id=3, prerequisite_id=2)

    is_acyclic, cycle = dag.validate_acyclic()
    assert is_acyclic is True
    assert cycle is None

    sorted_nodes = dag.topological_sort()
    assert [n.id for n in sorted_nodes] == [1, 2, 3]

    # Add cycle: 1 depends on 3
    dag.add_edge(concept_id=1, prerequisite_id=3)
    is_acyclic_cycle, cycle_path = dag.validate_acyclic()
    assert is_acyclic_cycle is False
    assert cycle_path is not None


def test_dag_prerequisites_and_remedial_pathfinder():
    """Verify root-cause remedial pathfinding for a struggling student."""
    dag = KnowledgeGraphDAG()
    dag.add_node(DAGNode(id=1, title="Basic Trigonometry", subject="Math", topic_code="TRIG-01", difficulty_level=1))
    dag.add_node(DAGNode(id=2, title="Trigonometric Identities", subject="Math", topic_code="TRIG-02", difficulty_level=2))
    dag.add_node(DAGNode(id=3, title="Derivatives of Trig Functions", subject="Math", topic_code="CALC-01", difficulty_level=3))

    dag.add_edge(concept_id=2, prerequisite_id=1)
    dag.add_edge(concept_id=3, prerequisite_id=2)

    # Student has not mastered Basic Trigonometry (0.45) or Trig Identities (0.50)
    mastery_map = {1: 0.45, 2: 0.50, 3: 0.20}

    all_met, details = dag.check_prerequisites_met(target_concept_id=3, student_mastery_map=mastery_map, passing_threshold=0.70)
    assert all_met is False
    assert len(details) == 1
    assert details[0]["satisfied"] is False

    remedial_path = dag.find_remedial_path(struggling_concept_id=3, student_mastery_map=mastery_map, passing_threshold=0.70)
    assert len(remedial_path) == 3
    # Step 1 should be the root cause: Basic Trigonometry
    assert remedial_path[0]["concept_id"] == 1
    assert remedial_path[0]["is_knowledge_gap"] is True
    assert remedial_path[1]["concept_id"] == 2
    assert remedial_path[2]["concept_id"] == 3


def test_cohort_gap_heatmap_generator():
    """Verify cohort gap heatmap aggregation across students."""
    dag = KnowledgeGraphDAG()
    dag.add_node(DAGNode(id=1, title="Vectors", subject="Physics", topic_code="PHY-VEC", difficulty_level=1))
    dag.add_node(DAGNode(id=2, title="2D Projectiles", subject="Physics", topic_code="PHY-PROJ", difficulty_level=2))

    cohort = {
        "student_A": {1: 0.85, 2: 0.40},
        "student_B": {1: 0.90, 2: 0.50},
        "student_C": {1: 0.75, 2: 0.35},
        "student_D": {1: 0.80, 2: 0.90},
    }

    heatmap = dag.generate_cohort_gap_heatmap(cohort)
    assert heatmap["total_concepts"] == 2
    assert heatmap["total_students"] == 4

    # Concept 2 has 3 out of 4 students struggling (75% struggle rate -> critical bottleneck)
    c2_stat = heatmap["concept_matrix"][2]
    assert c2_stat["struggling_students"] == 3
    assert c2_stat["is_critical_bottleneck"] is True


# ===========================================================================
# 3. Contract 3: Universal 2-Minute Crisis Escalation SLA Tests
# ===========================================================================

def test_synchronous_crisis_detection():
    """Verify local zero-latency crisis detection against critical patterns."""
    crisis_prompts = [
        ("I want to kill myself", AISafetyCategory.SELF_HARM, AISafetySeverity.CRITICAL),
        ("thinking about ending my life today", AISafetyCategory.SELF_HARM, AISafetySeverity.CRITICAL),
        ("bringing a gun to school tomorrow", AISafetyCategory.VIOLENCE, AISafetySeverity.CRITICAL),
        ("can't take this anymore, unbearable pain and having a breakdown", AISafetyCategory.SEVERE_DISTRESS, AISafetySeverity.HIGH),
        ("go kill yourself, nobody likes you", AISafetyCategory.BULLYING, AISafetySeverity.HIGH),
    ]

    for text, expected_cat, expected_sev in crisis_prompts:
        is_crisis, cat, sev, pat = UniversalCrisisEscalationEngine.scan_for_crisis_synchronous(text)
        assert is_crisis is True, f"Failed to detect: {text}"
        assert cat == expected_cat
        assert sev == expected_sev
        assert pat is not None

    clean_text = "Can you explain how gravity causes acceleration?"
    is_crisis, cat, sev, pat = UniversalCrisisEscalationEngine.scan_for_crisis_synchronous(clean_text)
    assert is_crisis is False


def test_emergency_card_generation():
    """Verify structured emergency card construction with international directory and guidance."""
    card = UniversalCrisisEscalationEngine.generate_emergency_card(
        category=AISafetyCategory.SELF_HARM,
        severity=AISafetySeverity.CRITICAL,
    )
    assert card.category == AISafetyCategory.SELF_HARM.value
    assert card.severity == AISafetySeverity.CRITICAL.value
    assert card.counselor_escalated is True
    assert len(card.hotlines) >= 1
    assert any("findahelpline.com" in h["contact"] for h in card.hotlines)


@pytest.mark.asyncio
async def test_crisis_escalation_sla_compliance():
    """Verify SLA report measurement and compliance guarantee (<= 120s)."""
    report = await UniversalCrisisEscalationEngine.evaluate_and_escalate(
        prompt="I want to commit suicide",
        student_id="student-sla-test",
        org_id=None,
        db_session=None,
    )
    assert report.is_crisis is True
    assert report.category == AISafetyCategory.SELF_HARM
    assert report.severity == AISafetySeverity.CRITICAL
    assert report.within_sla is True
    assert report.dispatch_latency_ms < (CRISIS_ESCALATION_SLA_SECONDS * 1000.0)
    assert report.quiet_hours_overridden is True
    assert report.emergency_card is not None
