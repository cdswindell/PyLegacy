from importlib.resources import files

from pytrain_ui.panels import PanelAction, panel_actions, panel_title


def test_bell_horn_panel_matches_existing_controller_commands() -> None:
    actions = panel_actions("bell_horn")
    assert [(a.section, a.label, a.command) for a in actions] == [
        ("Bell", "Cycle Tone", "CYCLE_BELL_TONE"),
        ("Bell", "Ring / Pause", "RING_BELL"),
        ("Bell", "On", "BELL_ON"),
        ("Bell", "Off", "BELL_OFF"),
        ("Horn", "Cycle Tone", "CYCLE_HORN_TONE"),
        ("Horn", "Blow", "BLOW_HORN_ONE"),
        ("Horn", "Grade Crossing", "GRADE_CROSSING_SEQ"),
    ]


def test_lighting_specs_keep_steam_and_diesel_options_separate() -> None:
    actions = panel_actions("lights")
    diesel = [a for a in actions if "d" in a.type_keys]
    steam = [a for a in actions if "s" in a.type_keys]

    assert {a.command for a in diesel} >= {
        "CAB_AUTO",
        "DITCH_ON",
        "GROUND_AUTO",
        "LOCO_MARKER_AUTO",
        "MARS_ON",
        "RULE_17_AUTO",
        "STROBE_LIGHT_ON_DOUBLE",
    }
    assert "DOGHOUSE_ON" not in {a.command for a in diesel}

    assert {a.command for a in steam} >= {
        "DOGHOUSE_ON",
        "GROUND_AUTO",
        "LOCO_MARKER_AUTO",
        "TENDER_MARKER_ON",
        "MARS_ON",
        "RULE_17_AUTO",
    }
    assert "DITCH_ON" not in {a.command for a in steam}


def test_crew_and_tower_specs_include_full_existing_groups() -> None:
    crew = {a.command for a in panel_actions("crew")}
    tower = {a.command for a in panel_actions("tower")}

    assert {
        "ENGINEER_ACK_CLEARED",
        "ENGINEER_SPEED_STOP_HOLD",
        "ENGINEER_DEPARTURE_GRANTED",
        "ENGINEER_FUEL_LEVEL",
        "ENGINEER_ACK_WELCOME_BACK",
        "CONDUCTOR_WATCH_YOUR_STEP",
        "STATION_DEPARTING",
        "STEWARD_SECOND_SEATING",
        "SPECIAL_GUEST_DISABLED",
    } <= crew
    assert {
        "TOWER_ALL_CLEAR",
        "TOWER_DEPARTURE_DENIED",
        "EMERGENCY_CONTEXT_DEPENDENT",
        "TOWER_CONTEXT_DEPENDENT",
        "TOWER_SPEED_STOP_HOLD",
        "TOWER_SPEED_HIGHBALL",
    } <= tower


def test_passenger_panels_have_controller_view_destinations() -> None:
    assert panel_title("conductor") == "Conductor Actions"
    assert panel_title("steward") == "Steward Dialogs"
    assert panel_title("station") == "Station Dialogs"

    assert {a.command for a in panel_actions("conductor")} == {
        "CONDUCTOR_ALL_ABOARD",
        "CONDUCTOR_NEXT_STOP",
        "CONDUCTOR_PREMATURE_STOP",
        "CONDUCTOR_TICKETS_PLEASE",
        "CONDUCTOR_WATCH_YOUR_STEP",
        "PASSENGER_CAR_STARTUP",
        "PASSENGER_CAR_SHUTDOWN",
        "SPECIAL_GUEST_ENABLED",
        "SPECIAL_GUEST_DISABLED",
    }
    assert {a.command for a in panel_actions("steward")} == {
        "STEWARD_WELCOME_ABOARD",
        "STEWARD_LOUNGE_CAR_OPEN",
        "STEWARD_FIRST_SEATING",
        "STEWARD_SECOND_SEATING",
    }
    assert {a.command for a in panel_actions("station")} == {
        "STATION_ARRIVING",
        "STATION_ARRIVED",
        "STATION_BOARDING",
        "STATION_DEPARTING",
    }


def test_more_panel_covers_command_driven_extra_functions() -> None:
    commands = {a.command for a in panel_actions("more")}
    assert {
        "START_UP_IMMEDIATE",
        "SHUTDOWN_IMMEDIATE",
        "ENGINEER_FUEL_LEVEL",
        "ENGINEER_WATER_LEVEL",
        "SPEED_ROLL",
        "VOLUME_UP",
        "VOLUME_DOWN",
        "AUX_NUMBER_1",
        "AUX_NUMBER_4",
        "LABOR_EFFECT_UP",
        "LABOR_EFFECT_DOWN",
    } <= commands


def test_more_panel_scopes_fuel_and_water_like_controller_view() -> None:
    actions = {action.command: action for action in panel_actions("more")}

    assert actions["ENGINEER_FUEL_LEVEL"].type_keys == frozenset({"d", "s"})
    assert actions["ENGINEER_WATER_LEVEL"].type_keys == frozenset({"s"})


def test_more_panel_describes_short_and_long_press_behavior() -> None:
    actions = {action.command: action for action in panel_actions("more")}

    assert actions["START_UP_IMMEDIATE"].hold_command == "START_UP_DELAYED"
    assert actions["SHUTDOWN_IMMEDIATE"].hold_command == "SHUTDOWN_DELAYED"
    assert actions["ENGINEER_FUEL_LEVEL"].hold_command == "ENGINEER_FUEL_REFILLED"
    assert actions["ENGINEER_WATER_LEVEL"].hold_command == "ENGINEER_WATER_REFILLED"
    hold_commands = (
        "START_UP_IMMEDIATE",
        "SHUTDOWN_IMMEDIATE",
        "ENGINEER_FUEL_LEVEL",
        "ENGINEER_WATER_LEVEL",
    )
    assert all(actions[command].hold_threshold_ms == 1000 for command in hold_commands)


def test_panel_action_rejects_non_positive_hold_threshold() -> None:
    try:
        PanelAction("Engine", "Start Up", "START_UP_IMMEDIATE", hold_threshold_ms=0)
    except ValueError as exc:
        assert "positive hold threshold" in str(exc)
    else:
        raise AssertionError("PanelAction accepted a non-positive hold threshold")


def test_popup_hold_commands_are_not_hardcoded_in_qml() -> None:
    qml = files("pytrain_ui.qt.qml").joinpath("CommandPanelPopup.qml").read_text(encoding="utf-8")
    assert "START_UP_DELAYED" not in qml
    assert "SHUTDOWN_DELAYED" not in qml
    assert "ENGINEER_FUEL_REFILLED" not in qml
    assert "ENGINEER_WATER_REFILLED" not in qml


def test_panel_specs_do_not_import_a_gui_toolkit() -> None:
    import pytrain_ui.panels as panels

    assert "PySide6" not in panels.__dict__
    assert "guizero" not in panels.__dict__
