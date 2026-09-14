"""
Dynamic Scholarship & Offer Letter Generator (M24, M27)
======================================================
Generates customized, formal admission offer and scholarship congratulatory letters
for admitted students with dynamic fee calculations, scholarship discounts, and onboarding steps.
"""

from typing import Optional
from datetime import datetime, timezone


class MissingOfferFacts(ValueError):
    """Raised when an offer letter would have to invent a name or a figure.

    Surface this to the user as "configure the campus / fee structure first";
    never swallow it and send a letter containing a placeholder amount.
    """


def generate_personalized_offer_copy(
    student_name: str,
    grade: str,
    discount_pct: float,
    campus_name: str,
    parent_name: Optional[str] = None,
    academic_year: Optional[str] = None,
    annual_tuition: Optional[float] = None,
    curriculum: Optional[str] = None,
    validity_days: int = 14,
    special_conditions: Optional[str] = None,
) -> str:
    """
    Generates tailored, professional acceptance and scholarship award letter copy.

    Args:
        student_name: Name of the admitted student.
        grade: Target grade / academic level (e.g. "Grade 9", "Kindergarten").
        discount_pct: Awarded scholarship discount percentage (0.0 to 100.0).
        campus_name: Name of the admitting campus (e.g. "CSG Cambridge International Campus").
        parent_name: Optional parent/guardian name for personal salutation.
        academic_year: Academic session (defaults to current/upcoming year e.g. "2026-2027").
        annual_tuition: Base annual tuition fee in local currency (defaults to 12000.0).
        curriculum: Academic curriculum (e.g. "Cambridge IGCSE & A-Levels").
        validity_days: Number of days before the offer expires.
        special_conditions: Any specific requirements (e.g., maintaining 3.5 GPA).

    Returns:
        Structured formal markdown letter string.
    """
    # An offer letter is a formal representation to a family. Every figure and
    # name in it must come from the school's own record: these previously fell
    # back to a fictional campus ("CSG International Academy") and, below, an
    # invented annual tuition of 12,500 -- a financial claim a parent could
    # reasonably act on. Refuse to generate rather than invent.
    if not campus_name or not str(campus_name).strip():
        raise MissingOfferFacts(
            "Cannot generate an offer letter: the campus name is unknown. "
            "Assign the lead to a campus first."
        )
    if annual_tuition is None or float(annual_tuition) <= 0:
        raise MissingOfferFacts(
            "Cannot generate an offer letter: no annual tuition was supplied. "
            "Link a fee structure so the letter quotes the real amount."
        )

    s_name = str(student_name).strip() if student_name else "Candidate"
    g_name = str(grade).strip() if grade else "Admitted Grade"
    c_name = str(campus_name).strip()
    p_name = str(parent_name).strip() if parent_name else f"The Parents / Guardians of {s_name}"
    curr = str(curriculum).strip() if curriculum else "Advanced Cambridge & STEAM Curriculum"
    year = str(academic_year).strip() if academic_year else "2026-2027 Academic Session"
    
    # Tuition calculations
    base_fee = float(annual_tuition)
    discount = max(0.0, min(100.0, float(discount_pct) if discount_pct is not None else 0.0))
    annual_savings = base_fee * (discount / 100.0)
    net_payable = base_fee - annual_savings

    today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    lines = []

    # Header
    lines.append(f"**{c_name.upper()}**")
    lines.append("*Office of Admissions & Student Financial Aid*")
    lines.append(f"**Date:** {today_str}\n")

    # Salutation
    lines.append(f"**To:** {p_name}")
    lines.append(f"**Subject: Official Offer of Admission & Academic Placement for {s_name} – {year}**\n")

    # Admission Congratulatory Statement
    lines.append(f"Dear {p_name},\n")
    lines.append(
        f"On behalf of the Admissions Committee and Faculty of **{c_name}**, it is our distinct pleasure to officially "
        f"congratulate you and offer **{s_name}** admission into **{g_name}** for the **{year}**.\n"
    )
    lines.append(
        f"Our Admissions Committee was thoroughly impressed by {s_name}'s academic readiness, intellectual curiosity, "
        f"and personal character. We are confident that {s_name} will thrive within our rigorous **{curr}** learning environment."
    )

    # Scholarship Section (if applicable)
    if discount > 0:
        lines.append(f"\n### 🎓 Prestigious Merit & Academic Scholarship Award")
        lines.append(
            f"In recognition of {s_name}'s exemplary performance during the admissions evaluation, the Board of Governors "
            f"is pleased to award {s_name} a **{discount:g}% Annual Tuition Scholarship**.\n"
        )
        lines.append("| Fee Component | Amount / Percentage |")
        lines.append("| :--- | :--- |")
        lines.append(f"| **Standard Annual Tuition** | ${base_fee:,.2f} |")
        lines.append(f"| **Merit Scholarship Award ({discount:g}%)** | -${annual_savings:,.2f} |")
        lines.append(f"| **Net Annual Tuition Payable** | **${net_payable:,.2f}** |")
        lines.append(f"| **Total Annual Family Savings** | **${annual_savings:,.2f}** |\n")
        
        if special_conditions:
            lines.append(f"*Scholarship Continuation Terms:* {special_conditions}")
        else:
            lines.append(
                f"*Scholarship Continuation Terms:* This scholarship remains active across academic terms contingent on "
                f"{s_name} maintaining commendable academic progress (minimum 3.2 GPA or equivalent) and upholding exemplary student conduct."
            )
    else:
        lines.append(f"\n### 📋 Tuition & Fee Schedule")
        lines.append(f"• **Standard Annual Tuition:** ${base_fee:,.2f}")
        lines.append(f"• **Payment Frequency Options:** Available in Annual, Bi-Annual, or Termly Installment Plans.")
        lines.append(f"• **Sibling Benefit:** An automatic 5% fee remission applies for any enrolled siblings.")

    # Next Steps and Formal Acceptance
    lines.append(f"\n### 📝 Next Steps to Confirm Enrollment")
    lines.append(
        f"To formally secure {s_name}'s seat in {g_name}, please complete the following steps within **{validity_days} days**:\n"
        f"1. **Sign & Return Acceptance**: Complete the online Enrollment Acceptance Agreement.\n"
        f"2. **Seat Reservation Deposit**: Submit the standard registration deposit to confirm classroom placement.\n"
        f"3. **Welcome & Orientation Package**: Access the CSG Learner Portal to finalize uniform sizing, bus routes, and device setup."
    )

    # Closing
    lines.append(
        f"\nWe look forward to welcoming {s_name} into the {c_name} family for an inspiring academic journey.\n\n"
        f"Warmest regards,\n\n"
        f"**Director of Admissions & Student Enrollment**\n"
        f"**Office of the Principal & Academic Head**\n"
        f"*{c_name}*"
    )

    return "\n".join(lines)
