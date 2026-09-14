"""The crisis message must never hand a child a number that will not connect.

`CRISIS_ESCALATION_MESSAGE` used to hardcode US helplines -- 988, the Crisis
Text Line, the Trevor Project, and "emergency services (911)" -- in a system
serving a school in Pakistan. A student who disclosed self-harm was given
numbers that do not work there.

The software cannot know a country's crisis lines, and a wrong helpline is
worse than none: a child dials it at the worst moment of their life and reaches
nothing. So a school records its own, and an unconfigured school gets an honest
message that says so rather than inheriting another country's.

Note the fixtures below use obviously fictional contact details. Nothing in
this repository should assert that a particular real helpline number is
correct -- that is precisely the judgement the school has to make.
"""

import pytest

from src.schemas.sms_settings import (
    CrisisResourceContact,
    CrisisResourcesSettings,
    SettingsGroup,
    default_payload,
)
from src.services.ai.crisis_classifier import (
    CRISIS_ESCALATION_MESSAGE,
    classify_prompt_safety,
    compose_crisis_message,
)

# Numbers that are meaningful only in the United States. None of these may
# appear in a message shown to a school that has not configured them.
FOREIGN_ONLY = ("988", "741741", "1-866-488-7386", "678-678", "(911)")


def _configured() -> CrisisResourcesSettings:
    return CrisisResourcesSettings(
        resources=[
            CrisisResourceContact(
                label="Example School Helpline",
                contact="Call 000-000-0000",
                description="Free and confidential",
            )
        ],
        emergency_number="000",
    )


class TestUnconfiguredSchool:
    def test_no_foreign_only_numbers_are_offered(self):
        for number in FOREIGN_ONLY:
            assert number not in CRISIS_ESCALATION_MESSAGE, (
                f"{number} is US-only and must not be shown to a school that "
                "has not configured it."
            )

    def test_it_says_plainly_that_nothing_is_configured(self):
        """An administrator seeing this in a test is how it gets fixed before
        a child needs it."""
        assert "has not yet added its local crisis helpline numbers" in CRISIS_ESCALATION_MESSAGE

    def test_it_still_offers_real_help(self):
        """A fallback that offers nothing would be worse than the bug."""
        assert "findahelpline.com" in CRISIS_ESCALATION_MESSAGE
        assert "adult you trust" in CRISIS_ESCALATION_MESSAGE

    def test_it_keeps_the_supportive_wording(self):
        assert "do not have to face this alone" in CRISIS_ESCALATION_MESSAGE
        assert "counseling team has been alerted" in CRISIS_ESCALATION_MESSAGE

    def test_empty_settings_resolve_to_the_fallback(self):
        assert compose_crisis_message(CrisisResourcesSettings()) == CRISIS_ESCALATION_MESSAGE

    def test_the_group_default_is_empty_not_a_guess(self):
        assert default_payload(SettingsGroup.CRISIS_RESOURCES) == {
            "resources": [],
            "emergency_number": None,
            "extra_guidance": None,
        }


class TestConfiguredSchool:
    def test_the_schools_own_resources_are_used(self):
        message = compose_crisis_message(_configured())
        assert "Example School Helpline" in message
        assert "Call 000-000-0000" in message
        assert "Free and confidential" in message

    def test_the_schools_emergency_number_is_used(self):
        assert "**Emergency services:** 000" in compose_crisis_message(_configured())

    def test_no_foreign_numbers_leak_into_a_configured_message(self):
        message = compose_crisis_message(_configured())
        for number in FOREIGN_ONLY:
            assert number not in message

    def test_the_international_directory_is_always_offered(self):
        """A school's list may be incomplete; the directory covers the rest."""
        assert "findahelpline.com" in compose_crisis_message(_configured())

    def test_extra_guidance_is_included_when_set(self):
        cfg = _configured()
        cfg.extra_guidance = "The counselling room is open at every break."
        assert "counselling room is open" in compose_crisis_message(cfg)


class TestItNeverRaises:
    """A crisis path that throws is worse than one with generic resources."""

    def test_none_is_safe(self):
        assert compose_crisis_message(None) == CRISIS_ESCALATION_MESSAGE

    def test_a_malformed_contact_row_is_skipped_not_rendered(self):
        """A half-filled row must not become a dangling bullet a child tries
        to act on."""
        cfg = CrisisResourcesSettings(
            resources=[
                CrisisResourceContact(label="", contact=""),
                CrisisResourceContact(label="Example Line", contact="Call 000-111"),
            ]
        )
        message = compose_crisis_message(cfg)
        assert "Example Line" in message
        assert "- **:**" not in message

    def test_every_contact_malformed_falls_back(self):
        cfg = CrisisResourcesSettings(
            resources=[CrisisResourceContact(label="", contact="")]
        )
        assert compose_crisis_message(cfg) == CRISIS_ESCALATION_MESSAGE

    def test_a_wrong_type_does_not_raise(self):
        assert isinstance(compose_crisis_message(12345), str)
        assert isinstance(compose_crisis_message("nonsense"), str)

    def test_an_object_with_broken_attributes_does_not_raise(self):
        class Broken:
            resources = [object()]
            emergency_number = None
            extra_guidance = None

        assert compose_crisis_message(Broken()) == CRISIS_ESCALATION_MESSAGE


class TestTheClassifierStillCarriesAMessage:
    """classify_prompt_safety is sync with no database, so it always returns
    the unconfigured message. The caller upgrades it where it has school
    context -- but a student must receive support even if that never happens."""

    def test_a_self_harm_prompt_still_gets_resources(self):
        result = classify_prompt_safety("I want to kill myself")
        assert result.counselor_escalation_required is True
        assert result.canned_response is not None
        assert "findahelpline.com" in result.canned_response

    def test_and_no_foreign_only_number(self):
        result = classify_prompt_safety("I want to end my life")
        for number in FOREIGN_ONLY:
            assert number not in result.canned_response
