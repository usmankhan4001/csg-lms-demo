"""
CSG-SMS Curriculum Masters: Programs & Syllabus Topics
======================================================

Two academic masters the catalogue was missing.

Why `Program` is NOT `CurricularPathway`
----------------------------------------
`CurricularPathway` (db/sms_pathways.py) is a *student-facing course bundle*:
it carries `required_credits`, and its `PathwayCourse` children carry
`semester_sequence` and `prerequisite_course_id`, and students are attached to
it through `StudentPathwayEnrollment`. That is a specialisation track
("Pre-Engineering"), not a qualification framework.

A `Program` is the awarding framework the school offers -- "Cambridge IGCSE",
"FBISE Matric". It has an awarding body, a level and a duration; nobody
"enrols" in it via `StudentPathwayEnrollment`, and `required_credits` /
`semester_sequence` are meaningless for it. Folding the two into one table
would leave `StudentPathwayEnrollment.pathway_id` pointing at either a board or
a track, and would make "which board is this syllabus written against"
unanswerable -- which is exactly the question the AI tutor grounding needs
answered.

So `Program` is a separate, org-scoped academic master. `SyllabusTopic` may
optionally name one, so the same Learnhouse course can carry a different
syllabus per board.

Tenancy
-------
Both tables carry a NOT NULL `org_id` (FK to `organization.id`) and a NULLABLE
`campus_id` (FK to `campus.id`). NULL means the row is offered org-wide, which
is the common case for a board qualification. Readers must treat NULL as
"applies to every campus", not as "belongs to no campus" -- filtering on
`campus_id == <scoped>` alone hides every org-wide row from exactly the
campuses it applies to.

`SyllabusTopic` carries the same NULLABLE `campus_id`, with the same meaning:
NULL is the org-wide scheme of work, a value is that campus's own pacing of the
same course. Two campuses of one school routinely teach the same Learnhouse
course at different rates -- one is three topics ahead by the winter break -- so
the syllabus row, not just the section, has to be able to say which campus it
belongs to. Readers must apply the same `IS NULL` disjunction as for `Program`.

Timestamps are timezone-aware UTC ISO-8601 strings, matching db/sms_campus.py.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, ForeignKey, Index, Integer
from sqlmodel import Field, SQLModel


def get_utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------
# Program Models
# ---------------------------------------------------------

class ProgramBase(SQLModel):
    """Base schema for an academic Program (board / qualification)."""
    name: str = Field(
        ...,
        max_length=200,
        description="Program title (e.g. 'Cambridge IGCSE', 'FBISE Matric')",
    )
    code: str = Field(
        ...,
        max_length=50,
        description="Short program code (e.g. 'IGCSE', 'FBISE-MATRIC')",
    )
    awarding_body: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Examining board (e.g. 'Cambridge Assessment International Education')",
    )
    level: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Academic level (e.g. 'secondary', 'matriculation', 'o_level')",
    )
    description: Optional[str] = Field(default=None, description="Free-text program description")
    duration_terms: Optional[int] = Field(
        default=None,
        ge=1,
        description="Nominal program length in academic terms. None means 'not stated'.",
    )
    is_active: bool = Field(default=True, description="Whether the program is currently offered")


class Program(ProgramBase, table=True):
    """Database model for an academic Program.

    NOTE on index names: `org_id` and `campus_id` carry `index=True`, which
    SQLAlchemy auto-names `ix_sms_program_org_id` / `ix_sms_program_campus_id`.
    The composite indexes below are deliberately named differently -- a custom
    Index whose name collides with an auto-generated one makes `create_all`
    emit CREATE INDEX twice and the API fails to boot.
    """
    __tablename__ = "sms_program"
    __table_args__ = (
        Index("ix_sms_program_org_code", "org_id", "code"),
        Index("ix_sms_program_org_active", "org_id", "is_active"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("organization.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    # NULL = offered org-wide. See the module docstring: readers must OR this
    # with IS NULL rather than comparing for equality.
    campus_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("campus.id", ondelete="CASCADE"),
            index=True,
            nullable=True,
        ),
    )
    created_at: str = Field(default_factory=get_utc_now_iso)
    updated_at: str = Field(default_factory=get_utc_now_iso)


class ProgramCreate(ProgramBase):
    """Schema for creating a Program."""
    campus_id: Optional[int] = None


class ProgramUpdate(SQLModel):
    """Schema for updating a Program. Omitted fields are left untouched."""
    name: Optional[str] = None
    code: Optional[str] = None
    awarding_body: Optional[str] = None
    level: Optional[str] = None
    description: Optional[str] = None
    duration_terms: Optional[int] = None
    is_active: Optional[bool] = None
    campus_id: Optional[int] = None


class ProgramRead(ProgramBase):
    """Schema for reading a Program."""
    id: int
    org_id: int
    campus_id: Optional[int] = None
    created_at: str
    updated_at: str


# ---------------------------------------------------------
# Syllabus Topic Models
# ---------------------------------------------------------

class SyllabusTopicBase(SQLModel):
    """Base schema for a Syllabus Topic belonging to a Course."""
    course_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("course.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        description="Learnhouse Course ID the topic belongs to",
    )
    title: str = Field(..., max_length=255, description="Topic title (e.g. 'Quadratic Equations')")
    code: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Optional syllabus reference (e.g. 'CIE-4024-3.2', 'PHY-9.1')",
    )
    description: Optional[str] = Field(default=None, description="Topic detail / learning outcomes")
    sequence: int = Field(
        default=0,
        ge=0,
        description="Teaching order within the course syllabus (ascending)",
    )
    grade_level: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Grade this topic is taught at (e.g. 'Grade 9'). None = every grade.",
    )
    program_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("sms_program.id", ondelete="SET NULL"),
            index=True,
            nullable=True,
        ),
        description="Program (board) whose syllabus this topic is written against",
    )
    academic_term_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("academic_term.id", ondelete="SET NULL"),
            index=True,
            nullable=True,
        ),
        description="Term this topic is taught in. None = not term-scoped.",
    )
    is_active: bool = Field(default=True, description="Whether the topic is part of the live syllabus")


class SyllabusTopic(SyllabusTopicBase, table=True):
    """Database model for a Syllabus Topic.

    This is the entity "current term syllabus topics" resolves to: a topic
    belongs to a course and is optionally narrowed to one term and one grade,
    so a report card or an AI tutor can ask for the topics in scope right now
    instead of the whole year's scheme of work.

    NOTE on index names: see `Program` above -- `course_id`, `program_id` and
    `academic_term_id` carry `index=True`, so the composites below are named
    differently to avoid a duplicate CREATE INDEX at boot.
    """
    __tablename__ = "sms_syllabus_topic"
    __table_args__ = (
        Index("ix_sms_topic_course_sequence", "course_id", "sequence"),
        Index("ix_sms_topic_course_term", "course_id", "academic_term_id"),
        Index("ix_sms_topic_course_campus", "course_id", "campus_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("organization.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    # NULL = the org-wide scheme of work for this course. See the module
    # docstring: readers must OR this with IS NULL, exactly as for Program.
    campus_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("campus.id", ondelete="CASCADE"),
            index=True,
            nullable=True,
        ),
    )
    created_at: str = Field(default_factory=get_utc_now_iso)
    updated_at: str = Field(default_factory=get_utc_now_iso)


class SyllabusTopicCreate(SQLModel):
    """Schema for creating a Syllabus Topic.

    Declared standalone rather than inheriting `SyllabusTopicBase`, matching
    db/sms_section_subject.py: the base carries `sa_column=` definitions that
    belong to the table, not to a request body.
    """
    course_id: int
    title: str
    code: Optional[str] = None
    description: Optional[str] = None
    sequence: int = 0
    grade_level: Optional[str] = None
    program_id: Optional[int] = None
    academic_term_id: Optional[int] = None
    campus_id: Optional[int] = None
    is_active: bool = True


class SyllabusTopicUpdate(SQLModel):
    """Schema for updating a Syllabus Topic. Omitted fields are left untouched."""
    title: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    sequence: Optional[int] = None
    grade_level: Optional[str] = None
    program_id: Optional[int] = None
    academic_term_id: Optional[int] = None
    campus_id: Optional[int] = None
    is_active: Optional[bool] = None


class SyllabusTopicRead(SQLModel):
    """Schema for reading a Syllabus Topic."""
    id: int
    org_id: int
    course_id: int
    title: str
    code: Optional[str] = None
    description: Optional[str] = None
    sequence: int
    grade_level: Optional[str] = None
    program_id: Optional[int] = None
    academic_term_id: Optional[int] = None
    campus_id: Optional[int] = None
    is_active: bool
    created_at: str
    updated_at: str
