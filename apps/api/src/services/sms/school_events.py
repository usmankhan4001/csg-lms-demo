"""Every school event this system can tell somebody about (Lane J).

WHY ONE MODULE RATHER THAN ONE PER ROUTER
-----------------------------------------
Lane I suggested registering each event beside the code that raises it. That
keeps an event and its sender reviewable together, which is a real benefit, but
it loses something more important: **the catalogue must be complete in every
process, however the process was started.**

`events._REGISTRY` and `templates._DEFAULTS` are per-process dictionaries, safe
only because every worker imports the same modules at startup. Scattering
registrations across nine routers makes that guarantee depend on import order
and on which routers a given entrypoint happens to mount. The arq worker
(`core/worker.py`) does not mount the API's routers at all -- so a fee reminder
or a deferred-delivery job running there would raise `KeyError: unknown
notification event` for any event registered inside a router module. The
preferences screen has the same problem in reverse: it can only offer a toggle
for an event that is registered, so a half-imported catalogue silently hides
settings from a parent.

So: every event is declared here, once, and each sender imports the constant it
raises. The import IS the registration, co-location is preserved by that
explicit import, and any process that can raise an event necessarily has the
whole catalogue.

CHOOSING A SEVERITY
-------------------
Severity is not a priority hint. It decides whether a person may mute the
message, and getting it wrong in either direction does real harm:

  * Over-classify (everything SAFEGUARDING) and the preference system is
    decorative. A family that cannot turn down the volume turns the school off
    entirely -- they filter the sender, and then the one message that mattered
    is also unread.
  * Under-classify and a child's safeguarding incident sits in a quiet-hours
    queue until morning.

Each event below states its tier and why. The rule of thumb used throughout:
**SAFEGUARDING is for harm, IMPORTANT is for same-day money and attendance,
ROUTINE is for everything a person can read tomorrow without cost.**

CONFIDENTIALITY
---------------
A notification is the easiest place in a school system to leak something. Two
rules are applied here and enforced by the templates:

  1. **No free-text narrative is ever interpolated into a message.** A
     disciplinary `description` or an attendance `remarks` field routinely
     names other children ("pushed X in the corridor"). Those fields are
     deliberately NOT in any `required_context` below and must not be added --
     a template renders the title, the date and the severity, and the reader
     signs in for the rest.
  2. **Recipients are resolved from the subject's own guardian links**, never
     from a section roster or a class list.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Sequence

from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_identity import SchoolRole
from src.services.notifications import (
    Category,
    NotificationEvent,
    Severity,
    notify_event,
    register_event,
)
from src.services.notifications import templates

logger = logging.getLogger(__name__)

# One school day. Used wherever a job or a handler can legitimately run more
# than once over the same record in a day (a re-submitted register, a nightly
# reminder sweep, a recalculated report card) and the family should still hear
# about it exactly once.
ONE_SCHOOL_DAY = 86_400


def _register_template(event, role, subject: str, body_html: str) -> None:
    """Register a template for `role`, and as the role-agnostic fallback.

    WHY THE FALLBACK IS NOT OPTIONAL. `templates.render` resolves a template by
    (event, role) and falls back to (event, None); with no None entry it raises
    TemplateNotFound. The role comes from the recipient's `SMSUserRole` grant,
    and a guardian can legitimately have NONE -- linked to a child through
    `StudentGuardian` but never granted the PARENT role, which is the ordinary
    state of a family added by hand or by an import that stopped at the link.

    `notify_event` contains that failure per recipient, so nothing breaks; the
    message is simply counted as failed and that parent hears nothing. A parent
    silently not being told their child was absent is precisely the failure
    this whole lane exists to remove, so every event registers a fallback with
    the same wording rather than relying on a role grant existing.
    """
    templates.register_default_template(event.key, role, subject, body_html)
    templates.register_default_template(event.key, None, subject, body_html)


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

ABSENCE_RECORDED = register_event(
    NotificationEvent(
        key="attendance.absence_recorded",
        category=Category.ATTENDANCE,
        severity=Severity.IMPORTANT,
        # IMPORTANT, not ROUTINE: a parent who believes their child is at
        # school and is not needs to know while the school day is still
        # running. Deferring this to 07:00 the next morning would be telling
        # them a day late, which is worse than not telling them.
        # Not SAFEGUARDING: an absence is usually a cold, and a parent who
        # already knows (they kept the child home) is entitled to switch the
        # daily message off.
        description="A student was marked absent from a register.",
        default_audience=(SchoolRole.PARENT,),
        required_context=("student_name", "date"),
        # One message per student per day however many periods they miss and
        # however many times the teacher presses save. Without this a child
        # absent all day in a 7-period school generates seven emails, which is
        # precisely how a family learns to filter the sender.
        dedupe_window_seconds=ONE_SCHOOL_DAY,
    )
)
_register_template(
    ABSENCE_RECORDED,
    SchoolRole.PARENT,
    "{{student_name}} was marked absent today",
    (
        "<p>{{student_name}} was marked absent on {{date}}.</p>"
        "<p>If this is unexpected, please contact the school office. "
        "If the absence was planned, you can submit a note through the "
        "parent portal.</p>"
    ),
)


ABSENCE_STREAK = register_event(
    NotificationEvent(
        key="attendance.absence_streak",
        category=Category.ATTENDANCE,
        severity=Severity.IMPORTANT,
        # Same tier as a single absence rather than higher. A streak is more
        # serious, but the school's response to it is the pastoral concern
        # record and a human conversation, not a louder email. Escalating this
        # to SAFEGUARDING would make it unmutable for the many families whose
        # child has a two-week illness the school already knows about.
        description="A student has been absent for several consecutive school days.",
        default_audience=(SchoolRole.PARENT,),
        required_context=("student_name", "streak"),
        dedupe_window_seconds=ONE_SCHOOL_DAY,
    )
)
_register_template(
    ABSENCE_STREAK,
    SchoolRole.PARENT,
    "{{student_name}} has been absent {{streak}} days in a row",
    (
        "<p>{{student_name}} has now been marked absent for {{streak}} "
        "consecutive school days.</p>"
        "<p>Please contact the school if this is unexpected, or submit a "
        "leave request if it is planned.</p>"
    ),
)


EXCUSE_REVIEWED = register_event(
    NotificationEvent(
        key="attendance.excuse_reviewed",
        category=Category.ATTENDANCE,
        severity=Severity.ROUTINE,
        # ROUTINE: this is the outcome of something the parent themselves
        # submitted and are waiting on. It carries no new obligation and
        # nothing changes if they read it at breakfast rather than at 23:00.
        description="An absence note was approved or rejected.",
        default_audience=(SchoolRole.PARENT,),
        required_context=("student_name", "date", "outcome"),
    )
)
_register_template(
    EXCUSE_REVIEWED,
    SchoolRole.PARENT,
    "Absence note for {{student_name}}: {{outcome}}",
    (
        "<p>The absence note you submitted for {{student_name}} covering "
        "{{date}} has been {{outcome}}.</p>"
        "<p>You can see the full attendance record in the parent portal.</p>"
    ),
)


# ---------------------------------------------------------------------------
# Academic
# ---------------------------------------------------------------------------

REPORT_CARD_SENT = register_event(
    NotificationEvent(
        key="academic.report_card_sent",
        category=Category.ACADEMIC,
        severity=Severity.ROUTINE,
        # ROUTINE: a report card is a considered document a family will sit
        # down with. Waking someone for it would be absurd, and a parent who
        # prefers to hear it from their child rather than by email is entitled
        # to mute it -- the report card itself remains in the portal either way.
        description="A teacher released a term report card to the family.",
        default_audience=(SchoolRole.PARENT, SchoolRole.STUDENT),
        required_context=("student_name", "term_name"),
    )
)
_register_template(
    REPORT_CARD_SENT,
    SchoolRole.PARENT,
    "{{student_name}}'s report card for {{term_name}} is ready",
    (
        "<p>{{student_name}}'s report card for {{term_name}} has been "
        "released and is now available in the parent portal.</p>"
    ),
)
templates.register_default_template(
    REPORT_CARD_SENT.key,
    SchoolRole.STUDENT,
    "Your report card for {{term_name}} is ready",
    (
        "<p>Your report card for {{term_name}} has been released and is now "
        "available in your portal.</p>"
    ),
)


# NOT REGISTERED: "grades posted".
#
# The brief asked for it and I could not wire it honestly. There is no moment
# in this gradebook at which marks become final. `POST /entries/batch` is
# documented "Enter or update scores" -- it is the teacher's working surface,
# used repeatedly while marking a pile of scripts, and `GradeChangeEvent`
# exists precisely because marks get corrected afterwards. Raising a family
# notification there would tell a parent a provisional mark, and then a
# different one.
#
# Report cards have the release step that marks lack (draft -> sent, with an
# explicit teacher action), which is why REPORT_CARD_SENT above is wired and
# this is not. Registering the event anyway would be worse than leaving it
# out: the preferences screen lists every registered event, so it would give a
# parent a toggle for a message that can never arrive.
#
# TO WIRE THIS someone must first decide what "posted" means -- most likely a
# per-assessment publish flag, the same shape as the report-card send.


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

SUBSTITUTION_ASSIGNED = register_event(
    NotificationEvent(
        key="schedule.substitution_assigned",
        category=Category.SCHEDULE,
        severity=Severity.IMPORTANT,
        # IMPORTANT rather than ROUTINE, and this is the one place I depart
        # from "schedule changes are routine". Cover is arranged when somebody
        # calls in sick, which is the evening before or the morning of. A
        # ROUTINE message raised at 22:00 sits in the quiet-hours queue until
        # the 07:00 sweep -- a teacher covering period 1 would find out as they
        # arrived, or after. The class is the thing that fails, not the email.
        description="A teacher was assigned to cover another teacher's class.",
        default_audience=(SchoolRole.TEACHER,),
        required_context=("substitution_date",),
    )
)
_register_template(
    SUBSTITUTION_ASSIGNED,
    SchoolRole.TEACHER,
    "You are covering a class on {{substitution_date}}",
    (
        "<p>You have been assigned to cover a class on "
        "{{substitution_date}}.</p>"
        "<p>Your timetable in the staff portal shows the period, section and "
        "room.</p>"
    ),
)


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------
#
# TWO EVENTS, NOT ONE, AND THE SPLIT IS THE WHOLE POINT.
#
# Severity is a property of the event key, fixed at registration -- it cannot
# vary per raise. But a uniform infringement and a violent assault are the same
# database row with a different `severity` column, and they warrant opposite
# treatment: one a parent may reasonably switch off, the other they may not.
#
# Registering a single `discipline.incident` event would force a choice between
# making playground scuffles unmutable and making a serious safeguarding matter
# something a parent can silence. So the raising code reads the incident's own
# severity and picks the event to match.

DISCIPLINE_INCIDENT_SERIOUS = register_event(
    NotificationEvent(
        key="safeguarding.discipline_incident_serious",
        category=Category.SAFEGUARDING,
        severity=Severity.SAFEGUARDING,
        # MAJOR and CRITICAL only. A parent cannot mute being told their child
        # was involved in something serious, and it does not wait for morning.
        description="A major or critical disciplinary incident involving a student was recorded.",
        default_audience=(SchoolRole.PARENT,),
        # NOTE what is absent: `description`. The incident narrative routinely
        # names other children, and a message that leaks one family's child to
        # another is the worst failure this module could have. Title, date and
        # severity only; the detail is behind a login.
        required_context=("student_name", "incident_date", "severity"),
    )
)
_register_template(
    DISCIPLINE_INCIDENT_SERIOUS,
    SchoolRole.PARENT,
    "A serious incident involving {{student_name}} was recorded",
    (
        "<p>The school has recorded a {{severity}} incident involving "
        "{{student_name}} on {{incident_date}}.</p>"
        "<p>A member of staff will be in contact. The full record is "
        "available to you in the parent portal.</p>"
    ),
)


DISCIPLINE_INCIDENT_RECORDED = register_event(
    NotificationEvent(
        key="academic.discipline_incident_recorded",
        category=Category.ACADEMIC,
        severity=Severity.ROUTINE,
        # MINOR and MODERATE. Filed under ACADEMIC because there is no conduct
        # category and school conduct is the nearest true grouping -- putting
        # it under SAFEGUARDING would be a lie twice over: the registry would
        # reject the ROUTINE severity, and a parent muting "safeguarding" to
        # stop late marks would mute genuine safeguarding messages.
        description="A minor or moderate disciplinary incident involving a student was recorded.",
        default_audience=(SchoolRole.PARENT,),
        required_context=("student_name", "incident_date"),
        dedupe_window_seconds=ONE_SCHOOL_DAY,
    )
)
_register_template(
    DISCIPLINE_INCIDENT_RECORDED,
    SchoolRole.PARENT,
    "A behaviour note was recorded for {{student_name}}",
    (
        "<p>The school recorded a behaviour note for {{student_name}} on "
        "{{incident_date}}.</p>"
        "<p>You can read it in the parent portal.</p>"
    ),
)


# ---------------------------------------------------------------------------
# Raising an event from a request handler
# ---------------------------------------------------------------------------


async def student_display_name(
    db_session: AsyncSession, student_user_id: int
) -> Optional[str]:
    """How to refer to a student in a message, or None if we cannot.

    Returns None rather than a placeholder when the account has no name on it.
    That matters: `templates.render` omits the line carrying a missing field,
    so a nameless student produces a shorter message. The alternative --
    `f"Student #{student_id}"`, which the existing absence-streak subscriber
    uses -- sends a parent an email about "Student #4471", which reads as a
    system fault and tells them nothing they can act on.
    """
    from src.db.users import User

    user = await db_session.get(User, student_user_id)
    if user is None:
        return None
    full_name = " ".join(
        part
        for part in (
            getattr(user, "first_name", None),
            getattr(user, "last_name", None),
        )
        if part
    ).strip()
    if full_name:
        return full_name
    # A username is a real, human-chosen identifier and is better than nothing;
    # a numeric id is not.
    return getattr(user, "username", None) or None


async def raise_school_event(
    db_session: AsyncSession,
    *,
    event_key: str,
    org_id: Optional[int],
    recipients: Optional[Sequence[Any]] = None,
    context: Optional[Mapping[str, Any]] = None,
    campus_id: Optional[int] = None,
    related_kind: Optional[str] = None,
    related_id: Optional[int] = None,
) -> Optional[Any]:
    """Raise an event without ever being able to break the caller.

    USE THIS FROM HANDLERS, not `notify_event` directly.

    `notify_event` documents itself as "Never raises", and it very nearly is --
    but it raises `ValueError` when `org_id` is None, deliberately, so that a
    message naming a child can never be sent to an unresolved tenant. That
    decision is right. It also means the one guarantee a handler needs -- that
    telling somebody about a saved register can never un-save the register --
    is not quite true at the call site.

    So this wrapper holds the line the handlers actually depend on:

      * a missing tenant is logged and dropped, never raised into a teacher's
        roll-call submission;
      * any other failure (mail provider down, guardian row missing, template
        error) is logged and dropped;
      * nothing is ever swallowed silently -- every path logs, because a
        permanently broken notification route that raises nothing and records
        nothing looks exactly like a healthy one.

    Returns the `EventResult` when the event was raised, or None when it could
    not be, so a caller that wants to record delivery can, and a caller that
    does not can ignore it.
    """
    if org_id is None:
        # Not an exception: the originating action has already succeeded and
        # must stand. But loud, because an endpoint reaching here is
        # misconfigured -- every SMS route should resolve a tenant.
        logger.warning(
            "Notification %s dropped: no organisation on the request, so there "
            "is no safe tenant to send within.",
            event_key,
        )
        return None

    try:
        return await notify_event(
            db_session,
            event_key=event_key,
            org_id=org_id,
            recipients=recipients,
            context=dict(context or {}),
            campus_id=campus_id,
            related_kind=related_kind,
            related_id=related_id,
        )
    except Exception:
        logger.warning(
            "Notification %s failed for org %s (%s %s). The originating action "
            "stands; only the message was lost.",
            event_key,
            org_id,
            related_kind,
            related_id,
            exc_info=True,
        )
        return None


__all__ = [
    "ABSENCE_RECORDED",
    "ABSENCE_STREAK",
    "DISCIPLINE_INCIDENT_RECORDED",
    "DISCIPLINE_INCIDENT_SERIOUS",
    "EXCUSE_REVIEWED",
    "ONE_SCHOOL_DAY",
    "REPORT_CARD_SENT",
    "SUBSTITUTION_ASSIGNED",
    "student_display_name",
    "raise_school_event",
]
