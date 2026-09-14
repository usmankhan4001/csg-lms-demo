"""
SMS Alumni Tracking Database Models (Module M33).

Tracks graduated students, higher education destinations, career milestones,
and mentorship connections.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class AlumniProfile(SQLModel, table=True):
    __tablename__ = "sms_alumni_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    campus_id: Optional[int] = Field(default=None, index=True)
    user_id: int = Field(index=True, description="Learnhouse user ID")
    graduation_year: int = Field(index=True)
    degree_or_diploma: str = Field(description="High School Diploma, O/A Levels, Bachelor, etc.")
    current_company: Optional[str] = Field(default=None)
    job_title: Optional[str] = Field(default=None)
    industry: Optional[str] = Field(default=None)
    higher_ed_institution: Optional[str] = Field(default=None)
    higher_ed_major: Optional[str] = Field(default=None)
    linkedin_url: Optional[str] = Field(default=None)
    location_city: Optional[str] = Field(default=None)
    location_country: Optional[str] = Field(default=None)
    willing_to_mentor: bool = Field(default=False)
    mentorship_topics: Optional[str] = Field(default=None, description="Comma-separated topics")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AlumniMilestone(SQLModel, table=True):
    __tablename__ = "sms_alumni_milestones"

    id: Optional[int] = Field(default=None, primary_key=True)
    alumni_id: int = Field(foreign_key="sms_alumni_profiles.id", index=True)
    title: str = Field(description="Promotion, award, startup founded, publication")
    description: Optional[str] = Field(default=None)
    milestone_date: str = Field(description="ISO Date YYYY-MM-DD")
    created_at: datetime = Field(default_factory=datetime.utcnow)
