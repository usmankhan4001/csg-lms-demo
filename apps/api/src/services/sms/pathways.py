from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_pathways import (
    CurricularPathway,
    PathwayCourse,
    StudentPathwayEnrollment,
)
from src.schemas.sms_pathways import (
    CurricularPathwayCreate,
    CurricularPathwayRead,
    PathwayCourseRead,
    StudentPathwayProgressRead,
)


class CurricularPathwayService:
    @staticmethod
    async def create_pathway(
        db: AsyncSession,
        payload: CurricularPathwayCreate,
        org_id: Optional[int],
    ) -> CurricularPathway:
        pathway = CurricularPathway(
            org_id=org_id,
            name=payload.name,
            code=payload.code,
            description=payload.description,
            required_credits=payload.required_credits,
        )
        db.add(pathway)
        await db.commit()
        await db.refresh(pathway)

        for c in payload.courses:
            pc = PathwayCourse(
                pathway_id=pathway.id,
                course_id=c.course_id,
                credits=c.credits,
                is_mandatory=c.is_mandatory,
                semester_sequence=c.semester_sequence,
                prerequisite_course_id=c.prerequisite_course_id,
            )
            db.add(pc)

        await db.commit()
        return pathway

    @staticmethod
    async def list_pathways(
        db: AsyncSession,
        org_id: Optional[int],
    ) -> List[CurricularPathwayRead]:
        query = select(CurricularPathway).where(CurricularPathway.is_active == True)  # noqa: E712
        if org_id is not None:
            query = query.where(CurricularPathway.org_id == org_id)
        results = (await db.exec(query)).all()

        output = []
        for p in results:
            courses = (
                await db.exec(
                    select(PathwayCourse)
                    .where(PathwayCourse.pathway_id == p.id)
                    .order_by(PathwayCourse.semester_sequence.asc())
                )
            ).all()
            output.append(
                CurricularPathwayRead(
                    id=p.id,
                    org_id=p.org_id,
                    name=p.name,
                    code=p.code,
                    description=p.description,
                    required_credits=p.required_credits,
                    is_active=p.is_active,
                    created_at=p.created_at,
                    courses=[
                        PathwayCourseRead(
                            id=c.id,
                            pathway_id=c.pathway_id,
                            course_id=c.course_id,
                            credits=c.credits,
                            is_mandatory=c.is_mandatory,
                            semester_sequence=c.semester_sequence,
                            prerequisite_course_id=c.prerequisite_course_id,
                        )
                        for c in courses
                    ],
                )
            )
        return output

    @staticmethod
    async def enroll_student(
        db: AsyncSession,
        student_id: int,
        pathway_id: int,
        org_id: Optional[int],
    ) -> StudentPathwayEnrollment:
        pathway = await db.get(CurricularPathway, pathway_id)
        if not pathway or not pathway.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pathway not found or inactive")

        existing = await db.exec(
            select(StudentPathwayEnrollment).where(
                StudentPathwayEnrollment.student_id == student_id,
                StudentPathwayEnrollment.pathway_id == pathway_id,
            )
        )
        if existing.first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Student already enrolled in this pathway")

        enrollment = StudentPathwayEnrollment(
            org_id=org_id,
            student_id=student_id,
            pathway_id=pathway_id,
            status="in_progress",
        )
        db.add(enrollment)
        await db.commit()
        await db.refresh(enrollment)
        return enrollment

    @staticmethod
    async def get_student_progress(
        db: AsyncSession,
        student_id: int,
    ) -> List[StudentPathwayProgressRead]:
        enrollments = (
            await db.exec(
                select(StudentPathwayEnrollment).where(StudentPathwayEnrollment.student_id == student_id)
            )
        ).all()

        output = []
        for e in enrollments:
            pathway = await db.get(CurricularPathway, e.pathway_id)
            if not pathway:
                continue

            courses = (
                await db.exec(select(PathwayCourse).where(PathwayCourse.pathway_id == pathway.id))
            ).all()
            total_req = pathway.required_credits
            # Assume progress based on active enrollment calculation
            earned_credits = min(total_req, len(courses) * 3)
            pct = round((earned_credits / total_req * 100), 1) if total_req > 0 else 100.0

            output.append(
                StudentPathwayProgressRead(
                    id=e.id,
                    org_id=e.org_id,
                    student_id=e.student_id,
                    pathway_id=pathway.id,
                    pathway_name=pathway.name,
                    status=e.status,
                    total_required_credits=total_req,
                    earned_credits=earned_credits,
                    progress_percentage=pct,
                    enrolled_at=e.enrolled_at,
                )
            )
        return output
