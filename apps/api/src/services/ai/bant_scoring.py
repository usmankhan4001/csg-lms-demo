"""
5-Factor BANT Lead Qualification Engine
=======================================
Phase 3 RevOps AI: Calculates quantitative qualification scores (0-100)
across Budget (25pts), Authority (25pts), Need (25pts), and Timeline (25pts),
categorizing admissions leads into actionable conversion tiers:
- HOT (>= 80)
- WARM (60 - 79)
- COLD (40 - 59)
- NURTURE (< 40)
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from src.db.sms_revops import AdmissionsLead


class BANTTier(str, Enum):
    """Conversion readiness tier for admissions lead qualification."""
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"
    NURTURE = "NURTURE"


class BANTScoreBreakdown(BaseModel):
    """Component-level factor scoring breakdown (each max 25 points)."""
    budget_score: float = Field(..., ge=0.0, le=25.0, description="Budget fit and fee readiness (max 25)")
    authority_score: float = Field(..., ge=0.0, le=25.0, description="Decision-maker presence and verified authority (max 25)")
    need_score: float = Field(..., ge=0.0, le=25.0, description="Academic alignment and grade/curriculum demand (max 25)")
    timeline_score: float = Field(..., ge=0.0, le=25.0, description="Enrollment urgency and start timeline (max 25)")
    total_score: float = Field(..., ge=0.0, le=100.0, description="Aggregated BANT qualification score (0-100)")


class BANTQualificationResult(BaseModel):
    """Complete BANT evaluation with tiering, signals, and operational recommendations."""
    lead_id: Optional[int] = None
    total_score: float
    tier: BANTTier
    breakdown: BANTScoreBreakdown
    conversion_signals: List[str]
    risk_factors: List[str]
    recommended_next_action: str
    qualification_summary: str


# High-demand enrollment milestone grades
HIGH_DEMAND_GRADES = {
    "kindergarten", "kg", "kg1", "kg2", "pre-k", "eyfs", "reception",
    "grade 1", "year 1", "grade 6", "year 7", "grade 9", "year 10",
    "grade 11", "year 12", "ib diploma", "a-levels", "a levels", "o-levels", "o levels"
}

STANDARD_DEMAND_GRADES = {
    "grade 2", "grade 3", "grade 4", "grade 5", "grade 7", "grade 8",
    "grade 10", "grade 12", "year 2", "year 3", "year 4", "year 5",
    "year 6", "year 8", "year 9", "year 11", "year 13"
}


def _extract_lead_dict(lead_data: Union[Dict[str, Any], AdmissionsLead]) -> Dict[str, Any]:
    """Helper to convert AdmissionsLead or dict into standard dictionary format."""
    if isinstance(lead_data, AdmissionsLead):
        return {
            "id": lead_data.id,
            "campus_id": lead_data.campus_id,
            "parent_name": lead_data.parent_name,
            "student_name": lead_data.student_name,
            "email": lead_data.email,
            "phone": lead_data.phone,
            "grade_applying_for": lead_data.grade_applying_for,
            "grade": lead_data.grade_applying_for,
            "budget_range": lead_data.budget_range,
            "notes": lead_data.notes,
            "source": lead_data.source.value if hasattr(lead_data.source, "value") else str(lead_data.source),
            "origin": lead_data.origin.value if hasattr(lead_data.origin, "value") else str(lead_data.origin),
            "stage": lead_data.stage.value if hasattr(lead_data.stage, "value") else str(lead_data.stage),
            "whatsapp_consent": lead_data.whatsapp_consent,
            "email_consent": lead_data.email_consent,
            "last_contacted_at": lead_data.last_contacted_at,
        }
    elif isinstance(lead_data, dict):
        return dict(lead_data)
    return {}


def score_budget_factor(data: Dict[str, Any], signals: List[str], risks: List[str]) -> float:
    """
    Evaluates Budget (Max 25 pts):
    - Full fee readiness / corporate sponsor / high budget = 25 pts
    - Standard / moderate / flexible = 18 pts
    - Low / scholarship dependent / financial aid = 10 pts
    - Unspecified / neutral default = 12 pts
    - Stated budget numerical checks vs expected tuition
    - Fee sensitivity penalties
    """
    budget_fit = data.get("budget_fit") or data.get("financial_readiness") or data.get("budget_range")
    stated_budget = data.get("stated_budget")
    expected_fee = data.get("expected_fee") or data.get("base_tuition") or 10000.0
    fee_concern = data.get("fee_concern", False) or data.get("has_fee_concern", False)

    score = 12.0  # neutral baseline

    if isinstance(budget_fit, str):
        bf = budget_fit.strip().lower()
        if any(term in bf for term in ["high", "excellent", "full_fee", "corporate_sponsor", "ready", "tier_1", "executive"]):
            score = 25.0
            signals.append("Budget Readiness: Full fee ability with corporate or high-income backing.")
        elif any(term in bf for term in ["medium", "moderate", "standard", "flexible", "tier_2"]):
            score = 18.0
            signals.append("Budget Readiness: Standard tuition capacity with standard payment terms.")
        elif any(term in bf for term in ["low", "scholarship_dependent", "financial_aid", "discount_needed", "tier_3"]):
            score = 10.0
            risks.append("Budget Constraint: Enrollment is contingent on scholarship or financial concession.")
        elif "$" in bf or "k" in bf or any(char.isdigit() for char in bf):
            # Parse rough range
            score = 16.0
            signals.append(f"Budget Range specified: {budget_fit}")

    if isinstance(stated_budget, (int, float)) and stated_budget > 0:
        if stated_budget >= expected_fee:
            score = 25.0
            signals.append(f"Stated Budget (${stated_budget:,.0f}) fully covers expected tuition (${expected_fee:,.0f}).")
        elif stated_budget >= (expected_fee * 0.8):
            score = 18.0
            signals.append(f"Stated Budget (${stated_budget:,.0f}) is close to expected tuition (${expected_fee:,.0f}).")
        else:
            score = 10.0
            risks.append(f"Stated Budget (${stated_budget:,.0f}) is below expected tuition (${expected_fee:,.0f}).")

    if fee_concern:
        score = max(0.0, score - 5.0)
        risks.append("Price Sensitivity: Family expressed explicit fee sensitivity or requested payment installments.")

    return max(0.0, min(25.0, round(score, 1)))


def score_authority_factor(data: Dict[str, Any], signals: List[str], risks: List[str]) -> float:
    """
    Evaluates Authority (Max 25 pts):
    - Verified Primary Parent / Guardian Name (8 pts)
    - Valid multi-factor contactability: Email + Phone (8 pts)
    - Multi-Channel Compliance Opt-In: WhatsApp & Email consent (5 pts)
    - Decision maker role / Corporate Sponsor / Sibling Parent (4 pts)
    """
    parent_name = data.get("parent_name") or data.get("guardian_name") or data.get("name")
    email = data.get("email")
    phone = data.get("phone") or data.get("mobile") or data.get("contact_number")
    whatsapp_consent = data.get("whatsapp_consent", False)
    email_consent = data.get("email_consent", False)
    guardian_role = data.get("guardian_role") or data.get("relationship") or "parent"
    is_corporate = data.get("is_corporate_sponsor", False) or data.get("corporate_sponsor", False)

    score = 0.0

    # 1. Primary Parent / Decision Maker Identity
    if parent_name and len(str(parent_name).strip()) >= 2:
        score += 8.0
        signals.append(f"Decision Maker: Direct engagement with primary guardian ({parent_name}).")
    else:
        risks.append("Authority Gap: Incomplete primary parent/guardian identification.")

    # 2. Verified Contact Reachability
    contact_pts = 0.0
    if email and "@" in str(email) and "." in str(email):
        contact_pts += 4.0
    if phone and len(str(phone).strip()) >= 7:
        contact_pts += 4.0
    score += contact_pts

    if contact_pts == 8.0:
        signals.append("Verified Contacts: Both direct phone and email confirmed.")
    else:
        risks.append("Contact Incomplete: Missing either valid email or direct phone.")

    # 3. Channel Opt-In & Compliance Consent
    consent_pts = 0.0
    if whatsapp_consent:
        consent_pts += 2.5
    if email_consent:
        consent_pts += 2.5
    score += consent_pts

    if consent_pts >= 5.0:
        signals.append("Compliance Verified: Full opt-in consent for WhatsApp and Email outreach.")
    elif consent_pts == 0.0:
        risks.append("Consent Pending: No proactive channel opt-in consent provided yet.")

    # 4. Institutional / Sibling / Sponsorship Backing
    if is_corporate or str(guardian_role).lower() in ["father", "mother", "legal_guardian", "sponsor"]:
        score += 4.0
    else:
        score += 2.0

    return max(0.0, min(25.0, round(score, 1)))


def score_need_factor(data: Dict[str, Any], signals: List[str], risks: List[str]) -> float:
    """
    Evaluates Need (Max 25 pts):
    - Target Grade Demand: High demand milestone grades vs standard (max 12 pts)
    - Clear Academic / Curriculum Preference: IB, Cambridge, STEM, AP (5 pts)
    - Explicit Student Need: Relocation, academic uplift, gifted pathway, boarding (5 pts)
    - Prior Academic Track / Previous School Record (3 pts)
    """
    grade = data.get("grade_applying_for") or data.get("grade") or data.get("target_grade")
    student_name = data.get("student_name") or data.get("child_name")
    curriculum = data.get("curriculum_preference") or data.get("curriculum") or data.get("academic_track")
    notes = str(data.get("notes") or "").lower()
    prev_school = data.get("previous_school") or data.get("current_school")

    score = 0.0

    # 1. Grade demand
    if grade:
        grade_str = str(grade).strip().lower()
        if any(g in grade_str for g in HIGH_DEMAND_GRADES):
            score += 12.0
            signals.append(f"Curriculum Need: Targeting milestone transition grade ({grade}).")
        elif any(g in grade_str for g in STANDARD_DEMAND_GRADES):
            score += 8.0
            signals.append(f"Standard Grade Need: Entry level {grade}.")
        else:
            score += 6.0
    else:
        risks.append("Need Undefined: Target grade level unspecified.")
        score += 3.0

    # 2. Specific Curriculum Fit
    if curriculum and str(curriculum).strip():
        score += 5.0
        signals.append(f"Curriculum Alignment: Specific track identified ({curriculum}).")
    elif any(term in notes for term in ["ib", "cambridge", "igcse", "stem", "ap", "american", "matric"]):
        score += 4.0
        signals.append("Curriculum Interest: Prospective match for campus academic offerings.")
    else:
        score += 2.0

    # 3. Explicit Need Driver
    if any(driver in notes for driver in ["relocat", "transfer", "dissatisfied", "gifted", "boarding", "scholarship", "olympiad"]):
        score += 5.0
        signals.append("Urgent Academic Need: Specific transfer/enrichment motivation stated in inquiry.")
    elif student_name and str(student_name).strip():
        score += 3.0
    else:
        score += 1.0

    # 4. Previous School
    if prev_school and str(prev_school).strip():
        score += 3.0
        signals.append(f"Prior Academic Background: Transferring from {prev_school}.")
    else:
        score += 1.5

    return max(0.0, min(25.0, round(score, 1)))


def score_timeline_factor(data: Dict[str, Any], signals: List[str], risks: List[str]) -> float:
    """
    Evaluates Timeline (Max 25 pts):
    - Immediate / Current Term / Within 30 Days = 25 pts
    - Upcoming Semester / 1-3 Months = 18 pts
    - Future Session / > 6 Months / Exploring = 10 pts
    - Unspecified / Flexible = 12 pts
    """
    timeline = data.get("start_timeline") or data.get("target_start_term") or data.get("urgency") or data.get("timeline")
    notes = str(data.get("notes") or "").lower()
    stage = str(data.get("stage") or "").upper()

    score = 12.0

    if isinstance(timeline, str):
        tl = timeline.strip().lower()
        if any(term in tl for term in ["immediate", "now", "current term", "this month", "urgent", "30 days", "asap", "fall 2026", "q1"]):
            score = 25.0
            signals.append("Timeline Commitment: Immediate enrollment requested for active term.")
        elif any(term in tl for term in ["next term", "next semester", "upcoming", "1-3 months", "spring 2027", "q2"]):
            score = 18.0
            signals.append("Timeline Commitment: Target start within next 1-3 months.")
        elif any(term in tl for term in ["next year", "future", "6 months", "exploring", "not sure", "tentative"]):
            score = 10.0
            risks.append("Extended Timeline: Long-range inquiry (> 6 months lead time).")
        else:
            score = 14.0
    elif any(term in notes for term in ["urgent", "immediate", "asap", "now", "starting soon"]):
        score = 22.0
        signals.append("Timeline Urgency: Urgency keywords detected in admissions inquiry notes.")
    elif stage in ["TOUR_BOOKED", "ASSESSMENT_SCHEDULED", "OFFER_SENT"]:
        score = 20.0
        signals.append(f"Pipeline Momentum: Lead actively advanced to stage {stage}.")

    return max(0.0, min(25.0, round(score, 1)))


def calculate_bant_score(lead_data: Union[Dict[str, Any], AdmissionsLead]) -> BANTQualificationResult:
    """
    Executes the 5-Factor BANT Lead Qualification algorithm:
    1. Budget Score (25 pts)
    2. Authority Score (25 pts)
    3. Need Score (25 pts)
    4. Timeline Score (25 pts)
    Total: 0-100 pts.

    Tiering:
    - HOT (>= 80): Immediate VIP admissions engagement & offer dispatch.
    - WARM (60-79): Personalized counseling, syllabus walk-through, campus tour.
    - COLD (40-59): 14-day automated email/WhatsApp value-add nurture sequence.
    - NURTURE (< 40): Long-tail informational drip & open house invitations.
    """
    clean_data = _extract_lead_dict(lead_data)
    signals: List[str] = []
    risks: List[str] = []

    budget = score_budget_factor(clean_data, signals, risks)
    authority = score_authority_factor(clean_data, signals, risks)
    need = score_need_factor(clean_data, signals, risks)
    timeline = score_timeline_factor(clean_data, signals, risks)

    total = round(budget + authority + need + timeline, 1)
    total = max(0.0, min(100.0, total))

    # Determine Tier
    if total >= 80.0:
        tier = BANTTier.HOT
        recommended_action = (
            "Priority Admissions Action: Schedule VIP Campus Tour within 2 hours and initiate "
            "Automated Matriculation Handshake."
        )
        summary = (
            f"High-intent candidate (BANT Score {total}/100). Verified decision-maker with full budget "
            "readiness and immediate academic timeline."
        )
    elif total >= 60.0:
        tier = BANTTier.WARM
        recommended_action = (
            "Active Counselor Engagement: Dispatch personalized curriculum syllabus & fee schedule; "
            "invite parent for 1-on-1 counselor briefing."
        )
        summary = (
            f"Qualified prospective family (BANT Score {total}/100). Strong academic alignment; "
            "requires final fee schedule confirmation or tour attendance."
        )
    elif total >= 40.0:
        tier = BANTTier.COLD
        recommended_action = (
            "Nurture Sequence: Enroll in 14-day WhatsApp value drip highlighting campus faculty, "
            "accreditation, and extracurricular achievements."
        )
        summary = (
            f"Early-stage inquiry (BANT Score {total}/100). Moderate fit; requires further data enrichment "
            "and engagement nurturing."
        )
    else:
        tier = BANTTier.NURTURE
        recommended_action = (
            "Long-tail Marketing: Retain in quarterly newsletter audience and invite to future annual Open Day."
        )
        summary = (
            f"Low readiness inquiry (BANT Score {total}/100). Sparse contact information or distant timeline."
        )

    breakdown = BANTScoreBreakdown(
        budget_score=budget,
        authority_score=authority,
        need_score=need,
        timeline_score=timeline,
        total_score=total,
    )

    return BANTQualificationResult(
        lead_id=clean_data.get("id"),
        total_score=total,
        tier=tier,
        breakdown=breakdown,
        conversion_signals=signals,
        risk_factors=risks,
        recommended_next_action=recommended_action,
        qualification_summary=summary,
    )
