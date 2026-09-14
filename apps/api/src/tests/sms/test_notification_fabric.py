"""
The notification fabric (M35, Lane I): taxonomy, templates, preferences,
quiet hours, idempotency.

WHAT THESE TESTS PROTECT, in order of how much damage the failure does.

**A safeguarding message cannot be muted.** Not "is not muted by default" --
cannot be. The mechanism is an early return in `resolve_delivery()` placed
above any preference read, so the test writes the mute row directly into the
database, bypassing the API that would refuse it, and asserts the message is
delivered anyway. If someone later moves preference loading above that early
return, this test fails.

**A missing fact is never invented.** This repository has had nine fabrication
defects removed from it, including an endpoint that reported a 4.0 GPA and
honour-roll status for a student with no grades. A template is the easiest
place for the tenth: "your child attended {{count}} classes" with no count is a
cosmetic bug, and the same code path filling it with a zero is a lie to a
parent. The renderer drops the line and says which one it dropped.

**A retried job does not tell a parent twice.** arq retries failed jobs and a
cron run can overlap a slow predecessor. Two workers racing must not both
decide they are the original sender, which is why the claim is an insert
against a unique key rather than a read-then-write.
"""

import datetime
from datetime import datetime as dt
from unittest.mock import patch

import pytest
from sqlmodel import select

from src.db.notification_prefs import (
    NotificationDispatch,
    NotificationPreference,
    NotificationQuietHours,
    NotificationTemplateOverride,
)
from src.db.notifications import Notification, NotificationDelivery
from src.db.sms_identity import SchoolRole, SMSUserRole, StudentGuardian
from src.db.users import User
from src.services.notifications import templates
from src.services.notifications.dispatch import (
    STATUS_QUEUED,
    STATUS_SUPPRESSED,
    compose_idempotency_key,
    notify_event,
    resolve_guardians_of,
)
from src.services.notifications.events import (
    Category,
    NotificationEvent,
    Severity,
    all_events,
    get_event,
    is_registered,
    register_event,
)
from src.services.notifications.preferences import (
    Decision,
    resolve_delivery,
    set_preference,
)

# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------


# Distinguishes "caller did not specify an email" from "caller specified an
# empty one". `email or default` cannot: both None and "" are falsy, so a test
# asking for an address-less user would silently get a perfectly good address
# and assert nothing.
_UNSET = object()


async def _user(db, id_: int, email=_UNSET) -> User:
    u = User(
        id=id_,
        username=f"nf_user{id_}",
        first_name="Test",
        last_name=f"User{id_}",
        email=(f"nf_user{id_}@test.com" if email is _UNSET else email),
        password="hashed",
        user_uuid=f"nf-uuid-{id_}",
        creation_date=str(dt.now()),
        update_date=str(dt.now()),
    )
    db.add(u)
    await db.commit()
    return u


async def _grant(db, user_id: int, org_id: int, role: SchoolRole) -> None:
    db.add(SMSUserRole(user_id=user_id, org_id=org_id, role=role))
    await db.commit()


# Registered once at import. Using dedicated test events rather than the
# built-ins keeps these tests independent of wording Lane J may change.
ROUTINE_EVENT = register_event(
    NotificationEvent(
        key="test.routine_notice",
        category=Category.ACADEMIC,
        severity=Severity.ROUTINE,
        description="A routine academic notice used by the fabric tests.",
        default_audience=(SchoolRole.PARENT,),
        required_context=("student_name",),
    )
)

IMPORTANT_EVENT = register_event(
    NotificationEvent(
        key="test.important_notice",
        category=Category.ATTENDANCE,
        severity=Severity.IMPORTANT,
        description="An important attendance notice used by the fabric tests.",
        default_audience=(SchoolRole.PARENT,),
        dedupe_window_seconds=3600,
    )
)

SAFEGUARDING_EVENT = register_event(
    NotificationEvent(
        key="test.safeguarding_notice",
        category=Category.SAFEGUARDING,
        severity=Severity.SAFEGUARDING,
        description="A safeguarding notice used by the fabric tests.",
        default_audience=(SchoolRole.PSYCHOLOGIST,),
    )
)

templates.register_default_template(
    "test.routine_notice",
    None,
    "Notice about {{student_name}}",
    "<p>Hello.</p><p>This concerns {{student_name}}.</p><p>Score: {{score}}</p>",
)
templates.register_default_template(
    "test.important_notice", None, "Attendance notice", "<p>An attendance notice.</p>"
)
templates.register_default_template(
    "test.safeguarding_notice", None, "Urgent", "<p>A student needs support.</p>"
)


# --------------------------------------------------------------------------
# The taxonomy
# --------------------------------------------------------------------------


class TestEventRegistry:
    def test_unknown_event_raises_rather_than_failing_open(self):
        """`resolve_feature` in this codebase fails open on an unknown key and
        that made several gates decorative. The same mistake here would let a
        typo'd event deliver as ROUTINE, which is mutable."""
        with pytest.raises(KeyError, match="unknown notification event"):
            get_event("test.no_such_event_anywhere")

    def test_redefining_an_event_differently_raises(self):
        """Two modules disagreeing about severity is how a safeguarding message
        would silently become mutable."""
        with pytest.raises(ValueError, match="already registered"):
            register_event(
                NotificationEvent(
                    key="test.routine_notice",
                    category=Category.ACADEMIC,
                    # Conflicting severity. Deliberately IMPORTANT rather than
                    # SAFEGUARDING: the latter would be rejected by
                    # __post_init__ for its category mismatch before
                    # register_event ever saw it, and this test is about the
                    # registry, not the constructor.
                    severity=Severity.IMPORTANT,
                    description="different",
                )
            )

    def test_identical_reregistration_is_allowed(self):
        """Module re-import must not explode."""
        again = register_event(
            NotificationEvent(
                key="test.routine_notice",
                category=Category.ACADEMIC,
                severity=Severity.ROUTINE,
                description="A routine academic notice used by the fabric tests.",
                default_audience=(SchoolRole.PARENT,),
                required_context=("student_name",),
            )
        )
        assert again.key == "test.routine_notice"

    def test_safeguarding_severity_must_sit_in_safeguarding_category(self):
        """Otherwise the settings screen renders a mute toggle that does nothing."""
        with pytest.raises(ValueError, match="must agree"):
            NotificationEvent(
                key="test.mismatched",
                category=Category.ACADEMIC,
                severity=Severity.SAFEGUARDING,
                description="mismatched",
            )

    def test_severity_properties_encode_the_rules(self):
        assert Severity.SAFEGUARDING.is_mutable is False
        assert Severity.IMPORTANT.is_mutable is True
        assert Severity.SAFEGUARDING.respects_quiet_hours is False
        assert Severity.IMPORTANT.respects_quiet_hours is False
        assert Severity.ROUTINE.respects_quiet_hours is True

    def test_catalogue_is_stably_ordered(self):
        """The preferences screen lists these; an unstable order is a UI that
        rearranges itself between visits."""
        assert all_events() == sorted(
            all_events(), key=lambda e: (e.category.value, e.key)
        )
        assert is_registered("finance.fee_reminder")


# --------------------------------------------------------------------------
# Templates: never invent a value
# --------------------------------------------------------------------------


class TestTemplateRendering:
    @pytest.mark.asyncio
    async def test_missing_field_omits_its_line_and_never_renders_a_placeholder(self):
        rendered = await templates.render(
            None, ROUTINE_EVENT, org_id=1, context={"student_name": "Ayesha"}
        )
        # The line we had data for survives.
        assert "Ayesha" in rendered.body_html
        # The line we did not is gone entirely -- not blank, not zero, not braces.
        assert "{{score}}" not in rendered.body_html
        assert "Score:" not in rendered.body_html
        assert "score" in rendered.omitted_fields
        assert rendered.is_complete is False

    @pytest.mark.asyncio
    async def test_complete_context_renders_everything(self):
        rendered = await templates.render(
            None,
            ROUTINE_EVENT,
            org_id=1,
            context={"student_name": "Ayesha", "score": "82%"},
        )
        assert "Ayesha" in rendered.body_html
        assert "82%" in rendered.body_html
        assert rendered.omitted_fields == []
        assert rendered.is_complete is True

    @pytest.mark.asyncio
    async def test_empty_string_counts_as_missing(self):
        """'Amount outstanding: ' with nothing after it is the same failure as
        leaving the placeholder in."""
        rendered = await templates.render(
            None,
            ROUTINE_EVENT,
            org_id=1,
            context={"student_name": "Ayesha", "score": "   "},
        )
        assert "Score:" not in rendered.body_html
        assert "score" in rendered.omitted_fields

    @pytest.mark.asyncio
    async def test_subject_falls_back_to_description_rather_than_showing_braces(self):
        rendered = await templates.render(None, ROUTINE_EVENT, org_id=1, context={})
        assert "{{" not in rendered.subject
        assert rendered.subject == ROUTINE_EVENT.description

    @pytest.mark.asyncio
    async def test_values_are_html_escaped(self):
        """School-entered data reaches an HTML email body."""
        rendered = await templates.render(
            None,
            ROUTINE_EVENT,
            org_id=1,
            context={"student_name": "<script>alert(1)</script>", "score": "1"},
        )
        assert "<script>" not in rendered.body_html
        assert "&lt;script&gt;" in rendered.body_html

    @pytest.mark.asyncio
    async def test_body_never_renders_empty(self):
        """If every line depended on data we lack, say the one true thing we know."""
        event = NotificationEvent(
            key="test.all_placeholders",
            category=Category.ACADEMIC,
            severity=Severity.ROUTINE,
            description="Every line needed data.",
        )
        templates.register_default_template(
            event.key, None, "Subject", "<p>{{a}}</p><p>{{b}}</p>"
        )
        rendered = await templates.render(None, event, org_id=1, context={})
        # Every line was dropped, so the description stands in for the body
        # rather than a parent receiving a blank email.
        assert rendered.body_html.strip()
        assert "Every line needed data." in rendered.body_html
        assert "{{" not in rendered.body_html

    @pytest.mark.asyncio
    async def test_school_override_replaces_the_built_in_wording(self, db, org):
        db.add(
            NotificationTemplateOverride(
                org_id=org.id,
                campus_id=None,
                event_key="test.routine_notice",
                role=None,
                subject="Our own subject",
                body_html="<p>Our own words about {{student_name}}.</p>",
            )
        )
        await db.commit()

        rendered = await templates.render(
            db, ROUTINE_EVENT, org_id=org.id, context={"student_name": "Ayesha"}
        )
        assert rendered.used_override is True
        assert rendered.subject == "Our own subject"
        assert "Our own words about Ayesha" in rendered.body_html

    @pytest.mark.asyncio
    async def test_another_orgs_override_is_not_used(self, db, org):
        """Template text is school-authored content; leaking it across tenants
        is the same class of defect as leaking a record."""
        db.add(
            NotificationTemplateOverride(
                org_id=999,
                event_key="test.routine_notice",
                role=None,
                subject="Other school's subject",
                body_html="<p>Other school.</p>",
            )
        )
        await db.commit()

        rendered = await templates.render(
            db, ROUTINE_EVENT, org_id=org.id, context={"student_name": "Ayesha"}
        )
        assert rendered.used_override is False
        assert "Other school" not in rendered.body_html


# --------------------------------------------------------------------------
# Preferences and quiet hours
# --------------------------------------------------------------------------


class TestPreferences:
    @pytest.mark.asyncio
    async def test_a_muted_user_still_receives_a_safeguarding_message(self, db, org):
        """THE load-bearing test. The mute row is written directly, bypassing
        set_preference() which would refuse it, so this proves the resolver
        short-circuits rather than merely that the API validates."""
        user = await _user(db, 9001)
        db.add(
            NotificationPreference(
                user_id=user.id,
                org_id=org.id,
                event_key=SAFEGUARDING_EVENT.key,
                category=None,
                channel="email",
                enabled=False,
            )
        )
        await db.commit()

        decision = await resolve_delivery(
            db, user_id=user.id, event=SAFEGUARDING_EVENT, channel="email"
        )
        assert decision.allow is True
        assert "cannot be suppressed" in decision.reason

    @pytest.mark.asyncio
    async def test_set_preference_refuses_to_mute_safeguarding(self, db, org):
        """A stored preference that the resolver can never read would leave the
        settings screen showing a switch that does nothing."""
        user = await _user(db, 9002)
        with pytest.raises(ValueError, match="cannot be muted"):
            await set_preference(
                db,
                user_id=user.id,
                channel="email",
                enabled=False,
                event=SAFEGUARDING_EVENT,
            )

    @pytest.mark.asyncio
    async def test_a_muted_routine_event_is_suppressed(self, db, org):
        user = await _user(db, 9003)
        await set_preference(
            db, user_id=user.id, channel="email", enabled=False, event=ROUTINE_EVENT
        )
        decision = await resolve_delivery(
            db, user_id=user.id, event=ROUTINE_EVENT, channel="email"
        )
        assert decision.allow is False
        assert "muted" in decision.reason

    @pytest.mark.asyncio
    async def test_category_mute_covers_its_events(self, db, org):
        """A parent mutes 'academic' once rather than enumerating every event
        that will ever exist in that category."""
        user = await _user(db, 9004)
        await set_preference(
            db,
            user_id=user.id,
            channel="email",
            enabled=False,
            category=Category.ACADEMIC.value,
        )
        decision = await resolve_delivery(
            db, user_id=user.id, event=ROUTINE_EVENT, channel="email"
        )
        assert decision.allow is False

    @pytest.mark.asyncio
    async def test_specific_event_preference_beats_category(self, db, org):
        user = await _user(db, 9005)
        await set_preference(
            db,
            user_id=user.id,
            channel="email",
            enabled=False,
            category=Category.ACADEMIC.value,
        )
        await set_preference(
            db, user_id=user.id, channel="email", enabled=True, event=ROUTINE_EVENT
        )
        decision = await resolve_delivery(
            db, user_id=user.id, event=ROUTINE_EVENT, channel="email"
        )
        assert decision.allow is True

    @pytest.mark.asyncio
    async def test_no_preference_row_means_deliver_not_deny(self, db, org):
        """Absence of configuration is not consent to silence."""
        user = await _user(db, 9006)
        decision = await resolve_delivery(
            db, user_id=user.id, event=ROUTINE_EVENT, channel="email"
        )
        assert decision.allow is True

    @pytest.mark.asyncio
    async def test_quiet_hours_defer_a_routine_message_rather_than_dropping_it(
        self, db, org
    ):
        user = await _user(db, 9007)
        db.add(
            NotificationQuietHours(
                user_id=user.id,
                start_minute=22 * 60,  # 22:00
                end_minute=7 * 60,  # 07:00, wrapping past midnight
                timezone_name="UTC",
            )
        )
        await db.commit()

        at_2300 = datetime.datetime(2026, 9, 14, 23, 0, tzinfo=datetime.timezone.utc)
        decision = await resolve_delivery(
            db, user_id=user.id, event=ROUTINE_EVENT, channel="email", now=at_2300
        )
        assert decision.allow is True, "quiet hours must defer, never discard"
        assert decision.is_deferred is True
        assert decision.deferred_until is not None
        assert decision.deferred_until.hour == 7

    @pytest.mark.asyncio
    async def test_important_severity_ignores_quiet_hours(self, db, org):
        """A child absent today, or a fee due tonight, arrives when it happens."""
        user = await _user(db, 9008)
        db.add(
            NotificationQuietHours(
                user_id=user.id, start_minute=22 * 60, end_minute=7 * 60, timezone_name="UTC"
            )
        )
        await db.commit()

        at_2300 = datetime.datetime(2026, 9, 14, 23, 0, tzinfo=datetime.timezone.utc)
        decision = await resolve_delivery(
            db, user_id=user.id, event=IMPORTANT_EVENT, channel="email", now=at_2300
        )
        assert decision.allow is True
        assert decision.is_deferred is False

    @pytest.mark.asyncio
    async def test_outside_quiet_hours_delivers_immediately(self, db, org):
        user = await _user(db, 9009)
        db.add(
            NotificationQuietHours(
                user_id=user.id, start_minute=22 * 60, end_minute=7 * 60, timezone_name="UTC"
            )
        )
        await db.commit()

        at_1000 = datetime.datetime(2026, 9, 14, 10, 0, tzinfo=datetime.timezone.utc)
        decision = await resolve_delivery(
            db, user_id=user.id, event=ROUTINE_EVENT, channel="email", now=at_1000
        )
        assert decision.is_deferred is False

    @pytest.mark.asyncio
    async def test_quiet_hours_respect_the_recipients_own_timezone(self, db, org):
        """23:00 UTC is 04:00 in Karachi -- inside a 22:00-07:00 window there,
        and the window belongs to the recipient, not the server."""
        user = await _user(db, 9010)
        db.add(
            NotificationQuietHours(
                user_id=user.id,
                start_minute=22 * 60,
                end_minute=7 * 60,
                timezone_name="Asia/Karachi",
            )
        )
        await db.commit()

        at_2300_utc = datetime.datetime(2026, 9, 14, 23, 0, tzinfo=datetime.timezone.utc)
        decision = await resolve_delivery(
            db, user_id=user.id, event=ROUTINE_EVENT, channel="email", now=at_2300_utc
        )
        assert decision.is_deferred is True

    @pytest.mark.asyncio
    async def test_unknown_timezone_falls_back_to_utc_rather_than_raising(self, db, org):
        """A school that typed its timezone wrong must not thereby silence every
        message to every family."""
        user = await _user(db, 9011)
        db.add(
            NotificationQuietHours(
                user_id=user.id,
                start_minute=22 * 60,
                end_minute=7 * 60,
                timezone_name="Not/ARealZone",
            )
        )
        await db.commit()

        decision = await resolve_delivery(
            db, user_id=user.id, event=ROUTINE_EVENT, channel="email"
        )
        assert isinstance(decision, Decision)

    @pytest.mark.asyncio
    async def test_equal_start_and_end_means_no_quiet_hours_not_all_day(self, db, org):
        """The opposite reading would defer everything, forever, silently."""
        user = await _user(db, 9012)
        db.add(
            NotificationQuietHours(
                user_id=user.id, start_minute=0, end_minute=0, timezone_name="UTC"
            )
        )
        await db.commit()

        decision = await resolve_delivery(
            db, user_id=user.id, event=ROUTINE_EVENT, channel="email"
        )
        assert decision.is_deferred is False


# --------------------------------------------------------------------------
# Idempotency
# --------------------------------------------------------------------------


class TestIdempotency:
    def test_same_event_same_recipient_same_window_yields_one_key(self):
        t = datetime.datetime(2026, 9, 14, 12, 0, tzinfo=datetime.timezone.utc)
        a = compose_idempotency_key(
            event_key="finance.fee_reminder",
            recipient_user_id=7,
            related_kind="voucher",
            related_id=3,
            dedupe_window_seconds=86_400,
            now=t,
        )
        b = compose_idempotency_key(
            event_key="finance.fee_reminder",
            recipient_user_id=7,
            related_kind="voucher",
            related_id=3,
            dedupe_window_seconds=86_400,
            now=t + datetime.timedelta(hours=3),
        )
        assert a == b, "a retry three hours later is the same daily reminder"

    def test_different_recipients_yield_different_keys(self):
        t = datetime.datetime(2026, 9, 14, 12, 0, tzinfo=datetime.timezone.utc)
        a = compose_idempotency_key(
            event_key="finance.fee_reminder",
            recipient_user_id=7,
            related_kind="voucher",
            related_id=3,
            dedupe_window_seconds=86_400,
            now=t,
        )
        b = compose_idempotency_key(
            event_key="finance.fee_reminder",
            recipient_user_id=8,
            related_kind="voucher",
            related_id=3,
            dedupe_window_seconds=86_400,
            now=t,
        )
        assert a != b, "both parents must be told"

    def test_zero_window_makes_every_raise_distinct(self):
        a = compose_idempotency_key(
            event_key="x",
            recipient_user_id=1,
            related_kind=None,
            related_id=None,
            dedupe_window_seconds=0,
        )
        b = compose_idempotency_key(
            event_key="x",
            recipient_user_id=1,
            related_kind=None,
            related_id=None,
            dedupe_window_seconds=0,
        )
        assert a != b

    @pytest.mark.asyncio
    async def test_a_retry_does_not_notify_the_same_parent_twice(self, db, org):
        user = await _user(db, 9020)
        await _grant(db, user.id, org.id, SchoolRole.PARENT)

        with patch(
            "src.services.email.utils.send_email", return_value=None
        ) as mock_send:
            first = await notify_event(
                db,
                event_key=IMPORTANT_EVENT.key,
                org_id=org.id,
                recipients=[user],
                related_kind="voucher",
                related_id=42,
            )
            second = await notify_event(
                db,
                event_key=IMPORTANT_EVENT.key,
                org_id=org.id,
                recipients=[user],
                related_kind="voucher",
                related_id=42,
            )

        assert first.created == 1
        assert second.created == 0
        assert second.duplicate == 1
        assert mock_send.call_count == 1, "the parent was emailed exactly once"

        rows = (await db.execute(select(NotificationDispatch))).scalars().all()
        assert len(rows) == 1


# --------------------------------------------------------------------------
# The dispatcher end to end
# --------------------------------------------------------------------------


class TestNotifyEvent:
    @pytest.mark.asyncio
    async def test_missing_org_id_raises_rather_than_defaulting_to_tenant_one(
        self, db, org
    ):
        """`principal.org_id or 1` exists eighteen times in this codebase and
        silently writes one school's data into another's. A notification names
        a child, so this refuses instead."""
        user = await _user(db, 9030)
        with pytest.raises(ValueError, match="requires an explicit org_id"):
            await notify_event(
                db, event_key=ROUTINE_EVENT.key, org_id=None, recipients=[user]
            )

    @pytest.mark.asyncio
    async def test_unregistered_event_sends_nothing_and_does_not_raise(self, db, org):
        user = await _user(db, 9031)
        result = await notify_event(
            db, event_key="test.never_registered", org_id=org.id, recipients=[user]
        )
        assert result.created == 0
        assert result.delivered == 0

    @pytest.mark.asyncio
    async def test_a_provider_failure_records_failed_and_does_not_raise(self, db, org):
        """A register must save even when the mail server is down."""
        user = await _user(db, 9032)
        await _grant(db, user.id, org.id, SchoolRole.PARENT)

        with patch(
            "src.services.email.utils.send_email", side_effect=RuntimeError("smtp down")
        ):
            result = await notify_event(
                db,
                event_key=ROUTINE_EVENT.key,
                org_id=org.id,
                recipients=[user],
                context={"student_name": "Ayesha"},
            )

        assert result.failed >= 1
        assert result.created == 1, "the in-app copy still exists"

        deliveries = (await db.execute(select(NotificationDelivery))).scalars().all()
        assert any(d.status == "failed" and d.channel == "email" for d in deliveries)

    @pytest.mark.asyncio
    async def test_a_suppressed_recipient_is_recorded_as_suppressed_not_failed(
        self, db, org
    ):
        """'Why didn't this parent hear from us' has four different answers and
        an administrator needs the right one."""
        user = await _user(db, 9033)
        await _grant(db, user.id, org.id, SchoolRole.PARENT)
        await set_preference(
            db, user_id=user.id, channel="email", enabled=False, event=ROUTINE_EVENT
        )

        with patch("src.services.email.utils.send_email") as mock_send:
            result = await notify_event(
                db,
                event_key=ROUTINE_EVENT.key,
                org_id=org.id,
                recipients=[user],
                context={"student_name": "Ayesha"},
            )

        assert result.suppressed == 1
        assert result.failed == 0
        mock_send.assert_not_called()

        deliveries = (await db.execute(select(NotificationDelivery))).scalars().all()
        assert any(d.status == STATUS_SUPPRESSED for d in deliveries)
        # The in-app copy still exists: muting email is not muting the app.
        assert result.created == 1

    @pytest.mark.asyncio
    async def test_a_deferred_message_is_queued_not_emailed_yet(self, db, org):
        user = await _user(db, 9034)
        await _grant(db, user.id, org.id, SchoolRole.PARENT)
        db.add(
            NotificationQuietHours(
                user_id=user.id, start_minute=22 * 60, end_minute=7 * 60, timezone_name="UTC"
            )
        )
        await db.commit()

        at_2300 = datetime.datetime(2026, 9, 14, 23, 0, tzinfo=datetime.timezone.utc)
        with patch("src.services.email.utils.send_email") as mock_send:
            result = await notify_event(
                db,
                event_key=ROUTINE_EVENT.key,
                org_id=org.id,
                recipients=[user],
                context={"student_name": "Ayesha"},
                now=at_2300,
            )

        assert result.deferred == 1
        mock_send.assert_not_called()
        deliveries = (await db.execute(select(NotificationDelivery))).scalars().all()
        assert any(d.status == STATUS_QUEUED for d in deliveries)

    @pytest.mark.asyncio
    async def test_omitted_fields_are_reported_to_the_caller(self, db, org):
        """So Lane J can log "we told them less than we meant to" rather than
        discovering it from a parent."""
        user = await _user(db, 9035)
        await _grant(db, user.id, org.id, SchoolRole.PARENT)

        with patch("src.services.email.utils.send_email", return_value=None):
            result = await notify_event(
                db,
                event_key=ROUTINE_EVENT.key,
                org_id=org.id,
                recipients=[user],
                context={"student_name": "Ayesha"},
            )

        assert "score" in result.omitted_fields

    @pytest.mark.asyncio
    async def test_one_recipients_failure_does_not_abort_the_rest(self, db, org):
        """One family's broken address must not cost the other thirty."""
        good = await _user(db, 9036, email="good@test.com")
        # An empty address, not None: `_user` substitutes a default for a falsy
        # argument, so passing None here would silently give this user a
        # perfectly good address and the test would assert nothing.
        bad = await _user(db, 9037, email="")
        await _grant(db, good.id, org.id, SchoolRole.PARENT)
        await _grant(db, bad.id, org.id, SchoolRole.PARENT)

        with patch("src.services.email.utils.send_email", return_value=None):
            result = await notify_event(
                db,
                event_key=ROUTINE_EVENT.key,
                org_id=org.id,
                recipients=[bad, good],
                context={"student_name": "Ayesha"},
            )

        assert result.created == 2, "both got an in-app copy"
        assert result.delivered == 1, "only the one with an address got email"

    @pytest.mark.asyncio
    async def test_duplicate_recipients_are_notified_once(self, db, org):
        """A guardian of two children in one class must not get two copies."""
        user = await _user(db, 9038)
        await _grant(db, user.id, org.id, SchoolRole.PARENT)

        with patch("src.services.email.utils.send_email", return_value=None) as mock_send:
            result = await notify_event(
                db,
                event_key=ROUTINE_EVENT.key,
                org_id=org.id,
                recipients=[user, user],
                context={"student_name": "Ayesha"},
            )

        assert result.created == 1
        assert mock_send.call_count == 1

    @pytest.mark.asyncio
    async def test_default_audience_is_resolved_when_recipients_are_omitted(
        self, db, org
    ):
        psych = await _user(db, 9039)
        await _grant(db, psych.id, org.id, SchoolRole.PSYCHOLOGIST)
        unrelated = await _user(db, 9040)
        await _grant(db, unrelated.id, org.id, SchoolRole.STUDENT)

        with patch("src.services.email.utils.send_email", return_value=None):
            result = await notify_event(
                db, event_key=SAFEGUARDING_EVENT.key, org_id=org.id
            )

        assert result.created == 1, "only the psychologist, not the student"

    @pytest.mark.asyncio
    async def test_no_recipients_sends_nothing_quietly(self, db, org):
        result = await notify_event(
            db, event_key=ROUTINE_EVENT.key, org_id=org.id, recipients=[]
        )
        assert result.created == 0


class TestGuardianResolution:
    @pytest.mark.asyncio
    async def test_resolves_the_guardians_linked_to_a_student(self, db, org):
        student = await _user(db, 9050)
        mother = await _user(db, 9051)
        father = await _user(db, 9052)
        stranger = await _user(db, 9053)

        db.add(StudentGuardian(guardian_user_id=mother.id, student_id=student.id))
        db.add(StudentGuardian(guardian_user_id=father.id, student_id=student.id))
        await db.commit()

        guardians = await resolve_guardians_of(db, student.id)
        ids = {g.id for g in guardians}
        assert ids == {mother.id, father.id}
        assert stranger.id not in ids

    @pytest.mark.asyncio
    async def test_a_student_with_no_guardian_returns_empty_not_everyone(self, db, org):
        """The failure mode worth guarding: an empty filter that matches all."""
        student = await _user(db, 9054)
        await _user(db, 9055)
        assert await resolve_guardians_of(db, student.id) == []
