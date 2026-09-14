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
    keys = ("sound_on", "sound_off", "option_one_on", "option_one_off", "option_two_on", "option_two_off")
    for key in keys:
        action = CAB_ACTIONS_BY_KEY[key]
        assert action_applies_to_type(action, "p") is True
        assert action_applies_to_type(action, "f") is True


def test_steam_repeat_controls_preserve_engine_gui_cadence() -> None:
    for key in ("let_off", "water_injector"):
        action = CAB_ACTIONS_BY_KEY[key]
        assert action_applies_to_type(action, "s") is True
        assert action.repeat is True
        assert action.repeat_interval_ms == 200


def test_crane_operations_do_not_leak_to_other_types() -> None:
    crane_keys = (
        "crane_sound_on",
        "crane_sound_off",
        "crane_radio",
        "crane_boom",
        "crane_outriggers",
        "crane_main_hook",
        "crane_front_lamp",
        "crane_aux_hook",
        "crane_rear_lamp",
        "crane_toggle",
    )
    for key in crane_keys:
        action = CAB_ACTIONS_BY_KEY[key]
        assert action_applies_to_type(action, "r") is True
        assert action_applies_to_type(action, "d") is False


def test_transformer_operations_match_transformer_layout_family() -> None:
    transformer_keys = (
        "transformer_horn",
        "transformer_bell",
        "transformer_front_coupler",
        "transformer_rear_coupler",
        "transformer_direction",
        "transformer_on",
        "transformer_off",
    )
    for key in transformer_keys:
        action = CAB_ACTIONS_BY_KEY[key]
        assert action_applies_to_type(action, "t") is True
        assert action_applies_to_type(action, "d") is False


def test_acela_uses_specific_variants_where_layout_overrides_engine_cells() -> None:
    # Acela shares ordinary engine RPM/labor/Aux1 cells.
    for key in ("rpm_up", "rpm_down", "labor_up", "labor_down", "sequence"):
        assert action_applies_to_type(CAB_ACTIONS_BY_KEY[key], "a") is True

    # Startup/shutdown and Aux2/Aux3 have dedicated "a" variants in
    # ENGINE_OPS_LAYOUT. The dedicated startup/shutdown variants still use the
    # same immediate/delayed hold behavior as other Legacy engines, while the
    # Acela Aux2/Aux3 keys remain plain buttons.
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["startup"], "a") is False
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["shutdown"], "a") is False
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["lights"], "a") is False
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["more"], "a") is False

    acela_startup = CAB_ACTIONS_BY_KEY["acela_startup"]
    acela_shutdown = CAB_ACTIONS_BY_KEY["acela_shutdown"]
    assert action_applies_to_type(acela_startup, "a") is True
    assert action_applies_to_type(acela_shutdown, "a") is True
    assert acela_startup.hold is True
    assert acela_startup.hold_command == "START_UP_DELAYED"
    assert acela_shutdown.hold is True
    assert acela_shutdown.hold_command == "SHUTDOWN_DELAYED"

    for key in ("acela_aux2", "acela_aux3"):
        action = CAB_ACTIONS_BY_KEY[key]
        assert action_applies_to_type(action, "a") is True
        assert action.hold is False

    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["pantograph_both_down"], "a") is True
    assert action_applies_to_type(CAB_ACTIONS_BY_KEY["pantograph_both_up"], "a") is True


def test_non_engine_aux_variants_keep_plain_button_semantics() -> None:
    assert CAB_ACTIONS_BY_KEY["car_aux1"].repeat_interval_ms == 200
    assert CAB_ACTIONS_BY_KEY["car_aux1"].hold is False
    assert CAB_ACTIONS_BY_KEY["car_aux2"].hold is False
    assert CAB_ACTIONS_BY_KEY["car_aux3"].hold is False
    assert CAB_ACTIONS_BY_KEY["crane_aux1"].repeat_interval_ms == 200
    assert CAB_ACTIONS_BY_KEY["crane_aux1"].hold is False
    assert CAB_ACTIONS_BY_KEY["crane_aux2"].hold is False
    assert CAB_ACTIONS_BY_KEY["crane_aux3"].hold is False
    assert CAB_ACTIONS_BY_KEY["acela_aux2"].hold is False
    assert CAB_ACTIONS_BY_KEY["acela_aux3"].hold is False
    assert CAB_ACTIONS_BY_KEY["acela_aux3"].label == "Aux3 · Arcing"
