"""
Content Relevance & Age/Grade-Appropriate Guardrails
======================================================
Client requirement: the Socratic Tutor should be "paired with a dedicated
agent scoped to the student's enrolled subjects" and should adjust its
vocabulary/explanation depth to the student's grade/class level.

Kept as a sibling to crisis_classifier.py rather than folded into it:
crisis_classifier.py is specifically about safety/crisis/self-harm
interception (a distinct, higher-priority concern with its own escalation
path to counselors). This module is about pedagogical scope and
grade-appropriateness — a different concern with its own tuning knobs —
so splitting it keeps each module focused and avoids overloading the
crisis-specific one. socratic_tutor.py calls this module the same way it
already calls crisis_classifier: a plain function call against the raw
student prompt (plus, here, the student's known enrollment context),
returning a structured result the caller can act on.
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Subject-scope relevance
# ---------------------------------------------------------------------------

# Keyword fingerprints for common academic subjects. Used to (a) infer the
# subject of a free-text course name (see socratic_tutor.get_student_enrollment_scope),
# and (b) recognize when a student's question falls within a DIFFERENT
# catalogued subject than any of their enrolled ones.
SUBJECT_KEYWORDS = {
    "mathematics": [
        "math", "algebra", "geometry", "calculus", "equation", "trigonometry",
        "arithmetic", "fraction", "polynomial", "derivative", "integral",
    ],
    "science": [
        "science", "physics", "chemistry", "biology", "photosynthesis", "atom",
        "molecule", "cell", "force", "energy", "reaction", "ecosystem",
    ],
    "english": [
        "english", "literature", "essay", "grammar", "poem", "poetry", "novel",
        "vocabulary", "writing", "reading comprehension",
    ],
    "history": [
        "history", "civilization", "revolution", "empire", "historical",
        "ancient", "monarchy", "treaty",
    ],
    "computer_science": [
        "computer science", "programming", "coding", "algorithm", "python",
        "javascript", "software", "variable", "function", "loop",
    ],
    "geography": [
        "geography", "continent", "climate", "map", "country", "capital",
        "terrain", "population",
    ],
    "art": ["art", "painting", "drawing", "sculpture", "color theory", "composition"],
    "music": ["music", "rhythm", "melody", "chord", "scale", "instrument"],
}

# Categories that are unambiguously off-topic for an academic tutoring
# session, regardless of the student's enrolled subject(s). Kept narrow
# (mirroring crisis_classifier's own pattern lists) to minimize false
# positives against legitimate academic phrasing.
OFF_TOPIC_PATTERNS = [
    r"\b(who (will|is going to) win the (game|match|super bowl|world cup))\b",
    r"\b(celebrity gossip|latest (movie|album) release|dating advice|horoscope|astrology reading)\b",
    r"\b(current stock price|crypto(currency)? price|lottery numbers)\b",
    r"\b(write me a (rap|song) about|tell me a joke about)\b",
]


@dataclass
class RelevanceCheckResult:
    is_relevant: bool
    matched_subject: Optional[str] = None
    reason: str = ""
    redirect_message: Optional[str] = None


def infer_subject_from_text(text: str) -> Optional[str]:
    """Best-effort keyword match of a catalogued subject name from free text
    (e.g. a course name like "AP Biology" -> "science")."""
    if not text:
        return None
    lowered = text.lower()
    for subject, keywords in SUBJECT_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return subject
    return None


def check_content_relevance(
    query: str,
    enrolled_subjects: Optional[List[str]] = None,
) -> RelevanceCheckResult:
    """
    Checks whether a student's query stays within the subject matter of
    their enrolled coursework. Two-stage heuristic:

      1. Reject prompts matching a clearly off-topic category outright,
         regardless of enrollment data.
      2. If the student's enrolled subjects are known AND the prompt
         keyword-matches a DIFFERENT catalogued subject than any of them,
         flag it out-of-scope and redirect toward the enrolled subject(s).

    Ambiguous or general queries (no confident subject match) are treated
    as relevant — this guardrail only intercepts confidently off-topic
    prompts, to avoid frustrating students with false positives on
    legitimate but keyword-sparse questions (e.g. "what's 5 + 3?").
    """
    prompt_clean = (query or "").lower().strip()

    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, prompt_clean, re.IGNORECASE):
            subjects_str = (
                ", ".join(s.replace("_", " ").title() for s in (enrolled_subjects or []))
                or "your enrolled coursework"
            )
            return RelevanceCheckResult(
                is_relevant=False,
                reason="Query matches an off-topic category unrelated to academic tutoring",
                redirect_message=(
                    f"I'm your Socratic tutor for {subjects_str}, so I can't help with that. "
                    "Let's get back to your coursework — what concept are you working on?"
                ),
            )

    if enrolled_subjects:
        normalized_enrolled = {s.lower() for s in enrolled_subjects}
        matched = infer_subject_from_text(prompt_clean)
        if matched and matched not in normalized_enrolled:
            subjects_str = ", ".join(s.replace("_", " ").title() for s in enrolled_subjects)
            return RelevanceCheckResult(
                is_relevant=False,
                matched_subject=matched,
                reason=f"Query matches subject '{matched}', outside the student's enrolled subjects",
                redirect_message=(
                    f"That looks like a {matched.replace('_', ' ')} question, but with me you're "
                    f"currently studying {subjects_str}. I can only tutor within your enrolled "
                    "coursework — let's focus back on that. What would you like to work on?"
                ),
            )

    return RelevanceCheckResult(is_relevant=True, reason="Query is within scope or ambiguous enough to allow")


# ---------------------------------------------------------------------------
# 2. Grade / age-appropriate vocabulary depth
# ---------------------------------------------------------------------------

@dataclass
class GradeProfile:
    band: str  # "elementary" | "middle" | "high" | "unknown"
    reading_level: str
    guidance: str


_GRADE_NUMBER_PATTERN = re.compile(r"(\d+)")


def _extract_grade_number(grade_level: Optional[str]) -> Optional[int]:
    """Pulls a numeric grade out of strings like 'Grade 9', '10th Grade', 'KG-1'."""
    if not grade_level:
        return None
    lowered = grade_level.lower()
    if "kg" in lowered or "kindergarten" in lowered:
        return 0
    match = _GRADE_NUMBER_PATTERN.search(lowered)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def get_grade_profile(grade_level: Optional[str]) -> GradeProfile:
    """
    Maps a raw grade-level string (as stored on
    src.db.sms_campus.ClassSection.grade_level, e.g. 'Grade 9', 'KG-1') to a
    vocabulary/explanation-depth profile the Socratic Tutor's system prompt
    can enforce.
    """
    grade_num = _extract_grade_number(grade_level)

    if grade_num is None:
        return GradeProfile(
            band="unknown",
            reading_level="general student",
            guidance="Use clear, accessible language suitable for a general student audience.",
        )

    if grade_num <= 5:
        return GradeProfile(
            band="elementary",
            reading_level=f"elementary (grade {grade_num})",
            guidance=(
                f"The student is in grade {grade_num} (elementary school). Use very simple "
                "vocabulary, short sentences, and concrete everyday analogies. Avoid technical "
                "jargon, multi-syllable academic terms, and abstract notation unless you "
                "immediately explain it with a simple, relatable example."
            ),
        )
    elif grade_num <= 8:
        return GradeProfile(
            band="middle",
            reading_level=f"middle school (grade {grade_num})",
            guidance=(
                f"The student is in grade {grade_num} (middle school). Use age-appropriate "
                "vocabulary, introduce technical terms gradually with brief definitions, and "
                "keep explanations mostly concrete with occasional abstract reasoning."
            ),
        )
    else:
        return GradeProfile(
            band="high",
            reading_level=f"high school (grade {grade_num})",
            guidance=(
                f"The student is in grade {grade_num} (high school). You may use standard "
                "academic vocabulary and formal notation appropriate for college-preparatory "
                "coursework, while still briefly explaining any advanced terminology you "
                "introduce."
            ),
        )


def build_guardrail_context(
    enrolled_subjects: Optional[List[str]] = None,
    grade_level: Optional[str] = None,
) -> str:
    """Compose the guardrail directives appended to the tutor's system prompt."""
    profile = get_grade_profile(grade_level)
    parts = [f"GRADE-APPROPRIATE DEPTH: {profile.guidance}"]
    if enrolled_subjects:
        subjects_str = ", ".join(s.replace("_", " ").title() for s in enrolled_subjects)
        parts.append(
            f"SUBJECT SCOPE: This student is enrolled in: {subjects_str}. Keep all guidance, "
            "examples, and analogies grounded in these subjects, and gently redirect the "
            "conversation back to them if it drifts."
        )
    return "\n\n".join(parts)
