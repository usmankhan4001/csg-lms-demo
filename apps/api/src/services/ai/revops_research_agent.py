"""
Admissions Lead Research Agent (M23)
====================================
Turns a raw inquiry into a research brief an admissions officer can act on
before the first conversation: what we actually know, what we demonstrably do
NOT know, and the questions worth asking to close those gaps.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
It does not enrich from the open web, look up a family, or ask a language
model to "research" a prospect. Two reasons, both hard constraints rather
than preferences:

1. **Privacy.** These are real families, frequently with a named minor child.
   Scraping or inferring facts about them and filing it in a CRM is not
   something a school should be doing silently, and nothing in this system
   captures consent for it.

2. **Fabrication.** An LLM asked to "research this lead" from a name, an
   email and a grade will produce fluent, plausible, entirely invented
   detail -- a previous school, a sibling, an income bracket. This codebase
   has already had to tear out two endpoints that returned invented academic
   data as if it were real. A brief that quietly guesses is worse than no
   brief, because an officer will act on it in front of the parent.

So every field here is either derived from data the school holds, or is
explicitly reported as unknown. `unknown_fields` is part of the output
contract, not an afterthought: the gaps are the most actionable thing in the
brief, because they are what the first call should be spent on.
"""

from typing import Any, Dict, List, Optional

from src.services.ai.revops_lead_scoring import (
    HIGH_DEMAND_GRADES,
    MODERATE_DEMAND_GRADES,
    calculate_lead_score,
)

# Fields an officer would want before a first conversation. Absence is
# reported, never filled in.
_RESEARCHABLE_FIELDS = (
    ("student_name", "Student's name"),
    ("parent_name", "Parent / guardian name"),
    ("email", "Email address"),
    ("phone", "Phone number"),
    ("grade_applying_for", "Grade applying for"),
    ("budget_range", "Budget expectation"),
    ("previous_school", "Current / previous school"),
    ("curriculum_preference", "Curriculum preference"),
    ("start_timeline", "Intended start date"),
)

# Questions keyed to the gap they close. Asked only when the field is missing,
# so the officer is never prompted to ask something already answered.
_GAP_QUESTIONS = {
    "previous_school": "Which school is {student} attending at the moment, and how are they finding it?",
    "curriculum_preference": "Is the family looking for a particular curriculum, or still comparing options?",
    "start_timeline": "When are they hoping {student} would start — this coming term, or a later intake?",
    "budget_range": "Have they had a chance to look at the fee structure for {grade}?",
    "grade_applying_for": "Which grade are they applying for, and what is {student}'s date of birth?",
    "phone": "What is the best number to reach them on?",
    "email": "Which email should the admissions pack go to?",
}


def _normalise_grade(grade: Optional[str]) -> str:
    return (grade or "").strip().lower()


def classify_grade_demand(grade: Optional[str]) -> Dict[str, Any]:
    """Where this grade sits in the school's own enrolment demand bands.

    Reuses the bands the lead scorer already uses (`revops_lead_scoring`)
    rather than declaring a second, divergent opinion about which grades are
    in demand -- two scoring engines that disagree is the failure mode worth
    avoiding here.
    """
    normalised = _normalise_grade(grade)
    if not normalised:
        return {
            "band": "unknown",
            "note": "No grade recorded, so intake demand cannot be assessed.",
        }
    if normalised in HIGH_DEMAND_GRADES:
        return {
            "band": "high",
            "note": (
                "A milestone intake grade — these fill early, so a fast response "
                "matters more than usual here."
            ),
        }
    if normalised in MODERATE_DEMAND_GRADES:
        return {
            "band": "moderate",
            "note": "A mid-year grade with steady demand; seats are usually available.",
        }
    return {
        "band": "unlisted",
        "note": (
            "This grade is not in the school's recorded demand bands. Confirm "
            "the grade is offered before promising a seat."
        ),
    }


def summarise_engagement(activities: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """What the CRM can actually show about prior contact.

    An empty activity log means *no recorded contact*, which is reported as
    exactly that -- not as "low engagement", which would be an inference the
    data does not support (contact may simply have happened off-system).
    """
    if not activities:
        return {
            "recorded_touchpoints": 0,
            "last_activity_type": None,
            "summary": "No contact recorded in the CRM yet.",
        }

    types = [str(a.get("activity_type") or "").upper() for a in activities if isinstance(a, dict)]
    return {
        "recorded_touchpoints": len(activities),
        "last_activity_type": types[0] if types else None,
        "summary": (
            f"{len(activities)} contact event(s) recorded in the CRM. "
            "This reflects logged activity only — calls or messages handled "
            "off-system will not appear."
        ),
    }


def build_lead_research_brief(
    lead: Dict[str, Any],
    activities: Optional[List[Dict[str, Any]]] = None,
    campus_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Produce a research brief from data the school holds.

    Args:
        lead: The `AdmissionsLead` record as a dict.
        activities: `LeadActivityLog` rows for this lead, newest first.
        campus_info: Optional campus metadata (name, curriculum) for context.

    Returns:
        A brief with `known_facts`, `unknown_fields`, `questions_to_ask`,
        `grade_demand`, `engagement`, `score_summary` and `talking_points`.
        Nothing in it is inferred about the family beyond what they supplied.
    """
    if not isinstance(lead, dict):
        lead = {}
    campus = campus_info if isinstance(campus_info, dict) else {}

    student = (lead.get("student_name") or "").strip() or "the student"
    grade = (lead.get("grade_applying_for") or lead.get("grade") or "").strip()

    known_facts: Dict[str, Any] = {}
    unknown_fields: List[str] = []
    for key, label in _RESEARCHABLE_FIELDS:
        value = lead.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            unknown_fields.append(label)
        else:
            known_facts[label] = value

    questions: List[str] = []
    for key, template in _GAP_QUESTIONS.items():
        value = lead.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            questions.append(
                template.format(student=student, grade=grade or "that grade")
            )

    grade_demand = classify_grade_demand(grade)
    engagement = summarise_engagement(activities)

    # Reuse the existing scorer rather than second-guessing it.
    score_result = calculate_lead_score({**lead, "grade": grade})
    score_summary = {
        "score": score_result.get("score"),
        "intent": score_result.get("intent"),
        "recommended_next_action": score_result.get("recommended_next_action"),
        "key_conversion_factors": score_result.get("key_conversion_factors", []),
    }

    talking_points: List[str] = []
    if grade_demand["band"] == "high":
        talking_points.append(
            f"{grade or 'This grade'} is a milestone intake — worth mentioning that seats move quickly."
        )
    if campus.get("campus_name"):
        talking_points.append(f"Position the conversation around {campus['campus_name']}.")
    if campus.get("curriculum"):
        talking_points.append(f"Curriculum on offer: {campus['curriculum']}.")
    if engagement["recorded_touchpoints"] == 0:
        talking_points.append(
            "First recorded contact — open by confirming what prompted the inquiry."
        )
    if unknown_fields:
        talking_points.append(
            f"{len(unknown_fields)} detail(s) still unknown; the questions below are the fastest way to close them."
        )

    return {
        "lead_id": lead.get("id"),
        "student_name": lead.get("student_name"),
        "grade_applying_for": grade or None,
        "known_facts": known_facts,
        "unknown_fields": unknown_fields,
        "questions_to_ask": questions,
        "grade_demand": grade_demand,
        "engagement": engagement,
        "score_summary": score_summary,
        "talking_points": talking_points,
        "sources": [
            "CRM lead record",
            "CRM activity log" if activities else "CRM activity log (empty)",
        ],
        "disclaimer": (
            "Compiled only from data this school holds. No external lookup was "
            "performed and nothing about the family has been inferred or "
            "generated. Fields listed under unknown_fields are genuinely "
            "unknown."
        ),
    }
