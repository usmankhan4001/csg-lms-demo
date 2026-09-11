"""
AI Lead Scoring Engine (M22, M24)
==================================
Analyzes prospective student/parent inquiries to compute a quantitative lead score (0-100),
intent categorization (HOT, WARM, COLD), key conversion drivers, and recommended next action.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


# High-demand / high-conversion target grades and academic levels
HIGH_DEMAND_GRADES = {
    "kindergarten", "kg", "kg1", "kg2", "pre-k", "eyfs", "reception",
    "grade 1", "year 1", "grade 6", "year 7", "grade 9", "year 10",
    "grade 11", "year 12", "ib diploma", "a-levels", "a levels"
}

MODERATE_DEMAND_GRADES = {
    "grade 2", "grade 3", "grade 4", "grade 5", "grade 7", "grade 8",
    "grade 10", "grade 12", "year 2", "year 3", "year 4", "year 5",
    "year 6", "year 8", "year 9", "year 11", "year 13"
}


def calculate_lead_score(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes a multi-factor quantitative lead score (0 to 100) and actionable conversion insights.

    Factors evaluated:
    1. Inquiry Completeness (25 pts): Name, grade, email, phone, previous school, parent info.
    2. Responsiveness & Engagement (20 pts): Interaction frequency, speed, open/reply history.
    3. Target Grade Demand (15 pts): High-enrollment milestone grades (KG, G1, G9, G11/IB).
    4. Budget & Financial Fit (20 pts): Budget alignment, fee readiness, corporate/sibling tier.
    5. Inquiry Timeline & Urgency (20 pts): Immediate / upcoming semester vs far future.

    Returns:
        Dict containing:
        - score: int (0-100)
        - intent: 'HOT' | 'WARM' | 'COLD'
        - breakdown: component scores
        - key_conversion_factors: list of identified signals/factors
        - recommended_next_action: prioritized operational step for RevOps/Admissions
    """
    if not isinstance(lead_data, dict):
        lead_data = {}

    conversion_factors: List[str] = []
    
    # -------------------------------------------------------------------------
    # 1. Inquiry Completeness (Max 25 pts)
    # -------------------------------------------------------------------------
    completeness_score = 0.0
    student_name = lead_data.get("student_name") or lead_data.get("child_name")
    parent_name = lead_data.get("parent_name") or lead_data.get("guardian_name") or lead_data.get("name")
    email = lead_data.get("email")
    phone = lead_data.get("phone") or lead_data.get("mobile") or lead_data.get("contact_number")
    grade = lead_data.get("grade") or lead_data.get("target_grade") or lead_data.get("year_group")
    prev_school = lead_data.get("previous_school") or lead_data.get("current_school")
    curriculum_pref = lead_data.get("curriculum_preference") or lead_data.get("curriculum")

    if student_name and str(student_name).strip():
        completeness_score += 5.0
    if parent_name and str(parent_name).strip():
        completeness_score += 4.0
    if email and "@" in str(email):
        completeness_score += 5.0
    if phone and len(str(phone).strip()) >= 7:
        completeness_score += 5.0
    if grade and str(grade).strip():
        completeness_score += 3.0
    if prev_school and str(prev_school).strip():
        completeness_score += 1.5
    if curriculum_pref and str(curriculum_pref).strip():
        completeness_score += 1.5

    completeness_score = min(25.0, completeness_score)

    if completeness_score >= 20.0:
        conversion_factors.append("High profile completeness with verified contact details")
    elif completeness_score < 10.0:
        conversion_factors.append("Incomplete inquiry data (missing primary contact or student details)")

    # -------------------------------------------------------------------------
    # 2. Responsiveness & Engagement (Max 20 pts)
    # -------------------------------------------------------------------------
    responsiveness_score = 0.0
    interactions_count = lead_data.get("interactions_count", 0)
    try:
        interactions_count = int(interactions_count)
    except (ValueError, TypeError):
        interactions_count = 0

    has_visited_website = lead_data.get("visited_website", False)
    has_opened_email = lead_data.get("opened_email", False)
    has_replied_whatsapp = lead_data.get("replied_whatsapp", False) or lead_data.get("whatsapp_replied", False)
    attended_webinar_or_event = lead_data.get("attended_event", False) or lead_data.get("attended_open_day", False)
    requested_callback = lead_data.get("requested_callback", False) or lead_data.get("tour_requested", False)

    if interactions_count >= 5:
        responsiveness_score += 8.0
    elif interactions_count >= 2:
        responsiveness_score += 5.0
    elif interactions_count >= 1:
        responsiveness_score += 3.0

    if has_replied_whatsapp:
        responsiveness_score += 5.0
        conversion_factors.append("Active two-way WhatsApp interaction")
    if attended_webinar_or_event:
        responsiveness_score += 4.0
        conversion_factors.append("Attended Open Day or Virtual Information Session")
    if requested_callback:
        responsiveness_score += 3.0
        conversion_factors.append("Directly requested admissions callback or campus tour")
    if has_opened_email or has_visited_website:
        responsiveness_score += 2.0

    responsiveness_score = min(20.0, responsiveness_score)

    # -------------------------------------------------------------------------
    # 3. Target Grade Demand (Max 15 pts)
    # -------------------------------------------------------------------------
    grade_demand_score = 0.0
    if grade:
        grade_str = str(grade).strip().lower()
        if any(g in grade_str for g in HIGH_DEMAND_GRADES):
            grade_demand_score = 15.0
            conversion_factors.append(f"Targeting high-demand milestone grade: {grade}")
        elif any(g in grade_str for g in MODERATE_DEMAND_GRADES):
            grade_demand_score = 10.0
            conversion_factors.append(f"Standard entry grade: {grade}")
        else:
            grade_demand_score = 7.0
    else:
        grade_demand_score = 4.0

    # -------------------------------------------------------------------------
    # 4. Budget & Financial Fit (Max 20 pts)
    # -------------------------------------------------------------------------
    budget_fit_score = 0.0
    budget_fit_status = lead_data.get("budget_fit") or lead_data.get("financial_readiness")
    stated_budget = lead_data.get("stated_budget")
    tuition_tier = lead_data.get("tuition_tier", "standard")
    fee_concern = lead_data.get("fee_concern", False)

    if isinstance(budget_fit_status, str):
        bfs = budget_fit_status.lower()
        if bfs in ["high", "excellent", "full_fee", "corporate_sponsor", "ready"]:
            budget_fit_score = 20.0
            conversion_factors.append("Full fee readiness with corporate/private budget alignment")
        elif bfs in ["medium", "moderate", "standard", "flexible"]:
            budget_fit_score = 14.0
        elif bfs in ["low", "scholarship_dependent", "financial_aid"]:
            budget_fit_score = 8.0
            conversion_factors.append("Inquiry contingent on scholarship or financial aid")
        else:
            budget_fit_score = 10.0
    elif isinstance(stated_budget, (int, float)) and stated_budget > 0:
        expected_fee = lead_data.get("expected_fee", 10000)
        if stated_budget >= expected_fee:
            budget_fit_score = 20.0
            conversion_factors.append(f"Stated budget ({stated_budget}) matches tuition tier")
        elif stated_budget >= (expected_fee * 0.75):
            budget_fit_score = 14.0
        else:
            budget_fit_score = 8.0
    else:
        # Default neutral fit
        budget_fit_score = 12.0

    if fee_concern:
        budget_fit_score = max(0.0, budget_fit_score - 4.0)
        conversion_factors.append("Expressed fee sensitivity or requested payment plan")

    budget_fit_score = min(20.0, max(0.0, budget_fit_score))

    # -------------------------------------------------------------------------
    # 5. Inquiry Timeline & Urgency (Max 20 pts)
    # -------------------------------------------------------------------------
    timeline_score = 0.0
    start_timeline = lead_data.get("start_timeline") or lead_data.get("target_start_term") or lead_data.get("urgency")

    if isinstance(start_timeline, str):
        st = start_timeline.lower()
        if any(term in st for term in ["immediate", "now", "current term", "this month", "urgent", "30 days"]):
            timeline_score = 20.0
            conversion_factors.append("Immediate enrollment timeline requested")
        elif any(term in st for term in ["next term", "next semester", "upcoming term", "fall", "spring", "1-3 months"]):
            timeline_score = 16.0
            conversion_factors.append("Upcoming semester target enrollment")
        elif any(term in st for term in ["next year", "future", "6 months", "exploring", "not sure"]):
            timeline_score = 8.0
            conversion_factors.append("Longer-range inquiry (> 6 months)")
        else:
            timeline_score = 12.0
    else:
        timeline_score = 10.0

    # Calculate Total Score (0-100)
    total_score = round(
        completeness_score + responsiveness_score + grade_demand_score + budget_fit_score + timeline_score,
        1
    )
    total_score = max(0.0, min(100.0, total_score))

    # Categorize Intent
    if total_score >= 75.0:
        intent = "HOT"
        recommended_next_action = "Priority Admissions Outreach within 2 hours: Schedule VIP Campus Tour & Fast-Track Assessment."
    elif total_score >= 45.0:
        intent = "WARM"
        recommended_next_action = "Send Personalized Curriculum & Fee Guide via WhatsApp; Trigger 3-Day Virtual Tour Nurture Drip."
    else:
        intent = "COLD"
        recommended_next_action = "Enroll in 14-Day Value-Add Educational Drip & Invite to Upcoming Campus Open Day."

    return {
        "score": total_score,
        "intent": intent,
        "breakdown": {
            "completeness_score": round(completeness_score, 1),
            "responsiveness_score": round(responsiveness_score, 1),
            "grade_demand_score": round(grade_demand_score, 1),
            "budget_fit_score": round(budget_fit_score, 1),
            "timeline_score": round(timeline_score, 1),
        },
        "key_conversion_factors": conversion_factors,
        "recommended_next_action": recommended_next_action,
        "lead_id": lead_data.get("id") or lead_data.get("lead_id"),
    }
