from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_alumni import AlumniMilestone, AlumniProfile
from src.schemas.sms_alumni import (
    AlumniMilestoneCreate,
    AlumniMilestoneRead,
    AlumniProfileCreate,
    AlumniProfileRead,
    AlumniProfileUpdate,
)


class AlumniService:
    @staticmethod
    async def create_profile(
        db: AsyncSession,
        payload: AlumniProfileCreate,
        org_id: Optional[int],
        campus_id: Optional[int],
    ) -> AlumniProfile:
        existing = await db.exec(
            select(AlumniProfile).where(
                AlumniProfile.user_id == payload.user_id,
                AlumniProfile.org_id == org_id,
            )
        )
        if existing.first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Alumni profile already exists for this user")

        profile = AlumniProfile(
            org_id=org_id,
            campus_id=campus_id,
            user_id=payload.user_id,
            graduation_year=payload.graduation_year,
            degree_or_diploma=payload.degree_or_diploma,
            current_company=payload.current_company,
            job_title=payload.job_title,
            industry=payload.industry,
            higher_ed_institution=payload.higher_ed_institution,
            higher_ed_major=payload.higher_ed_major,
            linkedin_url=payload.linkedin_url,
            location_city=payload.location_city,
            location_country=payload.location_country,
            willing_to_mentor=payload.willing_to_mentor,
            mentorship_topics=payload.mentorship_topics,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def list_profiles(
        db: AsyncSession,
        org_id: Optional[int],
        graduation_year: Optional[int] = None,
        industry: Optional[str] = None,
        willing_to_mentor: Optional[bool] = None,
    ) -> List[AlumniProfileRead]:
        query = select(AlumniProfile)
        if org_id is not None:
            query = query.where(AlumniProfile.org_id == org_id)
        if graduation_year is not None:
            query = query.where(AlumniProfile.graduation_year == graduation_year)
        if industry is not None:
            query = query.where(AlumniProfile.industry == industry)
        if willing_to_mentor is not None:
            query = query.where(AlumniProfile.willing_to_mentor == willing_to_mentor)

        query = query.order_by(AlumniProfile.graduation_year.desc())
        results = (await db.exec(query)).all()

        output = []
        for p in results:
            milestones = (
                await db.exec(
                    select(AlumniMilestone).where(AlumniMilestone.alumni_id == p.id).order_by(AlumniMilestone.milestone_date.desc())
                )
            ).all()
            output.append(
                AlumniProfileRead(
                    id=p.id,
                    org_id=p.org_id,
                    campus_id=p.campus_id,
                    user_id=p.user_id,
                    graduation_year=p.graduation_year,
                    degree_or_diploma=p.degree_or_diploma,
                    current_company=p.current_company,
                    job_title=p.job_title,
                    industry=p.industry,
                    higher_ed_institution=p.higher_ed_institution,
                    higher_ed_major=p.higher_ed_major,
                    linkedin_url=p.linkedin_url,
                    location_city=p.location_city,
                    location_country=p.location_country,
                    willing_to_mentor=p.willing_to_mentor,
                    mentorship_topics=p.mentorship_topics,
                    created_at=p.created_at,
                    milestones=[
                        AlumniMilestoneRead(
                            id=m.id,
                            alumni_id=m.alumni_id,
                            title=m.title,
                            description=m.description,
                            milestone_date=m.milestone_date,
                            created_at=m.created_at,
                        )
                        for m in milestones
                    ],
                )
            )
        return output

    @staticmethod
    async def add_milestone(
        db: AsyncSession,
        payload: AlumniMilestoneCreate,
        org_id: Optional[int],
    ) -> AlumniMilestone:
        profile = await db.get(AlumniProfile, payload.alumni_id)
        # ONE answer for "no such profile" and "not this school's profile".
        #
        # Splitting them -- 404 for the first, 403 "Access denied" for the
        # second -- is a cross-tenant existence oracle: walking alumni_id values
        # and reading the status code tells an authenticated user at school A
        # exactly which alumni profile ids exist at school B, and by counting
        # them, roughly how large another school's alumni register is. The
        # profile body was never disclosed; its existence was.
        #
        # Identical detail text as well as identical status: a differing message
        # leaks precisely what the shared status code is there to hide. This
        # mirrors the same fix in services/sms/discipline.py.
        if not profile or (org_id and profile.org_id != org_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alumni profile not found",
            )

        milestone = AlumniMilestone(
            alumni_id=payload.alumni_id,
            title=payload.title,
            description=payload.description,
            milestone_date=payload.milestone_date,
        )
        db.add(milestone)
        await db.commit()
        await db.refresh(milestone)
        return milestone
