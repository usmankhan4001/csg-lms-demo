"""
Pedagogic AI Socratic Engine & Cognitive Scaffolding (Phase 4 / M39)
===================================================================
Implements:
1. Bloom's Taxonomy cognitive progression (Remember -> Understand -> Apply -> Analyze -> Evaluate).
2. Strict refusal of direct answers to assignments/homework with cognitive redirection.
3. Progressive 3-Tier Hint Ladder (Tier 1: Clue, Tier 2: Process, Tier 3: Guided Sub-step).
4. Adaptive cognitive state tracking and pedagogical scaffolding.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BloomTaxonomyLevel(str, Enum):
    REMEMBER = "REMEMBER"       # Recall facts, definitions, formulas
    UNDERSTAND = "UNDERSTAND"   # Explain ideas, summarize concepts, interpret meaning
    APPLY = "APPLY"             # Use information in new situations, solve problems
    ANALYZE = "ANALYZE"         # Draw connections, break into components, compare
    EVALUATE = "EVALUATE"       # Justify stance, critique methods, verify solutions
    CREATE = "CREATE"           # Synthesize new patterns, formulate hypotheses


BLOOM_PROGRESSION_ORDER: List[BloomTaxonomyLevel] = [
    BloomTaxonomyLevel.REMEMBER,
    BloomTaxonomyLevel.UNDERSTAND,
    BloomTaxonomyLevel.APPLY,
    BloomTaxonomyLevel.ANALYZE,
    BloomTaxonomyLevel.EVALUATE,
    BloomTaxonomyLevel.CREATE,
]

BLOOM_DESCRIPTIONS: Dict[BloomTaxonomyLevel, str] = {
    BloomTaxonomyLevel.REMEMBER: "Recall foundational definitions, terms, and core principles.",
    BloomTaxonomyLevel.UNDERSTAND: "Explain the concept in your own words and interpret its meaning.",
    BloomTaxonomyLevel.APPLY: "Apply formulas, theorems, and algorithms to solve specific scenarios.",
    BloomTaxonomyLevel.ANALYZE: "Break down the structure, compare alternative methods, and identify patterns.",
    BloomTaxonomyLevel.EVALUATE: "Critique reasoning, justify chosen approaches, and verify error boundaries.",
    BloomTaxonomyLevel.CREATE: "Formulate novel hypotheses and construct generalized problem-solving frameworks.",
}


class HintTier(int, Enum):
    TIER_1_CLUE = 1         # Conceptual Clue: Probes high-level definitions, intuition, framing questions
    TIER_2_PROCESS = 2      # Process / Strategy: Identifies relevant theorems, mathematical formulas, structure
    TIER_3_GUIDED_STEP = 3  # Guided Sub-step: Atomic sub-step prompt or worked analogous problem with modified numbers


@dataclass
class CognitiveState:
    student_id: str
    concept_id: Optional[int] = None
    subject: Optional[str] = None
    current_bloom_level: BloomTaxonomyLevel = BloomTaxonomyLevel.REMEMBER
    consecutive_successes: int = 0
    consecutive_struggles: int = 0
    hint_requests_count: int = 0
    highest_hint_tier_used: int = 0
    comprehension_score: float = 0.5  # 0.0 to 1.0
    dialogue_turn_count: int = 0
    history_summary: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "student_id": self.student_id,
            "concept_id": self.concept_id,
            "subject": self.subject,
            "current_bloom_level": self.current_bloom_level.value,
            "consecutive_successes": self.consecutive_successes,
            "consecutive_struggles": self.consecutive_struggles,
            "hint_requests_count": self.hint_requests_count,
            "highest_hint_tier_used": self.highest_hint_tier_used,
            "comprehension_score": round(self.comprehension_score, 2),
            "dialogue_turn_count": self.dialogue_turn_count,
        }


# Direct answer solicitation patterns (homework dumping, cheating, requesting final answer)
HOMEWORK_SOLICITATION_PATTERNS = [
    r"\b(give me the (final |exact )?answer(s)?)\b",
    r"\b(what is the (exact |correct )?answer to (this|number|question|problem))\b",
    r"\b(do (my|this) (homework|assignment|worksheet|test|quiz|exam))\b",
    r"\b(solve this.*(for me|completely))\b",
    r"\b(solve (this|it) for me)\b",
    r"\b(write (my|the) (entire |complete )?(essay|code|program|solution))\b",
    r"\b(tell me (the|what) option ([a-d]|1-4) is correct)\b",
    r"\b(just give me the solution without explaining)\b",
    r"\b(cheat|answer key|leak)\b",
]


@dataclass
class RefusalCheckResult:
    is_direct_answer_request: bool
    detected_pattern: Optional[str] = None
    refusal_message: Optional[str] = None
    pedagogic_pivot_question: Optional[str] = None


class SocraticPedagogicEngine:
    """
    Pedagogical AI Engine orchestrating Socratic dialogue, Bloom's cognitive ladders,
    strict answer refusal, and progressive 3-tier hint scaffolding.
    """

    @classmethod
    def check_direct_answer_refusal(cls, query: str) -> RefusalCheckResult:
        """
        Detects if a student is asking for a direct answer or complete homework solution.
        Returns a strict refusal paired with a constructive Socratic pivot question.
        """
        clean_query = query.lower().strip()
        for pattern in HOMEWORK_SOLICITATION_PATTERNS:
            match = re.search(pattern, clean_query, re.IGNORECASE)
            if match:
                refusal_msg = (
                    "I cannot give you the final answer or do the problem for you, as my goal is to help "
                    "you master the underlying concepts so you can solve it with confidence."
                )
                pivot = (
                    "Let's break this down together. What is the very first step or definition related to "
                    "this problem, or what have you tried so far?"
                )
                return RefusalCheckResult(
                    is_direct_answer_request=True,
                    detected_pattern=pattern,
                    refusal_message=refusal_msg,
                    pedagogic_pivot_question=pivot,
                )

        return RefusalCheckResult(is_direct_answer_request=False)

    @classmethod
    def advance_cognitive_level(
        cls,
        state: CognitiveState,
        student_response_quality: float,  # 0.0 to 1.0 (e.g. accuracy or depth)
    ) -> Tuple[BloomTaxonomyLevel, str]:
        """
        Advances or scaffolds the student's Bloom's Taxonomy cognitive level based on performance.
        - 2 consecutive successes (quality >= 0.75) promote to next Bloom level.
        - 2 consecutive struggles (quality < 0.40) scaffold down to previous Bloom level.
        """
        state.dialogue_turn_count += 1
        current_idx = BLOOM_PROGRESSION_ORDER.index(state.current_bloom_level)

        if student_response_quality >= 0.75:
            state.consecutive_successes += 1
            state.consecutive_struggles = 0
            state.comprehension_score = min(1.0, state.comprehension_score + 0.15)

            if state.consecutive_successes >= 2 and current_idx < len(BLOOM_PROGRESSION_ORDER) - 1:
                next_level = BLOOM_PROGRESSION_ORDER[current_idx + 1]
                state.current_bloom_level = next_level
                state.consecutive_successes = 0
                transition_note = (
                    f"Mastery demonstrated at {BLOOM_PROGRESSION_ORDER[current_idx].value}. "
                    f"Promoted to {next_level.value} level."
                )
                return next_level, transition_note

            return state.current_bloom_level, "Reinforcing current cognitive level."

        elif student_response_quality < 0.40:
            state.consecutive_struggles += 1
            state.consecutive_successes = 0
            state.comprehension_score = max(0.0, state.comprehension_score - 0.12)

            if state.consecutive_struggles >= 2 and current_idx > 0:
                prev_level = BLOOM_PROGRESSION_ORDER[current_idx - 1]
                state.current_bloom_level = prev_level
                state.consecutive_struggles = 0
                transition_note = (
                    f"Scaffolding support: stepping back to {prev_level.value} to solidify foundational intuition."
                )
                return prev_level, transition_note

            return state.current_bloom_level, "Providing guided scaffolding at current cognitive level."

        else:
            state.consecutive_successes = 0
            state.consecutive_struggles = 0
            return state.current_bloom_level, "Steady progress at current cognitive level."

    @classmethod
    def generate_hint_guidance(
        cls,
        tier: HintTier,
        concept_title: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates structured progressive hint scaffolding directives for the LLM system prompt.
        """
        target = concept_title or "this concept"
        if tier == HintTier.TIER_1_CLUE:
            return {
                "tier": 1,
                "name": "Conceptual Clue",
                "directive": (
                    f"Provide a Level 1 Conceptual Clue for {target}. Probe foundational definitions, "
                    "physical intuition, or key terminology without revealing the algorithm, formula, or steps. "
                    "Ask an open question to see if the student remembers the core concept."
                ),
                "penalty_weight": 0.05,
            }
        elif tier == HintTier.TIER_2_PROCESS:
            return {
                "tier": 2,
                "name": "Process & Strategy",
                "directive": (
                    f"Provide a Level 2 Process / Strategy hint for {target}. Direct the student to the "
                    "applicable mathematical formula, theorem, or structural roadmap. Do not compute the answer "
                    "with their numbers — show the template and ask what variables match."
                ),
                "penalty_weight": 0.15,
            }
        else:  # TIER_3_GUIDED_STEP
            return {
                "tier": 3,
                "name": "Guided Sub-step / Worked Analogous Example",
                "directive": (
                    f"Provide a Level 3 Guided Sub-step or Worked Analogous Example for {target}. "
                    "Construct a parallel problem with DIFFERENT numerical values, solve it step-by-step to demonstrate "
                    "the pattern, and then ask the student to execute the very first step on their own original problem."
                ),
                "penalty_weight": 0.30,
            }

    @classmethod
    def build_socratic_prompt(
        cls,
        student_query: str,
        cognitive_state: Optional[CognitiveState] = None,
        hint_tier: Optional[HintTier] = None,
        context: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Constructs system prompt and enhanced user prompt with Bloom's Taxonomy cognitive framing,
        hint ladder constraints, and anti-direct-answer guardrails.
        """
        bloom_level = (
            cognitive_state.current_bloom_level if cognitive_state else BloomTaxonomyLevel.REMEMBER
        )
        bloom_desc = BLOOM_DESCRIPTIONS.get(bloom_level, "")

        system_parts = [
            "You are the CSG-LMS Socratic AI Academic Tutor, an expert pedagogical guide.",
            "STRICT RULES:",
            "1. NEVER GIVE DIRECT ANSWERS: Do not output the final solution, answer key, or complete essay/code.",
            "2. SOCRATIC DIALOGUE: Always guide the student using questions that prompt active reasoning.",
            f"3. COGNITIVE LEVEL: The student is currently at Bloom's Taxonomy level '{bloom_level.value}' ({bloom_desc}). "
            f"Tailor your questions to engage their cognitive faculties at this specific level.",
        ]

        if hint_tier is not None:
            hint_info = cls.generate_hint_guidance(hint_tier, subject=subject)
            system_parts.append(
                f"4. HINT SCAFFOLDING TIER {hint_info['tier']} ({hint_info['name']}):\n   {hint_info['directive']}"
            )
        else:
            system_parts.append(
                "4. STANDARD SOCRATIC RESPONSE: Engage with an exploratory probing question that encourages the student to reflect."
            )

        if context and context.strip():
            system_parts.append(f"\n--- RELEVANT TEXTBOOK & CURRICULUM CONTEXT ---\n{context.strip()}\n--- END CONTEXT ---")

        system_prompt = "\n\n".join(system_parts)
        user_prompt = student_query.strip()

        return system_prompt, user_prompt
