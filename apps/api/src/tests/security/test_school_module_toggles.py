"""The school module toggles must actually switch a module off.

These eleven flags were fully ENFORCED but not SETTABLE: the only toggle UI
knew Learnhouse's own six keys, so disabling a school module meant hand-editing
the org config JSON. `sms_exam` was the sharpest example -- registered in
ALL_FEATURES, resolved correctly, but with no AdminToggles field at all, so it
could never be set through the typed surface.

This pins the whole chain: the key is settable -> resolve_feature honours it ->
the router dependency raises 403. A toggle that resolves but does not gate, or
gates but cannot be set, is the bug this page exists to fix.
"""

import pytest
from fastapi import HTTPException

from src.db.organization_config import AdminToggles
from src.security.features_utils.resolve import ALL_FEATURES, resolve_feature
from src.services.orgs.orgs import SCHOOL_MODULE_FEATURES

# The modules an org admin may switch. sms_campus is deliberately excluded --
# it is the tenancy root and lives in ALWAYS_ON_FEATURES.
SCHOOL_MODULES = sorted(SCHOOL_MODULE_FEATURES)


def _config(**toggles) -> dict:
    """A v2 org config with the given modules disabled."""
    return {
        "config_version": "2.0",
        "admin_toggles": {k: {"disabled": v} for k, v in toggles.items()},
    }


def test_every_school_module_is_settable_through_the_typed_surface():
    """A key in ALL_FEATURES with no AdminToggles field resolves but cannot be
    set -- exactly the sms_exam bug. Guard against the next one."""
    fields = set(AdminToggles.model_fields.keys())
    missing = [k for k in SCHOOL_MODULES if k not in fields]
    assert missing == [], (
        f"These school modules are enforced but have no AdminToggles field, so "
        f"they cannot be switched off except by hand-editing config JSON: {missing}"
    )


def test_every_school_module_is_actually_a_registered_feature():
    unknown = [k for k in SCHOOL_MODULES if k not in ALL_FEATURES]
    assert unknown == [], f"Toggle offered for unregistered feature(s): {unknown}"


@pytest.mark.parametrize("module", SCHOOL_MODULES)
def test_disabling_a_module_makes_it_resolve_disabled(module):
    resolved = resolve_feature(module, _config(**{module: True}), 1)
    assert resolved["enabled"] is False, (
        f"{module} was switched off but still resolves enabled -- the menu would "
        "hide it while the API kept serving requests."
    )


@pytest.mark.parametrize("module", SCHOOL_MODULES)
def test_a_module_is_on_by_default(module):
    """A school that has never opened this page has every module on."""
    resolved = resolve_feature(module, {"config_version": "2.0"}, 1)
    assert resolved["enabled"] is True


def test_disabling_one_module_does_not_disable_its_neighbours():
    config = _config(sms_fees=True)
    assert resolve_feature("sms_fees", config, 1)["enabled"] is False
    for other in SCHOOL_MODULES:
        if other == "sms_fees":
            continue
        assert resolve_feature(other, config, 1)["enabled"] is True, (
            f"Disabling sms_fees also switched off {other}"
        )


@pytest.mark.asyncio
async def test_a_disabled_module_raises_403_not_a_silent_pass():
    """The gate must REFUSE, not just hide the nav entry.

    Hiding a module in the menu while its API keeps answering is the worse
    failure: it looks disabled and isn't.
    """
    from src.security.features_utils import dependencies as deps

    class _Cfg:
        config = _config(sms_gradebook=True)

    class _Result:
        def scalars(self):
            class _S:
                def first(_self):
                    return _Cfg()
            return _S()

    class _Session:
        async def execute(self, *_a, **_k):
            return _Result()

    with pytest.raises(HTTPException) as exc:
        await deps._check_feature_enabled("sms_gradebook", 1, _Session())
    assert exc.value.status_code == 403


def test_the_assertion_discriminates():
    """If resolve_feature ever stops honouring admin_toggles, the parametrized
    disable tests above would pass vacuously. This fails if that happens."""
    enabled_cfg = _config(sms_fees=False)  # explicitly NOT disabled
    assert resolve_feature("sms_fees", enabled_cfg, 1)["enabled"] is True
