"""
Automated Marketing Drip Generator (M27)
========================================
Generates a personalized 4-stage multichannel nurture sequence for prospective student leads:
- Stage 1 (Day 1): Welcome & Core Value Proposition (Email / WhatsApp)
- Stage 2 (Day 3): Campus Video Tour & State-of-the-Art Facilities (WhatsApp / Email)
- Stage 3 (Day 7): Merit Scholarship & Financial Aid Invitation (Email / SMS)
- Stage 4 (Day 14): Personal Admissions Officer 1-on-1 Consultation Follow-up (Phone / WhatsApp)
"""

from typing import Dict, Any, List, Optional


def generate_nurture_sequence(
    lead: Dict[str, Any],
    campus_info: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Constructs an automated, personalized 4-stage multichannel marketing drip sequence.

    Args:
        lead: Prospective lead data (student_name, parent_name, grade, curriculum, email, phone, etc.)
        campus_info: Campus metadata (campus_name, city, virtual_tour_url, principal_name, admissions_phone, etc.)

    Returns:
        List of 4 structured drip stage dictionaries.
    """
    if not isinstance(lead, dict):
        lead = {}
    if not isinstance(campus_info, dict):
        campus_info = {}

    parent_name = lead.get("parent_name") or lead.get("name") or "Valued Parent"
    student_name = lead.get("student_name") or lead.get("child_name") or "your child"
    grade = lead.get("grade") or lead.get("target_grade") or "the upcoming academic year"
    curriculum = lead.get("curriculum_preference") or lead.get("curriculum") or "world-standard dual accredited"
    lead_id = lead.get("id") or lead.get("lead_id") or "lead_unknown"

    campus_name = campus_info.get("name") or campus_info.get("campus_name") or "CSG International Academy"
    city = campus_info.get("city") or "our central campus"
    admissions_phone = campus_info.get("admissions_phone") or campus_info.get("phone") or "+1 (800) 555-CSG-EDU"
    tour_url = campus_info.get("virtual_tour_url") or f"https://tour.csg-edu.org/{campus_name.lower().replace(' ', '-')}"
    principal_name = campus_info.get("principal_name") or "Dr. Alistair Montgomery"
    scholarship_deadline = campus_info.get("scholarship_deadline") or "the end of the current term"

    sequence: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Stage 1: Day 1 - Welcome & Core Academic Value Proposition
    # -------------------------------------------------------------------------
    stage_1 = {
        "stage": 1,
        "day": 1,
        "channel": "email_whatsapp",
        "subject": f"Welcome to {campus_name} – Admissions Pathway for {student_name}",
        "content": (
            f"Dear {parent_name},\n\n"
            f"Welcome to {campus_name}! We are thrilled that you are considering us for {student_name}'s education in {grade}.\n\n"
            f"At {campus_name}, our pedagogical philosophy bridges rigorous {curriculum} academics with future-ready skills: "
            f"AI literacy, bilingual leadership, and collaborative inquiry. With an average 1:8 teacher-student ratio, every learner "
            f"receives dedicated mentorship to thrive academically and personally.\n\n"
            f"Our dedicated Admissions Team is here to guide you every step of the way. Feel free to reply directly to this message "
            f"or call us at {admissions_phone}.\n\n"
            f"Warm regards,\n"
            f"Admissions Office | {campus_name}"
        ),
        "call_to_action": "Schedule an Initial Admissions Discovery Call",
        "metadata": {
            "lead_id": lead_id,
            "stage_name": "welcome_value_prop",
            "trigger_delay_days": 1,
            "target_grade": grade,
            "campus_name": campus_name,
        },
    }
    sequence.append(stage_1)

    # -------------------------------------------------------------------------
    # Stage 2: Day 3 - Immersive Campus Video Tour & World-Class Facilities
    # -------------------------------------------------------------------------
    stage_2 = {
        "stage": 2,
        "day": 3,
        "channel": "whatsapp_email",
        "subject": f"Experience {campus_name} in 360° – Interactive Virtual Campus Tour",
        "content": (
            f"Hi {parent_name},\n\n"
            f"Take a peek inside our vibrant classrooms, state-of-the-art STEAM robotics laboratories, Olympic swimming complex, "
            f"and performing arts theatre where {student_name} will learn and grow!\n\n"
            f"Experience our interactive 360° video walkthrough here: {tour_url}\n\n"
            f"Would you prefer to experience the energy in person? We host private, guided campus tours every weekday from 9:00 AM to 3:00 PM.\n\n"
            f"Best wishes,\n"
            f"Admissions Team | {campus_name}"
        ),
        "call_to_action": "Book an In-Person Guided Campus Tour",
        "metadata": {
            "lead_id": lead_id,
            "stage_name": "campus_video_tour",
            "trigger_delay_days": 3,
            "virtual_tour_url": tour_url,
            "campus_name": campus_name,
        },
    }
    sequence.append(stage_2)

    # -------------------------------------------------------------------------
    # Stage 3: Day 7 - Merit & Leadership Scholarship Invitation
    # -------------------------------------------------------------------------
    stage_3 = {
        "stage": 3,
        "day": 7,
        "channel": "email_sms",
        "subject": f"Merit & Leadership Scholarship Opportunity for {student_name} at {campus_name}",
        "content": (
            f"Dear {parent_name},\n\n"
            f"We believe outstanding potential deserves institutional support. For {grade} applicants, {campus_name} offers competitive "
            f"Merit, STEM Excellence, and Leadership Scholarships providing up to 30% tuition fee reduction.\n\n"
            f"Scholarship evaluations for {student_name} evaluate:\n"
            f"• Prior academic achievement and report card remarks\n"
            f"• Cognitive readiness and diagnostic assessment performance\n"
            f"• Extracurricular leadership, sports, or creative portfolio\n\n"
            f"Priority scholarship application round closes on {scholarship_deadline}. We encourage you to submit {student_name}'s "
            f"records early to secure seat priority.\n\n"
            f"Warmly,\n"
            f"Scholarships & Financial Aid Committee | {campus_name}"
        ),
        "call_to_action": "Apply for Merit & Leadership Scholarship",
        "metadata": {
            "lead_id": lead_id,
            "stage_name": "scholarship_invitation",
            "trigger_delay_days": 7,
            "scholarship_deadline": scholarship_deadline,
            "campus_name": campus_name,
        },
    }
    sequence.append(stage_3)

    # -------------------------------------------------------------------------
    # Stage 4: Day 14 - Personal Admissions Officer 1-on-1 Consultation
    # -------------------------------------------------------------------------
    stage_4 = {
        "stage": 4,
        "day": 14,
        "channel": "phone_whatsapp",
        "subject": f"Personal Follow-up from {principal_name}'s Office – {campus_name}",
        "content": (
            f"Dear {parent_name},\n\n"
            f"I hope you are doing well. As seats for {grade} at {campus_name} are approaching full capacity for the upcoming session, "
            f"I wanted to personally reach out and see if you have any questions regarding {student_name}'s enrollment.\n\n"
            f"I have reserved a dedicated 15-minute consultation window for you to discuss academic subject pathways, transition support, "
            f"or bus transport routes directly with our leadership team.\n\n"
            f"Please let me know if tomorrow at 11:00 AM or 3:00 PM works for a quick phone call or in-person coffee on campus.\n\n"
            f"Sincerely,\n"
            f"{principal_name} & The Admissions Executive Team\n"
            f"Direct Contact: {admissions_phone} | {campus_name}"
        ),
        "call_to_action": "Confirm 1-on-1 Executive Consultation",
        "metadata": {
            "lead_id": lead_id,
            "stage_name": "executive_follow_up",
            "trigger_delay_days": 14,
            "principal_name": principal_name,
            "campus_name": campus_name,
        },
    }
    sequence.append(stage_4)

    return sequence
