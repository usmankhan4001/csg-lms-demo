"""Curriculum masters: Programs and Syllabus Topics.

Handlers are called directly with a real `KeycloakUserPrincipal` (see
`_principals.py`) because FastAPI's dependency injection does not run for a
plain coroutine call -- the same shape as the rest of the school suite.
"""

import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import require_roles
from src.db.sms_campus import AcademicTerm, AcademicYear, Campus
from src.db.sms_curriculum import (
    ProgramCreate,
    ProgramUpdate,
    SyllabusTopicCreate,
    SyllabusTopicUpdate,
)
from src.routers.sms_curriculum import (
    READ_ROLES,
    WRITE_ROLES,
    create_program,
    create_topic,
    delete_program,
    delete_topic,
    get_program,
    get_topic,
    list_programs,
    list_topics,
    update_program,
    update_topic,
)
from src.tests.sms._principals import STAFF, SUPERADMIN, principal

# A caller from a different school. Same roles, different tenant.
OTHER_ORG_ADMIN = principal("SCHOOL_ADMIN", user_id=9, org_id=2, campus_id=2)


@pytest.mark.asyncio
async def test_program_crud(db: AsyncSession, org):
    """Create, read, update and delete a Program, scoped to the caller's org."""
    created = await create_program(
        payload=ProgramCreate(
            name="Cambridge IGCSE",
            code="IGCSE",
            awarding_body="Cambridge Assessment International Education",
            level="secondary",
            duration_terms=6,
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert created.id is not None
    assert created.org_id == org.id
    assert created.is_active is True
    # Not stated is not zero.
    assert created.duration_terms == 6

    listed = await list_programs(
        campus_id=None, is_active=None, session=db, principal=SUPERADMIN
    )
    assert [p.id for p in listed] == [created.id]

    fetched = await get_program(program_id=created.id, session=db, principal=SUPERADMIN)
    assert fetched.code == "IGCSE"

    updated = await update_program(
        program_id=created.id,
        payload=ProgramUpdate(description="8 subjects across 6 terms", is_active=False),
        session=db,
        principal=SUPERADMIN,
    )
    assert updated.description == "8 subjects across 6 terms"
    assert updated.is_active is False
    # Untouched fields survive a partial update.
    assert updated.code == "IGCSE"

    # An inactive program is excluded by an explicit is_active filter.
    active = await list_programs(
        campus_id=None, is_active=True, session=db, principal=SUPERADMIN
    )
    assert active == []

    deleted = await delete_program(
        program_id=created.id, session=db, principal=SUPERADMIN
    )
    assert deleted == {"success": True, "id": created.id}

    with pytest.raises(HTTPException) as exc:
        await get_program(program_id=created.id, session=db, principal=SUPERADMIN)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_syllabus_topic_ordering(db: AsyncSession, org, course):
    """Topics come back in `sequence` order regardless of insertion order."""
    third = await create_topic(
        payload=SyllabusTopicCreate(
            course_id=course.id, title="Trigonometry", sequence=3
        ),
        session=db,
        principal=SUPERADMIN,
    )
    first = await create_topic(
        payload=SyllabusTopicCreate(
            course_id=course.id, title="Linear Equations", sequence=1
        ),
        session=db,
        principal=SUPERADMIN,
    )
    second = await create_topic(
        payload=SyllabusTopicCreate(
            course_id=course.id, title="Quadratic Equations", sequence=2
        ),
        session=db,
        principal=SUPERADMIN,
    )

    topics = await list_topics(
        course_id=course.id,
        program_id=None,
        academic_term_id=None,
        grade_level=None,
        campus_id=None,
        is_active=None,
        session=db,
        principal=SUPERADMIN,
    )
    assert [t.id for t in topics] == [first.id, second.id, third.id]
    assert [t.sequence for t in topics] == [1, 2, 3]

    # Re-sequencing moves the topic in the returned order.
    await update_topic(
        topic_id=third.id,
        payload=SyllabusTopicUpdate(sequence=0),
        session=db,
        principal=SUPERADMIN,
    )
    reordered = await list_topics(
        course_id=course.id,
        program_id=None,
        academic_term_id=None,
        grade_level=None,
        campus_id=None,
        is_active=None,
        session=db,
        principal=SUPERADMIN,
    )
    assert [t.id for t in reordered] == [third.id, first.id, second.id]

    fetched = await get_topic(topic_id=first.id, session=db, principal=SUPERADMIN)
    assert fetched.title == "Linear Equations"

    await delete_topic(topic_id=second.id, session=db, principal=SUPERADMIN)
    with pytest.raises(HTTPException) as exc:
        await get_topic(topic_id=second.id, session=db, principal=SUPERADMIN)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_other_org_cannot_see_program_or_topic(db: AsyncSession, org, course):
    """A principal from another organisation sees nothing, and gets 404 by id."""
    program = await create_program(
        payload=ProgramCreate(name="FBISE Matric", code="FBISE-MAT"),
        session=db,
        principal=SUPERADMIN,
    )
    topic = await create_topic(
        payload=SyllabusTopicCreate(
            course_id=course.id, title="Chemical Bonding", sequence=1, program_id=program.id
        ),
        session=db,
        principal=SUPERADMIN,
    )

    # The owning org sees both.
    assert len(await list_programs(campus_id=None, is_active=None, session=db, principal=SUPERADMIN)) == 1
    assert (
        len(
            await list_topics(
                course_id=course.id,
                program_id=None,
                academic_term_id=None,
                grade_level=None,
                campus_id=None,
                is_active=None,
                session=db,
                principal=SUPERADMIN,
            )
        )
        == 1
    )

    # The other org sees neither.
    assert await list_programs(campus_id=None, is_active=None, session=db, principal=OTHER_ORG_ADMIN) == []
    assert (
        await list_topics(
            course_id=course.id,
            program_id=None,
            academic_term_id=None,
            grade_level=None,
            campus_id=None,
            is_active=None,
            session=db,
            principal=OTHER_ORG_ADMIN,
        )
        == []
    )

    for fetch in (
        lambda: get_program(program_id=program.id, session=db, principal=OTHER_ORG_ADMIN),
        lambda: get_topic(topic_id=topic.id, session=db, principal=OTHER_ORG_ADMIN),
    ):
        with pytest.raises(HTTPException) as exc:
            await fetch()
        assert exc.value.status_code == 404

    # And it cannot write to them either.
    for mutate in (
        lambda: update_program(
            program_id=program.id,
            payload=ProgramUpdate(name="Hijacked"),
            session=db,
            principal=OTHER_ORG_ADMIN,
        ),
        lambda: delete_topic(topic_id=topic.id, session=db, principal=OTHER_ORG_ADMIN),
    ):
        with pytest.raises(HTTPException) as exc:
            await mutate()
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_topic_cannot_be_pinned_to_another_orgs_program(db: AsyncSession, org, course):
    """`program_id` is checked against the caller's org, not just accepted."""
    with pytest.raises(HTTPException) as exc:
        await create_topic(
            payload=SyllabusTopicCreate(
                course_id=course.id, title="Orphan Topic", program_id=9999
            ),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_current_term_syllabus_topics(db: AsyncSession, org, course):
    """`course_id` + `academic_term_id` resolves the topics in scope right now."""
    campus = Campus(name="Main Campus", code="MAIN-01", org_id=org.id)
    db.add(campus)
    await db.commit()
    await db.refresh(campus)

    year = AcademicYear(name="2026-2027", campus_id=campus.id)
    db.add(year)
    await db.commit()
    await db.refresh(year)

    term1 = AcademicTerm(name="Term 1", academic_year_id=year.id)
    term2 = AcademicTerm(name="Term 2", academic_year_id=year.id)
    db.add(term1)
    db.add(term2)
    await db.commit()
    await db.refresh(term1)
    await db.refresh(term2)

    for title, seq, term, grade in (
        ("Number Systems", 1, term1, "Grade 9"),
        ("Algebra", 2, term1, "Grade 9"),
        ("Geometry", 1, term2, "Grade 9"),
        ("Statistics", 3, term1, "Grade 10"),
    ):
        await create_topic(
            payload=SyllabusTopicCreate(
                course_id=course.id,
                title=title,
                sequence=seq,
                academic_term_id=term.id,
                grade_level=grade,
            ),
            session=db,
            principal=SUPERADMIN,
        )

    def _list(term=None, grade=None):
        return list_topics(
            course_id=course.id,
            program_id=None,
            academic_term_id=term,
            grade_level=grade,
            campus_id=None,
            is_active=None,
            session=db,
            principal=SUPERADMIN,
        )

    term1_topics = await _list(term=term1.id)
    assert [t.title for t in term1_topics] == ["Number Systems", "Algebra", "Statistics"]

    # The "current term" query narrows by term AND grade together.
    current = await _list(term=term1.id, grade="Grade 9")
    assert [t.title for t in current] == ["Number Systems", "Algebra"]

    term2_topics = await _list(term=term2.id)
    assert [t.title for t in term2_topics] == ["Geometry"]


@pytest.mark.asyncio
async def test_program_campus_scoping(db: AsyncSession, org):
    """A campus-bound admin sees their own programs plus the org-wide ones."""
    campus_a = Campus(name="Campus A", code="CAMP-A", org_id=org.id)
    campus_b = Campus(name="Campus B", code="CAMP-B", org_id=org.id)
    db.add(campus_a)
    db.add(campus_b)
    await db.commit()
    await db.refresh(campus_a)
    await db.refresh(campus_b)

    org_wide = await create_program(
        payload=ProgramCreate(name="Cambridge IGCSE", code="IGCSE"),
        session=db,
        principal=SUPERADMIN,
    )
    campus_b_only = await create_program(
        payload=ProgramCreate(
            name="Campus B Vocational", code="CAMPB-VOC", campus_id=campus_b.id
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert org_wide.campus_id is None
    assert campus_b_only.campus_id == campus_b.id

    admin_a = principal("SCHOOL_ADMIN", user_id=3, org_id=org.id, campus_id=campus_a.id)

    # Their own campus's programs AND the org-wide ones -- not campus B's.
    assert [p.id for p in await list_programs(campus_id=None, is_active=None, session=db, principal=admin_a)] == [
        org_wide.id
    ]
    # Asking for another campus does not widen that; it is pinned, not refused.
    assert [
        p.id
        for p in await list_programs(
            campus_id=campus_b.id, is_active=None, session=db, principal=admin_a
        )
    ] == [org_wide.id]

    # Writing into another campus is refused outright.
    with pytest.raises(HTTPException) as exc:
        await create_program(
            payload=ProgramCreate(name="Sneaky", code="SNEAK", campus_id=campus_b.id),
            session=db,
            principal=admin_a,
        )
    assert exc.value.status_code == 403

    # Omitting the campus does NOT create an org-wide program: NULL is what
    # "every campus" means here, so it is pinned to the caller's own campus.
    pinned = await create_program(
        payload=ProgramCreate(name="Campus A Only", code="CAMPA-ONLY"),
        session=db,
        principal=admin_a,
    )
    assert pinned.campus_id == campus_a.id


@pytest.mark.asyncio
async def test_topic_campus_scoping(db: AsyncSession, org, course):
    """Two campuses can pace the same course differently; neither sees the other."""
    campus_a = Campus(name="Campus A", code="CAMP-A", org_id=org.id)
    campus_b = Campus(name="Campus B", code="CAMP-B", org_id=org.id)
    db.add(campus_a)
    db.add(campus_b)
    await db.commit()
    await db.refresh(campus_a)
    await db.refresh(campus_b)

    org_wide = await create_topic(
        payload=SyllabusTopicCreate(course_id=course.id, title="Number Systems", sequence=1),
        session=db,
        principal=SUPERADMIN,
    )
    only_a = await create_topic(
        payload=SyllabusTopicCreate(
            course_id=course.id, title="Algebra", sequence=2, campus_id=campus_a.id
        ),
        session=db,
        principal=SUPERADMIN,
    )
    only_b = await create_topic(
        payload=SyllabusTopicCreate(
            course_id=course.id, title="Geometry", sequence=3, campus_id=campus_b.id
        ),
        session=db,
        principal=SUPERADMIN,
    )

    def _list(as_principal, campus=None):
        return list_topics(
            course_id=course.id,
            program_id=None,
            academic_term_id=None,
            grade_level=None,
            campus_id=campus,
            is_active=None,
            session=db,
            principal=as_principal,
        )

    # A superadmin is not pinned to a campus, so they see the lot...
    assert {t.id for t in await _list(SUPERADMIN)} == {org_wide.id, only_a.id, only_b.id}
    # ...and can still ask for one campus: its topics plus the org-wide ones.
    assert {t.id for t in await _list(SUPERADMIN, campus=campus_b.id)} == {
        org_wide.id,
        only_b.id,
    }

    admin_a = principal("SCHOOL_ADMIN", user_id=3, org_id=org.id, campus_id=campus_a.id)
    assert {t.id for t in await _list(admin_a)} == {org_wide.id, only_a.id}
    assert {t.id for t in await _list(admin_a, campus=campus_b.id)} == {
        org_wide.id,
        only_a.id,
    }

    with pytest.raises(HTTPException) as exc:
        await create_topic(
            payload=SyllabusTopicCreate(
                course_id=course.id, title="Sneaky", campus_id=campus_b.id
            ),
            session=db,
            principal=admin_a,
        )
    assert exc.value.status_code == 403

    pinned = await create_topic(
        payload=SyllabusTopicCreate(course_id=course.id, title="Statistics", sequence=4),
        session=db,
        principal=admin_a,
    )
    assert pinned.campus_id == campus_a.id


@pytest.mark.asyncio
async def test_curriculum_endpoints_are_role_gated():
    """Students may not read or write the curriculum; staff may."""
    student = principal("STUDENT")

    with pytest.raises(HTTPException) as exc:
        await require_roles(WRITE_ROLES)(principal=student)
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        await require_roles(READ_ROLES)(principal=student)
    assert exc.value.status_code == 403

    # A teacher reads the syllabus but does not redefine it.
    teacher = principal("TEACHER")
    assert (await require_roles(READ_ROLES)(principal=teacher)).sub == teacher.sub
    with pytest.raises(HTTPException) as exc:
        await require_roles(WRITE_ROLES)(principal=teacher)
    assert exc.value.status_code == 403

    assert (await require_roles(WRITE_ROLES)(principal=STAFF)).sub == STAFF.sub


@pytest.mark.asyncio
async def test_unscoped_principal_is_refused(db: AsyncSession, org, course):
    """A principal attached to no school gets 403, not organisation 1's data."""
    unscoped = principal("SCHOOL_ADMIN", org_id=None)

    with pytest.raises(HTTPException) as exc:
        await list_programs(campus_id=None, is_active=None, session=db, principal=unscoped)
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        await create_topic(
            payload=SyllabusTopicCreate(course_id=course.id, title="Nowhere"),
            session=db,
            principal=unscoped,
        )
    assert exc.value.status_code == 403
