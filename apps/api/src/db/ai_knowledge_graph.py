"""
Concept Knowledge Graph & Student 360 Mastery Matrix Models (M44, M45)
======================================================================
Database models and Pydantic schemas for concept dependency graphs,
prerequisites, pgvector semantic embeddings, and student mastery evaluation.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, Float, ForeignKey, Index, Integer, String, Text
from sqlmodel import Field, SQLModel
from pgvector.sqlalchemy import Vector


# ---------------------------------------------------------------------------
# 1. ConceptNode (Knowledge Graph Node)
# ---------------------------------------------------------------------------

class ConceptNodeBase(SQLModel):
    subject: str = Field(sa_column=Column(String(100), index=True, nullable=False))
    topic_code: str = Field(sa_column=Column(String(50), index=True, nullable=False))
    title: str = Field(sa_column=Column(String(255), nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    difficulty_level: int = Field(default=1, ge=1, le=5, sa_column=Column(Integer, nullable=False))


class ConceptNodeCreate(ConceptNodeBase):
    embedding: Optional[List[float]] = None


class ConceptNodeUpdate(SQLModel):
    subject: Optional[str] = None
    topic_code: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    difficulty_level: Optional[int] = Field(default=None, ge=1, le=5)
    embedding: Optional[List[float]] = None


class ConceptNodeRead(ConceptNodeBase):
    id: int
    created_at: str
    updated_at: str


class ConceptNode(ConceptNodeBase, table=True):
    __tablename__ = "concept_nodes"
    __table_args__ = (
        Index("ix_concept_nodes_subject_topic", "subject", "topic_code"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(768), nullable=True))
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        sa_column=Column(String(64), nullable=False)
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        sa_column=Column(String(64), nullable=False)
    )


# ---------------------------------------------------------------------------
# 2. ConceptPrerequisite (Knowledge Graph Edge)
# ---------------------------------------------------------------------------

class ConceptPrerequisiteBase(SQLModel):
    concept_id: int = Field(
        sa_column=Column(Integer, ForeignKey("concept_nodes.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    prerequisite_concept_id: int = Field(
        sa_column=Column(Integer, ForeignKey("concept_nodes.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    strength_weight: float = Field(default=1.0, ge=0.0, le=1.0, sa_column=Column(Float, nullable=False))


class ConceptPrerequisiteCreate(ConceptPrerequisiteBase):
    pass


class ConceptPrerequisiteRead(ConceptPrerequisiteBase):
    id: int
    created_at: str


class ConceptPrerequisite(ConceptPrerequisiteBase, table=True):
    __tablename__ = "concept_prerequisites"
    __table_args__ = (
        Index("ix_prerequisite_pair", "concept_id", "prerequisite_concept_id", unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        sa_column=Column(String(64), nullable=False)
    )


# ---------------------------------------------------------------------------
# 3. StudentConceptMastery (Student 360 Mastery Matrix State)
# ---------------------------------------------------------------------------

class StudentConceptMasteryBase(SQLModel):
    student_id: str = Field(sa_column=Column(String(255), index=True, nullable=False))
    concept_id: int = Field(
        sa_column=Column(Integer, ForeignKey("concept_nodes.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    mastery_score: float = Field(default=0.0, ge=0.0, le=1.0, sa_column=Column(Float, nullable=False))
    confidence_level: float = Field(default=0.5, ge=0.0, le=1.0, sa_column=Column(Float, nullable=False))
    attempts_count: int = Field(default=1, sa_column=Column(Integer, default=1, nullable=False))


class StudentConceptMasteryCreate(StudentConceptMasteryBase):
    pass


class StudentConceptMasteryUpdate(SQLModel):
    mastery_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence_level: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    attempts_count: Optional[int] = None


class StudentConceptMasteryRead(StudentConceptMasteryBase):
    id: int
    last_evaluated_at: str


class StudentConceptMastery(StudentConceptMasteryBase, table=True):
    __tablename__ = "student_concept_masteries"
    __table_args__ = (
        Index("ix_student_concept_unique", "student_id", "concept_id", unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    last_evaluated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        sa_column=Column(String(64), nullable=False)
    )


# ---------------------------------------------------------------------------
# 4. API Request/Response Schemas
# ---------------------------------------------------------------------------

class MasteryEvaluationInput(SQLModel):
    concept_id: int
    quiz_score: float = Field(description="Score between 0.0 and 1.0 or 0 and 100")
    difficulty: Optional[int] = Field(default=None, ge=1, le=5, description="Assessment difficulty level (1-5)")


class MasteryRadarItem(SQLModel):
    """One subject's row on the Student 360 mastery radar.

    `average_mastery` and `proficiency_tier` are OPTIONAL and are None when no
    concept in this subject has been assessed for this student yet.

    WHY: they used to be plain floats/strings, and a concept the student had
    never been assessed on contributed a score of 0.0 to the average. A newly
    enrolled child therefore scored 0% in every subject and was labelled
    "Novice" -- a confident judgement about their ability derived from the
    complete absence of evidence. `assessed_concepts` is the denominator, so a
    reader can always tell "scored zero" from "not measured".
    """

    subject: str
    average_mastery: Optional[float] = None
    total_concepts: int
    assessed_concepts: int = 0
    mastered_concepts: int
    in_progress_concepts: int
    proficiency_tier: Optional[str] = None


class StudentMasteryRadarResponse(SQLModel):
    student_id: str
    radar_data: List[MasteryRadarItem]
    # None when the student has no mastery record at all -- NOT 0.0, which
    # reads as total failure rather than "nothing tracked yet".
    overall_mastery_average: Optional[float] = None
    total_mastered_concepts: int
    total_tracked_concepts: int
    total_assessed_concepts: int = 0


class LearningPathConceptItem(SQLModel):
    concept_id: int
    subject: str
    topic_code: str
    title: str
    difficulty_level: int
    current_mastery: float
    confidence_level: float
    status: str  # "MASTERED", "IN_PROGRESS", "READY_TO_LEARN", "BLOCKED"
    prerequisites_met: bool
    recommendation_reason: str


class StudentLearningPathResponse(SQLModel):
    student_id: str
    subject: Optional[str] = None
    readiness_summary: str
    gap_concepts: List[LearningPathConceptItem]
    recommended_next_concepts: List[LearningPathConceptItem]
    mastered_concepts: List[LearningPathConceptItem]
    estimated_study_time_mins: int
