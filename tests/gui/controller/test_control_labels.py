#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import pytest

from src.pytrain.gui.controller.control_labels import (
    ADMIN_CHORD_NOTE,
    ADMIN_PANEL_TITLE,
    CATALOG_PANEL_TITLE,
    GLOBAL_CHORD_TITLE,
    SWITCH_PANEL_TITLE,
    ARROW_HORIZONTAL,
    ARROW_VERTICAL,
    action_label,
    axis_label,
    button_label,
    chord_label,
    command_label,
    controls_summary,
    touchpad_label,
)
from src.pytrain.gui.controller.steam_deck_input import ControlProfile

CUSTOM_PROFILE = {
    "dead_zone": 0.15,
    "hysteresis": 0.05,
    "throttle_rate": 36.0,
    "repeat_interval": 0.1,
    "direction_threshold": 0.75,
    "axes": {"1": {"action": "throttle", "target": "right", "invert": True}},
    "buttons": {
        "0": {"action": "bell", "target": "left"},
        "11": {"action": "reset", "target": "focused", "repeat": True},
    },
    "chords": [{"buttons": [5, 3], "action": "halt", "target": "global"}],
}


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        # No table entry for any of these: Mixins.clean_title names them, which is the
        # whole point of resolving through the enums rather than hand-writing English.
        ("rear_coupler", "Rear coupler"),
        ("front_coupler", "Front coupler"),
        ("bell", "Ring bell"),
        ("reset", "Reset"),
        ("volume_up", "Volume up"),
        ("tower_chatter", "Tower chatter"),
    ],
)
def test_engine_commands_are_named_by_their_enum(action, expected) -> None:
    assert action_label(action) == expected


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        # "horn" resolves to BLOW_HORN_ONE, whose clean_title is "Blow Horn One".
        ("horn", "Horn"),
        ("startup", "Startup"),
        ("shutdown", "Shutdown"),
    ],
)
def test_awkward_enum_names_are_overridden(action, expected) -> None:
    assert action_label(action) == expected


def test_app_actions_have_labels_of_their_own() -> None:
    # These drive the GUI rather than an engine, so no enum names them.
    assert action_label("focus_toggle") == "Swap focused pane"
    assert action_label("scope_catalog") == "Open catalog"
    assert action_label("show_controls") == "Show these controls"


def test_an_unknown_action_is_still_readable() -> None:
    # A custom profile can invent action names; the help screen must not raise or print
    # a raw identifier.
    assert action_label("my_custom_thing") == "My custom thing"


def test_command_label_returns_none_for_a_non_command() -> None:
    assert command_label("NOT_A_COMMAND") is None


@pytest.mark.parametrize(
    ("index", "expected"), [(0, "A"), (4, "L1"), (6, "View"), (9, "L3"), (15, "..."), (17, "L4"), (11, "Button 11")]
)
def test_button_labels_including_the_unknown_fallback(index, expected) -> None:
    assert button_label(index) == expected


def test_axis_and_touchpad_fallbacks() -> None:
    assert axis_label(1) == f"Left stick {ARROW_VERTICAL}"
    assert axis_label(0) == f"Left stick {ARROW_HORIZONTAL}"
    assert axis_label(9) == "Axis 9"
    assert touchpad_label(0) == "Left trackpad"
    assert touchpad_label(7) == "Touchpad 7"


def test_chords_render_modifier_first() -> None:
    # ChordBinding.buttons is a frozenset, so display order has to be imposed: never
    # "X + L1".
    assert chord_label(frozenset({2, 4})) == "L1 + X"
    assert chord_label(frozenset({4, 5})) == "L1 + R1"
    assert chord_label(frozenset({0, 4})) == "L1 + A"


def test_chord_with_unknown_buttons_sorts_last_by_index() -> None:
    assert chord_label(frozenset({13, 12, 4})) == "L1 + Button 12 + Button 13"


def _section(profile: ControlProfile, title: str):
    return next(section for section in controls_summary(profile) if section.title == title)


def test_summary_of_the_bundled_profile_names_the_deck_buttons() -> None:
    entries = _section(ControlProfile.load(None), "Buttons").entries
    rendered = {entry.input: entry.action for entry in entries}

    assert rendered["L1"] == "Rear coupler"
    assert rendered["R4"] == "Volume up"
    assert rendered["Menu"] == "Open catalog"


def test_summary_marks_pane_scoped_bindings() -> None:
    # Which pane a stick drives is the thing people get wrong in landscape mode.
    entries = _section(ControlProfile.load(None), "Sticks").entries

    assert (f"Left stick {ARROW_VERTICAL}", "Throttle LEFT") == (entries[0].input, entries[0].action)
    assert any(entry.action == "Throttle RIGHT" for entry in entries)


def test_sticks_list_throttle_before_direction_per_pane() -> None:
    # Sorting by axis index put Direction first, which is not how anyone thinks about a
    # throttle.
    actions = [entry.action for entry in _section(ControlProfile.load(None), "Sticks").entries]

    assert actions == ["Throttle LEFT", "Direction LEFT", "Throttle RIGHT", "Direction RIGHT"]


def test_axis_inversion_is_not_surfaced() -> None:
    # The throttle behaves correctly; whether the profile inverts the axis to achieve
    # that is an implementation detail, not something to read on a help screen.
    entries = _section(ControlProfile.load(None), "Sticks").entries

    assert all("invert" not in entry.note.lower() for entry in entries)


def test_triggers_describe_their_hold_behaviour() -> None:
    # L2/R2 split a tap from a hold via LONG_PRESS_ACTIONS, which the screen has to say.
    entries = {entry.input: entry.note for entry in _section(ControlProfile.load(None), "Triggers").entries}

    assert entries["L2"] == "hold: with dialog"
    assert entries["R2"] == "hold: with dialog"


def test_chords_are_grouped_by_where_they_work() -> None:
    # Where a chord works lives in its heading rather than on every row: as per-row notes
    # they made this the widest column, then wrapped every entry and pushed Close off the
    # display.
    sections = {section.title: section for section in controls_summary(ControlProfile.load(None))}

    everywhere = sections[GLOBAL_CHORD_TITLE]
    assert [entry.input for entry in everywhere.entries] == ["L1 + R1", "L3 + R3"]
    assert all(entry.note == "" for entry in everywhere.entries)

    admin = sections[ADMIN_PANEL_TITLE]
    assert [entry.input for entry in admin.entries] == ["L1 + X", "L1 + Y", "L1 + B", "L1 + A"]
    # The heading names the panel now, so the three-second hold -- which it used to carry --
    # is said per row. Losing it would make these read like an ordinary chord.
    assert all(entry.note == ADMIN_CHORD_NOTE for entry in admin.entries)

    # Nothing left over: the plain "Chords" heading is dropped when it would be empty.
    assert "Chords" not in sections


def test_a_pane_scoped_chord_is_not_filed_under_anywhere() -> None:
    # A custom profile may bind a chord to the focused pane; it must not appear under a
    # heading promising the binding works anywhere.
    profile = ControlProfile.from_dict(
        {
            **CUSTOM_PROFILE,
            "chords": [
                {"buttons": [5, 3], "action": "halt", "target": "global"},
                {"buttons": [5, 1], "action": "bell", "target": "focused"},
            ],
        }
    )
    sections = {section.title: section for section in controls_summary(profile)}

    assert [entry.action for entry in sections[GLOBAL_CHORD_TITLE].entries] == ["HALT - emergency stop"]
    assert [entry.action for entry in sections["Chords"].entries] == ["Ring bell"]


def test_summary_separates_triggers_from_sticks() -> None:
    profile = ControlProfile.load(None)

    assert [entry.input for entry in _section(profile, "Triggers").entries] == ["L2", "R2"]
    assert all(entry.input.startswith(("Left stick", "Right stick")) for entry in _section(profile, "Sticks").entries)


def test_summary_flags_repeating_buttons() -> None:
    entries = {entry.input: entry.note for entry in _section(ControlProfile.load(None), "Buttons").entries}

    assert entries["X"] == "repeats"
    assert entries["L1"] == ""


def test_the_switch_panel_remap_is_listed() -> None:
    # A panel showing a switch has no engine to drive, so the sticks and triggers throw the
    # switch there. Without this the screen would describe only their engine meaning.
    section = _section(ControlProfile.load(None), SWITCH_PANEL_TITLE)

    assert section.fixed is True
    assert [entry.input for entry in section.entries] == [
        "L2 / R2",
        f"Left stick {ARROW_VERTICAL} / {ARROW_HORIZONTAL}",
        f"Right stick {ARROW_VERTICAL} / {ARROW_HORIZONTAL}",
    ]
    # Each stick's own pane, and the arrows pair off against the actions: vertical throws
    # thru, horizontal throws out. The heading supplies the word "switch".
    assert [entry.action for entry in section.entries] == [
        "Throw thru / out",
        "Throw thru / out LEFT",
        "Throw thru / out RIGHT",
    ]


def test_the_switch_panel_names_its_sticks_as_the_sticks_section_does() -> None:
    # One vocabulary for one control: a row saying "Stick" where the section above says
    # "Left stick" reads like a third stick nobody has, and leaves which pane it throws to
    # the reader to work out.
    profile = ControlProfile.load(None)
    named_above = {entry.input.rsplit(" ", 1)[0] for entry in _section(profile, "Sticks").entries}

    switch_sticks = [entry.input for entry in _section(profile, SWITCH_PANEL_TITLE).entries if "stick" in entry.input]

    assert named_above == {"Left stick", "Right stick"}
    assert len(switch_sticks) == 2
    assert all(any(row.startswith(name) for name in named_above) for row in switch_sticks)


def test_context_sections_are_titled_by_the_panel_they_apply_to() -> None:
    # These three describe one kind of panel each, so they are titled the same way: the
    # reader should not have to notice that "Admin panel only" and "While the catalog is
    # open" are the same kind of heading. Routes and Aux will join them.
    titles = {section.title for section in controls_summary(ControlProfile.load(None))}

    assert {"Active Admin Panel", "Active Catalog Panel", "Active Switch Panel"} <= titles


def test_fixed_sections_are_marked_as_such() -> None:
    # The D-pad is handled by the router, not the profile, so a custom profile cannot
    # change it -- the screen must not imply otherwise.
    sections = {section.title: section.fixed for section in controls_summary(ControlProfile.load(None))}

    assert sections["D-pad"] is True
    assert sections[CATALOG_PANEL_TITLE] is True
    assert sections["Buttons"] is False


def test_summary_follows_a_custom_profile() -> None:
    # The actual "someone overrode the config" guarantee: nothing about the bundled
    # layout is baked into the help screen.
    profile = ControlProfile.from_dict(CUSTOM_PROFILE)

    buttons = {entry.input: entry.action for entry in _section(profile, "Buttons").entries}
    assert buttons == {"A": "Ring bell LEFT", "Button 11": "Reset"}
    # halt targets global, so it files under the "works anywhere" heading.
    assert [entry.input for entry in _section(profile, GLOBAL_CHORD_TITLE).entries] == ["R1 + Y"]
    assert [entry.action for entry in _section(profile, "Sticks").entries] == ["Throttle RIGHT"]


def test_empty_sections_are_dropped() -> None:
    # The custom profile binds no trackpads, so that heading must not appear empty.
    titles = [section.title for section in controls_summary(ControlProfile.from_dict(CUSTOM_PROFILE))]

    assert "Trackpads" not in titles
    assert "Triggers" not in titles
    assert "Buttons" in titles
