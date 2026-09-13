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


def test_diesel_and_steam_match_existing_controller_visibility_rules() -> None:
    rpm = cab_action("rpm_up")
    smoke = cab_action("smoke_up")
    assert rpm is not None and smoke is not None

    assert action_applies_to_type(rpm, "d") is True
    assert action_applies_to_type(rpm, "s") is False
    assert action_applies_to_type(smoke, "d") is True
    assert action_applies_to_type(smoke, "s") is True
    assert action_applies_to_type(smoke, "l") is False


def test_action_model_remains_toolkit_neutral() -> None:
    import pytrain_ui.actions as actions

    assert "PySide6" not in actions.__dict__
    assert "guizero" not in actions.__dict__
