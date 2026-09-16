"""
In-class polls and Q&A for a live class.

The sidebar in PROJECT_DOCS/09_EXPANDED_SYSTEM_ARCHITECTURE_AND_LIVE_CLASSES.md
§5 -- a poll with percentages, and a Q&A thread with upvotes -- needs a store
and a set of rules. This is it.

WHO MAY DO WHAT
---------------
  * Host (the session's own teacher, or a school/super admin) creates,
    activates and closes polls, and resolves questions. Being a TEACHER is
    not permission over another teacher's class; the check is per class.
  * A student ACTIVELY ENROLLED in the section the class belongs to may
    answer a poll, ask a question and upvote. Holding the STUDENT role is
    not membership: a student at this school is not entitled into every
    classroom in it.
  * Nobody else. An unentitled caller gets 404, never 403 -- a class they may
    not know about is indistinguishable from one that does not exist.

That is the same rule `live_classes.py` applies to handing out a room token
(`_assert_may_enter_room` / `_caller_is_enrolled`). It is restated here rather
than imported: those helpers are private to a router this one must not edit,
and a cross-router import of a private name is the kind of coupling that
breaks silently. The rule is mirrored, not shared.

TENANCY
-------
`LiveClassSession` has no org/campus columns, so both are derived
section -> campus -> org on every request and stamped onto every row written.
Nothing in a request body is ever believed for identity, privilege or tenant.

LIVE RESULTS
------------
Students do NOT see results while a poll is ACTIVE; they see them once it is
CLOSED. Counts are withheld too, not just percentages -- a percentage is
arithmetic over a count, so publishing the count publishes the percentage
anyway. The reason is the setting: these are children, and a live bar chart
of how the room is answering turns a check of understanding into a
bandwagon, and puts a child's answer under an audience in real time. The
host sees results throughout, because the host is the one who has to decide
what to re-teach.

Mounted under the same "/live" prefix as live_classes.router -- see router.py.
"""

import datetime
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_campus import Campus, ClassSection, StudentEnrollment
from src.db.sms_live_class import LiveClassSession
from src.db.sms_live_class_interaction import (
    LiveClassPoll,
    LiveClassPollOption,
    LiveClassPollResponse,
    LiveClassQuestion,
    LiveClassQuestionUpvote,
    LivePollStatus,
)
from src.security.school_ownership import (
    get_user_id,
    require_org_id,
    require_user_id,
    resolve_scoped_campus_id,
)
from src.services.sms.live_class_interaction import tally_poll

router = APIRouter()

# Same gate live_classes.py applies to running a class: being staff is not
# permission over every class in the school, so host rights are checked per
# class below.
_CLASS_STAFF = ["SUPER_ADMIN", "SCHOOL_ADMIN", "TEACHER"]

# Roles that may host a class besides its own teacher. A school needs someone
# able to step in when a teacher cannot.
_HOST_ROLES = ("SUPER_ADMIN", "SCHOOL_ADMIN")


# ── Request / response shapes ────────────────────────────────────────────────


class PollOptionCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=300)


class CreatePollRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    options: List[PollOptionCreate] = Field(..., min_length=2, max_length=10)


class PollResponseCreate(BaseModel):
    option_id: int


class PollOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    position: int


class PollOptionResultRead(PollOptionRead):
    """An option plus what the class answered.

    `percentage` is None when nobody has answered -- see
    services/sms/live_class_interaction.py. It is never 0.0 as a stand-in for
    "no answers".
    """

    response_count: int
    percentage: Optional[float] = None


class PollResultsRead(BaseModel):
    total_responses: int
    options: List[PollOptionResultRead]


class PollRead(BaseModel):
    id: int
    session_id: int
    question: str
    status: LivePollStatus
    created_by_user_id: int
    activated_at: Optional[datetime.datetime] = None
    closed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    options: List[PollOptionRead]
    # None means "not shown to this caller" -- a student while the poll is
    # still open. Not an empty result: an empty result is a real answer of
    # "nobody responded", and this is the absence of an answer.
    results: Optional[PollResultsRead] = None
    # The caller's own answer, which they may see even when the class's
    # results are still hidden.
    my_option_id: Optional[int] = None
    can_manage: bool = False


class CreateQuestionRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)
    is_anonymous: bool = False


class ResolveQuestionRequest(BaseModel):
    resolved: bool = True


class QuestionRead(BaseModel):
    id: int
    session_id: int
    body: str
    is_anonymous: bool
    is_resolved: bool
    resolved_by_user_id: Optional[int] = None
    resolved_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    # None for an anonymous question -- anonymous to the class, not to the
    # host, who has to be able to moderate it.
    author_user_id: Optional[int] = None
    upvote_count: int = 0
    has_upvoted: bool = False
    can_manage: bool = False


# ── Authorisation ────────────────────────────────────────────────────────────


def _not_found() -> HTTPException:
    """A class the caller is not entitled to is indistinguishable from one
    that does not exist -- never 403, which would confirm it is real."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Live class not found"
    )


async def _load_class_or_404(session: AsyncSession, class_id: int) -> LiveClassSession:
    live = (
        await session.execute(
            select(LiveClassSession).where(LiveClassSession.id == class_id)
        )
    ).scalar_one_or_none()
    if live is None:
        raise _not_found()
    return live


async def _load_poll_or_404(session: AsyncSession, poll_id: int) -> LiveClassPoll:
    poll = (
        await session.execute(select(LiveClassPoll).where(LiveClassPoll.id == poll_id))
    ).scalar_one_or_none()
    if poll is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Poll not found"
        )
    return poll


async def _load_question_or_404(
    session: AsyncSession, question_id: int
) -> LiveClassQuestion:
    question = (
        await session.execute(
            select(LiveClassQuestion).where(LiveClassQuestion.id == question_id)
        )
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Question not found"
        )
    return question


async def _class_tenancy(
    session: AsyncSession, live: LiveClassSession
) -> Tuple[int, int]:
    """The (org_id, campus_id) this class belongs to.

    Derived section -> campus -> org, the same way live_classes.py does it.
    A class with no section has no roster, so there is nobody to poll and
    nobody to ask a question: refusing beats writing a row whose tenant is
    unknown.
    """
    if live.section_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This live class is not attached to a section, so it has no "
                "roster: there is nobody to poll and nobody to ask."
            ),
        )
    row = (
        await session.execute(
            select(ClassSection.campus_id, Campus.org_id)
            .join(Campus, Campus.id == ClassSection.campus_id)
            .where(ClassSection.id == live.section_id)
        )
    ).first()
    if row is None:
        raise _not_found()
    return row[1], row[0]


def _assert_in_scope(
    principal: KeycloakUserPrincipal, org_id: int, campus_id: int
) -> None:
    """Refuse a class belonging to another school, or another campus of it."""
    if principal.is_superadmin:
        return
    if require_org_id(principal) != org_id:
        raise _not_found()
    if resolve_scoped_campus_id(principal, campus_id) != campus_id:
        raise _not_found()


def _caller_is_host(
    principal: KeycloakUserPrincipal, live: LiveClassSession
) -> bool:
    """Host rights follow from who the caller IS, never from the payload."""
    if principal.is_superadmin or principal.has_any_role(list(_HOST_ROLES)):
        return True
    caller_id = get_user_id(principal)
    return caller_id is not None and caller_id == live.teacher_id


async def _caller_is_enrolled(
    session: AsyncSession, live: LiveClassSession, student_user_id: Optional[int]
) -> bool:
    """Active enrolment in the section this class belongs to.

    Mirrors `_caller_is_enrolled` in live_classes.py: the STUDENT role is not
    membership, and a class with no section has no roster to test against.
    """
    if live.section_id is None or student_user_id is None:
        return False
    row = (
        await session.execute(
            select(StudentEnrollment.id).where(
                and_(
                    StudentEnrollment.section_id == live.section_id,
                    StudentEnrollment.student_id == student_user_id,
                    StudentEnrollment.status == "active",
                )
            )
        )
    ).first()
    return row is not None


async def _class_for_member(
    session: AsyncSession, principal: KeycloakUserPrincipal, class_id: int
) -> Tuple[LiveClassSession, int, int, bool]:
    """(class, org_id, campus_id, is_host) for a caller entitled to be in the
    room: its host, or a student enrolled in its section. Everyone else 404s.
    """
    live = await _load_class_or_404(session, class_id)
    org_id, campus_id = await _class_tenancy(session, live)
    _assert_in_scope(principal, org_id, campus_id)
    if _caller_is_host(principal, live):
        return live, org_id, campus_id, True
    if await _caller_is_enrolled(session, live, get_user_id(principal)):
        return live, org_id, campus_id, False
    raise _not_found()


async def _class_for_host(
    session: AsyncSession, principal: KeycloakUserPrincipal, class_id: int
) -> Tuple[LiveClassSession, int, int]:
    """The class, for a caller who may run it.

    Deliberately NOT `_class_for_member` plus a host check: that would 404 a
    colleague who is entitled to know the class exists but may not run it,
    which is a 403 -- the answer `live_classes.py` already gives a
    non-host teacher for the same question.
    """
    live = await _load_class_or_404(session, class_id)
    org_id, campus_id = await _class_tenancy(session, live)
    _assert_in_scope(principal, org_id, campus_id)
    if not _caller_is_host(principal, live):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only this class's teacher or a school administrator may manage it.",
        )
    return live, org_id, campus_id


async def _assert_enrolled_student(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    live: LiveClassSession,
) -> int:
    """The caller must be a student on this class's roster, not merely
    someone allowed in the room -- the host does not get a vote in their own
    poll, and a colleague sitting in does not either."""
    student_id = require_user_id(principal)
    if not await _caller_is_enrolled(session, live, student_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a student enrolled in this class's section may do that.",
        )
    return student_id


# ── Read assembly ────────────────────────────────────────────────────────────


async def _poll_read(
    session: AsyncSession,
    poll: LiveClassPoll,
    principal: KeycloakUserPrincipal,
    *,
    is_host: bool,
) -> PollRead:
    options = (
        await session.execute(
            select(LiveClassPollOption)
            .where(LiveClassPollOption.poll_id == poll.id)
            .order_by(LiveClassPollOption.position)
        )
    ).scalars().all()

    counted = (
        await session.execute(
            select(LiveClassPollResponse.option_id, func.count(LiveClassPollResponse.id))
            .where(LiveClassPollResponse.poll_id == poll.id)
            .group_by(LiveClassPollResponse.option_id)
        )
    ).all()
    counts: Dict[int, int] = {option_id: count for option_id, count in counted}
    tally = tally_poll({option.id: counts.get(option.id, 0) for option in options})

    caller_id = get_user_id(principal)
    my_option_id: Optional[int] = None
    if caller_id is not None:
        my_option_id = (
            await session.execute(
                select(LiveClassPollResponse.option_id).where(
                    and_(
                        LiveClassPollResponse.poll_id == poll.id,
                        LiveClassPollResponse.student_user_id == caller_id,
                    )
                )
            )
        ).scalar_one_or_none()

    # See the module docstring: the host always sees results, the class sees
    # them once the poll is closed.
    results: Optional[PollResultsRead] = None
    if is_host or poll.status == LivePollStatus.CLOSED:
        results = PollResultsRead(
            total_responses=tally.total_responses,
            options=[
                PollOptionResultRead(
                    id=option.id,
                    text=option.text,
                    position=option.position,
                    response_count=counts.get(option.id, 0),
                    percentage=tally.percentage_for(option.id),
                )
                for option in options
            ],
        )

    return PollRead(
        id=poll.id,
        session_id=poll.session_id,
        question=poll.question,
        status=poll.status,
        created_by_user_id=poll.created_by_user_id,
        activated_at=poll.activated_at,
        closed_at=poll.closed_at,
        created_at=poll.created_at,
        options=[
            PollOptionRead(id=option.id, text=option.text, position=option.position)
            for option in options
        ],
        results=results,
        my_option_id=my_option_id,
        can_manage=is_host,
    )


async def _question_read(
    session: AsyncSession,
    question: LiveClassQuestion,
    principal: KeycloakUserPrincipal,
    *,
    is_host: bool,
    upvote_count: Optional[int] = None,
    has_upvoted: Optional[bool] = None,
) -> QuestionRead:
    if upvote_count is None:
        upvote_count = (
            await session.execute(
                select(func.count(LiveClassQuestionUpvote.id)).where(
                    LiveClassQuestionUpvote.question_id == question.id
                )
            )
        ).scalar_one()

    caller_id = get_user_id(principal)
    if has_upvoted is None:
        has_upvoted = False
        if caller_id is not None:
            has_upvoted = (
                await session.execute(
                    select(LiveClassQuestionUpvote.id).where(
                        and_(
                            LiveClassQuestionUpvote.question_id == question.id,
                            LiveClassQuestionUpvote.student_user_id == caller_id,
                        )
                    )
                )
            ).scalar_one_or_none() is not None

    return QuestionRead(
        id=question.id,
        session_id=question.session_id,
        body=question.body,
        is_anonymous=question.is_anonymous,
        is_resolved=question.is_resolved,
        resolved_by_user_id=question.resolved_by_user_id,
        resolved_at=question.resolved_at,
        created_at=question.created_at,
        # Anonymous to the class, not to the host who has to moderate it.
        author_user_id=(
            question.author_user_id
            if (not question.is_anonymous or is_host)
            else None
        ),
        upvote_count=upvote_count,
        has_upvoted=has_upvoted,
        can_manage=is_host,
    )


async def _question_reads(
    session: AsyncSession,
    questions: List[LiveClassQuestion],
    principal: KeycloakUserPrincipal,
    *,
    is_host: bool,
) -> List[QuestionRead]:
    """The thread, most-upvoted first.

    Counts and the caller's own upvotes are read in two queries rather than
    per question, so a busy thread is not an N+1.
    """
    if not questions:
        return []
    question_ids = [q.id for q in questions]

    counted = (
        await session.execute(
            select(
                LiveClassQuestionUpvote.question_id,
                func.count(LiveClassQuestionUpvote.id),
            )
            .where(LiveClassQuestionUpvote.question_id.in_(question_ids))
            .group_by(LiveClassQuestionUpvote.question_id)
        )
    ).all()
    counts: Dict[int, int] = {qid: count for qid, count in counted}

    caller_id = get_user_id(principal)
    mine: set = set()
    if caller_id is not None:
        mine = set(
            (
                await session.execute(
                    select(LiveClassQuestionUpvote.question_id).where(
                        and_(
                            LiveClassQuestionUpvote.question_id.in_(question_ids),
                            LiveClassQuestionUpvote.student_user_id == caller_id,
                        )
                    )
                )
            )
            .scalars()
            .all()
        )

    ordered = sorted(
        questions, key=lambda q: (-counts.get(q.id, 0), q.created_at, q.id)
    )
    return [
        await _question_read(
            session,
            q,
            principal,
            is_host=is_host,
            upvote_count=counts.get(q.id, 0),
            has_upvoted=q.id in mine,
        )
        for q in ordered
    ]


# ── Polls ────────────────────────────────────────────────────────────────────


@router.post(
    "/classes/{class_id}/polls",
    response_model=PollRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an in-class poll",
    description=(
        "Creates a poll with its options, as DRAFT: the class cannot see it "
        "until it is activated. Host only."
    ),
)
async def create_poll(
    class_id: int,
    payload: CreatePollRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> PollRead:
    _live, org_id, campus_id = await _class_for_host(session, principal, class_id)
    campus_id = resolve_scoped_campus_id(principal, campus_id)

    poll = LiveClassPoll(
        session_id=class_id,
        org_id=org_id,
        campus_id=campus_id,
        question=payload.question.strip(),
        status=LivePollStatus.DRAFT,
        created_by_user_id=require_user_id(principal),
    )
    session.add(poll)
    await session.flush()

    for position, option in enumerate(payload.options):
        session.add(
            LiveClassPollOption(
                poll_id=poll.id,
                org_id=org_id,
                campus_id=campus_id,
                text=option.text.strip(),
                position=position,
            )
        )
    await session.commit()
    await session.refresh(poll)

    return await _poll_read(session, poll, principal, is_host=True)


@router.get(
    "/classes/{class_id}/polls",
    response_model=List[PollRead],
    summary="List an in-class poll history",
    description=(
        "Every poll for this class. The host sees drafts too; the class sees "
        "only polls that were actually put to them."
    ),
)
async def list_polls(
    class_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[PollRead]:
    _live, _org_id, _campus_id, is_host = await _class_for_member(
        session, principal, class_id
    )

    stmt = (
        select(LiveClassPoll)
        .where(LiveClassPoll.session_id == class_id)
        .order_by(LiveClassPoll.created_at, LiveClassPoll.id)
    )
    if not is_host:
        # A draft is a half-written poll; showing it would publish the
        # question before the teacher meant to ask it.
        stmt = stmt.where(LiveClassPoll.status != LivePollStatus.DRAFT)
    polls = (await session.execute(stmt)).scalars().all()

    return [await _poll_read(session, poll, principal, is_host=is_host) for poll in polls]


@router.get(
    "/polls/{poll_id}",
    response_model=PollRead,
    summary="Read one poll",
    description=(
        "Results are included for the host at any time, and for the class "
        "once the poll is closed."
    ),
)
async def get_poll(
    poll_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> PollRead:
    poll = await _load_poll_or_404(session, poll_id)
    _live, _org_id, _campus_id, is_host = await _class_for_member(
        session, principal, poll.session_id
    )
    if not is_host and poll.status == LivePollStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Poll not found"
        )
    return await _poll_read(session, poll, principal, is_host=is_host)


@router.post(
    "/polls/{poll_id}/activate",
    response_model=PollRead,
    summary="Put a poll to the class",
    description="Opens the poll for answers. Host only.",
)
async def activate_poll(
    poll_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> PollRead:
    poll = await _load_poll_or_404(session, poll_id)
    await _class_for_host(session, principal, poll.session_id)

    if poll.status == LivePollStatus.CLOSED:
        # Reopening would let late answers into a result the class has
        # already seen.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This poll is closed and cannot be reopened.",
        )
    if poll.status != LivePollStatus.ACTIVE:
        poll.status = LivePollStatus.ACTIVE
        poll.activated_at = datetime.datetime.now(datetime.timezone.utc)
        await session.commit()
        await session.refresh(poll)

    return await _poll_read(session, poll, principal, is_host=True)


@router.post(
    "/polls/{poll_id}/close",
    response_model=PollRead,
    summary="Close a poll",
    description=(
        "Stops accepting answers and publishes the results to the class. "
        "Host only. Closing an already-closed poll is a no-op, not an error."
    ),
)
async def close_poll(
    poll_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> PollRead:
    poll = await _load_poll_or_404(session, poll_id)
    await _class_for_host(session, principal, poll.session_id)

    if poll.status != LivePollStatus.CLOSED:
        poll.status = LivePollStatus.CLOSED
        poll.closed_at = datetime.datetime.now(datetime.timezone.utc)
        await session.commit()
        await session.refresh(poll)

    return await _poll_read(session, poll, principal, is_host=True)


@router.post(
    "/polls/{poll_id}/responses",
    response_model=PollRead,
    status_code=status.HTTP_201_CREATED,
    summary="Answer a poll",
    description=(
        "One answer per student per poll. Only while the poll is ACTIVE, and "
        "only for a student enrolled in the class's section."
    ),
)
async def respond_to_poll(
    poll_id: int,
    payload: PollResponseCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> PollRead:
    poll = await _load_poll_or_404(session, poll_id)
    live, org_id, campus_id, is_host = await _class_for_member(
        session, principal, poll.session_id
    )
    student_id = await _assert_enrolled_student(session, principal, live)

    if not is_host and poll.status == LivePollStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Poll not found"
        )
    if poll.status != LivePollStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This poll is not accepting answers.",
        )

    option = (
        await session.execute(
            select(LiveClassPollOption).where(
                and_(
                    LiveClassPollOption.id == payload.option_id,
                    LiveClassPollOption.poll_id == poll.id,
                )
            )
        )
    ).scalar_one_or_none()
    if option is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That option does not belong to this poll.",
        )

    existing = (
        await session.execute(
            select(LiveClassPollResponse).where(
                and_(
                    LiveClassPollResponse.poll_id == poll.id,
                    LiveClassPollResponse.student_user_id == student_id,
                )
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already answered this poll.",
        )

    session.add(
        LiveClassPollResponse(
            poll_id=poll.id,
            option_id=option.id,
            org_id=org_id,
            campus_id=resolve_scoped_campus_id(principal, campus_id),
            student_user_id=student_id,
        )
    )
    await session.commit()
    await session.refresh(poll)

    return await _poll_read(session, poll, principal, is_host=is_host)


# ── Q&A ──────────────────────────────────────────────────────────────────────


@router.post(
    "/classes/{class_id}/questions",
    response_model=QuestionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ask a question in the class Q&A",
    description=(
        "Host or an enrolled student. An anonymous question is anonymous to "
        "the class, not to the host."
    ),
)
async def ask_question(
    class_id: int,
    payload: CreateQuestionRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> QuestionRead:
    _live, org_id, campus_id, is_host = await _class_for_member(
        session, principal, class_id
    )

    question = LiveClassQuestion(
        session_id=class_id,
        org_id=org_id,
        campus_id=resolve_scoped_campus_id(principal, campus_id),
        author_user_id=require_user_id(principal),
        body=payload.body.strip(),
        is_anonymous=payload.is_anonymous,
    )
    session.add(question)
    await session.commit()
    await session.refresh(question)

    return await _question_read(session, question, principal, is_host=is_host)


@router.get(
    "/classes/{class_id}/questions",
    response_model=List[QuestionRead],
    summary="Read the class Q&A thread",
    description="Most upvoted first, then oldest first.",
)
async def list_questions(
    class_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[QuestionRead]:
    _live, _org_id, _campus_id, is_host = await _class_for_member(
        session, principal, class_id
    )
    questions = (
        await session.execute(
            select(LiveClassQuestion)
            .where(LiveClassQuestion.session_id == class_id)
            .order_by(LiveClassQuestion.created_at, LiveClassQuestion.id)
        )
    ).scalars().all()
    return await _question_reads(session, list(questions), principal, is_host=is_host)


@router.post(
    "/questions/{question_id}/upvote",
    response_model=QuestionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upvote a question",
    description="One upvote per student per question. Enrolled students only.",
)
async def upvote_question(
    question_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> QuestionRead:
    question = await _load_question_or_404(session, question_id)
    live, org_id, campus_id, is_host = await _class_for_member(
        session, principal, question.session_id
    )
    student_id = await _assert_enrolled_student(session, principal, live)

    existing = (
        await session.execute(
            select(LiveClassQuestionUpvote).where(
                and_(
                    LiveClassQuestionUpvote.question_id == question.id,
                    LiveClassQuestionUpvote.student_user_id == student_id,
                )
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already upvoted this question.",
        )

    session.add(
        LiveClassQuestionUpvote(
            question_id=question.id,
            org_id=org_id,
            campus_id=resolve_scoped_campus_id(principal, campus_id),
            student_user_id=student_id,
        )
    )
    await session.commit()
    await session.refresh(question)

    return await _question_read(
        session, question, principal, is_host=is_host, has_upvoted=True
    )


@router.post(
    "/questions/{question_id}/resolve",
    response_model=QuestionRead,
    summary="Mark a question resolved",
    description=(
        "Host only. The question stays in the thread; resolving it is how the "
        "host says 'answered' without deleting what a child asked."
    ),
)
async def resolve_question(
    question_id: int,
    payload: ResolveQuestionRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CLASS_STAFF)),
) -> QuestionRead:
    question = await _load_question_or_404(session, question_id)
    await _class_for_host(session, principal, question.session_id)

    question.is_resolved = payload.resolved
    if payload.resolved:
        question.resolved_by_user_id = require_user_id(principal)
        question.resolved_at = datetime.datetime.now(datetime.timezone.utc)
    else:
        question.resolved_by_user_id = None
        question.resolved_at = None
    await session.commit()
    await session.refresh(question)

    return await _question_read(session, question, principal, is_host=True)
