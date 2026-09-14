from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class AlumniProfileCreate(BaseModel):
    user_id: int
    graduation_year: int
    degree_or_diploma: str
    current_company: Optional[str] = None
    job_title: Optional[str] = None
    industry: Optional[str] = None
    higher_ed_institution: Optional[str] = None
    higher_ed_major: Optional[str] = None
    linkedin_url: Optional[str] = None
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    willing_to_mentor: bool = False
    mentorship_topics: Optional[str] = None


class AlumniProfileUpdate(BaseModel):
    current_company: Optional[str] = None
    job_title: Optional[str] = None
    industry: Optional[str] = None
    higher_ed_institution: Optional[str] = None
    higher_ed_major: Optional[str] = None
    linkedin_url: Optional[str] = None
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    willing_to_mentor: Optional[bool] = None
    mentorship_topics: Optional[str] = None


class AlumniMilestoneCreate(BaseModel):
    alumni_id: int
    title: str
    description: Optional[str] = None
    milestone_date: str


class AlumniMilestoneRead(BaseModel):
    id: int
    alumni_id: int
    title: str
    description: Optional[str]
    milestone_date: str
    created_at: datetime


class AlumniProfileRead(BaseModel):
    id: int
    org_id: Optional[int]
    campus_id: Optional[int]
    user_id: int
    graduation_year: int
    degree_or_diploma: str
    current_company: Optional[str]
    job_title: Optional[str]
    industry: Optional[str]
    higher_ed_institution: Optional[str]
    higher_ed_major: Optional[str]
    linkedin_url: Optional[str]
    location_city: Optional[str]
    location_country: Optional[str]
    willing_to_mentor: bool
    mentorship_topics: Optional[str]
    created_at: datetime
    milestones: List[AlumniMilestoneRead] = []
