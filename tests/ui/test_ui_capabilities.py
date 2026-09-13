from pytrain_ui.actions import CAB_ACTIONS_BY_KEY, action_applies_to_type
from pytrain_ui.capabilities import equipment_capabilities


def test_freight_capabilities_include_common_car_and_freight_operations() -> None:
    capabilities = equipment_capabilities("f")

    assert capabilities.supports_tag("pf") is True
    assert capabilities.supports_tag("f") is True
    assert capabilities.supports_tag("d") is False


def test_passenger_capabilities_exclude_diesel_operations() -> None:
    capabilities = equipment_capabilities("p")

    assert capabilities.supports_tag("pf") is True
    assert capabilities.supports_tag("p") is True
    assert capabilities.supports_tag("d") is False


def test_freight_gets_wheel_sounds_but_not_rpm() -> None:
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["flat_wheel"], "f") is True
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["rpm_up"], "f") is False
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["rpm_down"], "f") is False


def test_passenger_gets_next_stop_and_car_lights_but_not_rpm() -> None:
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["next_stop"], "p") is True
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["car_lights_on"], "p") is True
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["car_lights_off"], "p") is True
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["rpm_up"], "p") is False


def test_common_passenger_freight_sound_controls_apply_to_both() -> None:
    for key in ("sound_on", "sound_off", "option_one_on", "option_one_off", "option_two_on", "option_two_off"):
        action = CAB_ACTIONS_BY_KEY[key]
        assert action_applies_to_type(action, "p") is True
        assert action_applies_to_type(action, "f") is True
