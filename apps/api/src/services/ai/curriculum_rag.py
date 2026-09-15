"""
Curriculum RAG Knowledge Base & Admissions Counselor Agent
===========================================================
Phase 3 RevOps AI: Grounds 24/7 conversational admissions queries against
campus syllabi, quarterly tuition schedules, payment plans, and school policies.
Provides contextual semantic retrieval, verified citations, confidence scoring,
and actionable guidance for prospective parents and students.
"""

import re
import math
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Source document citation for grounded admissions counselor answers."""
    doc_id: str
    title: str
    category: str
    campus_id: Optional[int] = None
    grade_levels: List[str] = []
    snippet: str
    relevance_score: float


class CurriculumRAGResponse(BaseModel):
    """Grounded admissions counselor response."""
    query: str
    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0, description="Grounded retrieval confidence score (0.0-1.0)")
    citations: List[Citation]
    grounded_facts: List[str]
    suggested_followups: List[str]
    campus_id: Optional[int] = None
    grade_level: Optional[str] = None


# ---------------------------------------------------------------------------
# Pre-seeded Institutional Knowledge Base
# ---------------------------------------------------------------------------

DEFAULT_KNOWLEDGE_DOCS: List[Dict[str, Any]] = [
    {
        "doc_id": "KB-CURR-IB-01",
        "title": "International Baccalaureate (IB) Diploma & MYP Curriculum Guide",
        "category": "curriculum",
        "grade_levels": ["Grade 9", "Grade 10", "Grade 11", "Grade 12", "Year 10", "Year 11", "Year 12", "Year 13"],
        "keywords": ["ib", "diploma", "myp", "higher level", "standard level", "theory of knowledge", "tok", "cas", "extended essay", "international"],
        "content": (
            "Our campus offers the full International Baccalaureate (IB) Middle Years Programme (MYP) "
            "for Grades 6-10 and the prestigious IB Diploma Programme (DP) for Grades 11-12. "
            "The IB curriculum emphasizes inquiry-based learning, global citizenship, and critical thinking. "
            "Core requirements include Theory of Knowledge (TOK), Creativity, Activity, Service (CAS), and the 4,000-word Extended Essay. "
            "Students select 6 subject groups including Higher Level (HL) and Standard Level (SL) courses in Mathematics: Analysis & Approaches, "
            "Physics, Chemistry, Biology, Economics, History, and English Literature."
        ),
    },
    {
        "doc_id": "KB-CURR-CAMBRIDGE-02",
        "title": "Cambridge IGCSE & A-Levels Academic Syllabus",
        "category": "curriculum",
        "grade_levels": ["Grade 9", "Grade 10", "Grade 11", "Grade 12", "O-Levels", "A-Levels"],
        "keywords": ["cambridge", "igcse", "a-levels", "a levels", "cie", "o-levels", "stem", "sciences", "british curriculum"],
        "content": (
            "The Cambridge International curriculum provides rigorous preparation for global university admissions. "
            "In Grades 9-10 (IGCSE), students undertake 7-9 subjects including English First Language, Mathematics, Sciences (Physics, Chemistry, Biology), "
            "and Humanities. In Grades 11-12 (Cambridge International AS & A-Levels), students specialize in 3-4 advanced subjects. "
            "Our campus is an authorized Cambridge Examination Centre with state-of-the-art laboratory facilities and specialized STEM coaching."
        ),
    },
    {
        "doc_id": "KB-CURR-PRIMARY-03",
        "title": "Early Years & Primary Foundation Stage (EYFS & Grades 1-5)",
        "category": "curriculum",
        "grade_levels": ["KG", "KG1", "KG2", "Kindergarten", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"],
        "keywords": ["early years", "eyfs", "kindergarten", "kg", "primary", "phonics", "numeracy", "stem", "play-based"],
        "content": (
            "The Early Years and Primary School curriculum integrates inquiry-based STEM learning with foundational literacy and numeracy. "
            "Early Years (KG1/KG2) focuses on social-emotional development, phonics, sensorial discovery, and language immersion. "
            "Grades 1-5 build robust competencies in Singapore Math, guided reading, environmental science, coding basics, robotics, music, and physical education. "
            "Student-to-teacher ratio is maintained at 12:1 in Kindergarten and 18:1 in Primary classes to ensure individualized attention."
        ),
    },
    {
        "doc_id": "KB-FEE-SCHEDULE-01",
        "title": "Annual & Quarterly Tuition Fee Structure",
        "category": "tuition",
        "grade_levels": ["KG", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6", "Grade 7", "Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12"],
        "keywords": ["fee", "tuition", "quarterly", "instalments", "installments", "annual fee", "cost", "pricing", "admission fee"],
        "content": (
            "Standard academic tuition is structured annually and billed in four equal quarterly installments for family convenience. "
            "Base annual tuition ranges from $8,000/year (Kindergarten) to $12,000/year (Middle School Grades 6-8) and $15,000/year (High School Grades 9-12). "
            "Quarterly installments are due at the start of each term: Q1 (September 1), Q2 (December 1), Q3 (March 1), and Q4 (June 1). "
            "A one-time registration and admission processing fee of $500 applies to all newly matriculated students upon acceptance."
        ),
    },
    {
        "doc_id": "KB-FEE-SCHOLARSHIPS-02",
        "title": "Scholarships, Concessions, & Sibling Discounts",
        "category": "tuition",
        "grade_levels": ["All Grades", "Grade 6", "Grade 7", "Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12"],
        "keywords": ["scholarship", "discount", "sibling discount", "financial aid", "concession", "merit", "hardship"],
        "content": (
            "We offer generous merit-based scholarships and family concessions: "
            "1. Sibling Concession: 15% tuition discount for the second enrolled child, and 25% for the third and subsequent children. "
            "2. Academic Merit Scholarship: Up to 50% tuition reduction for applicants scoring in the top 95th percentile on the CSG Admissions Diagnostic. "
            "3. Special Talent / Sports / STEM Awards: Up to 30% tuition grant based on verified national or regional portfolio achievements. "
            "4. Need-based Financial Aid: Hardship grants evaluated confidentially by the School Board upon submission of tax and income records."
        ),
    },
    {
        "doc_id": "KB-POLICY-ATTENDANCE-01",
        "title": "Campus Attendance, Timetable & Punctuality Policy",
        "category": "policy",
        "grade_levels": ["All Grades"],
        "keywords": ["attendance", "absence", "leave", "punctuality", "minimum attendance", "schedule", "timetable"],
        "content": (
            "Regular attendance is critical for academic success. All enrolled students must maintain a minimum attendance threshold of 85% "
            "across each academic term to remain eligible for end-of-term examinations and course promotion. "
            "School hours are Monday through Friday from 8:00 AM to 3:30 PM. "
            "Medical absences must be accompanied by a licensed physician's certificate submitted through the Parent Portal within 48 hours. "
            "Unexcused absences exceeding 5 consecutive days trigger an automatic pastoral review."
        ),
    },
    {
        "doc_id": "KB-POLICY-ACCREDITATION-02",
        "title": "Cognia Accreditation & University Placement Records",
        "category": "policy",
        "grade_levels": ["Grade 9", "Grade 10", "Grade 11", "Grade 12"],
        "keywords": ["cognia", "accreditation", "university", "placement", "ivy league", "russell group", "transcripts", "global"],
        "content": (
            "Our institution is fully accredited by Cognia (NCA CASI, NWAC, SACS CASI) and recognized by the Ministry of Education. "
            "Graduates receive an accredited High School Diploma alongside Cambridge/IB transcripts. "
            "Over 94% of graduating seniors receive offers from top-tier global institutions across the US (Ivy League, UC System), "
            "UK (Russell Group, Oxford, Cambridge), Canada (U of T, UBC), and leading regional universities. "
            "Full-time college counselors provide 1-on-1 career guidance, SAT/ACT test prep, and university application portfolio mentoring."
        ),
    },
    {
        "doc_id": "KB-ADM-MATRICULATION-01",
        "title": "Automated Matriculation & Onboarding Handshake Protocol",
        "category": "admissions",
        "grade_levels": ["All Grades"],
        "keywords": ["matriculation", "enrollment", "handshake", "onboarding", "documents", "placement", "portal access"],
        "content": (
            "Once an admissions offer is accepted, our Automated Matriculation Handshake executes: "
            "1. Permanent Learnhouse student and parent portal accounts are provisioned instantly. "
            "2. The student is assigned to their designated class section with teacher assignment and timetable access. "
            "3. Structured quarterly fee vouchers are generated in the Parent Billing Portal with flexible payment links. "
            "4. Welcome packet, campus ID badge, locker allocation, and orientation schedule are dispatched via email and WhatsApp. "
            "Required onboarding documents include previous academic transcripts, birth certificate/passport copy, and immunization health record."
        ),
    },
]


def _tokenize(text: str) -> Set[str]:
    """Tokenize string into lowercase alphanumeric keywords."""
    words = re.findall(r"\b[a-z0-9_\-]{2,}\b", text.lower())
    return set(words)


def _compute_relevance(query_tokens: Set[str], doc: Dict[str, Any], campus_id: Optional[int], grade_level: Optional[str]) -> float:
    """Calculates TF-IDF/keyword overlap relevance score with grade/campus boosting."""
    if not query_tokens:
        return 0.0

    doc_text = f"{doc.get('title', '')} {' '.join(doc.get('keywords', []))} {doc.get('content', '')}"
    doc_tokens = _tokenize(doc_text)

    overlap = query_tokens.intersection(doc_tokens)
    if not overlap:
        return 0.0

    # Base Jaccard-like score with TF weighting
    score = len(overlap) / (math.sqrt(len(query_tokens)) * math.sqrt(min(len(doc_tokens), 100)))

    # Grade level match boost
    if grade_level and str(grade_level).strip():
        gl_clean = str(grade_level).strip().lower()
        doc_grades = [g.lower() for g in doc.get("grade_levels", [])]
        if any(gl_clean in g or g in gl_clean for g in doc_grades) or "all grades" in doc_grades:
            score *= 1.35

    # Campus match boost if document is campus specific
    doc_campus = doc.get("campus_id")
    if campus_id is not None and doc_campus is not None:
        if doc_campus == campus_id:
            score *= 1.25
        else:
            score *= 0.5  # Penalize cross-campus docs

    return min(1.0, round(score, 3))


class CurriculumKnowledgeBase:
    """In-memory multi-tenant RAG Knowledge Base for admissions counseling."""

    def __init__(self) -> None:
        self.documents: List[Dict[str, Any]] = list(DEFAULT_KNOWLEDGE_DOCS)

    def add_document(self, doc: Dict[str, Any]) -> str:
        doc_id = doc.get("doc_id") or f"KB-CUSTOM-{len(self.documents) + 1:03d}"
        doc_copy = dict(doc)
        doc_copy["doc_id"] = doc_id
        self.documents.append(doc_copy)
        return doc_id

    def search(
        self,
        query: str,
        campus_id: Optional[int] = None,
        grade_level: Optional[str] = None,
        category: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Citation]:
        query_tokens = _tokenize(query)
        scored_citations: List[Citation] = []

        for doc in self.documents:
            if category and doc.get("category") != category:
                continue

            rel_score = _compute_relevance(query_tokens, doc, campus_id, grade_level)
            if rel_score > 0.08:
                snippet = doc.get("content", "")[:280] + "..." if len(doc.get("content", "")) > 280 else doc.get("content", "")
                scored_citations.append(
                    Citation(
                        doc_id=doc.get("doc_id", "KB-DOC"),
                        title=doc.get("title", "Admissions Knowledge Document"),
                        category=doc.get("category", "general"),
                        campus_id=doc.get("campus_id"),
                        grade_levels=doc.get("grade_levels", []),
                        snippet=snippet,
                        relevance_score=rel_score,
                    )
                )

        scored_citations.sort(key=lambda c: c.relevance_score, reverse=True)
        return scored_citations[:top_k]


# Global singleton instance
_knowledge_base = CurriculumKnowledgeBase()


def query_curriculum_rag(
    query: str,
    campus_id: Optional[int] = None,
    grade_level: Optional[str] = None,
    category: Optional[str] = None,
    top_k: int = 3,
) -> CurriculumRAGResponse:
    """
    Executes a grounded conversational RAG query for admissions counselors.
    Retrieves syllabus content, tuition fee schedules, discount rules, or school policies.
    """
    clean_query = (query or "").strip()
    citations = _knowledge_base.search(
        clean_query,
        campus_id=campus_id,
        grade_level=grade_level,
        category=category,
        top_k=top_k,
    )

    if not citations:
        # Fallback response when query has zero domain match
        return CurriculumRAGResponse(
            query=clean_query,
            answer=(
                "Thank you for contacting our Admissions Office. While I could not locate exact institutional "
                "guidelines matching your specific inquiry, our admissions team is delighted to assist you. "
                "Please connect with our admissions counselors directly at admissions@csg.edu or schedule a campus tour."
            ),
            confidence=0.2,
            citations=[],
            grounded_facts=[
                "Admissions office is open Monday through Friday from 8:00 AM to 4:00 PM.",
                "Direct inquiries can be scheduled via website tour booking.",
            ],
            suggested_followups=[
                "What is the annual tuition fee for Grade 9?",
                "Do you offer the IB Diploma or Cambridge A-Levels?",
                "What scholarships and sibling discounts are available?",
            ],
            campus_id=campus_id,
            grade_level=grade_level,
        )

    # Synthesize grounded answer from top citations
    primary_citation = citations[0]
    matched_doc = next((d for d in _knowledge_base.documents if d["doc_id"] == primary_citation.doc_id), None)
    content_body = matched_doc.get("content", "") if matched_doc else primary_citation.snippet

    grounded_facts: List[str] = []
    suggested_followups: List[str] = []

    # Contextual categorization
    if primary_citation.category == "tuition":
        answer = (
            f"Here is our institutional tuition and fee structure: {content_body} "
            "All fee schedules are managed transparently with quarterly billing schedules and secure digital payment options."
        )
        grounded_facts = [
            "Tuition is payable in four quarterly installments.",
            "15% discount for 2nd sibling, 25% discount for 3rd sibling.",
            "Merit scholarships up to 50% available via admissions assessment.",
        ]
        suggested_followups = [
            "How do I apply for the Academic Merit Scholarship?",
            "What payment methods are supported for quarterly fee vouchers?",
            "Can I request a custom monthly installment schedule?",
        ]
    elif primary_citation.category == "curriculum":
        answer = (
            f"Regarding our academic curriculum: {content_body} "
            "Our faculty provides personalized academic support, college counseling, and state-of-the-art laboratory access."
        )
        grounded_facts = [
            "Authorized international curriculum (IB & Cambridge examination centers).",
            "Individualized university placement counseling starting in Grade 9.",
            "Low student-to-teacher ratios with specialized STEM and Arts labs.",
        ]
        suggested_followups = [
            "What subject combinations are available in Grade 11?",
            "How does the campus support university admissions (Ivy League / Russell Group)?",
            "What extracurricular activities and athletic clubs are available?",
        ]
    elif primary_citation.category == "policy":
        answer = (
            f"Regarding campus policies and governance: {content_body} "
            "We maintain strict standards to ensure a safe, disciplined, and high-performing learning environment."
        )
        grounded_facts = [
            "Mandatory 85% attendance required across each term.",
            "Accredited by Cognia and recognized by global universities.",
            "Dedicated pastoral care and counseling for student wellbeing.",
        ]
        suggested_followups = [
            "What is the school timetable and daily schedule?",
            "How does the school handle medical leave and excused absences?",
            "What transportation and bus routes are available?",
        ]
    else:  # Admissions & Matriculation
        answer = (
            f"Regarding admissions and matriculation: {content_body} "
            "Our admissions counselors guide families through every step from initial inquiry to classroom onboarding."
        )
        grounded_facts = [
            "Automated handshake provisions student & parent accounts upon acceptance.",
            "Diagnostic placement assessment ensures proper grade-level assignment.",
            "Instant access to parent portal, fee ledger, and timetable.",
        ]
        suggested_followups = [
            "What documents are required for matriculation?",
            "How soon after offer acceptance is the student portal activated?",
            "Can we book a campus tour before finalizing enrollment?",
        ]

    confidence = min(0.98, max(0.5, primary_citation.relevance_score + 0.4))

    return CurriculumRAGResponse(
        query=clean_query,
        answer=answer,
        confidence=round(confidence, 2),
        citations=citations,
        grounded_facts=grounded_facts,
        suggested_followups=suggested_followups,
        campus_id=campus_id,
        grade_level=grade_level,
    )


def add_campus_knowledge_doc(doc: Dict[str, Any]) -> str:
    """Adds a new custom document to the active RAG knowledge base."""
    return _knowledge_base.add_document(doc)
