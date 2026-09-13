from pytrain_ui.actions import CAB_ACTIONS, cab_action, cab_actions


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
    assert cab_action("does_not_exist") is None


def test_specialized_actions_carry_capability_metadata() -> None:
    labor = cab_action("labor_up")
    assert labor is not None
    assert labor.command_kind == "sequence"
    assert labor.legacy_only is True

    pantograph = cab_action("pantograph_up")
    assert pantograph is not None
    assert pantograph.legacy_only is True
    assert pantograph.engine_types == ("ELECTRIC", "ALSTOM")
    assert pantograph.icon == "panto-up-a.jpg"


def test_action_model_remains_toolkit_neutral() -> None:
    import pytrain_ui.actions as actions

    assert "PySide6" not in actions.__dict__
    assert "guizero" not in actions.__dict__
