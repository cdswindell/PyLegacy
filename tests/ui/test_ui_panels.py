from pytrain_ui.panels import panel_actions, panel_title


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


def test_passenger_panels_have_controller_view_destinations() -> None:
    assert panel_title("conductor") == "Conductor Actions"
    assert panel_title("steward") == "Steward Dialogs"
    assert panel_title("station") == "Station Dialogs"
    assert {a.command for a in panel_actions("conductor")} >= {"CONDUCTOR_ALL_ABOARD", "CONDUCTOR_NEXT_STOP"}
    assert {a.command for a in panel_actions("steward")} >= {"STEWARD_WELCOME_ABOARD", "STEWARD_FIRST_SEATING"}
    assert {a.command for a in panel_actions("station")} == {
        "STATION_ARRIVING", "STATION_ARRIVED", "STATION_BOARDING", "STATION_DEPARTING"
    }


def test_panel_specs_do_not_import_a_gui_toolkit() -> None:
    import pytrain_ui.panels as panels

    assert "PySide6" not in panels.__dict__
    assert "guizero" not in panels.__dict__
