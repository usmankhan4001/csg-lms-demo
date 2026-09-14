"""
Turning an event plus its facts into words a person reads (M35, Lane I).

TWO RULES, BOTH LEARNED THE HARD WAY IN THIS REPOSITORY.

**A missing fact omits its line. It never renders a placeholder and it never
invents a value.** This codebase has had nine fabrication defects torn out of
it -- an endpoint returning a 4.0 GPA and "honor roll" for a student with no
grades, a parent digest reporting invented attendance percentages, a knowledge
graph serving hardcoded mastery scores. A template is the easiest place for the
tenth to appear, because "Dear {{first_name}}" reaching a parent looks like a
cosmetic bug while "your child attended 0 classes" reaching the same parent
looks like information. Both come from the same cause, so `render()` drops any
line whose facts are missing and reports which ones it dropped.

**A school's voice is its own.** The built-in wording is a default, not a house
style. An override is resolved campus-first then organisation, which is exactly
how `services/sms/settings.py` resolves a settings group -- an administrator who
has learned one resolution order should not have to learn a second.

Rendering is deliberately a tiny bespoke substitution rather than Jinja: these
templates are authored by school administrators through a web form, and handing
an untrusted author a real template engine hands them arbitrary attribute access
inside the server. Values are HTML-escaped on the way in.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.notification_prefs import NotificationTemplateOverride
from src.db.sms_identity import SchoolRole
from src.services.notifications.events import NotificationEvent

logger = logging.getLogger(__name__)

# {{ field_name }} with optional surrounding whitespace.
_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


@dataclass
class RenderedMessage:
    """What to send, plus what we could not say.

    `omitted_fields` is returned rather than logged-and-forgotten so a caller
    can tell the difference between "the school worded it briefly" and "we had
    no data and quietly said less than we meant to". Lane J should log it.
    """

    subject: str
    body_html: str
    omitted_fields: List[str] = field(default_factory=list)
    used_override: bool = False

    @property
    def is_complete(self) -> bool:
        return not self.omitted_fields


class TemplateNotFound(LookupError):
    """No built-in template and no override for this event/role pair."""


# ---------------------------------------------------------------------------
# Built-in defaults
# ---------------------------------------------------------------------------
#
# Keyed (event_key, role) with a None-role fallback. Written plainly and
# without exclamation marks: this is a school writing to a family, not a
# product writing to a user. Every line that depends on a fact is its own
# line, because omission works line-by-line.

_DEFAULTS: Dict[Tuple[str, Optional[str]], Tuple[str, str]] = {
    (
        "safeguarding.crisis_alert",
        None,
    ): (
        "Urgent: a student may need support",
        "<p>A student has disclosed something that our safety checks flagged as "
        "needing a person, not a system.</p>"
        "<p>Category: {{category}}</p>"
        "<p>Severity: {{severity}}</p>"
        "<p>Please review this in the counselling area of the school system. "
        "This message deliberately contains no details of what the student "
        "said.</p>",
    ),
    (
        "finance.fee_reminder",
        SchoolRole.PARENT.value,
    ): (
        "Fee reminder for {{student_name}}",
        "<p>This is a reminder about a fee for {{student_name}}.</p>"
        "<p>Amount outstanding: {{amount}}</p>"
        "<p>Due: {{due_date}}</p>"
        "<p>You can view the full statement in the school system. If you have "
        "already paid, please disregard this message.</p>",
    ),
}


def register_default_template(
    event_key: str, role: Optional[SchoolRole], subject: str, body_html: str
) -> None:
    """Add a built-in template. Lane J calls this beside each event it registers."""
    _DEFAULTS[(event_key, role.value if role else None)] = (subject, body_html)


def _lookup_default(event_key: str, role: Optional[SchoolRole]) -> Tuple[str, str]:
    if role is not None:
        specific = _DEFAULTS.get((event_key, role.value))
        if specific is not None:
            return specific
    generic = _DEFAULTS.get((event_key, None))
    if generic is not None:
        return generic
    raise TemplateNotFound(
        f"no template for event {event_key!r} (role={role.value if role else None}). "
        f"Register one with register_default_template() next to the event."
    )


async def _lookup_override(
    db_session: AsyncSession,
    org_id: int,
    campus_id: Optional[int],
    event_key: str,
    role: Optional[SchoolRole],
) -> Optional[Tuple[str, str]]:
    """The school's own wording, campus-first then org, role-first then generic.

    Never raises: a failure to load an override falls back to the built-in
    wording. A school that mis-saved a template must still be able to tell a
    parent their child is absent.
    """
    try:
        rows = (
            await db_session.execute(
                select(NotificationTemplateOverride).where(
                    NotificationTemplateOverride.org_id == org_id,
                    NotificationTemplateOverride.event_key == event_key,
                )
            )
        ).scalars().all()
    except Exception:
        logger.exception(
            "Could not load notification template overrides for org=%s event=%s; "
            "falling back to the built-in wording.",
            org_id,
            event_key,
        )
        return None

    if not rows:
        return None

    role_value = role.value if role else None

    def rank(row: NotificationTemplateOverride) -> tuple:
        # Higher is better. Campus beats org; an exact role beats the catch-all.
        campus_match = 1 if (campus_id is not None and row.campus_id == campus_id) else 0
        if row.campus_id is not None and row.campus_id != campus_id:
            return (-1, -1)  # another campus's template: not applicable here
        role_match = 1 if (role_value is not None and row.role == role_value) else 0
        if row.role is not None and row.role != role_value:
            return (-1, -1)  # another role's template
        return (campus_match, role_match)

    applicable = [(rank(r), r) for r in rows]
    applicable = [(score, r) for score, r in applicable if score != (-1, -1)]
    if not applicable:
        return None

    applicable.sort(key=lambda pair: pair[0], reverse=True)
    best = applicable[0][1]
    return (best.subject, best.body_html)


def _substitute(text: str, context: Mapping[str, Any]) -> Tuple[str, List[str]]:
    """Replace every placeholder whose value we actually have.

    Returns the rendered text and the names that had no value. A value of None,
    an empty string, or a whitespace-only string counts as absent: a template
    reading "Amount outstanding: " with nothing after it is the same failure as
    one reading "Amount outstanding: {{amount}}".
    """
    missing: List[str] = []

    def replace(match: re.Match) -> str:
        name = match.group(1)
        value = context.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(name)
            return match.group(0)  # left intact so the line can be dropped whole
        return html.escape(str(value))

    return _PLACEHOLDER.sub(replace, text), missing


def _drop_incomplete_lines(body: str) -> Tuple[str, List[str]]:
    """Remove any block that still carries an unfilled placeholder.

    Operates per top-level <p> so that one missing fact costs one sentence
    rather than the whole message. A body with no paragraph markup is treated as
    a single block: better to send nothing than to send a paragraph with
    "{{amount}}" sitting in the middle of it.
    """
    dropped: List[str] = []
    blocks = re.split(r"(?i)(?=<p[\s>])", body)
    kept: List[str] = []
    for block in blocks:
        found = _PLACEHOLDER.findall(block)
        if found:
            dropped.extend(found)
            continue
        kept.append(block)
    return "".join(kept), dropped


async def render(
    db_session: Optional[AsyncSession],
    event: NotificationEvent,
    *,
    org_id: int,
    role: Optional[SchoolRole] = None,
    campus_id: Optional[int] = None,
    context: Optional[Mapping[str, Any]] = None,
) -> RenderedMessage:
    """Render one event for one role. Never invents a value.

    `db_session` may be None to render the built-in wording without a database
    round trip -- used by tests and by the preview in the settings screen.
    """
    ctx: Dict[str, Any] = dict(context or {})
    used_override = False

    subject_tpl = body_tpl = None
    if db_session is not None:
        override = await _lookup_override(db_session, org_id, campus_id, event.key, role)
        if override is not None:
            subject_tpl, body_tpl = override
            used_override = True

    if subject_tpl is None or body_tpl is None:
        subject_tpl, body_tpl = _lookup_default(event.key, role)

    subject, subject_missing = _substitute(subject_tpl, ctx)
    body, body_missing = _substitute(body_tpl, ctx)

    # A subject is a single line and cannot lose part of itself gracefully. If
    # it depends on a fact we do not have, fall back to the event's description
    # rather than mailing someone a subject with braces in it.
    if subject_missing:
        subject = event.description

    body, dropped = _drop_incomplete_lines(body)
    omitted = sorted(set(subject_missing) | set(body_missing) | set(dropped))

    if omitted:
        logger.info(
            "Notification %s rendered without %s -- those lines were omitted rather "
            "than filled with a placeholder.",
            event.key,
            ", ".join(omitted),
        )

    if not body.strip():
        # Everything depended on data we do not have. Say the one true thing we
        # know instead of sending an empty message.
        body = f"<p>{html.escape(event.description)}</p>"

    return RenderedMessage(
        subject=subject,
        body_html=body,
        omitted_fields=omitted,
        used_override=used_override,
    )
