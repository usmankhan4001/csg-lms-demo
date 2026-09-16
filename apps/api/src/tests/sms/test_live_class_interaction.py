"""In-class polls and Q&A: who may answer, and what an empty result says.

The cases that matter are the refusals and the gaps. A poll nobody answered
has NO percentages, not 0% -- a share of zero answers is not a fact, and in a
classroom it reads as "the class got it wrong". A student who is not on the
roster, or is at another school, gets 404 rather than 403, so a class they
may not know about stays indistinguishable from one that does not exist.

Handlers are called directly, so FastAPI's dependency injection never runs and
`require_roles` is not exercised -- the same trade-off as
test_live_class_module.py. The per-class host/enrolment rules ARE exercised,
because that is where the real authorisation lives. The role gate itself is
pinned by the two tests at the bottom, which go through a real app.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, get_current_user_principal
from src.db.sms_campus import AcademicYear, Campus, ClassSection, StudentEnrollment
from src.db.sms_live_class import LiveClassSession
from src.db.sms_live_class_interaction import (
    LiveClassPoll,
    LiveClassPollResponse,
    LiveClassQuestion,
    LiveClassQuestionUpvote,
    LivePollStatus,
)
from src.routers.sms_live_class_interaction import (
    CreatePollRequest,
    CreateQuestionRequest,
    PollOptionCreate,
    PollResponseCreate,
    ResolveQuestionRequest,
    activate_poll,
    ask_question,
    close_poll,
    create_poll,
    get_poll,
    list_polls,
    list_questions,
    resolve_question,
    respond_to_poll,
    router as interaction_router,
    upvote_question,
)
from src.services.sms.live_class_interaction import tally_poll

SECTION_ID = 5
TEACHER_ID = 101
STUDENT_ID = 501
CAMPUS_ID = 1
ORG_ID = 1


def _principal(user_id: int, roles=(), org_id=ORG_ID, campus_id=None):
    """A resolved principal -- see the note in test_live_classes.py."""
    return SimpleNamespace(
        is_superadmin=False,
        org_id=org_id,
        campus_id=campus_id,
        has_role=lambda r: r in roles,
        has_any_role=lambda wanted: any(r in roles for r in wanted),
        raw_claims={"lh_user_id": user_id},
    )


def _host(user_id: int = TEACHER_ID, **kwargs) -> SimpleNamespace:
    return _principal(user_id, roles=("TEACHER",), **kwargs)


def _student(user_id: int = STUDENT_ID, **kwargs) -> SimpleNamespace:
    return _principal(user_id, roles=("STUDENT",), **kwargs)


async def _school(
    db: AsyncSession,
    campus_id: int = CAMPUS_ID,
    org_id: int = ORG_ID,
    section_id: int = SECTION_ID,
    teacher_id: int = TEACHER_ID,
) -> None:
    """A campus, academic year and section for a class to belong to."""
    if await db.get(Campus, campus_id) is None:
        db.add(
            Campus(
                id=campus_id,
                org_id=org_id,
                name=f"Campus {campus_id}",
                code=f"C{campus_id}",
            )
        )
    if await db.get(AcademicYear, campus_id) is None:
        db.add(AcademicYear(id=campus_id, campus_id=campus_id, name="2026-2027"))
    if await db.get(ClassSection, section_id) is None:
        db.add(
            ClassSection(
                id=section_id,
                campus_id=campus_id,
                grade_level="Grade 9",
                section_name="A",
                class_teacher_id=teacher_id,
            )
        )
    await db.commit()


async def _enrol(
    db: AsyncSession, student_id: int, section_id: int = SECTION_ID, status: str = "active"
) -> None:
    db.add(
        StudentEnrollment(
            student_id=student_id,
            section_id=section_id,
            academic_year_id=1,
            status=status,
        )
    )
    await db.commit()


async def _class(
    db: AsyncSession, room_name: str = "math-101", section_id=SECTION_ID, teacher_id=TEACHER_ID
) -> LiveClassSession:
    live = LiveClassSession(
        title=room_name,
        teacher_id=teacher_id,
        section_id=section_id,
        room_name=room_name,
    )
    db.add(live)
    await db.commit()
    await db.refresh(live)
    return live


async def _open_poll(
    db: AsyncSession, class_id: int, question: str = "Identify the phase:"
) -> "LiveClassPoll":
    """A poll the host has created and put to the class."""
    poll_read = await create_poll(
        class_id=class_id,
        payload=CreatePollRequest(
            question=question,
            options=[PollOptionCreate(text="Metaphase"), PollOptionCreate(text="Telophase")],
        ),
        session=db,
        principal=_host(),
    )
    await activate_poll(poll_id=poll_read.id, session=db, principal=_host())
    return await db.get(LiveClassPoll, poll_read.id)


# ── Percentages ─────────────────────────────────────────────────────────────


def test_a_poll_nobody_answered_has_no_percentages():
    """The standing rule: absence of data is never rendered as a value."""
    tally = tally_poll({1: 0, 2: 0})
    assert tally.total_responses == 0
    assert tally.percentage_for(1) is None
    assert tally.percentage_for(2) is None


def test_percentages_are_computed_from_the_answers_that_exist():
    tally = tally_poll({1: 3, 2: 1})
    assert tally.total_responses == 4
    assert tally.percentage_for(1) == 75.0
    assert tally.percentage_for(2) == 25.0


@pytest.mark.asyncio
async def test_a_poll_with_no_responses_reports_no_percentages(db: AsyncSession):
    """A closed poll nobody answered: counts of zero, and NO percentages."""
    await _school(db)
    await _enrol(db, STUDENT_ID)
    live = await _class(db)
    poll = await _open_poll(db, live.id)
    await close_poll(poll_id=poll.id, session=db, principal=_host())

    host_view = await get_poll(poll_id=poll.id, session=db, principal=_host())
    assert host_view.results is not None
    assert host_view.results.total_responses == 0
    assert [o.percentage for o in host_view.results.options] == [None, None]
    assert [o.response_count for o in host_view.results.options] == [0, 0]

    # And the class sees the same honest gap, not a wall of zeroes.
    student_view = await get_poll(poll_id=poll.id, session=db, principal=_student())
    assert student_view.results is not None
    assert [o.percentage for o in student_view.results.options] == [None, None]


@pytest.mark.asyncio
async def test_percentages_appear_once_somebody_answers(db: AsyncSession):
    await _school(db)
    await _enrol(db, STUDENT_ID)
    await _enrol(db, 502)
    live = await _class(db)
    poll = await _open_poll(db, live.id)

    first = (await get_poll(poll_id=poll.id, session=db, principal=_host())).options[0].id
    await respond_to_poll(
        poll_id=poll.id,
        payload=PollResponseCreate(option_id=first),
        session=db,
        principal=_student(),
    )
    await close_poll(poll_id=poll.id, session=db, principal=_host())

    view = await get_poll(poll_id=poll.id, session=db, principal=_student())
    assert view.results is not None
    assert view.results.total_responses == 1
    assert view.results.options[0].percentage == 100.0
    assert view.results.options[1].percentage == 0.0


# ── Who may answer a poll ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_enrolled_student_can_answer_a_poll(db: AsyncSession):
    await _school(db)
    await _enrol(db, STUDENT_ID)
    live = await _class(db)
    poll = await _open_poll(db, live.id)
    option_id = (
        await get_poll(poll_id=poll.id, session=db, principal=_host())
    ).options[1].id

    view = await respond_to_poll(
        poll_id=poll.id,
        payload=PollResponseCreate(option_id=option_id),
        session=db,
        principal=_student(),
    )
    assert view.my_option_id == option_id

    stored = (
        await db.execute(
            select(LiveClassPollResponse).where(
                LiveClassPollResponse.poll_id == poll.id
            )
        )
    ).scalars().all()
    assert [r.student_user_id for r in stored] == [STUDENT_ID]
    assert [(r.org_id, r.campus_id) for r in stored] == [(ORG_ID, CAMPUS_ID)]


@pytest.mark.asyncio
async def test_a_student_not_on_the_roster_cannot_answer(db: AsyncSession):
    """Same school, same campus, not enrolled: the STUDENT role is not
    membership."""
    await _school(db)
    await _enrol(db, STUDENT_ID)
    live = await _class(db)
    poll = await _open_poll(db, live.id)
    option_id = (await get_poll(poll_id=poll.id, session=db, principal=_host())).options[0].id

    with pytest.raises(HTTPException) as exc:
        await respond_to_poll(
            poll_id=poll.id,
            payload=PollResponseCreate(option_id=option_id),
            session=db,
            principal=_student(user_id=502),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_a_student_at_another_school_cannot_answer(db: AsyncSession):
    await _school(db)
    await _school(db, campus_id=2, org_id=2, section_id=6, teacher_id=201)
    await _enrol(db, STUDENT_ID)
    await _enrol(db, 601, section_id=6)
    live = await _class(db)
    poll = await _open_poll(db, live.id)
    option_id = (await get_poll(poll_id=poll.id, session=db, principal=_host())).options[0].id

    with pytest.raises(HTTPException) as exc:
        await respond_to_poll(
            poll_id=poll.id,
            payload=PollResponseCreate(option_id=option_id),
            session=db,
            principal=_student(user_id=601, org_id=2),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_a_second_answer_to_the_same_poll_is_refused(db: AsyncSession):
    """One student, one answer: otherwise one child moves the result."""
    await _school(db)
    await _enrol(db, STUDENT_ID)
    live = await _class(db)
    poll = await _open_poll(db, live.id)
    options = (await get_poll(poll_id=poll.id, session=db, principal=_host())).options

    await respond_to_poll(
        poll_id=poll.id,
        payload=PollResponseCreate(option_id=options[0].id),
        session=db,
        principal=_student(),
    )
    with pytest.raises(HTTPException) as exc:
        await respond_to_poll(
            poll_id=poll.id,
            payload=PollResponseCreate(option_id=options[1].id),
            session=db,
            principal=_student(),
        )
    assert exc.value.status_code == 409

    stored = (
        await db.execute(
            select(LiveClassPollResponse).where(
                LiveClassPollResponse.poll_id == poll.id
            )
        )
    ).scalars().all()
    assert len(stored) == 1


@pytest.mark.asyncio
async def test_an_answer_to_a_closed_poll_is_refused(db: AsyncSession):
    await _school(db)
    await _enrol(db, STUDENT_ID)
    live = await _class(db)
    poll = await _open_poll(db, live.id)
    option_id = (await get_poll(poll_id=poll.id, session=db, principal=_host())).options[0].id
    await close_poll(poll_id=poll.id, session=db, principal=_host())

    with pytest.raises(HTTPException) as exc:
        await respond_to_poll(
            poll_id=poll.id,
            payload=PollResponseCreate(option_id=option_id),
            session=db,
            principal=_student(),
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_the_host_does_not_get_a_vote_in_their_own_poll(db: AsyncSession):
    await _school(db)
    live = await _class(db)
    poll = await _open_poll(db, live.id)
    option_id = (await get_poll(poll_id=poll.id, session=db, principal=_host())).options[0].id

    with pytest.raises(HTTPException) as exc:
        await respond_to_poll(
            poll_id=poll.id,
            payload=PollResponseCreate(option_id=option_id),
            session=db,
            principal=_host(),
        )
    assert exc.value.status_code == 403


# ── Who may run a poll ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_only_the_host_can_close_a_poll(db: AsyncSession):
    await _school(db)
    await _enrol(db, STUDENT_ID)
    live = await _class(db)
    poll = await _open_poll(db, live.id)

    # A colleague: same school, but not this class's teacher.
    with pytest.raises(HTTPException) as exc:
        await close_poll(poll_id=poll.id, session=db, principal=_host(user_id=999))
    assert exc.value.status_code == 403

    # And a student in the class.
    with pytest.raises(HTTPException) as exc:
        await close_poll(poll_id=poll.id, session=db, principal=_student())
    assert exc.value.status_code == 403

    assert (await db.get(LiveClassPoll, poll.id)).status == LivePollStatus.ACTIVE

    closed = await close_poll(poll_id=poll.id, session=db, principal=_host())
    assert closed.status == LivePollStatus.CLOSED
    assert closed.closed_at is not None


@pytest.mark.asyncio
async def test_a_school_admin_may_close_a_poll_they_do_not_teach(db: AsyncSession):
    """A school needs someone able to step in when a teacher cannot."""
    await _school(db)
    live = await _class(db)
    poll = await _open_poll(db, live.id)

    admin = _principal(900, roles=("SCHOOL_ADMIN",))
    closed = await close_poll(poll_id=poll.id, session=db, principal=admin)
    assert closed.status == LivePollStatus.CLOSED


@pytest.mark.asyncio
async def test_students_do_not_see_results_while_a_poll_is_open(db: AsyncSession):
    """The visibility decision: the class sees results once it is closed, and
    not before -- counts included, since a percentage is arithmetic over a
    count."""
    await _school(db)
    await _enrol(db, STUDENT_ID)
    live = await _class(db)
    poll = await _open_poll(db, live.id)
    option_id = (await get_poll(poll_id=poll.id, session=db, principal=_host())).options[0].id
    await respond_to_poll(
        poll_id=poll.id,
        payload=PollResponseCreate(option_id=option_id),
        session=db,
        principal=_student(),
    )

    during = await get_poll(poll_id=poll.id, session=db, principal=_student())
    assert during.results is None
    # They can still see their own answer.
    assert during.my_option_id == option_id

    # The host is not blinded: they have to decide what to re-teach.
    host_during = await get_poll(poll_id=poll.id, session=db, principal=_host())
    assert host_during.results is not None
    assert host_during.results.total_responses == 1

    await close_poll(poll_id=poll.id, session=db, principal=_host())
    after = await get_poll(poll_id=poll.id, session=db, principal=_student())
    assert after.results is not None
    assert after.results.total_responses == 1


@pytest.mark.asyncio
async def test_a_draft_poll_is_not_visible_to_the_class(db: AsyncSession):
    await _school(db)
    await _enrol(db, STUDENT_ID)
    live = await _class(db)
    created = await create_poll(
        class_id=live.id,
        payload=CreatePollRequest(
            question="Not ready yet?",
            options=[PollOptionCreate(text="Yes"), PollOptionCreate(text="No")],
        ),
        session=db,
        principal=_host(),
    )

    assert [p.id for p in await list_polls(class_id=live.id, session=db, principal=_student())] == []
    assert [p.id for p in await list_polls(class_id=live.id, session=db, principal=_host())] == [
        created.id
    ]


# ── Q&A ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_upvote_is_one_per_student(db: AsyncSession):
    await _school(db)
    await _enrol(db, STUDENT_ID)
    live = await _class(db)
    asked = await ask_question(
        class_id=live.id,
        payload=CreateQuestionRequest(body="Is ATP consumed during anaphase?"),
        session=db,
        principal=_student(),
    )

    first = await upvote_question(
        question_id=asked.id, session=db, principal=_student()
    )
    assert first.upvote_count == 1
    assert first.has_upvoted is True

    with pytest.raises(HTTPException) as exc:
        await upvote_question(question_id=asked.id, session=db, principal=_student())
    assert exc.value.status_code == 409

    stored = (
        await db.execute(
            select(LiveClassQuestionUpvote).where(
                LiveClassQuestionUpvote.question_id == asked.id
            )
        )
    ).scalars().all()
    assert len(stored) == 1
    assert [(v.org_id, v.campus_id) for v in stored] == [(ORG_ID, CAMPUS_ID)]


@pytest.mark.asyncio
async def test_a_second_students_upvote_counts(db: AsyncSession):
    await _school(db)
    await _enrol(db, STUDENT_ID)
    await _enrol(db, 502)
    live = await _class(db)
    asked = await ask_question(
        class_id=live.id,
        payload=CreateQuestionRequest(body="Is ATP consumed during anaphase?"),
        session=db,
        principal=_student(),
    )
    await upvote_question(question_id=asked.id, session=db, principal=_student())
    view = await upvote_question(question_id=asked.id, session=db, principal=_student(502))
    assert view.upvote_count == 2


@pytest.mark.asyncio
async def test_a_student_at_another_school_cannot_upvote(db: AsyncSession):
    await _school(db)
    await _school(db, campus_id=2, org_id=2, section_id=6, teacher_id=201)
    await _enrol(db, STUDENT_ID)
    await _enrol(db, 601, section_id=6)
    live = await _class(db)
    asked = await ask_question(
        class_id=live.id,
        payload=CreateQuestionRequest(body="Is ATP consumed during anaphase?"),
        session=db,
        principal=_student(),
    )

    with pytest.raises(HTTPException) as exc:
        await upvote_question(
            question_id=asked.id, session=db, principal=_student(user_id=601, org_id=2)
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_the_thread_is_ordered_by_upvotes(db: AsyncSession):
    await _school(db)
    await _enrol(db, STUDENT_ID)
    await _enrol(db, 502)
    live = await _class(db)
    quiet = await ask_question(
        class_id=live.id,
        payload=CreateQuestionRequest(body="Quiet one"),
        session=db,
        principal=_student(),
    )
    popular = await ask_question(
        class_id=live.id,
        payload=CreateQuestionRequest(body="Popular one"),
        session=db,
        principal=_student(502),
    )
    await upvote_question(question_id=popular.id, session=db, principal=_student())
    await upvote_question(question_id=popular.id, session=db, principal=_student(502))

    thread = await list_questions(class_id=live.id, session=db, principal=_student())
    assert [q.id for q in thread] == [popular.id, quiet.id]
    assert thread[0].upvote_count == 2


@pytest.mark.asyncio
async def test_only_the_host_can_resolve_a_question(db: AsyncSession):
    await _school(db)
    await _enrol(db, STUDENT_ID)
    live = await _class(db)
    asked = await ask_question(
        class_id=live.id,
        payload=CreateQuestionRequest(body="Is ATP consumed during anaphase?"),
        session=db,
        principal=_student(),
    )

    with pytest.raises(HTTPException) as exc:
        await resolve_question(
            question_id=asked.id,
            payload=ResolveQuestionRequest(resolved=True),
            session=db,
            principal=_student(),
        )
    assert exc.value.status_code == 403

    resolved = await resolve_question(
        question_id=asked.id,
        payload=ResolveQuestionRequest(resolved=True),
        session=db,
        principal=_host(),
    )
    assert resolved.is_resolved is True
    assert resolved.resolved_by_user_id == TEACHER_ID
    assert resolved.resolved_at is not None


@pytest.mark.asyncio
async def test_an_anonymous_question_hides_its_author_from_the_class(db: AsyncSession):
    """Anonymous to the class, not to the host: a school has to be able to
    find out who posted abuse."""
    await _school(db)
    await _enrol(db, STUDENT_ID)
    await _enrol(db, 502)
    live = await _class(db)
    asked = await ask_question(
        class_id=live.id,
        payload=CreateQuestionRequest(body="Is this on the test?", is_anonymous=True),
        session=db,
        principal=_student(),
    )

    stored = await db.get(LiveClassQuestion, asked.id)
    assert stored.author_user_id == STUDENT_ID

    thread = await list_questions(class_id=live.id, session=db, principal=_student(502))
    assert thread[0].author_user_id is None

    host_thread = await list_questions(class_id=live.id, session=db, principal=_host())
    assert host_thread[0].author_user_id == STUDENT_ID


@pytest.mark.asyncio
async def test_a_class_with_no_section_has_no_roster_to_poll(db: AsyncSession):
    """No section means no tenancy and no roster. Refuse rather than invent."""
    live = await _class(db, room_name="ad-hoc", section_id=None)

    with pytest.raises(HTTPException) as exc:
        await create_poll(
            class_id=live.id,
            payload=CreatePollRequest(
                question="Anyone there?",
                options=[PollOptionCreate(text="Yes"), PollOptionCreate(text="No")],
            ),
            session=db,
            principal=_host(),
        )
    assert exc.value.status_code == 400


# ── The role gate itself (through a real app, so DI runs) ────────────────────


@pytest.fixture
def app(db):
    application = FastAPI()
    application.include_router(interaction_router, prefix="/live")
    application.dependency_overrides[get_db_session] = lambda: db
    yield application
    application.dependency_overrides.clear()


def _real_principal(user_id: int, roles, org_id=ORG_ID, campus_id=None):
    return KeycloakUserPrincipal(
        sub=f"user-{user_id}",
        email=f"user{user_id}@test.local",
        org_id=org_id,
        campus_id=campus_id,
        realm_roles=list(roles),
        roles=set(roles),
        raw_claims={"lh_user_id": user_id},
    )


@pytest.mark.asyncio
async def test_a_student_cannot_create_a_poll(app, db):
    await _school(db)
    live = await _class(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _real_principal(
        STUDENT_ID, ("STUDENT",)
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/live/classes/{live.id}/polls",
            json={
                "question": "Identify the phase:",
                "options": [{"text": "Metaphase"}, {"text": "Telophase"}],
            },
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_the_host_can_create_a_poll_through_the_app(app, db):
    await _school(db)
    live = await _class(db)
    app.dependency_overrides[get_current_user_principal] = lambda: _real_principal(
        TEACHER_ID, ("TEACHER",)
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/live/classes/{live.id}/polls",
            json={
                "question": "Identify the phase:",
                "options": [{"text": "Metaphase"}, {"text": "Telophase"}],
            },
        )
    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"
    assert [o["text"] for o in response.json()["options"]] == ["Metaphase", "Telophase"]
