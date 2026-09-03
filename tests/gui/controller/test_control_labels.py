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
    ACTION_NOTES,
    ADMIN_PANEL_NOTE,
    ADMIN_PANEL_TITLE,
    BUTTONS_TITLE,
    CATALOG_PANEL_TITLE,
    DPAD_TITLE,
    GLOBAL_CHORD_TITLE,
    LCS_CONFIG_PANEL_TITLE,
    POPUP_PANEL_TITLE,
    ROUTE_PANEL_TITLE,
    SWITCH_PANEL_TITLE,
    ARROW_HORIZONTAL,
    ARROW_RIGHT,
    ARROW_UP,
    ARROW_VERTICAL,
    action_label,
    axis_label,
    button_label,
    chord_label,
    command_label,
    controls_summary,
    touchpad_label,
)
from src.pytrain.gui.controller.steam_deck_input import (
    BACK_PAGE_BUTTON,
    CLOSE_POPUP_BUTTON,
    ROUTE_FIRE_BUTTON_ACTIONS,
    ROUTE_SWALLOW_BUTTON_ACTIONS,
    SELECT_BUTTON,
    SWITCH_AXIS_ACTIONS,
    SWITCH_OUT_ACTIONS,
    SWITCH_OUT_BUTTON_ACTIONS,
    SWITCH_THRU_ACTIONS,
    SWITCH_THRU_BUTTON_ACTIONS,
    ControlProfile,
)

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


def test_the_catalog_row_says_which_pane_it_opens_and_says_it_as_a_note() -> None:
    # Alone among the actions above it says which pane it acts on: the bundled profile files
    # it under the global heading, which cannot speak for a binding scoped to the focused
    # pane. The qualifier is a note rather than part of the label, in the words the
    # focus-scoped headings use -- so the help screen draws it as it draws every other
    # parenthesised aside, a size down, instead of leaving one of them at full size.
    assert ACTION_NOTES["scope_catalog"] == "w focus"
    assert "(" not in action_label("scope_catalog")
    assert f"({ACTION_NOTES['scope_catalog']})" in CATALOG_PANEL_TITLE


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
    entries = _section(ControlProfile.load(None), BUTTONS_TITLE).entries
    rendered = {entry.input: entry.action for entry in entries}

    assert rendered["L1"] == "Rear coupler"
    assert rendered["R4"] == "Volume up"
    assert rendered["R5"] == "Tower chatter"


def test_the_system_buttons_read_with_what_works_anywhere() -> None:
    # View, Menu and the stick clicks do nothing to the engine in front of you and go on
    # working whatever is on screen -- between them they say which pane the rest of the
    # screen is about -- so they lead the global section instead of sitting in the middle of
    # a list of engine commands. No binding says that: the bundled profile has View and the
    # stick clicks on global actions and Menu on a pane-scoped one, so it is the button that
    # files them.
    system = ["View", "Menu", "L3", "R3"]
    sections = {section.title: section for section in controls_summary(ControlProfile.load(None))}

    assert [entry.input for entry in sections[GLOBAL_CHORD_TITLE].entries][: len(system)] == system
    assert not set(system) & {entry.input for entry in sections[BUTTONS_TITLE].entries}


def test_summary_marks_pane_scoped_bindings() -> None:
    # Which pane a stick drives is the thing people get wrong in landscape mode.
    entries = _section(ControlProfile.load(None), "Joysticks").entries

    assert (f"Left stick {ARROW_VERTICAL}", "Throttle LEFT") == (entries[0].input, entries[0].action)
    assert any(entry.action == "Throttle RIGHT" for entry in entries)


def test_sticks_list_throttle_before_direction_per_pane() -> None:
    # Sorting by axis index put Direction first, which is not how anyone thinks about a
    # throttle.
    actions = [entry.action for entry in _section(ControlProfile.load(None), "Joysticks").entries]

    assert actions == ["Throttle LEFT", "Direction LEFT", "Throttle RIGHT", "Direction RIGHT"]


def test_axis_inversion_is_not_surfaced() -> None:
    # The throttle behaves correctly; whether the profile inverts the axis to achieve
    # that is an implementation detail, not something to read on a help screen.
    entries = _section(ControlProfile.load(None), "Joysticks").entries

    assert all("invert" not in entry.note.lower() for entry in entries)


def test_triggers_describe_their_hold_behaviour() -> None:
    # L2/R2 split a tap from a hold via LONG_PRESS_ACTIONS, which the screen has to say.
    # Abbreviated: these two rows sit in the narrow middle column and were the pair that
    # wrapped there, and "w" reads as the qualifier it is.
    entries = {entry.input: entry.note for entry in _section(ControlProfile.load(None), BUTTONS_TITLE).entries}

    assert entries["L2"] == "hold: w dialog"
    assert entries["R2"] == "hold: w dialog"


def test_chords_are_grouped_by_where_they_work() -> None:
    # Where a chord works lives in its heading rather than on every row: as per-row notes
    # they made this the widest column, then wrapped every entry and pushed Close off the
    # display.
    sections = {section.title: section for section in controls_summary(ControlProfile.load(None))}

    # The buttons that work anywhere lead the section, chords after them: a press is
    # simpler than a chord, so it reads first.
    everywhere = sections[GLOBAL_CHORD_TITLE]
    assert [entry.input for entry in everywhere.entries] == ["View", "Menu", "L3", "R3", "L1 + R1", "L3 + R3"]
    # Nothing here is qualified except the one row the heading cannot speak for: Menu opens
    # the catalog of whichever pane has focus, where everything else here works anywhere.
    assert {entry.input: entry.note for entry in everywhere.entries if entry.note} == {"Menu": "w focus"}

    admin = sections[ADMIN_PANEL_TITLE]
    assert [entry.input for entry in admin.entries] == ["L1 + X", "L1 + Y", "L1 + B", "L1 + A"]
    # The hold is the same three seconds for all four, so it is the section's note rather
    # than four copies of itself on the rows. Losing it altogether would make these read
    # like an ordinary chord, which is the one thing they are not.
    assert admin.note == ADMIN_PANEL_NOTE
    assert all(entry.note == "" for entry in admin.entries)

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


def test_the_triggers_are_listed_with_the_buttons() -> None:
    # A section of their own spent a heading saying "these two are analog", which is not
    # what anyone reads a help screen to find out: L2/R2 do one thing on a pull, like a
    # button. They read where they sit on the Deck, directly under the bumpers.
    profile = ControlProfile.load(None)

    assert "Triggers" not in [section.title for section in controls_summary(profile)]
    inputs = [entry.input for entry in _section(profile, BUTTONS_TITLE).entries]
    after_bumper = inputs.index("R1") + 1
    assert inputs[after_bumper : after_bumper + 2] == ["L2", "R2"]
    # And the joysticks keep their section to themselves.
    assert all(
        entry.input.startswith(("Left stick", "Right stick")) for entry in _section(profile, "Joysticks").entries
    )


def test_summary_flags_repeating_buttons() -> None:
    entries = {entry.input: entry.note for entry in _section(ControlProfile.load(None), BUTTONS_TITLE).entries}

    assert entries["X"] == "repeats"
    assert entries["L1"] == ""


def test_the_switch_panel_remap_is_listed() -> None:
    # A panel showing a switch has no engine to drive, so the face buttons, the triggers and
    # the sticks throw the switch there. Without this the screen would describe only their
    # engine meaning.
    section = _section(ControlProfile.load(None), SWITCH_PANEL_TITLE)

    assert section.fixed is True
    assert [entry.input for entry in section.entries] == [
        "A / Y or L2 / R2",
        f"Left stick {ARROW_HORIZONTAL} / {ARROW_VERTICAL}",
        f"Right stick {ARROW_HORIZONTAL} / {ARROW_VERTICAL}",
    ]
    # Each stick's own pane, and the arrows pair off against the actions: horizontal throws
    # thru, vertical throws out. The heading supplies the word "switch".
    assert [entry.action for entry in section.entries] == [
        "Throw thru / out",
        "Throw thru / out LEFT",
        "Throw thru / out RIGHT",
    ]


def test_the_switch_row_names_the_buttons_the_router_claims() -> None:
    # Named from the router's own action sets, as the catalog's way out is named from
    # CLOSE_POPUP_BUTTON: the buttons are claimed by what the profile has them doing on an
    # engine, so a profile that moves sequence control or the horn moves the throw with it,
    # and this row would then be naming a button that does nothing.
    profile = ControlProfile.load(None)
    thru = [button_label(index) for index, b in profile.buttons.items() if b.action in SWITCH_THRU_BUTTON_ACTIONS]
    out = [button_label(index) for index, b in profile.buttons.items() if b.action in SWITCH_OUT_BUTTON_ACTIONS]

    row = _section(profile, SWITCH_PANEL_TITLE).entries[0]

    assert thru == ["A"] and out == ["Y"], "the bundled profile puts sequence control on A and the horn on Y"
    # Both ways of throwing on the one row, in the order the action pairs off against it:
    # thru is A or L2, out is Y or R2. The trigger halves stay literal -- they are the axes
    # DECK_AXIS_LABELS names, and deriving them is Job A of the parked bindings plan.
    assert row.input.startswith(f"{thru[0]} / {out[0]}")
    assert row.action == "Throw thru / out"


@pytest.mark.parametrize(
    ("row", "target", "side"),
    [(1, "left", "Left"), (2, "right", "Right")],
)
def test_the_switch_stick_rows_lead_with_the_axis_that_throws_thru(row, target, side) -> None:
    # The row pairs its two arrows off against "thru / out" by position, so the order is
    # load-bearing in a way the other rows' is not: reversed, the screen tells the reader to
    # push the stick the wrong way. Named from the router's own action sets and the profile's
    # own bindings, as the trigger row's face buttons are, since between them they are what
    # decides which deflection throws which way.
    profile = ControlProfile.load(None)
    thru = SWITCH_THRU_ACTIONS & SWITCH_AXIS_ACTIONS
    out = SWITCH_OUT_ACTIONS & SWITCH_AXIS_ACTIONS
    named = {
        "thru": [axis_label(i) for i, b in profile.axes.items() if b.action in thru and b.target == target],
        "out": [axis_label(i) for i, b in profile.axes.items() if b.action in out and b.target == target],
    }

    entry = _section(profile, SWITCH_PANEL_TITLE).entries[row]

    # The direction axis throws thru and is the horizontal one; the throttle axis throws out
    # and is the vertical one.
    assert named == {"thru": [f"{side} stick {ARROW_HORIZONTAL}"], "out": [f"{side} stick {ARROW_VERTICAL}"]}
    assert entry.input == f"{named['thru'][0]} / {ARROW_VERTICAL}", "the arrow that throws thru leads"
    assert entry.action == f"Throw thru / out {side.upper()}"


def test_the_route_panel_remap_is_listed() -> None:
    # The switch section's twin, and directly under it: a panel showing a route has no
    # engine either, so the same controls fire the route there. One action rather than two,
    # because a route has no un-fire -- both triggers do the one thing.
    #
    # Row for row as the switch section above, each stick naming the pane it fires, because
    # the reader here is asking what that very same stick does now a route is on display.
    # One row for both sticks fitted the column more easily and is what this said first, but
    # it left the pane to be worked out from an "own pane" note rather than read off the row.
    section = _section(ControlProfile.load(None), ROUTE_PANEL_TITLE)

    assert section.fixed is True
    assert [(entry.input, entry.action, entry.note) for entry in section.entries] == [
        ("A or L2 / R2", "Fire route", ""),
        (f"Left stick {ARROW_UP} / {ARROW_RIGHT}", "Fire route LEFT", ""),
        (f"Right stick {ARROW_UP} / {ARROW_RIGHT}", "Fire route RIGHT", ""),
    ]


def test_the_route_row_names_the_one_face_button_that_fires() -> None:
    # Named from the router's own action sets, as the switch row above it is: A fires because
    # the bundled profile has it running sequence control, so a profile that moves that
    # binding moves the fire with it and this row would otherwise name a dead button.
    #
    # Y's absence is the point of the last assertion. The switch row names both face buttons
    # because a switch has two things to do; a route has no un-fire for the second to mean, so
    # Y is claimed there and fires nothing, and a row naming it would promise a second way to
    # fire that does not exist.
    profile = ControlProfile.load(None)
    named = {index: button_label(index) for index in profile.buttons}
    fires = [named[i] for i, b in profile.buttons.items() if b.action in ROUTE_FIRE_BUTTON_ACTIONS]
    swallowed = [named[i] for i, b in profile.buttons.items() if b.action in ROUTE_SWALLOW_BUTTON_ACTIONS]
    routes = _section(profile, ROUTE_PANEL_TITLE)

    assert fires == ["A"] and swallowed == ["Y"], "the bundled profile puts sequence control on A and the horn on Y"
    # "A or L2 / R2": three ways to say the one thing, on the row that has room for them --
    # the trigger halves stay literal, as they do in the switch row.
    assert routes.entries[0].input.startswith(f"{fires[0]} or ")
    assert routes.entries[0].action == "Fire route"
    assert all(swallowed[0] not in entry.input for entry in routes.entries)


def test_the_route_rows_name_only_the_deflections_that_fire() -> None:
    # The switch rows carry the two-headed arrows because sign is ignored there: all four
    # deflections throw. A route fires on up and right alone, and "a / b" would promise
    # four. The distinction is the reader's only clue that pulling back does nothing.
    routes = _section(ControlProfile.load(None), ROUTE_PANEL_TITLE)
    switches = _section(ControlProfile.load(None), SWITCH_PANEL_TITLE)

    assert all(ARROW_VERTICAL not in entry.input for entry in routes.entries)
    assert all(ARROW_HORIZONTAL not in entry.input for entry in routes.entries)
    assert any(ARROW_VERTICAL in entry.input for entry in switches.entries)


def test_the_route_section_follows_the_switch_section() -> None:
    # Directly under it, which is also what puts it in the column that holds nothing but
    # the per-panel sections -- the switch section is the one that opens that column.
    titles = [section.title for section in controls_summary(ControlProfile.load(None))]

    assert titles[titles.index(SWITCH_PANEL_TITLE) + 1] == ROUTE_PANEL_TITLE


@pytest.mark.parametrize("title", [SWITCH_PANEL_TITLE, ROUTE_PANEL_TITLE])
def test_the_panel_remaps_name_their_sticks_as_the_joysticks_section_does(title) -> None:
    # One vocabulary for one control: a row saying "Stick" where the section above says
    # "Left stick" reads like a third stick nobody has, and leaves which pane it throws to
    # the reader to work out. Both remap sections, so a panel type added later has one
    # pattern to copy rather than two to choose between.
    profile = ControlProfile.load(None)
    named_above = {entry.input.rsplit(" ", 1)[0] for entry in _section(profile, "Joysticks").entries}

    sticks = [entry for entry in _section(profile, title).entries if "stick" in entry.input]

    assert named_above == {"Left stick", "Right stick"}
    assert len(sticks) == 2
    assert all(any(entry.input.startswith(name) for name in named_above) for entry in sticks)
    # And the pane on the row rather than in a note: one row per stick is worth the room it
    # costs only if it says which pane that stick works.
    assert [entry.action.rsplit(" ", 1)[-1] for entry in sticks] == ["LEFT", "RIGHT"]


def test_context_sections_are_titled_by_the_panel_they_apply_to() -> None:
    # These describe one kind of panel each, so they are titled the same way: the reader
    # should not have to notice that "Admin panel only" and "While the catalog is open"
    # are the same kind of heading. Aux will join them, as Routes did. The qualifier is the
    # same one the focus-scoped input sections carry, so "only while that panel has focus"
    # is read the same way wherever it appears.
    titles = {section.title for section in controls_summary(ControlProfile.load(None))}

    assert {"Admin Panel (w focus)", "Catalog Panel (w focus)"} <= titles
    assert SWITCH_PANEL_TITLE == "Switches (w focus)"
    assert ROUTE_PANEL_TITLE == "Routes (w focus)"
    assert {BUTTONS_TITLE, DPAD_TITLE} <= titles


def test_the_catalog_lists_both_ways_out_of_it() -> None:
    # X closes the catalog as surely as D-pad left does: the catalog is one of the pane's
    # popups, so the router's close-popup button dismisses it. Both on one row because a
    # reader looking at the catalog is asking how to leave it, and named from the router's
    # own constant so the row cannot go on promising a button that no longer closes popups.
    entries = {entry.input: entry.action for entry in _section(ControlProfile.load(None), CATALOG_PANEL_TITLE).entries}

    assert entries[f"Left or {button_label(CLOSE_POPUP_BUTTON)}"] == "Close catalog"


def test_the_lcs_config_panel_remap_is_listed() -> None:
    # That panel is worked through rather than glanced at, so five keys drive it while it is
    # up and the D-pad section's "Boost / brake speed" is untrue of two of them. Without this
    # the screen would describe only their engine meaning, which is the same reason the
    # switch and route sections exist.
    #
    # Five keys on three rows, and the pane's own two analog controls on a fourth: each row
    # pairs two inputs against what they do, the way the D-pad's own "Up / Down" pairs with
    # "Boost / brake speed". Four is every row there is room for -- see the layout note at
    # the end of controls_summary.
    #
    # Right says "and Next" because that is what it mostly does: on a page whose list is the
    # whole of what it asks, choosing is finishing, so right chooses and turns the page. The
    # exceptions -- the address page and the one page whose only control is a tick box --
    # would cost the row that says what B does.
    #
    # Configure is named on the A row because A presses it: on the last page there is no page
    # to turn to, and after three pages where A meant "next" a key that programs a module is
    # a surprise the screen has to state.
    section = _section(ControlProfile.load(None), LCS_CONFIG_PANEL_TITLE)

    assert section.fixed is True
    assert [(entry.input, entry.action, entry.note) for entry in section.entries] == [
        ("Up / Down", "Move the highlight", ""),
        ("Right / Left", "Choose and Next / undo", ""),
        (f"{button_label(SELECT_BUTTON)} / {button_label(BACK_PAGE_BUTTON)}", "Choose, Next or Configure / Back", ""),
        ("Stick / Pad", "Scroll the page", ""),
    ]


def test_the_lcs_config_rows_name_every_key_the_router_claims() -> None:
    # Named from the router's own constants, as the catalog's way out is named from
    # CLOSE_POPUP_BUTTON: _config_panel_only claims the four pad directions and these two
    # face buttons, and a row that named them literally would go on promising a key that has
    # since moved. Every claimed key has to appear, or the screen leaves one of the five
    # undocumented -- which is the whole complaint the section answers.
    section = _section(ControlProfile.load(None), LCS_CONFIG_PANEL_TITLE)
    named = " ".join(entry.input for entry in section.entries)

    for key in ("Up", "Down", "Right", "Left", button_label(SELECT_BUTTON), button_label(BACK_PAGE_BUTTON)):
        assert key in named, f"{key} drives the panel and is not on the screen"
    # X is not among them, and is not meant to be: it closes this panel through the popup
    # handling every panel is closed by, which the popup section states once for all of them.
    assert button_label(CLOSE_POPUP_BUTTON) not in named


def test_the_lcs_config_stick_and_pad_are_named_as_scrolling_the_page() -> None:
    # A page of that panel can stand taller than the screen leaves room for, and every other
    # row of the section works the controls *on* the page -- so a reader who has run out of
    # page has nothing here to reach for unless the two controls that move the page itself
    # are named (DeckInputRouter._config_panel_scrolled). One row for the two of them, the
    # way the rows above pair two inputs against what they do, and the action says the page
    # moves rather than the highlight on it, which is the row above's job.
    section = _section(ControlProfile.load(None), LCS_CONFIG_PANEL_TITLE)

    scrolling = [entry for entry in section.entries if entry.action.startswith("Scroll")]

    assert len(scrolling) == 1
    assert {"Stick", "Pad"} <= set(scrolling[0].input.split(" / "))
    assert "page" in scrolling[0].action
    # And nowhere else in the section: the key rows are about keys, and a control written up
    # on two rows is a control whose two rows can come to disagree.
    assert [entry.input for entry in section.entries if "Stick" in entry.input] == [scrolling[0].input]


def test_the_lcs_config_section_survives_a_stripped_down_profile() -> None:
    # Fixed sections come from the router, not from bindings, so a profile that binds almost
    # nothing still has to be told what the pad does while that panel is up. The custom
    # profile binds one axis, two buttons and a chord, and none of them is a key this
    # section names.
    profile = ControlProfile.from_dict(CUSTOM_PROFILE)

    section = _section(profile, LCS_CONFIG_PANEL_TITLE)

    assert section.fixed is True
    assert section.entries == _section(ControlProfile.load(None), LCS_CONFIG_PANEL_TITLE).entries


def test_the_lcs_config_section_reads_under_the_row_that_closes_a_panel() -> None:
    # X is the sixth key of that panel's set and is deliberately not one of its rows, so the
    # row that does say it has to be the one above: a reader working through the panel who
    # wants out finds it without leaving the section. It is also what puts the LCS rows at
    # the foot of the column of keys you press rather than among the per-panel sections,
    # which no longer have a column's room for them.
    titles = [section.title for section in controls_summary(ControlProfile.load(None))]

    assert titles[titles.index(POPUP_PANEL_TITLE) + 1] == LCS_CONFIG_PANEL_TITLE


def test_fixed_sections_are_marked_as_such() -> None:
    # The D-pad is handled by the router, not the profile, so a custom profile cannot
    # change it -- the screen must not imply otherwise.
    sections = {section.title: section.fixed for section in controls_summary(ControlProfile.load(None))}

    assert sections[DPAD_TITLE] is True
    assert sections[CATALOG_PANEL_TITLE] is True
    assert sections[ROUTE_PANEL_TITLE] is True
    assert sections[BUTTONS_TITLE] is False


def test_summary_follows_a_custom_profile() -> None:
    # The actual "someone overrode the config" guarantee: nothing about the bundled
    # layout is baked into the help screen.
    profile = ControlProfile.from_dict(CUSTOM_PROFILE)

    buttons = {entry.input: entry.action for entry in _section(profile, BUTTONS_TITLE).entries}
    assert buttons == {"A": "Ring bell LEFT", "Button 11": "Reset"}
    # halt targets global, so it files under the "works anywhere" heading.
    assert [entry.input for entry in _section(profile, GLOBAL_CHORD_TITLE).entries] == ["R1 + Y"]
    assert [entry.action for entry in _section(profile, "Joysticks").entries] == ["Throttle RIGHT"]


def test_empty_sections_are_dropped() -> None:
    # The custom profile binds no trackpads and no pane-scoped chord, so neither heading
    # may appear empty.
    titles = [section.title for section in controls_summary(ControlProfile.from_dict(CUSTOM_PROFILE))]

    assert "Trackpads" not in titles
    assert "Chords" not in titles
    assert BUTTONS_TITLE in titles
