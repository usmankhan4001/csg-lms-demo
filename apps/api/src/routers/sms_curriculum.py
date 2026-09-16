"""
CSG-SMS Curriculum Masters Router
=================================
CRUD for academic Programs (boards / qualifications) and for the Syllabus
Topics that hang off a Learnhouse course, under `/api/v1/sms/curriculum`.

Every handler resolves its tenant from the principal via `require_org_id` --
never from a client-supplied field, and never with a fallback to organisation 1
(see security/school_ownership.py). Every read and write filters on that
`org_id`, so a caller from another school gets an empty list or a 404 rather
than another school's curriculum.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    SCHOOL_ADMIN,
    STAFF,
    SUPER_ADMIN,
    TEACHER,
    KeycloakUserPrincipal,
    require_roles,
)
from src.db.sms_curriculum import (
    Program,
    ProgramCreate,
    ProgramRead,
    ProgramUpdate,
    SyllabusTopic,
    SyllabusTopicCreate,
    SyllabusTopicRead,
    SyllabusTopicUpdate,
)
from src.security.school_ownership import (
    assert_campus_allowed,
    require_org_id,
    resolve_scoped_campus_id,
)

router = APIRouter(prefix="/sms/curriculum", tags=["sms-curriculum"])

# Writing the curriculum is back-office work: who offers which board, and what
# its syllabus says. TEACHER is deliberately excluded -- a teacher consumes the
# syllabus, they do not redefine the school's programmes.
WRITE_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN, STAFF]
# Reading it is staff-wide: a teacher needs the syllabus to plan against it.
READ_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF]


# ---------------------------------------------------------
# Program Endpoints
# ---------------------------------------------------------

@router.get("/programs", response_model=List[ProgramRead], summary="List Programs")
async def list_programs(
    campus_id: Optional[int] = Query(None, description="Filter by campus"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(READ_ROLES)),
) -> List[ProgramRead]:
    org_id = require_org_id(principal)
    scoped_campus_id = resolve_scoped_campus_id(principal, campus_id)

    stmt = select(Program).where(Program.org_id == org_id)
    if scoped_campus_id is not None:
        # A campus-bound caller sees their own campus's programs AND the
        # org-wide ones. Comparing for equality alone would hide every
        # org-wide program from exactly the campuses it applies to.
        stmt = stmt.where(
            or_(Program.campus_id == scoped_campus_id, Program.campus_id.is_(None))
        )
    if is_active is not None:
        stmt = stmt.where(Program.is_active == is_active)

    result = await session.exec(stmt.order_by(Program.name))
    return list(result.all())


@router.post(
    "/programs",
    response_model=ProgramRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Program",
)
async def create_program(
    payload: ProgramCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(WRITE_ROLES)),
) -> ProgramRead:
    org_id = require_org_id(principal)
    # Fail loudly rather than quietly filing the program under another campus.
    assert_campus_allowed(principal, payload.campus_id)
    # ...and pin an omitted campus to the caller's own. Without this a
    # campus-bound admin creates an ORG-WIDE program by leaving the field out,
    # because NULL is what "applies to every campus" means on this table.
    campus_id = resolve_scoped_campus_id(principal, payload.campus_id)

    program = Program(
        org_id=org_id,
        campus_id=campus_id,
        **payload.model_dump(exclude={"campus_id"}),
    )
    session.add(program)
    await session.commit()
    await session.refresh(program)
    return program


@router.get("/programs/{program_id}", response_model=ProgramRead, summary="Get Program")
async def get_program(
    program_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(READ_ROLES)),
) -> ProgramRead:
    org_id = require_org_id(principal)
    program = (
        await session.exec(
            select(Program).where(Program.id == program_id, Program.org_id == org_id)
        )
    ).first()
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program


@router.put("/programs/{program_id}", response_model=ProgramRead, summary="Update Program")
async def update_program(
    program_id: int,
    payload: ProgramUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(WRITE_ROLES)),
) -> ProgramRead:
    org_id = require_org_id(principal)
    program = (
        await session.exec(
            select(Program).where(Program.id == program_id, Program.org_id == org_id)
        )
    ).first()
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    changes = payload.model_dump(exclude_unset=True)
    if "campus_id" in changes:
        assert_campus_allowed(principal, changes["campus_id"])
        changes["campus_id"] = resolve_scoped_campus_id(principal, changes["campus_id"])
    for field, value in changes.items():
        setattr(program, field, value)

    session.add(program)
    await session.commit()
    await session.refresh(program)
    return program


@router.delete("/programs/{program_id}", summary="Delete Program")
async def delete_program(
    program_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(WRITE_ROLES)),
) -> dict:
    org_id = require_org_id(principal)
    program = (
        await session.exec(
            select(Program).where(Program.id == program_id, Program.org_id == org_id)
        )
    ).first()
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    await session.delete(program)
    await session.commit()
    return {"success": True, "id": program_id}


# ---------------------------------------------------------
# Syllabus Topic Endpoints
# ---------------------------------------------------------

@router.get("/topics", response_model=List[SyllabusTopicRead], summary="List Syllabus Topics")
async def list_topics(
    course_id: Optional[int] = Query(None, description="Filter by Learnhouse Course ID"),
    program_id: Optional[int] = Query(None, description="Filter by Program (board)"),
    academic_term_id: Optional[int] = Query(None, description="Filter by Academic Term"),
    grade_level: Optional[str] = Query(None, description="Filter by grade level"),
    campus_id: Optional[int] = Query(None, description="Filter by campus"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(READ_ROLES)),
) -> List[SyllabusTopicRead]:
    """Topics in teaching order.

    `?course_id=&academic_term_id=` is the "current term syllabus topics" query
    the AI tutor and report cards are meant to be grounded in.
    """
    org_id = require_org_id(principal)
    scoped_campus_id = resolve_scoped_campus_id(principal, campus_id)

    stmt = select(SyllabusTopic).where(SyllabusTopic.org_id == org_id)
    if scoped_campus_id is not None:
        # Same disjunction as `list_programs`: a campus sees its own pacing of
        # a course AND the org-wide scheme of work, never another campus's.
        stmt = stmt.where(
            or_(
                SyllabusTopic.campus_id == scoped_campus_id,
                SyllabusTopic.campus_id.is_(None),
            )
        )
    if course_id is not None:
        stmt = stmt.where(SyllabusTopic.course_id == course_id)
    if program_id is not None:
        stmt = stmt.where(SyllabusTopic.program_id == program_id)
    if academic_term_id is not None:
        stmt = stmt.where(SyllabusTopic.academic_term_id == academic_term_id)
    if grade_level is not None:
        stmt = stmt.where(SyllabusTopic.grade_level == grade_level)
    if is_active is not None:
        stmt = stmt.where(SyllabusTopic.is_active == is_active)

    result = await session.exec(stmt.order_by(SyllabusTopic.sequence, SyllabusTopic.id))
    return list(result.all())


@router.post(
    "/topics",
    response_model=SyllabusTopicRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Syllabus Topic",
)
async def create_topic(
    payload: SyllabusTopicCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(WRITE_ROLES)),
) -> SyllabusTopicRead:
    org_id = require_org_id(principal)
    assert_campus_allowed(principal, payload.campus_id)
    campus_id = resolve_scoped_campus_id(principal, payload.campus_id)

    # A topic may only be attached to a program the caller's org owns --
    # otherwise a caller could pin their syllabus onto another school's board
    # and read it back through the program filter.
    if payload.program_id is not None:
        program = (
            await session.exec(
                select(Program).where(
                    Program.id == payload.program_id, Program.org_id == org_id
                )
            )
        ).first()
        if program is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Program not found"
            )

    topic = SyllabusTopic(
        org_id=org_id,
        campus_id=campus_id,
        **payload.model_dump(exclude={"campus_id"}),
    )
    session.add(topic)
    await session.commit()
    await session.refresh(topic)
    return topic


@router.get("/topics/{topic_id}", response_model=SyllabusTopicRead, summary="Get Syllabus Topic")
async def get_topic(
    topic_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(READ_ROLES)),
) -> SyllabusTopicRead:
    org_id = require_org_id(principal)
    topic = (
        await session.exec(
            select(SyllabusTopic).where(
                SyllabusTopic.id == topic_id, SyllabusTopic.org_id == org_id
            )
        )
    ).first()
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus topic not found"
        )
    return topic


@router.put(
    "/topics/{topic_id}", response_model=SyllabusTopicRead, summary="Update Syllabus Topic"
)
async def update_topic(
    topic_id: int,
    payload: SyllabusTopicUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(WRITE_ROLES)),
) -> SyllabusTopicRead:
    org_id = require_org_id(principal)
    topic = (
        await session.exec(
            select(SyllabusTopic).where(
                SyllabusTopic.id == topic_id, SyllabusTopic.org_id == org_id
            )
        )
    ).first()
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus topic not found"
        )

    changes = payload.model_dump(exclude_unset=True)
    if "campus_id" in changes:
        assert_campus_allowed(principal, changes["campus_id"])
        changes["campus_id"] = resolve_scoped_campus_id(principal, changes["campus_id"])
    if changes.get("program_id") is not None:
        program = (
            await session.exec(
                select(Program).where(
                    Program.id == changes["program_id"], Program.org_id == org_id
                )
            )
        ).first()
        if program is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Program not found"
            )

    for field, value in changes.items():
        setattr(topic, field, value)

    session.add(topic)
    await session.commit()
    await session.refresh(topic)
    return topic


@router.delete("/topics/{topic_id}", summary="Delete Syllabus Topic")
async def delete_topic(
    topic_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(WRITE_ROLES)),
) -> dict:
    org_id = require_org_id(principal)
    topic = (
        await session.exec(
            select(SyllabusTopic).where(
                SyllabusTopic.id == topic_id, SyllabusTopic.org_id == org_id
            )
        )
    ).first()
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus topic not found"
        )

    await session.delete(topic)
    await session.commit()
    return {"success": True, "id": topic_id}
