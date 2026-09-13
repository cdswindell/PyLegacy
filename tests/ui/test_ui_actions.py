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


def test_action_model_remains_toolkit_neutral() -> None:
    import pytrain_ui.actions as actions

    assert "PySide6" not in actions.__dict__
    assert "guizero" not in actions.__dict__
