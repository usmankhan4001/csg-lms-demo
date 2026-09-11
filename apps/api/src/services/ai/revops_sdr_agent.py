"""
Conversational Admissions SDR Agent (M25, M26)
==============================================
Handles prospective parent and student admissions inquiries across curriculum,
school fees, transport, and admissions criteria.
Performs real-time entity extraction (student age, grade, parent contact)
and detects tour booking intent.
"""

import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Intent regex / keyword patterns
TOUR_INTENT_PATTERNS = [
    r"\b(book|schedule|arrange|request|set up|plan)\b.*\b(tour|visit|campus tour|walkthrough|open day|appointment|meeting)\b",
    r"\b(visit|see|check out|come by|view)\b.*\b(school|campus|facilities|classrooms|lab)\b",
    r"\b(campus tour|school tour|physical visit|virtual tour)\b",
    r"\b(when can I visit|can we come over|available for a visit)\b",
]

FEE_PATTERNS = [
    r"\b(fee|fees|tuition|cost|price|pricing|payment|installment|discount|scholarship|afford|term fee|annual fee)\b"
]

CURRICULUM_PATTERNS = [
    r"\b(curriculum|syllabus|cambridge|igcse|a[- ]level|ib|pyp|myp|diploma|american|cbse|stem|robotics|subjects|academic program)\b"
]

TRANSPORT_PATTERNS = [
    r"\b(transport|bus|buses|commute|route|pick up|drop off|van|shuttle|travel|tracking)\b"
]

ADMISSIONS_CRITERIA_PATTERNS = [
    r"\b(admission|admissions|apply|application|requirement|requirements|criteria|eligibility|age limit|entrance exam|test|interview|document|deadline|cutoff)\b"
]


def extract_entities_from_text(message: str) -> Dict[str, Any]:
    """
    Extracts structured entities from natural language inquiry text:
    - student_name
    - student_age
    - grade
    - parent_name
    - email
    - phone
    - curriculum
    """
    entities: Dict[str, Any] = {
        "student_name": None,
        "student_age": None,
        "grade": None,
        "parent_name": None,
        "phone": None,
        "email": None,
        "curriculum": None,
    }

    if not message or not isinstance(message, str):
        return entities

    text = message.strip()

    # 1. Email extraction
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    if email_match:
        entities["email"] = email_match.group(0)

    # 2. Phone extraction (international and local phone formats)
    phone_match = re.search(r"(\+?\d{1,4}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}", text)
    if phone_match and len(re.sub(r"\D", "", phone_match.group(0))) >= 7:
        entities["phone"] = phone_match.group(0).strip()

    # 3. Student age extraction (e.g. "5 years old", "age 6", "is 7 years of age", "4-year-old")
    age_match = re.search(r"\b(?:age[d]?\s*[:]?\s*(\d{1,2})|(\d{1,2})\s*[- ]?years?[- ]?old|(\d{1,2})\s*yo\b)", text, re.IGNORECASE)
    if age_match:
        age_str = age_match.group(1) or age_match.group(2) or age_match.group(3)
        if age_str and age_str.isdigit():
            entities["student_age"] = int(age_str)

    # 4. Grade / Year level extraction (e.g. "Grade 5", "Year 9", "KG2", "Kindergarten", "Grade 10", "Pre-K")
    grade_match = re.search(
        r"\b(kindergarten|pre-k|eyfs|reception|kg\s*[12]?|grade\s*\d{1,2}|year\s*\d{1,2}|class\s*\d{1,2}|a[- ]levels?|ib\s*diploma)\b",
        text,
        re.IGNORECASE
    )
    if grade_match:
        entities["grade"] = grade_match.group(0).strip().title()

    # 5. Student Name extraction (e.g. "my son/daughter/child [Name]", "for [Name]")
    child_name_match = re.search(
        r"\b(?:my\s+(?:son|daughter|child|kid|boy|girl)\s+([A-Z][a-z]+)|for\s+([A-Z][a-z]+)(?:\s+who\s+is|\s+in\s+grade))\b",
        text
    )
    if child_name_match:
        entities["student_name"] = child_name_match.group(1) or child_name_match.group(2)

    # 6. Parent Name extraction (e.g. "I am [Name]", "My name is [Name]", "This is [Name]")
    parent_match = re.search(
        r"\b(?:my\s+name\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)|i\s+am\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)|this\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))\b",
        text,
        re.IGNORECASE
    )
    if parent_match:
        entities["parent_name"] = (parent_match.group(1) or parent_match.group(2) or parent_match.group(3)).title()

    # 7. Curriculum interest
    if re.search(r"\b(cambridge|igcse|a[- ]level)\b", text, re.IGNORECASE):
        entities["curriculum"] = "Cambridge (IGCSE / A-Levels)"
    elif re.search(r"\b(ib|international baccalaureate|pyp|myp|dp)\b", text, re.IGNORECASE):
        entities["curriculum"] = "International Baccalaureate (IB)"
    elif re.search(r"\b(american|ap|common core)\b", text, re.IGNORECASE):
        entities["curriculum"] = "American Curriculum (AP)"
    elif re.search(r"\b(cbse|icse)\b", text, re.IGNORECASE):
        entities["curriculum"] = "CBSE"
    elif re.search(r"\b(stem|robotics|ai)\b", text, re.IGNORECASE):
        entities["curriculum"] = "STEM Enrichment"

    return entities


def detect_inquiry_intent(message: str) -> Dict[str, Any]:
    """
    Detects the primary intent and whether tour booking is requested.
    """
    text = message.lower()
    tour_intent = any(re.search(p, text) for p in TOUR_INTENT_PATTERNS)
    
    intents = []
    if tour_intent:
        intents.append("book_tour")
    if any(re.search(p, text) for p in FEE_PATTERNS):
        intents.append("fee_inquiry")
    if any(re.search(p, text) for p in CURRICULUM_PATTERNS):
        intents.append("curriculum_inquiry")
    if any(re.search(p, text) for p in TRANSPORT_PATTERNS):
        intents.append("transport_inquiry")
    if any(re.search(p, text) for p in ADMISSIONS_CRITERIA_PATTERNS):
        intents.append("admissions_criteria")

    primary_intent = intents[0] if intents else "general_inquiry"

    return {
        "primary_intent": primary_intent,
        "all_intents": intents,
        "tour_intent_detected": tour_intent,
    }


def generate_sdr_response(
    intent_data: Dict[str, Any],
    entities: Dict[str, Any],
    lead_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generates a structured, pedagogical, high-conversion admissions response.
    """
    lead_ctx = lead_context or {}
    student_name = entities.get("student_name") or lead_ctx.get("student_name") or "your child"
    grade = entities.get("grade") or lead_ctx.get("grade") or "the desired grade"
    parent_name = entities.get("parent_name") or lead_ctx.get("parent_name")
    curriculum = entities.get("curriculum") or lead_ctx.get("curriculum") or "world-class dual British & IB accredited curriculum"

    greeting = f"Dear {parent_name}," if parent_name else "Hello!"
    primary_intent = intent_data.get("primary_intent", "general_inquiry")
    tour_detected = intent_data.get("tour_intent_detected", False)

    suggested_actions = []
    paragraphs = []

    paragraphs.append(
        f"{greeting} Thank you for reaching out to our Admissions Office. We would be delighted to assist you with information for {student_name} regarding enrollment for {grade}."
    )

    # Intent-specific response generation
    if primary_intent == "curriculum_inquiry" or "curriculum_inquiry" in intent_data.get("all_intents", []):
        paragraphs.append(
            f"**Curriculum & Academic Excellence**: We offer a comprehensive {curriculum} designed to develop critical inquiry, STEAM problem-solving, and bilingual mastery. Our academic pathway includes continuous formative assessment, experiential science laboratories, and dedicated university placement counseling."
        )
        suggested_actions.append("send_curriculum_guide")

    if primary_intent == "fee_inquiry" or "fee_inquiry" in intent_data.get("all_intents", []):
        paragraphs.append(
            "**Tuition & Flexible Payment Plans**: Our transparent fee structure covers all core textbooks, digital learning platforms, and standard co-curricular activities. We offer flexible termly installment options, a 5% sibling discount for second and subsequent children, and competitive Merit & Leadership Scholarships (up to 30% tuition fee remission)."
        )
        suggested_actions.append("send_fee_schedule")

    if primary_intent == "transport_inquiry" or "transport_inquiry" in intent_data.get("all_intents", []):
        paragraphs.append(
            "**Safe Campus Transport**: We operate a modern, air-conditioned bus fleet equipped with real-time GPS tracking (accessible via our Parent Mobile App), trained female bus attendants on all routes, RFID student check-in/check-out, and 3-point seatbelts covering major residential corridors."
        )
        suggested_actions.append("send_transport_routes")

    if primary_intent == "admissions_criteria" or "admissions_criteria" in intent_data.get("all_intents", []):
        paragraphs.append(
            "**Admissions Criteria & Process**: Admissions are based on age readiness, previous academic records (last 2 years report cards), and a student assessment (evaluating English proficiency, numeracy, and cognitive skills). Our admissions team provides an encouraging, stress-free evaluation environment."
        )
        suggested_actions.append("send_application_checklist")

    # Tour booking / Next steps call-to-action
    if tour_detected or primary_intent == "book_tour":
        paragraphs.append(
            "**Schedule Your Personalized Campus Tour**: We would love to welcome you and your family for a private campus tour and a 1-on-1 consultation with our Academic Principal. Tours are hosted Monday through Friday between 8:30 AM and 3:30 PM, or on Saturday mornings."
        )
        paragraphs.append("Would you prefer a morning or afternoon tour slot this week?")
        suggested_actions.append("schedule_campus_tour")
    else:
        paragraphs.append(
            "Would you like us to schedule a brief 15-minute campus tour or send our complete Admissions & Fee Guide directly to your email or WhatsApp?"
        )
        suggested_actions.append("offer_campus_tour")

    response_text = "\n\n".join(paragraphs)

    return {
        "response": response_text,
        "suggested_actions": suggested_actions,
    }


def handle_admissions_inquiry(
    message: str,
    lead_context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Main entrypoint for the Conversational Admissions SDR Agent (M25, M26).

    Args:
        message: Incoming prospective parent query or chat message.
        lead_context: Stored CRM lead metadata (if previously known).
        history: Conversation history list.

    Returns:
        Dict with:
        - intent: Identified primary intent
        - tour_intent_detected: bool
        - extracted_entities: Dict with student_age, grade, parent_contact, etc.
        - student_age: Extracted age or None
        - grade: Extracted grade or None
        - parent_contact: Dict with email, phone, parent_name
        - response: Conversational admissions response
        - suggested_actions: List of operational action tokens
    """
    if not message or not isinstance(message, str):
        message = ""

    # 1. Entity Extraction
    extracted_entities = extract_entities_from_text(message)

    # 2. Merge with lead_context if provided
    lead_ctx = lead_context or {}
    merged_entities = {
        "student_name": extracted_entities.get("student_name") or lead_ctx.get("student_name"),
        "student_age": extracted_entities.get("student_age") or lead_ctx.get("student_age") or lead_ctx.get("age"),
        "grade": extracted_entities.get("grade") or lead_ctx.get("grade") or lead_ctx.get("target_grade"),
        "parent_name": extracted_entities.get("parent_name") or lead_ctx.get("parent_name") or lead_ctx.get("guardian_name"),
        "phone": extracted_entities.get("phone") or lead_ctx.get("phone") or lead_ctx.get("mobile"),
        "email": extracted_entities.get("email") or lead_ctx.get("email"),
        "curriculum": extracted_entities.get("curriculum") or lead_ctx.get("curriculum"),
    }

    # 3. Intent Detection
    intent_data = detect_inquiry_intent(message)

    # 4. Generate Professional Admissions Response
    gen_result = generate_sdr_response(
        intent_data=intent_data,
        entities=merged_entities,
        lead_context=lead_ctx,
    )

    parent_contact = {
        "name": merged_entities.get("parent_name"),
        "phone": merged_entities.get("phone"),
        "email": merged_entities.get("email"),
    }

    return {
        "intent": intent_data["primary_intent"],
        "all_intents": intent_data["all_intents"],
        "tour_intent_detected": intent_data["tour_intent_detected"],
        "extracted_entities": merged_entities,
        "student_age": merged_entities.get("student_age"),
        "grade": merged_entities.get("grade"),
        "parent_contact": parent_contact,
        "response": gen_result["response"],
        "suggested_actions": gen_result["suggested_actions"],
    }
