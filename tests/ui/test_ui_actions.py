from pytrain_ui.actions import CAB_ACTIONS, action_applies_to_type, cab_action, cab_actions


def test_cab_actions_have_stable_unique_keys() -> None:
    actions = cab_actions()
    assert actions == CAB_ACTIONS
    keys = [action.key for action in actions]
    assert len(keys) == len(set(keys))


def test_cab_action_lookup_and_assets() -> None:
    front = cab_action("front_coupler")
    assert front is not None
    assert front.command == "FRONT_COUPLER"
    assert front.icon == "front-coupler.jpg"
    assert front.scope_tag == "cp"
    assert cab_action("does_not_exist") is None


def test_startup_and_shutdown_match_controller_view_long_holds() -> None:
    startup = cab_action("startup")
    shutdown = cab_action("shutdown")
    assert startup is not None and shutdown is not None
    assert startup.command == "START_UP_IMMEDIATE"
    assert startup.hold is True
    assert startup.hold_kind == "command"
    assert startup.hold_command == "START_UP_DELAYED"
    assert startup.hold_threshold_ms == 1000
    assert shutdown.command == "SHUTDOWN_IMMEDIATE"
    assert shutdown.hold is True
    assert shutdown.hold_kind == "command"
    assert shutdown.hold_command == "SHUTDOWN_DELAYED"
    assert shutdown.hold_threshold_ms == 1000


def test_controller_view_panel_holds_are_described_in_action_metadata() -> None:
    crew = cab_action("engineer_chatter")
    tower = cab_action("tower_chatter")
    lights = cab_action("lights")
    more = cab_action("more")
    sequence = cab_action("sequence")

    assert crew is not None and (crew.hold, crew.hold_kind, crew.hold_target) == (True, "panel", "crew")
    assert tower is not None and (tower.hold, tower.hold_kind, tower.hold_target) == (True, "panel", "tower")
    assert lights is not None and (lights.hold, lights.hold_kind, lights.hold_target) == (True, "panel", "lights")
    assert more is not None and (more.hold, more.hold_kind, more.hold_target) == (True, "panel", "more")
    assert sequence is not None and sequence.repeat is True


def test_passenger_holds_match_controller_view_destinations() -> None:
    conductor = cab_action("conductor")
    steward = cab_action("steward")
    station = cab_action("station")
    assert conductor is not None and conductor.scope_tag == "p" and conductor.hold_target == "conductor"
    assert steward is not None and steward.scope_tag == "p" and steward.hold_target == "steward"
    assert station is not None and station.scope_tag == "p" and station.hold_target == "station"
    assert all(action_applies_to_type(a, "p") for a in (conductor, steward, station))
    assert all(not action_applies_to_type(a, "d") for a in (conductor, steward, station))


def test_specialized_actions_mirror_engine_gui_scope_tags() -> None:
    labor = cab_action("labor_up")
    assert labor is not None
    assert labor.command_kind == "sequence"
    assert labor.legacy_only is True
    assert labor.scope_tag == "e"
    assert action_applies_to_type(labor, "d") is True
    assert action_applies_to_type(labor, "s") is True
    assert action_applies_to_type(labor, "f") is False

    front_panto = cab_action("pantograph_front_up")
    assert front_panto is not None
    assert front_panto.scope_tag == "l"
    assert front_panto.icon == "panto-up-f.jpg"
    assert action_applies_to_type(front_panto, "l") is True
    assert action_applies_to_type(front_panto, "d") is False
    assert action_applies_to_type(front_panto, "a") is False

    both_panto = cab_action("pantograph_both_up")
    assert both_panto is not None
    assert both_panto.scope_tag == "a"
    assert action_applies_to_type(both_panto, "a") is True
    assert action_applies_to_type(both_panto, "l") is False


def test_diesel_steam_and_electric_match_existing_controller_visibility_rules() -> None:
    rpm = cab_action("rpm_up")
    smoke = cab_action("smoke_up")
    electric_smoke = cab_action("electric_smoke_up")
    assert rpm is not None and smoke is not None and electric_smoke is not None

    assert action_applies_to_type(rpm, "d") is True
    assert action_applies_to_type(rpm, "s") is False
    assert action_applies_to_type(smoke, "d") is True
    assert action_applies_to_type(smoke, "s") is True
    assert action_applies_to_type(smoke, "l") is False
    assert action_applies_to_type(electric_smoke, "l") is True
    assert action_applies_to_type(electric_smoke, "s") is False


def test_secondary_actions_follow_engine_ops_layout() -> None:
    secondary = cab_actions("secondary")
    assert [action.key for action in secondary] == ["sequence", "lights", "more"]
    assert [action.command for action in secondary] == ["AUX1_OPTION_ONE", "AUX2_OPTION_ONE", "AUX3_OPTION_ONE"]
    assert all(action.scope_tag == "e" for action in secondary)
    assert all(action_applies_to_type(action, "d") for action in secondary)
    assert all(action_applies_to_type(action, "s") for action in secondary)
    assert all(action_applies_to_type(action, "l") for action in secondary)
    assert all(action_applies_to_type(action, "a") for action in secondary)


def test_momentum_tuning_actions_are_engine_scoped() -> None:
    tuning = cab_actions("tuning")
    assert [action.command for action in tuning] == ["MOMENTUM_LOW", "MOMENTUM_MEDIUM", "MOMENTUM_HIGH"]
    assert all(action_applies_to_type(action, "d") for action in tuning)
    assert all(action_applies_to_type(action, "s") for action in tuning)
    assert all(not action_applies_to_type(action, "f") for action in tuning)


def test_action_model_remains_toolkit_neutral() -> None:
    import pytrain_ui.actions as actions

    assert "PySide6" not in actions.__dict__
    assert "guizero" not in actions.__dict__
