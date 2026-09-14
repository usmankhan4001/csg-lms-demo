"""
The catalogue of things this school can tell someone about (M35, Lane I).

WHY A REGISTRY RATHER THAN AN ENUM: adding an event must be a registration, not
a patch to the delivery code. Lane J wires roughly a dozen school events
(absence, report card, offer, assignment, timetable change, ...) and later work
will add more. If each one required editing a match statement inside the
dispatcher, every new event would risk the delivery path that carries
safeguarding messages. Here an event declares itself and the dispatcher never
learns its name.

SEVERITY IS THE LOAD-BEARING FIELD. It is not a priority hint for sorting a
list -- it decides whether a person is allowed to mute the message at all:

    SAFEGUARDING  cannot be muted, ignores quiet hours, never batched.
                  Self-harm escalation, a safeguarding incident, an account
                  security event. `preferences.py` short-circuits on this tier
                  BEFORE loading any preference row, so a mute row for a
                  safeguarding event is unreachable rather than overridden.

    IMPORTANT     mutable, but ignores quiet hours. Money and attendance: a fee
                  that falls due tonight, a child absent from school today. A
                  parent may switch these off, but if they are on they arrive
                  when they happen.

    ROUTINE       mutable, deferred out of quiet hours. Assignments, digests,
                  timetable changes, recognition. The bulk of the traffic, and
                  the part that makes families mute everything if it arrives at
                  22:00.

Nothing here sends anything. This module is pure data plus a registry, so it
imports no session, no mail client and no model, and can be read by the
frontend settings screen and the dispatcher alike.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence

from src.db.sms_identity import SchoolRole

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    """How much say the recipient gets. See the module docstring."""

    SAFEGUARDING = "safeguarding"
    IMPORTANT = "important"
    ROUTINE = "routine"

    @property
    def is_mutable(self) -> bool:
        return self is not Severity.SAFEGUARDING

    @property
    def respects_quiet_hours(self) -> bool:
        return self is Severity.ROUTINE


class Category(str, Enum):
    """The grouping a person mutes in one gesture.

    Deliberately coarse. A settings screen that lists forty individual events is
    a screen nobody configures; one that lists eight categories is one a parent
    will actually use. A specific `event_key` preference still overrides its
    category for anyone who wants that precision.
    """

    SAFEGUARDING = "safeguarding"
    ATTENDANCE = "attendance"
    ACADEMIC = "academic"
    FINANCE = "finance"
    ADMISSIONS = "admissions"
    SCHEDULE = "schedule"
    RECOGNITION = "recognition"
    ACCOUNT = "account"


@dataclass(frozen=True)
class NotificationEvent:
    """One kind of thing the school can announce.

    `required_context` is what a template for this event is entitled to assume
    exists. It is checked at render time and a missing field omits its line
    rather than rendering a placeholder -- see `templates.py`. Declaring it here
    means a template author finds out at registration, not in a parent's inbox.
    """

    key: str
    category: Category
    severity: Severity
    description: str
    default_audience: Sequence[SchoolRole] = field(default_factory=tuple)
    required_context: Sequence[str] = field(default_factory=tuple)
    # Two events with the same dedupe window collapse into one message per
    # recipient per window. 0 means every raise is distinct.
    dedupe_window_seconds: int = 0

    def __post_init__(self) -> None:
        if self.severity is Severity.SAFEGUARDING and self.category is not Category.SAFEGUARDING:
            # Not pedantry: `preferences.py` short-circuits on severity and the
            # settings UI groups by category. If they disagree, a screen would
            # offer a mute toggle for something that cannot be muted, which is
            # worse than offering nothing.
            raise ValueError(
                f"event {self.key!r} is SAFEGUARDING severity but filed under "
                f"category {self.category.value!r}; they must agree or the "
                f"preferences UI will show an ineffective toggle"
            )


_REGISTRY: Dict[str, NotificationEvent] = {}


def register_event(event: NotificationEvent) -> NotificationEvent:
    """Add an event to the catalogue. Idempotent for an identical re-register.

    Raises on a genuine redefinition rather than overwriting: two modules
    disagreeing about an event's severity is exactly the bug that would let a
    safeguarding message become mutable, and it must fail at import.
    """
    existing = _REGISTRY.get(event.key)
    if existing is not None and existing != event:
        raise ValueError(
            f"notification event {event.key!r} is already registered with different "
            f"settings (severity {existing.severity.value} vs {event.severity.value}); "
            f"pick a distinct key rather than redefining one"
        )
    _REGISTRY[event.key] = event
    return event


def get_event(key: str) -> NotificationEvent:
    """Look up an event, or fail loudly.

    Deliberately NOT fail-open. `security/features_utils/resolve.py` fails open
    on an unknown feature key and that made several gates decorative; the same
    mistake here would let a typo'd event key deliver as ROUTINE and become
    mutable. An unregistered key is a programming error and says so.
    """
    try:
        return _REGISTRY[key]
    except KeyError:
        raise KeyError(
            f"unknown notification event {key!r}. Register it with "
            f"register_event(NotificationEvent(...)) in events.py before raising it."
        ) from None


def all_events() -> List[NotificationEvent]:
    """The catalogue, for the preferences screen. Stable order for a stable UI."""
    return sorted(_REGISTRY.values(), key=lambda e: (e.category.value, e.key))


def events_by_category() -> Dict[Category, List[NotificationEvent]]:
    out: Dict[Category, List[NotificationEvent]] = {}
    for event in all_events():
        out.setdefault(event.category, []).append(event)
    return out


def is_registered(key: str) -> bool:
    return key in _REGISTRY


# ---------------------------------------------------------------------------
# Built-in events
# ---------------------------------------------------------------------------
#
# Only the two that already have live senders are registered here, so this
# module is true on the day it lands rather than a promise. Lane J registers
# the rest alongside the code that raises them, which keeps an event and its
# sender in the same file where they can be reviewed together.

CRISIS_ALERT = register_event(
    NotificationEvent(
        key="safeguarding.crisis_alert",
        category=Category.SAFEGUARDING,
        severity=Severity.SAFEGUARDING,
        description="A student disclosed self-harm or severe distress to the AI tutor.",
        default_audience=(SchoolRole.PSYCHOLOGIST, SchoolRole.SCHOOL_ADMIN),
        required_context=("severity", "category"),
    )
)

FEE_REMINDER = register_event(
    NotificationEvent(
        key="finance.fee_reminder",
        category=Category.FINANCE,
        severity=Severity.IMPORTANT,
        description="A fee voucher is approaching its due date, due, or overdue.",
        default_audience=(SchoolRole.PARENT,),
        required_context=("student_name", "amount", "due_date"),
        # One reminder per voucher per day, however many times the job runs.
        dedupe_window_seconds=86_400,
    )
)
