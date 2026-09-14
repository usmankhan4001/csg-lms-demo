"""The school's real events, raised through the notification fabric (Lane J).

Lane I built the fabric and proved the fabric. These tests protect the seam
between the fabric and the school: that the right people are told, that telling
them cannot break the thing that happened, and that a message never says more
than the school actually knows.

WHAT EACH TEST IS DEFENDING, and why it is worth a test rather than a comment:

**Telling a family must never break the register.** A teacher submitting a
roll-call is doing the single most time-pressured thing in the school day, at
the classroom door, often on a phone. If a mail outage turns that into a 500
they press save again, and the second submission is what actually corrupts the
data. The notification path is wrapped so that it cannot propagate -- these
tests break delivery deliberately and assert the register still saves.

**A parent hears about their own child and no one else's.** The recipient list
for anything about a student is resolved from that student's own guardian
links, never from a section roster. A school incident routinely involves
several children, and the cheapest possible way to leak one family's business
to another is a notification.

**A message never invents a fact.** Nine fabrication defects have been removed
from this repository. The tenth would be easiest here: a template reading
"{{student_name}} was marked absent" with no name resolved, filled in with a
row id, sends a parent an email about "Student #4471".
"""

import datetime
from datetime import datetime as dt
from unittest.mock import AsyncMock, patch

import pytest

# Imported for their side effect: the test database is built from
# SQLModel.metadata, so a model no test module imports has no table.
from src.db import sms_attendance as _sms_attendance  # noqa: F401
from src.db import sms_discipline as _sms_discipline  # noqa: F401
from src.db import sms_timetable as _sms_timetable  # noqa: F401  (sms_attendance FKs to sms_class_period)
from src.db.sms_identity import SchoolRole, SMSUserRole, StudentGuardian
from src.db.users import User
from src.services.notifications import Severity, get_event
from src.services.sms import school_events


async def _user(db, id_: int, first="", last="") -> User:
    u = User(
        id=id_,
        username=f"se_user{id_}",
        first_name=first,
        last_name=last,
        email=f"se_user{id_}@test.local",
        password="hashed",
        user_uuid=f"se-uuid-{id_}",
        creation_date=str(dt.now()),
        update_date=str(dt.now()),
    )
    db.add(u)
    await db.commit()
    return u


# ---------------------------------------------------------------------------
# The catalogue itself
# ---------------------------------------------------------------------------


class TestCatalogue:
    def test_every_event_is_registered_at_import(self):
        """Import-time registration is the fabric's one hard rule.

        Production runs four worker processes. A `register_event()` executed
        inside a request handler would exist in whichever worker served that
        request, and `notify_event` would raise "unknown event" in the other
        three -- intermittently, under load, in production only. Importing this
        module is what makes the catalogue identical everywhere, so the test
        merely imports it and looks the events up through the public registry.
        """
        for event in (
            school_events.ABSENCE_RECORDED,
            school_events.ABSENCE_STREAK,
            school_events.EXCUSE_REVIEWED,
            school_events.REPORT_CARD_SENT,
            school_events.SUBSTITUTION_ASSIGNED,
            school_events.DISCIPLINE_INCIDENT_SERIOUS,
            school_events.DISCIPLINE_INCIDENT_RECORDED,
        ):
            assert get_event(event.key) is event

    def test_only_genuine_harm_is_unmutable(self):
        """Over-classification would make the preference system decorative.

        If everything is SAFEGUARDING then nothing can be switched off, and a
        family that cannot turn the volume down filters the sender instead --
        at which point the one message that mattered is also unread. Exactly
        one of Lane J's events is unmutable, and it is the serious-incident
        one.
        """
        unmutable = [
            e
            for e in (
                school_events.ABSENCE_RECORDED,
                school_events.ABSENCE_STREAK,
                school_events.EXCUSE_REVIEWED,
                school_events.REPORT_CARD_SENT,
                school_events.SUBSTITUTION_ASSIGNED,
                school_events.DISCIPLINE_INCIDENT_SERIOUS,
                school_events.DISCIPLINE_INCIDENT_RECORDED,
            )
            if e.severity is Severity.SAFEGUARDING
        ]
        assert unmutable == [school_events.DISCIPLINE_INCIDENT_SERIOUS]

    def test_no_event_asks_for_a_free_text_narrative(self):
        """Confidentiality, enforced at the catalogue rather than the template.

        A disciplinary `description`, an attendance `remarks` and a reviewer's
        `review_note` are all written by staff for staff, and all routinely
        name other children. A template can only interpolate what is declared
        in `required_context`, so keeping those names out of it is what stops
        a future template edit from widening the leak.
        """
        forbidden = {"description", "remarks", "notes", "review_note", "reason",
                     "narrative", "ai_narrative"}
        for event in school_events.__all__:
            obj = getattr(school_events, event)
            if not hasattr(obj, "required_context"):
                continue
            leaked = forbidden.intersection(obj.required_context)
            assert not leaked, (
                f"{obj.key} asks for {leaked}, which is staff free text and may "
                f"name other pupils"
            )


# ---------------------------------------------------------------------------
# raise_school_event: the guarantee handlers depend on
# ---------------------------------------------------------------------------


class TestRaiseSchoolEventCannotBreakTheCaller:
    @pytest.mark.asyncio
    async def test_a_missing_tenant_is_dropped_not_raised(self, db):
        """`notify_event` raises ValueError on org_id=None, deliberately.

        That is the right call inside the fabric -- a message naming a child
        must never go out under a guessed tenant. But a handler cannot be
        allowed to 500 because of it, so the wrapper absorbs it. Without this
        the absence path would crash for any principal whose org did not
        resolve.
        """
        result = await school_events.raise_school_event(
            db,
            event_key=school_events.ABSENCE_RECORDED.key,
            org_id=None,
            recipients=[],
            context={"student_name": "A", "date": "2026-01-01"},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_a_delivery_failure_is_dropped_not_raised(self, db):
        """The register is already committed by the time we try to send."""
        with patch(
            "src.services.sms.school_events.notify_event",
            new=AsyncMock(side_effect=RuntimeError("mail provider down")),
        ):
            result = await school_events.raise_school_event(
                db,
                event_key=school_events.ABSENCE_RECORDED.key,
                org_id=1,
                recipients=[],
                context={"student_name": "A", "date": "2026-01-01"},
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_an_unregistered_event_key_does_not_raise(self, db):
        """A typo'd key must not 500 a handler.

        `notify_event` absorbs the lookup failure itself and returns an empty
        result rather than None, so this asserts the guarantee that matters --
        nothing propagates and nothing was sent -- rather than the exact
        sentinel.
        """
        result = await school_events.raise_school_event(
            db,
            event_key="does.not.exist",
            org_id=1,
            recipients=[],
            context={},
        )
        assert result is None or result.created == 0


# ---------------------------------------------------------------------------
# Naming a student
# ---------------------------------------------------------------------------


class TestStudentDisplayName:
    @pytest.mark.asyncio
    async def test_a_named_student_is_named(self, db):
        await _user(db, 77001, first="Ayesha", last="Khan")
        assert await school_events.student_display_name(db, 77001) == "Ayesha Khan"

    @pytest.mark.asyncio
    async def test_an_unknown_student_is_none_not_a_row_id(self, db):
        """Returns None so the fabric drops the line.

        The alternative -- the `f"Student #{id}"` placeholder the previous
        absence-streak subscriber used -- emails a parent about "Student
        #77002", which reads as a system fault and tells them nothing. A
        shorter true message beats a complete false one.
        """
        assert await school_events.student_display_name(db, 77002) is None

    @pytest.mark.asyncio
    async def test_a_nameless_account_falls_back_to_its_username_not_its_id(self, db):
        """`first_name` is NOT NULL, so the real degenerate case is empty
        strings rather than nulls -- an account created by an import that had
        only an email address. A username is a human-chosen identifier and is
        worth sending; a row id is not."""
        await _user(db, 77003, first="", last="")
        assert await school_events.student_display_name(db, 77003) == "se_user77003"


# ---------------------------------------------------------------------------
# Absence: the flow a school performs every morning
# ---------------------------------------------------------------------------


class TestAbsenceNotification:
    @pytest.mark.asyncio
    async def test_a_parent_is_told_about_their_own_child_only(self, db):
        """Recipients come from this student's guardian links, nobody else's."""
        from src.services.notifications import resolve_guardians_of

        await _user(db, 77101, first="Mine", last="Child")
        await _user(db, 77102, first="Other", last="Child")
        await _user(db, 77111, first="My", last="Parent")
        await _user(db, 77112, first="Other", last="Parent")
        db.add(StudentGuardian(guardian_user_id=77111, student_id=77101))
        db.add(StudentGuardian(guardian_user_id=77112, student_id=77102))
        await db.commit()

        mine = await resolve_guardians_of(db, 77101)
        assert [g.id for g in mine] == [77111]

    @pytest.mark.asyncio
    async def test_the_roll_call_still_saves_when_notification_fails(self, db):
        """The whole point of the wrapper, proven through the real endpoint."""
        from datetime import date

        from src.db.sms_attendance import AttendanceStatus
        from src.routers.sms_attendance import submit_batch_roll_call
        from src.schemas.sms_attendance import (
            BatchRollCallRequest,
            RollCallStudentEntry,
        )
        from src.core.keycloak_auth import SUPER_ADMIN, KeycloakUserPrincipal

        await _user(db, 77201, first="Absent", last="Pupil")
        await _user(db, 77211, first="Their", last="Parent")
        db.add(StudentGuardian(guardian_user_id=77211, student_id=77201))
        await db.commit()

        principal = KeycloakUserPrincipal(
            sub="t-1",
            org_id=1,
            roles={SUPER_ADMIN},
            raw_claims={"lh_user_id": 5},
        )

        # Break delivery at the fabric, below the wrapper, so the wrapper is
        # what is actually under test rather than a mock of itself.
        with patch(
            "src.services.sms.school_events.notify_event",
            new=AsyncMock(side_effect=RuntimeError("mail provider down")),
        ):
            response = await submit_batch_roll_call(
                payload=BatchRollCallRequest(
                    section_id=771,
                    date=date(2026, 11, 3),
                    entries=[
                        RollCallStudentEntry(
                            student_id=77201, status=AttendanceStatus.ABSENT
                        )
                    ],
                    marked_by=5,
                ),
                session=db,
                principal=principal,
            )

        assert response.success is True
        assert response.total_recorded == 1


# ---------------------------------------------------------------------------
# Discipline: the confidentiality-sensitive one
# ---------------------------------------------------------------------------


class TestDisciplineSeveritySplit:
    def test_a_serious_incident_is_unmutable_and_a_minor_one_is_not(self):
        """Severity is fixed per event key, so the split must be two events.

        A uniform infringement and a violent assault are the same table row
        with a different severity column. One event would force a choice
        between making playground scuffles unmutable and letting a parent
        silence a safeguarding matter.
        """
        assert school_events.DISCIPLINE_INCIDENT_SERIOUS.severity is Severity.SAFEGUARDING
        assert school_events.DISCIPLINE_INCIDENT_SERIOUS.severity.is_mutable is False
        assert school_events.DISCIPLINE_INCIDENT_RECORDED.severity is Severity.ROUTINE
        assert school_events.DISCIPLINE_INCIDENT_RECORDED.severity.is_mutable is True

    def test_the_severity_bands_cover_every_enum_value(self):
        """A new severity must not silently fall into the routine bucket."""
        from src.db.sms_discipline import IncidentSeverityEnum
        from src.routers.sms_discipline import _SERIOUS_SEVERITIES

        assert _SERIOUS_SEVERITIES == {
            IncidentSeverityEnum.MAJOR,
            IncidentSeverityEnum.CRITICAL,
        }
        remaining = set(IncidentSeverityEnum) - _SERIOUS_SEVERITIES
        assert remaining == {
            IncidentSeverityEnum.MINOR,
            IncidentSeverityEnum.MODERATE,
        }, (
            "A new incident severity was added. Decide deliberately whether a "
            "family can mute it rather than letting it default to routine."
        )


class TestRenderingCannotLeakOrFail:
    """Two properties proven at the renderer, not just asserted in a docstring."""

    @pytest.mark.asyncio
    async def test_staff_free_text_never_reaches_a_family(self):
        """Even when a caller passes the narrative in anyway.

        The catalogue test above proves no event DECLARES these fields. This
        proves the stronger thing: passing them at raise time changes nothing,
        because a template can only interpolate placeholders it contains. So a
        future caller who helpfully adds `description` to the context cannot
        leak another child's name through it.
        """
        from src.services.notifications import templates

        rendered = await templates.render(
            None,
            school_events.DISCIPLINE_INCIDENT_SERIOUS,
            org_id=1,
            context={
                "student_name": "Ali",
                "incident_date": "2026-05-04",
                "severity": "major",
                "description": "pushed Hassan Iqbal in the corridor",
                "notes": "Hassan required first aid",
            },
        )
        blob = rendered.subject + rendered.body_html
        for leaked in ("Hassan", "Iqbal", "corridor", "first aid"):
            assert leaked not in blob, f"staff narrative leaked: {leaked!r}"
        assert "Ali" in blob

    @pytest.mark.asyncio
    async def test_a_guardian_with_no_role_grant_still_gets_a_message(self):
        """A guardian linked to a child but never granted the PARENT role.

        `render` resolves by (event, role) and falls back to (event, None). The
        role comes from an `SMSUserRole` grant, which a hand-linked guardian
        may simply not have -- and with no None entry this raises
        TemplateNotFound, which `notify_event` contains per recipient and
        counts as failed. The parent hears nothing, silently. That is the exact
        failure this lane exists to remove, so every event registers a
        role-agnostic fallback.
        """
        from src.services.notifications import templates

        for event in (
            school_events.ABSENCE_RECORDED,
            school_events.ABSENCE_STREAK,
            school_events.EXCUSE_REVIEWED,
            school_events.REPORT_CARD_SENT,
            school_events.SUBSTITUTION_ASSIGNED,
            school_events.DISCIPLINE_INCIDENT_SERIOUS,
            school_events.DISCIPLINE_INCIDENT_RECORDED,
        ):
            rendered = await templates.render(
                None,
                event,
                org_id=1,
                role=None,
                context={name: "x" for name in event.required_context},
            )
            assert rendered.body_html.strip(), f"{event.key} rendered empty for a roleless recipient"
