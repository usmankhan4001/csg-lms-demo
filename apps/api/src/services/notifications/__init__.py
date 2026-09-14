"""Notification & messaging services (M35, M13).

The import surface for anything raising a school event. Lane J and Phase 1's
invite delivery should need nothing from this package that is not re-exported
here:

    from src.services.notifications import (
        Category, NotificationEvent, Severity,
        notify_event, register_event, resolve_guardians_of,
    )
    from src.services.notifications import templates

    MY_EVENT = register_event(NotificationEvent(
        key="attendance.absence_recorded",
        category=Category.ATTENDANCE,
        severity=Severity.IMPORTANT,
        description="A student was marked absent.",
        default_audience=(SchoolRole.PARENT,),
        required_context=("student_name", "date"),
        dedupe_window_seconds=86_400,
    ))
    templates.register_default_template(
        MY_EVENT.key, SchoolRole.PARENT,
        "{{student_name}} was marked absent",
        "<p>{{student_name}} was marked absent on {{date}}.</p>",
    )

    await notify_event(session, event_key=MY_EVENT.key, org_id=org_id,
                       recipients=await resolve_guardians_of(session, student_id),
                       context={"student_name": name, "date": when},
                       related_kind="student", related_id=student_id)

`notify()` in `service.py` remains the delivery primitive and is unchanged;
call `notify_event()` instead unless you are deliberately bypassing
preferences, templating and duplicate suppression.

WORKERS=4 -- WHAT THIS MEANS FOR YOU
------------------------------------
Production runs four API worker processes, so anything held in a process exists
in one of them. This fabric is built around that, and there is exactly one rule
you have to follow:

    **Call `register_event()` and `register_default_template()` at MODULE
    IMPORT time, never inside a request handler or a job.**

The catalogue (`events._REGISTRY`) and the built-in templates
(`templates._DEFAULTS`) are per-process dictionaries. That is safe precisely
because every worker imports the same modules at startup and therefore builds
an identical catalogue. A registration performed at *runtime* would exist in
whichever worker served that one request, and `notify_event()` would then raise
"unknown notification event" in the other three -- intermittently, under load,
and only in production.

Everything that must be shared between workers already is, because it lives in
the database rather than in a process:

    preferences, quiet hours, template overrides   DB tables
    duplicate suppression                          DB unique constraint
    the quiet-hours queue                          DB table + arq cron
    the delivery log                               DB table

Note in particular that a deferred message is delivered by the arq cron job
`deliver_deferred_notifications` (every 15 minutes, registered in
`core/worker.py`), NOT by an in-process timer. The in-process event bus in
`core/events` is deliberately not used anywhere in this fabric: it fires in one
worker, which for a message to a family means a three-in-four chance of silence.
"""

from src.services.notifications.dispatch import (  # noqa: F401
    EventResult,
    compose_idempotency_key,
    notify_event,
    resolve_audience,
    resolve_guardians_of,
)
from src.services.notifications.events import (  # noqa: F401
    Category,
    NotificationEvent,
    Severity,
    all_events,
    events_by_category,
    get_event,
    is_registered,
    register_event,
)
from src.services.notifications.preferences import (  # noqa: F401
    Decision,
    resolve_delivery,
    set_preference,
)

__all__ = [
    "Category",
    "Decision",
    "EventResult",
    "NotificationEvent",
    "Severity",
    "all_events",
    "compose_idempotency_key",
    "events_by_category",
    "get_event",
    "is_registered",
    "notify_event",
    "register_event",
    "resolve_audience",
    "resolve_delivery",
    "resolve_guardians_of",
    "set_preference",
]
