"""Grade changes must be recoverable and attributable.

`GradebookEntry` is uniquely constrained on (student_id, assessment_plan_id)
and updated IN PLACE, so before this existed a corrected mark destroyed the
previous one and `graded_by` named only the most recent grader. A parent
asking "this was 72 last week, who changed it to 41 and why?" had no answer
available anywhere in the system.

These tests pin the properties that make the trail an audit trail rather than
a log: the previous value survives, creation is distinguishable from change,
attribution follows the authenticated caller rather than the payload, and
nothing can rewrite it.
"""

import inspect

import pytest
from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import KeycloakUserPrincipal
from src.db.sms_gradebook import GradeChangeAction, GradeChangeEvent
from src.routers.sms_gradebook import (
    batch_enter_grades,
    create_assessment_plan,
    get_grade_history,
)
from src.schemas.sms_gradebook import (
    AssessmentPlanCreate,
    BatchGradebookEntryRequest,
    GradebookEntryInput,
)

# Acts as a school admin: these tests are about the TRAIL, not about who may
# write a grade (that is test_gradebook_authorization.py). user_id 77 is what
# attribution must resolve to.
_ADMIN = KeycloakUserPrincipal(
    sub="admin-fixture",
    org_id=1,
    campus_id=1,
    roles={"SCHOOL_ADMIN"},
    raw_claims={"lh_user_id": 77},
)


async def _make_plan(db: AsyncSession, *, course_id: int, section_id: int):
    return await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=course_id,
            section_id=section_id,
            academic_term_id=1,
            assessment_name="Midterm",
            weight_percentage=40.0,
            max_score=100.0,
        ),
        session=db,
        principal=_ADMIN,
    )


async def _events_for(db: AsyncSession, entry_id: int):
    return (
        await db.execute(
            select(GradeChangeEvent)
            .where(GradeChangeEvent.gradebook_entry_id == entry_id)
            .order_by(GradeChangeEvent.id)
        )
    ).scalars().all()


@pytest.mark.asyncio
async def test_changing_a_mark_preserves_the_previous_value(db: AsyncSession):
    """The whole point: 72 -> 41 must leave 72 recoverable."""
    plan = await _make_plan(db, course_id=901, section_id=901)

    await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan.id,
            entries=[GradebookEntryInput(student_id=7001, raw_score=72.0)],
        ),
        session=db,
        principal=_ADMIN,
    )
    changed = await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan.id,
            entries=[GradebookEntryInput(student_id=7001, raw_score=41.0)],
            reason="Re-marked after moderation",
        ),
        session=db,
        principal=_ADMIN,
    )

    events = await _events_for(db, changed[0].id)
    assert len(events) == 2

    correction = events[1]
    assert correction.action == GradeChangeAction.CHANGED
    assert correction.previous_raw_score == 72.0
    assert correction.new_raw_score == 41.0
    assert correction.reason == "Re-marked after moderation"
    # The live row keeps only the new mark -- which is exactly why the trail
    # has to exist.
    assert changed[0].raw_score == 41.0


@pytest.mark.asyncio
async def test_creation_is_distinguishable_from_change(db: AsyncSession):
    """A first mark and a correction are different facts."""
    plan = await _make_plan(db, course_id=902, section_id=902)

    created = await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan.id,
            entries=[GradebookEntryInput(student_id=7002, raw_score=55.0)],
        ),
        session=db,
        principal=_ADMIN,
    )

    events = await _events_for(db, created[0].id)
    assert len(events) == 1
    assert events[0].action == GradeChangeAction.CREATED
    # None, not 0.0 -- 0.0 is a real score a student can be given.
    assert events[0].previous_raw_score is None
    assert events[0].new_raw_score == 55.0


@pytest.mark.asyncio
async def test_attribution_follows_the_caller_not_the_payload(db: AsyncSession):
    """`graded_by` was client-supplied and forgeable. The trail must name the
    authenticated caller even when the body claims somebody else."""
    plan = await _make_plan(db, course_id=903, section_id=903)

    saved = await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan.id,
            entries=[GradebookEntryInput(student_id=7003, raw_score=60.0)],
            graded_by=999999,
        ),
        session=db,
        principal=_ADMIN,
    )

    events = await _events_for(db, saved[0].id)
    assert events[0].changed_by_user_id == 77, (
        "History must be attributed to the authenticated principal, never to "
        "the payload graded_by."
    )
    assert events[0].changed_by_user_id != 999999


@pytest.mark.asyncio
async def test_batch_entry_writes_history_for_every_row(db: AsyncSession):
    """A whole class is marked in one call; every row needs its own trail."""
    plan = await _make_plan(db, course_id=904, section_id=904)

    saved = await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan.id,
            entries=[
                GradebookEntryInput(student_id=7010, raw_score=90.0),
                GradebookEntryInput(student_id=7011, raw_score=45.0),
                GradebookEntryInput(student_id=7012, raw_score=0.0),
            ],
        ),
        session=db,
        principal=_ADMIN,
    )

    assert len(saved) == 3
    for entry in saved:
        events = await _events_for(db, entry.id)
        assert len(events) == 1, f"no history row for entry {entry.id}"
        assert events[0].action == GradeChangeAction.CREATED
        assert events[0].student_id == entry.student_id

    # A genuine zero is recorded as a zero, not conflated with "no mark".
    zero = [e for e in saved if e.student_id == 7012][0]
    assert (await _events_for(db, zero.id))[0].new_raw_score == 0.0


def test_history_is_append_only_no_endpoint_can_rewrite_it():
    """A trail that can be edited or deleted is not a trail.

    Asserts against the router's own route table rather than by trying calls:
    the guarantee is that no such endpoint EXISTS.
    """
    from src.routers.sms_gradebook import router

    for route in router.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if "history" in path:
            assert methods <= {"GET", "HEAD", "OPTIONS"}, (
                f"{path} exposes {methods}: grade history must be read-only."
            )


@pytest.mark.asyncio
async def test_repeated_corrections_accumulate_rather_than_overwrite(db: AsyncSession):
    """Three corrections leave four rows, in order, each naming its predecessor."""
    plan = await _make_plan(db, course_id=905, section_id=905)

    for score in (50.0, 60.0, 70.0, 80.0):
        saved = await batch_enter_grades(
            payload=BatchGradebookEntryRequest(
                assessment_plan_id=plan.id,
                entries=[GradebookEntryInput(student_id=7004, raw_score=score)],
            ),
            session=db,
            principal=_ADMIN,
        )

    events = await _events_for(db, saved[0].id)
    assert [e.new_raw_score for e in events] == [50.0, 60.0, 70.0, 80.0]
    assert [e.previous_raw_score for e in events] == [None, 50.0, 60.0, 70.0]


@pytest.mark.asyncio
async def test_history_endpoint_returns_the_trail_for_staff(db: AsyncSession):
    plan = await _make_plan(db, course_id=906, section_id=906)
    saved = await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan.id,
            entries=[GradebookEntryInput(student_id=7005, raw_score=65.0)],
        ),
        session=db,
        principal=_ADMIN,
    )

    result = await get_grade_history(entry_id=saved[0].id, session=db, principal=_ADMIN)
    assert result.gradebook_entry_id == saved[0].id
    assert result.student_id == 7005
    assert len(result.events) == 1


@pytest.mark.asyncio
async def test_history_for_an_unknown_entry_is_404(db: AsyncSession):
    with pytest.raises(HTTPException) as exc:
        await get_grade_history(entry_id=98765432, session=db, principal=_ADMIN)
    assert exc.value.status_code == 404


def test_students_and_parents_cannot_read_grade_history():
    """Staff-only by construction.

    The current grade is already visible to a student; the TRAIL names the
    individual member of staff behind each correction and may carry an
    internal reason. Disclosure is a conversation a school has with a family,
    not an API response.
    """
    from src.routers import sms_gradebook

    src = " ".join(
        repr(p.default)
        for p in inspect.signature(sms_gradebook.get_grade_history).parameters.values()
    )
    assert "require_roles" in src, "get_grade_history must be role-gated"
    assert "STUDENT" not in sms_gradebook._GRADING_STAFF
    assert "PARENT" not in sms_gradebook._GRADING_STAFF
