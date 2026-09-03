#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""The context table, read as data.

accessory_bindings imports neither tkinter nor guizero, so every one of these runs
without a display -- the same bargain test_control_labels makes. What is checked here is
the shape of the table and the walk over it; what the router then does with a resolved entry
belongs to test_steam_deck_input.
"""

from __future__ import annotations

import pytest

from src.pytrain.gui.controller import steam_deck_input
from src.pytrain.gui.controller.accessory_bindings import (
    ACC_ASC2_CONTEXT,
    ACC_BPC2_CONTEXT,
    ACC_CONTEXT,
    ACC_GENERIC_CONTEXT,
    ACC_SENSOR_TRACK_CONTEXT,
    ANALOG_VERBS,
    AXIS_DIRECTION_NAMES,
    AXIS_VARIANT_ACTIONS,
    DEFAULT_CONTEXTS,
    DPAD_ACTION_NAMES,
    KNOWN_VERBS,
    NEVER_CLAIMED_ACTIONS,
    PANEL_AMC2,
    PANEL_ASC2,
    PANEL_BPC2,
    PANEL_CONTEXT_CHAINS,
    PANEL_GENERIC,
    PANEL_SENSOR_TRACK,
    POPUP_ONLY_ACTIONS,
    VERB_ACC_COMMAND,
    VERB_ASC2_MOMENTARY,
    VERB_LCS_OFF,
    VERB_LCS_ON,
    VERB_ACC_THROTTLE,
    ROUTE_CONTEXT,
    SHUTDOWN_DELAYED,
    SHUTDOWN_IMMEDIATE,
    STARTUP_DELAYED,
    STARTUP_IMMEDIATE,
    SWITCH_CONTEXT,
    VERB_CLAIM,
    VERB_ROUTE_FIRE,
    VERB_SENSOR_TRACK_REVERT,
    VERB_SENSOR_TRACK_SELECT,
    VERB_SENSOR_TRACK_STEP,
    VERB_SWITCH_OUT,
    VERB_SWITCH_THRU,
    ContextSpec,
    Dispatch,
    axis_actions,
    merge_contexts,
    bound_actions,
    resolve,
    resolve_axis,
)


def test_the_module_is_importable_without_a_display() -> None:
    # The reason the table is a module of its own: the whole map has to be readable headless,
    # so nothing here may reach for a toolkit.
    import src.pytrain.gui.controller.accessory_bindings as module
    import sys

    assert "tkinter" not in sys.modules or module.__dict__.get("tk") is None
    assert not any(name.startswith(("tk", "guizero")) for name in vars(module))


def test_the_long_press_action_names_agree_with_the_router() -> None:
    # The table spells these out rather than importing them, steam_deck_input being the module
    # that imports this one. That is only safe while the two agree.
    assert STARTUP_IMMEDIATE == steam_deck_input.STARTUP_IMMEDIATE
    assert STARTUP_DELAYED == steam_deck_input.STARTUP_DELAYED
    assert SHUTDOWN_IMMEDIATE == steam_deck_input.SHUTDOWN_IMMEDIATE
    assert SHUTDOWN_DELAYED == steam_deck_input.SHUTDOWN_DELAYED


def test_every_default_binding_names_a_known_verb() -> None:
    for spec in DEFAULT_CONTEXTS.values():
        for action, dispatch in spec.bindings.items():
            if dispatch is None:
                continue
            assert dispatch.verb in KNOWN_VERBS, f"{spec.name}.{action} names an unknown verb"


def test_every_context_is_named_by_the_key_it_is_filed_under() -> None:
    for name, spec in DEFAULT_CONTEXTS.items():
        assert spec.name == name


def test_every_inherited_context_exists() -> None:
    for spec in DEFAULT_CONTEXTS.values():
        if spec.inherits is not None:
            assert spec.inherits in DEFAULT_CONTEXTS, f"{spec.name} inherits a context that is not there"


@pytest.mark.parametrize(
    ("action", "verb"),
    [
        # Each stick throws its own pane's switch: pushed left or right through, up or down
        # out. The triggers follow the same split -- L2 carries shutdown and throws through,
        # R2 carries startup and throws out -- and so do the face buttons.
        ("direction", VERB_SWITCH_THRU),
        ("throttle", VERB_SWITCH_OUT),
        ("sequence_control", VERB_SWITCH_THRU),
        ("horn", VERB_SWITCH_OUT),
        ("shutdown", VERB_SWITCH_THRU),
        (SHUTDOWN_IMMEDIATE, VERB_SWITCH_THRU),
        (SHUTDOWN_DELAYED, VERB_SWITCH_THRU),
        ("startup", VERB_SWITCH_OUT),
        (STARTUP_IMMEDIATE, VERB_SWITCH_OUT),
        (STARTUP_DELAYED, VERB_SWITCH_OUT),
    ],
)
def test_the_switch_context_throws_each_control_the_way_the_panel_does(action, verb) -> None:
    resolution = resolve((SWITCH_CONTEXT,), action)

    assert resolution is not None
    assert resolution.dispatch.verb == verb


@pytest.mark.parametrize(
    "action",
    ["direction", "throttle", "sequence_control", "shutdown", "startup"],
)
def test_the_route_context_fires_from_everything_but_the_horn(action) -> None:
    resolution = resolve((ROUTE_CONTEXT,), action)

    assert resolution is not None
    assert resolution.dispatch.verb == VERB_ROUTE_FIRE


def test_the_route_context_claims_the_horn_and_sends_nothing() -> None:
    # A route has no un-fire, so Y is not made a second way to say the one thing. It is still
    # claimed: passed on, the horn would sound at whichever engine the pane held before.
    resolution = resolve((ROUTE_CONTEXT,), "horn")

    assert resolution is not None
    assert resolution.dispatch.verb == VERB_CLAIM
    assert resolution.claimed_only


def test_the_two_panel_types_claim_the_same_controls() -> None:
    # They differ in what those controls then do, not in which of them are taken.
    assert bound_actions(DEFAULT_CONTEXTS[SWITCH_CONTEXT]) == bound_actions(DEFAULT_CONTEXTS[ROUTE_CONTEXT])


def test_only_the_sticks_latch() -> None:
    for name in (SWITCH_CONTEXT, ROUTE_CONTEXT):
        assert axis_actions(DEFAULT_CONTEXTS[name]) == {"throttle", "direction"}


def test_a_switch_ignores_the_sign_and_a_route_does_not() -> None:
    # A switch has two things it can be asked to do and a pair of axes to ask them with, so
    # how far the stick moved is all that matters. A route has one, so only up and right act.
    for action in ("throttle", "direction"):
        assert resolve((SWITCH_CONTEXT,), action).dispatch.axis_signed is False
        assert resolve((ROUTE_CONTEXT,), action).dispatch.axis_signed is True


def test_both_contexts_hand_the_face_buttons_back_to_the_catalog() -> None:
    for name in (SWITCH_CONTEXT, ROUTE_CONTEXT):
        spec = DEFAULT_CONTEXTS[name]
        assert spec.yields_to_catalog == {"sequence_control", "horn"}
        # The same two are what can leave a repeat or a burst running behind them.
        assert spec.clears_held == spec.yields_to_catalog


def test_neither_context_claims_what_it_has_not_bound() -> None:
    # HALT, focus, the catalog and the rest keep the meaning they have everywhere else.
    for name in (SWITCH_CONTEXT, ROUTE_CONTEXT):
        assert resolve((name,), "halt") is None
        assert resolve((name,), "scope_catalog") is None
        assert resolve((name,), "bell") is None


def test_an_empty_chain_resolves_nothing() -> None:
    assert resolve((), "throttle") is None


def test_an_unknown_context_name_is_skipped_rather_than_raised() -> None:
    # A malformed profile must not take the gamepad out; the rest of the chain still answers.
    assert resolve(("no_such_context", SWITCH_CONTEXT), "throttle").dispatch.verb == VERB_SWITCH_OUT
    assert resolve(("no_such_context",), "throttle") is None


# --- chain walking -------------------------------------------------------------------------
#
# The switch and route contexts are both flat, having nothing more general to sit over. The
# chain is what the accessory contexts will be built from, so it is exercised here on a table
# written for the purpose rather than left untested until they arrive.


def _chained_table() -> dict[str, ContextSpec]:
    return {
        "base": ContextSpec(name="base", claims_unbound=True, bindings={"bell": Dispatch(VERB_CLAIM)}),
        "middle": ContextSpec(
            name="middle",
            inherits="base",
            bindings={"startup": Dispatch(VERB_SWITCH_THRU), "horn": Dispatch(VERB_SWITCH_OUT)},
        ),
        "outer": ContextSpec(
            name="outer",
            inherits="middle",
            bindings={"horn": Dispatch(VERB_ROUTE_FIRE), "startup": None},
        ),
    }


def test_the_most_specific_link_wins_where_two_define_the_same_action() -> None:
    resolution = resolve(("outer",), "horn", _chained_table())

    assert resolution.context.name == "outer"
    assert resolution.dispatch.verb == VERB_ROUTE_FIRE


def test_an_action_only_the_outer_link_defines_falls_through_to_it() -> None:
    resolution = resolve(("outer",), "bell", _chained_table())

    assert resolution.context.name == "base"
    assert resolution.dispatch.verb == VERB_CLAIM


def test_an_explicit_none_unbinds_without_reaching_the_link_it_inherits() -> None:
    # "Unbind this" has to be expressible, and it must not fall through to the entry it is
    # there to remove.
    resolution = resolve(("outer",), "startup", _chained_table())

    assert resolution is not None, "the base still claims it"
    assert resolution.dispatch is None
    assert resolution.claimed_only


def test_a_claiming_base_swallows_anything_the_chain_leaves_unbound() -> None:
    resolution = resolve(("outer",), "volume_up", _chained_table())

    assert resolution is not None
    assert resolution.context.name == "base"
    assert resolution.claimed_only


def test_an_explicitly_listed_chain_is_walked_in_the_order_given() -> None:
    table = _chained_table()

    assert resolve(("middle", "outer"), "horn", table).dispatch.verb == VERB_SWITCH_OUT
    assert resolve(("outer", "middle"), "horn", table).dispatch.verb == VERB_ROUTE_FIRE


def test_a_cycle_in_the_inheritance_terminates() -> None:
    table = {
        "a": ContextSpec(name="a", inherits="b", bindings={}),
        "b": ContextSpec(name="b", inherits="a", bindings={"horn": Dispatch(VERB_CLAIM)}),
    }

    assert resolve(("a",), "horn", table).dispatch.verb == VERB_CLAIM
    assert resolve(("a",), "bell", table) is None


# --------------------------------------------------------------------------------------- #
# Laying a profile's contexts section over the Python defaults.
# --------------------------------------------------------------------------------------- #


def _base() -> dict[str, ContextSpec]:
    return {
        "acc": ContextSpec(name="acc", claims_unbound=True),
        "acc_bpc2": ContextSpec(
            name="acc_bpc2",
            inherits="acc",
            bindings={"startup": Dispatch(VERB_CLAIM)},
        ),
    }


def test_a_silent_profile_leaves_the_defaults_exactly_as_they_were() -> None:
    assert merge_contexts(None) is DEFAULT_CONTEXTS


def test_an_override_replaces_one_entry_and_leaves_its_neighbours_alone() -> None:
    merged = merge_contexts(
        {"acc_bpc2": {"bindings": {"shutdown": {"verb": "lcs_off"}}}},
        base=_base(),
    )

    # The added entry is there, and the one the override said nothing about survives.
    assert merged["acc_bpc2"].bindings["shutdown"].verb == "lcs_off"
    assert merged["acc_bpc2"].bindings["startup"].verb == VERB_CLAIM
    # And the context it inherits is untouched.
    assert merged["acc"].claims_unbound is True


def test_null_unbinds_an_entry_without_removing_the_claim_below_it() -> None:
    # The distinction the whole None mechanism exists for: the control stops sending, but the
    # base context still swallows it rather than letting it reach an engine.
    merged = merge_contexts({"acc_bpc2": {"bindings": {"startup": None}}}, base=_base())

    assert merged["acc_bpc2"].bindings["startup"] is None
    resolution = resolve(("acc_bpc2",), "startup", merged)
    assert resolution is not None
    assert resolution.claimed_only is True
    assert resolution.context.name == "acc"


def test_a_profile_may_add_a_whole_context_and_chain_it() -> None:
    merged = merge_contexts(
        {
            "acc_asc2": {
                "inherits": "acc_bpc2",
                "bindings": {"sequence_control": {"verb": "asc2_momentary", "both_phases": True}},
            }
        },
        base=_base(),
    )

    assert merged["acc_asc2"].inherits == "acc_bpc2"
    assert merged["acc_asc2"].bindings["sequence_control"].both_phases is True
    # Inherited through the chain rather than restated.
    assert resolve(("acc_asc2",), "startup", merged).dispatch.verb == VERB_CLAIM


def test_a_context_set_to_null_is_dropped_entirely() -> None:
    merged = merge_contexts({"acc_bpc2": None}, base=_base())

    assert "acc_bpc2" not in merged
    assert "acc" in merged


def test_the_flags_are_overridable_and_default_to_what_was_there() -> None:
    merged = merge_contexts(
        {
            "acc_bpc2": {
                "claims_unbound": True,
                "yields_to_catalog": ["sequence_control"],
                "clears_held": ["horn"],
            }
        },
        base=_base(),
    )

    assert merged["acc_bpc2"].claims_unbound is True
    assert merged["acc_bpc2"].yields_to_catalog == frozenset({"sequence_control"})
    assert merged["acc_bpc2"].clears_held == frozenset({"horn"})
    # Silence keeps what the default had.
    assert merge_contexts({"acc": {}}, base=_base())["acc"].claims_unbound is True


@pytest.mark.parametrize(
    "raw",
    [
        "not an object",
        {"Acc Bpc2": {}},
        {"acc_bpc2": "not an object"},
        {"acc_bpc2": {"bindings": "not an object"}},
        {"acc_bpc2": {"bindings": {"shutdown": {"verb": "teleport"}}}},
        {"acc_bpc2": {"bindings": {"shutdown": "not an object"}}},
        {"acc_bpc2": {"bindings": {"shutdown": {"verb": "lcs_off", "data": "loud"}}}},
        {"acc_bpc2": {"bindings": {"shutdown": {"verb": "lcs_off", "command": 7}}}},
        {"acc_bpc2": {"inherits": 3}},
        {"acc_bpc2": {"claims_unbound": "yes"}},
        {"acc_bpc2": {"yields_to_catalog": "horn"}},
    ],
)
def test_a_malformed_entry_is_skipped_rather_than_raised(raw) -> None:
    # ControlProfile.load's discipline: a bad line costs that line. Nothing here may raise,
    # and what was already good has to survive.
    merged = merge_contexts(raw, base=_base())

    assert "shutdown" not in merged["acc_bpc2"].bindings
    assert merged["acc_bpc2"].bindings["startup"].verb == VERB_CLAIM
    assert merged["acc_bpc2"].inherits == "acc"


def test_an_unknown_action_is_skipped_when_the_caller_says_which_are_known() -> None:
    merged = merge_contexts(
        {"acc_bpc2": {"bindings": {"launch_missiles": {"verb": "lcs_on"}}}},
        base=_base(),
        known_actions={"startup", "shutdown"},
    )

    assert "launch_missiles" not in merged["acc_bpc2"].bindings


def test_an_unknown_axis_variant_is_skipped_when_the_caller_says_which_are_known() -> None:
    merged = merge_contexts(
        {"acc_bpc2": {"bindings": {"direction_sideways": {"verb": "lcs_on"}}}},
        base=_base(),
        known_actions={"direction_left", "direction_right"},
    )

    assert "direction_sideways" not in merged["acc_bpc2"].bindings


def test_a_protected_action_cannot_be_rebound_or_swallowed() -> None:
    # HALT has to work whatever is on screen, so no context may claim it -- the same rule
    # _validate_action_target keeps for a HALT that is not global.
    merged = merge_contexts(
        {"acc_bpc2": {"bindings": {"halt": {"verb": "claim"}}}},
        base=_base(),
        protected_actions={"halt"},
    )

    assert "halt" not in merged["acc_bpc2"].bindings


def test_a_command_list_survives_as_a_tuple() -> None:
    merged = merge_contexts(
        {"acc_bpc2": {"bindings": {"startup": {"verb": "acc_command", "command": ["A", "B"]}}}},
        base=_base(),
    )

    assert merged["acc_bpc2"].bindings["startup"].command == ("A", "B")


def test_the_generic_accessory_context_chains_over_the_base() -> None:
    # The aux-key bindings sit in acc_generic rather than in the shared base, so they cannot
    # leak onto a BPC2 or ASC2 panel, where there is no coupler or Boost key to answer them.
    spec = DEFAULT_CONTEXTS[ACC_GENERIC_CONTEXT]

    assert spec.inherits == ACC_CONTEXT
    assert bound_actions(DEFAULT_CONTEXTS[ACC_CONTEXT]) == frozenset()


@pytest.mark.parametrize(
    ("action", "verb", "command"),
    [
        ("throttle", VERB_ACC_THROTTLE, None),
        ("direction", VERB_ACC_COMMAND, "TOGGLE_DIRECTION"),
        ("rear_coupler", VERB_ACC_COMMAND, "REAR_COUPLER"),
        ("front_coupler", VERB_ACC_COMMAND, "FRONT_COUPLER"),
        ("dpad_up", VERB_ACC_COMMAND, "BOOST"),
        ("dpad_down", VERB_ACC_COMMAND, "BRAKE"),
    ],
)
def test_the_generic_panel_binds_the_keys_it_shows(action, verb, command) -> None:
    resolution = resolve(PANEL_CONTEXT_CHAINS[PANEL_GENERIC], action)

    assert resolution.context.name == ACC_GENERIC_CONTEXT
    assert resolution.dispatch.verb == verb
    assert resolution.dispatch.command == command


def test_the_generic_stick_toggle_is_latched_and_sign_blind() -> None:
    # A toggle has no left-hand or right-hand form, so the sign is ignored; and a held stick
    # must toggle once rather than flip a crane for as long as a thumb rests on it.
    dispatch = DEFAULT_CONTEXTS[ACC_GENERIC_CONTEXT].bindings["direction"]

    assert dispatch.axis_latched is True
    assert dispatch.axis_signed is False
    assert "direction" in axis_actions(DEFAULT_CONTEXTS[ACC_GENERIC_CONTEXT])


@pytest.mark.parametrize(
    ("value", "verb"),
    [(-1.0, VERB_LCS_OFF), (1.0, VERB_LCS_ON)],
)
def test_an_axis_variant_is_resolved_before_the_plain_action(value, verb) -> None:
    resolution = resolve_axis(PANEL_CONTEXT_CHAINS[PANEL_BPC2], "direction", value)

    assert resolution.context.name == ACC_BPC2_CONTEXT
    assert resolution.dispatch.verb == verb


@pytest.mark.parametrize("value", [-1.0, 1.0])
def test_an_axis_without_variants_falls_back_to_the_plain_action(value) -> None:
    resolution = resolve_axis(PANEL_CONTEXT_CHAINS[PANEL_GENERIC], "direction", value)

    assert resolution.context.name == ACC_GENERIC_CONTEXT
    assert resolution.dispatch.command == "TOGGLE_DIRECTION"


def test_a_one_sided_axis_override_unbinds_only_that_sign() -> None:
    merged = merge_contexts({ACC_BPC2_CONTEXT: {"bindings": {"direction_right": None}}})

    positive = resolve_axis(PANEL_CONTEXT_CHAINS[PANEL_BPC2], "direction", 1.0, merged)
    negative = resolve_axis(PANEL_CONTEXT_CHAINS[PANEL_BPC2], "direction", -1.0, merged)

    assert positive.claimed_only is True
    assert negative.dispatch.verb == VERB_LCS_OFF


def test_axis_variant_names_are_the_sign_pair_for_each_supported_axis() -> None:
    assert AXIS_DIRECTION_NAMES == {
        "direction": ("direction_left", "direction_right"),
        "throttle": ("throttle_down", "throttle_up"),
    }


def test_the_generic_dpad_entries_repeat_while_held() -> None:
    spec = DEFAULT_CONTEXTS[ACC_GENERIC_CONTEXT]

    assert spec.bindings["dpad_up"].repeat is True
    assert spec.bindings["dpad_down"].repeat is True


def test_only_the_accessory_throttle_is_analog() -> None:
    # An analog entry is sent for its value rather than fired on a press, which is why the
    # router needs a way to tell one apart from a latched axis binding.
    spec = DEFAULT_CONTEXTS[ACC_GENERIC_CONTEXT]

    assert spec.bindings["throttle"].is_analog is True
    assert spec.bindings["direction"].is_analog is False
    assert ANALOG_VERBS <= KNOWN_VERBS


def test_the_generic_panel_lets_go_of_the_shoulder_buttons_for_the_catalog() -> None:
    # L1 and R1 are the admin-chord and catalog-jump modifiers as well as the coupler keys.
    spec = DEFAULT_CONTEXTS[ACC_GENERIC_CONTEXT]

    assert {"front_coupler", "rear_coupler"} <= spec.yields_to_catalog


def test_an_unbound_generic_action_is_claimed_by_the_base() -> None:
    resolution = resolve(PANEL_CONTEXT_CHAINS[PANEL_GENERIC], "bell")

    assert resolution.context.name == ACC_CONTEXT
    assert resolution.claimed_only is True


@pytest.mark.parametrize("chain", [PANEL_CONTEXT_CHAINS[PANEL_BPC2], PANEL_CONTEXT_CHAINS[PANEL_ASC2]])
@pytest.mark.parametrize(
    ("action", "verb"),
    [
        ("startup", VERB_LCS_ON),
        (STARTUP_IMMEDIATE, VERB_LCS_ON),
        (STARTUP_DELAYED, VERB_LCS_ON),
        ("dpad_right", VERB_LCS_ON),
        ("shutdown", VERB_LCS_OFF),
        (SHUTDOWN_IMMEDIATE, VERB_LCS_OFF),
        (SHUTDOWN_DELAYED, VERB_LCS_OFF),
        ("dpad_left", VERB_LCS_OFF),
    ],
)
def test_the_power_district_pair_is_reached_from_both_panels(chain, action, verb) -> None:
    # The ASC2 panel gets the pair by inheriting acc_bpc2 rather than by restating it.
    resolution = resolve(chain, action)

    assert resolution.dispatch.verb == verb


@pytest.mark.parametrize(
    ("value", "verb"),
    [(-1.0, VERB_LCS_OFF), (1.0, VERB_LCS_ON)],
)
def test_the_power_district_stick_pair_is_reached_from_both_panels(value, verb) -> None:
    for panel in (PANEL_BPC2, PANEL_ASC2):
        resolution = resolve_axis(PANEL_CONTEXT_CHAINS[panel], "direction", value)

        assert resolution.context.name == ACC_BPC2_CONTEXT
        assert resolution.dispatch.verb == verb


def test_the_asc2_context_states_only_its_difference() -> None:
    spec = DEFAULT_CONTEXTS[ACC_ASC2_CONTEXT]

    assert spec.inherits == ACC_BPC2_CONTEXT
    assert set(spec.bindings) == {"sequence_control", "dpad_up", "throttle"}


@pytest.mark.parametrize("action", ["sequence_control", "dpad_up"])
def test_the_asc2_momentary_entry_carries_both_phases(action) -> None:
    # The only binding in the table whose release does something: the output is held on while
    # the control is, exactly as the on-screen key behaves.
    dispatch = resolve(PANEL_CONTEXT_CHAINS[PANEL_ASC2], action).dispatch

    assert dispatch.verb == VERB_ASC2_MOMENTARY
    assert dispatch.both_phases is True


@pytest.mark.parametrize("panel", [PANEL_BPC2, PANEL_ASC2])
@pytest.mark.parametrize("action", ["front_coupler", "rear_coupler", "dpad_down", "direction"])
def test_the_generic_aux_bindings_do_not_reach_the_power_district_panels(panel, action) -> None:
    # Neither context inherits acc_generic: there is no coupler, Brake or toggle key on these
    # panels, so the action is claimed by the base and sent nowhere.
    resolution = resolve(PANEL_CONTEXT_CHAINS[panel], action)

    assert resolution.context.name == ACC_CONTEXT
    assert resolution.claimed_only is True


def test_the_vertical_stick_holds_the_asc2_output_and_is_sign_blind() -> None:
    # The plain action rather than the throttle_up / throttle_down pair, so the variant lookup
    # finds neither and falls back to it: a push either way energizes the one output there is.
    for value in (1.0, -1.0):
        resolution = resolve_axis(PANEL_CONTEXT_CHAINS[PANEL_ASC2], "throttle", value)

        assert resolution.context.name == ACC_ASC2_CONTEXT
        assert resolution.dispatch.verb == VERB_ASC2_MOMENTARY
        assert resolution.dispatch.axis_held is True
        assert resolution.dispatch.both_phases is True


def test_the_asc2_stick_is_bound_as_the_plain_action_rather_than_the_sign_pair() -> None:
    bindings = DEFAULT_CONTEXTS[ACC_ASC2_CONTEXT].bindings

    assert "throttle_up" not in bindings
    assert "throttle_down" not in bindings


def test_the_vertical_stick_stays_unbound_on_a_bare_power_district() -> None:
    # There is no momentary output on that panel for a held stick to hold, so it is claimed by
    # the base and dropped rather than reaching an ASC2 entry it does not have.
    resolution = resolve_axis(PANEL_CONTEXT_CHAINS[PANEL_BPC2], "throttle", 1.0)

    assert resolution.context.name == ACC_CONTEXT
    assert resolution.claimed_only is True


# --------------------------------------------------------------------------------------- #
# The Sensor Track panel.
# --------------------------------------------------------------------------------------- #


@pytest.mark.parametrize(("action", "delta"), [("dpad_up", -1), ("dpad_down", 1)])
def test_the_dpad_steps_the_sequence_group_the_way_it_reads_on_screen(action, delta) -> None:
    # Up moves toward "No Action" and down toward "Recorded Sequence", the same convention
    # scroll_catalog(-1) uses for up: the highlight follows the pad rather than opposing it.
    resolution = resolve(PANEL_CONTEXT_CHAINS[PANEL_SENSOR_TRACK], action)

    assert resolution.context.name == ACC_SENSOR_TRACK_CONTEXT
    assert resolution.dispatch.verb == VERB_SENSOR_TRACK_STEP
    assert resolution.dispatch.data == delta


@pytest.mark.parametrize("action", ["dpad_up", "dpad_down"])
def test_the_sequence_step_does_not_repeat_while_the_dpad_is_held(action) -> None:
    # Ten options and a write per step: a held D-pad that repeated would cross the list
    # sending nine commands. One step per press, and the write follows the pause instead.
    dispatch = resolve(PANEL_CONTEXT_CHAINS[PANEL_SENSOR_TRACK], action).dispatch

    assert dispatch.repeat is False
    assert dispatch.both_phases is False
    assert dispatch.is_axis is False


def test_the_sensor_track_context_binds_the_dpad_and_the_two_keys_that_choose() -> None:
    # The panel has one control on it, and choosing from it takes three acts: step, select,
    # revert. Each of the last two has two ways to it, as the power district's On and Off have
    # -- the D-pad pointing the way it reads, and the face key that means the same elsewhere.
    # Everything else -- the sticks, the triggers, the horn -- is left to the acc base.
    bindings = DEFAULT_CONTEXTS[ACC_SENSOR_TRACK_CONTEXT].bindings

    assert set(bindings) == {"dpad_up", "dpad_down", "dpad_right", "dpad_left", "sequence_control", "reset"}
    assert bindings["dpad_up"].data == -1
    assert bindings["dpad_down"].data == 1
    assert bindings["dpad_right"].verb == bindings["sequence_control"].verb == VERB_SENSOR_TRACK_SELECT
    assert bindings["dpad_left"].verb == bindings["reset"].verb == VERB_SENSOR_TRACK_REVERT
    assert not any(dispatch.repeat for dispatch in bindings.values()), "one act per press"
    assert DEFAULT_CONTEXTS[ACC_SENSOR_TRACK_CONTEXT].inherits == ACC_CONTEXT


@pytest.mark.parametrize("action", ["throttle", "direction", "startup", "shutdown", "front_coupler", "horn"])
def test_the_sensor_track_panel_claims_its_other_controls_and_sends_none_of_them(action) -> None:
    # FR-0 on the one panel where the base does nearly all the work: a pane showing a Sensor
    # Track has no engine to drive, so a stick left over from one must not reach it.
    resolution = resolve(PANEL_CONTEXT_CHAINS[PANEL_SENSOR_TRACK], action)

    assert resolution.context.name == ACC_CONTEXT
    assert resolution.claimed_only is True


def test_the_sensor_track_context_states_its_own_catalog_carve_out() -> None:
    # Stated rather than inherited, because _handle_contexts reads yields_to_catalog from
    # whichever context supplied the binding -- and this one binds the D-pad. Inheriting it
    # from acc would not supply it, and an open catalog over this panel would step the
    # Sequence group instead of scrolling.
    spec = DEFAULT_CONTEXTS[ACC_SENSOR_TRACK_CONTEXT]

    assert DPAD_ACTION_NAMES <= spec.yields_to_catalog
    assert "dpad_up" in spec.bindings and "dpad_up" in spec.yields_to_catalog


def test_the_sensor_track_panel_is_the_only_new_chain() -> None:
    # AMC2 stays out: its panel's controls have no bindings, and a chain of nothing but the
    # base would claim every control and send none of them.
    assert PANEL_CONTEXT_CHAINS[PANEL_SENSOR_TRACK] == (ACC_SENSOR_TRACK_CONTEXT, ACC_CONTEXT)
    assert PANEL_AMC2 not in PANEL_CONTEXT_CHAINS


def test_a_held_axis_counts_as_an_axis_for_the_derived_name_sets() -> None:
    # axis_actions feeds the legacy *_AXIS_ACTIONS names the help screen is built from: a mode
    # it did not know about would leave a stick binding invisible to it.
    spec = DEFAULT_CONTEXTS[ACC_ASC2_CONTEXT]

    assert spec.bindings["throttle"].is_axis is True
    assert spec.bindings["sequence_control"].is_axis is False
    assert axis_actions(spec) == {"throttle"}


def test_a_latched_axis_is_still_an_axis() -> None:
    assert DEFAULT_CONTEXTS[ACC_BPC2_CONTEXT].bindings["direction_right"].is_axis is True
    assert axis_actions(DEFAULT_CONTEXTS[ACC_BPC2_CONTEXT]) == {"direction_left", "direction_right"}


def test_each_default_binding_claims_at_most_one_axis_mode() -> None:
    # Latched, held and analog are mutually exclusive: the router would have to pick one, and
    # which it picked would be an accident of the order of its branches.
    for spec in DEFAULT_CONTEXTS.values():
        for action, dispatch in spec.bindings.items():
            if dispatch is None:
                continue
            assert dispatch.axis_modes <= 1, f"{spec.name}.{action} claims two axis modes"


@pytest.mark.parametrize(
    "raw",
    [
        {"verb": VERB_ASC2_MOMENTARY, "axis_held": True, "axis_latched": True},
        {"verb": VERB_ACC_THROTTLE, "axis_held": True},
        {"verb": VERB_ACC_THROTTLE, "axis_latched": True},
    ],
)
def test_a_binding_claiming_two_axis_modes_is_skipped_rather_than_resolved_arbitrarily(raw) -> None:
    merged = merge_contexts({ACC_ASC2_CONTEXT: {"bindings": {"throttle": raw}}})

    assert merged[ACC_ASC2_CONTEXT].bindings["throttle"].verb == VERB_ASC2_MOMENTARY
    assert merged[ACC_ASC2_CONTEXT].bindings["throttle"].axis_held is True
    assert merged[ACC_ASC2_CONTEXT].bindings["throttle"].axis_latched is False


def test_a_profile_may_bind_a_held_axis_of_its_own() -> None:
    merged = merge_contexts(
        {ACC_BPC2_CONTEXT: {"bindings": {"throttle": {"verb": VERB_ASC2_MOMENTARY, "axis_held": True}}}}
    )
    dispatch = resolve_axis(PANEL_CONTEXT_CHAINS[PANEL_BPC2], "throttle", 1.0, merged).dispatch

    assert dispatch.axis_held is True
    assert dispatch.is_axis is True


@pytest.mark.parametrize("panel", [PANEL_GENERIC, PANEL_BPC2, PANEL_ASC2, PANEL_SENSOR_TRACK])
@pytest.mark.parametrize("action", sorted(NEVER_CLAIMED_ACTIONS))
def test_no_accessory_panel_claims_the_controls_it_is_left_by(panel, action) -> None:
    # The defect A-6 records: acc claims every unbound action, and that took in Menu as well
    # as the controls that would drive an engine. A panel the pad cannot leave is worse than
    # one that passes a stick on, so Menu is never swallowed -- with a popup up or without,
    # since being able to *open* the catalog is the point of carving it out at all.
    assert resolve(PANEL_CONTEXT_CHAINS[panel], action) is None
    assert resolve(PANEL_CONTEXT_CHAINS[panel], action, popup_visible=True) is None


@pytest.mark.parametrize("panel", [PANEL_GENERIC, PANEL_BPC2, PANEL_ASC2, PANEL_SENSOR_TRACK])
@pytest.mark.parametrize("action", sorted(POPUP_ONLY_ACTIONS))
def test_no_accessory_panel_claims_x_while_a_popup_is_up(panel, action) -> None:
    # The other half of A-6: a popup is modal, so an X the accessory panel swallowed left the
    # operator with a panel up and no button that would take it down.
    assert resolve(PANEL_CONTEXT_CHAINS[panel], action, popup_visible=True) is None


@pytest.mark.parametrize("panel", [PANEL_GENERIC, PANEL_BPC2, PANEL_ASC2])
@pytest.mark.parametrize("action", sorted(POPUP_ONLY_ACTIONS))
def test_x_is_claimed_again_once_there_is_no_popup_to_close(panel, action) -> None:
    # FR-7 asks of X only that it close an open popup, and the carve-out costs something when
    # it goes further than that: unclaimed, X falls through to the panel-command path and
    # repeats RESET at the pane, which a power district shown under TRAIN scope answers. With
    # nothing open it is an engine control like any other and the acc base swallows it.
    resolution = resolve(PANEL_CONTEXT_CHAINS[panel], action)

    assert resolution is not None
    assert resolution.context.name == ACC_CONTEXT
    assert resolution.claimed_only is True


@pytest.mark.parametrize("action", sorted(POPUP_ONLY_ACTIONS))
def test_the_sensor_track_panel_gives_x_a_meaning_of_its_own_with_no_popup_up(action) -> None:
    # The one accessory panel that binds X rather than swallowing it: with nothing open it is
    # the revert of the Sequence choice (A-7). Sent somewhere rather than dropped, but still
    # not to the engine the pane used to hold, which is all FR-0 asks.
    resolution = resolve(PANEL_CONTEXT_CHAINS[PANEL_SENSOR_TRACK], action)

    assert resolution is not None
    assert resolution.context.name == ACC_SENSOR_TRACK_CONTEXT
    assert resolution.dispatch.verb == VERB_SENSOR_TRACK_REVERT


@pytest.mark.parametrize("action", sorted(NEVER_CLAIMED_ACTIONS | POPUP_ONLY_ACTIONS))
def test_the_never_claimed_actions_are_ones_the_profile_can_bind(action) -> None:
    # Keyed on the action rather than on the button, so the names have to be actions the
    # profile actually knows -- a typo here would carve out nothing at all.
    assert action in steam_deck_input.SUPPORTED_ACTIONS


def test_the_carve_out_sets_name_menu_and_x_on_their_own_terms() -> None:
    # Two sets rather than one, so which of them is conditional is visible in the table rather
    # than hidden in the router.
    assert NEVER_CLAIMED_ACTIONS == {"scope_catalog"}
    assert POPUP_ONLY_ACTIONS == {"reset"}


def test_an_explicit_binding_wins_over_the_carve_out() -> None:
    # A default rather than a prohibition: a profile that deliberately puts something else on
    # Menu gets it, exactly as an explicit binding beats every other default in the table.
    merged = merge_contexts(
        {ACC_BPC2_CONTEXT: {"bindings": {"scope_catalog": {"verb": VERB_LCS_ON}}}},
    )
    resolution = resolve(PANEL_CONTEXT_CHAINS[PANEL_BPC2], "scope_catalog", merged)

    assert resolution.context.name == ACC_BPC2_CONTEXT
    assert resolution.dispatch.verb == VERB_LCS_ON


def test_an_explicit_claim_of_menu_is_honoured_too() -> None:
    # The other half of the same rule: a profile may say "take Menu and do nothing with it",
    # which is a binding like any other and is not what the carve-out protects against.
    merged = merge_contexts({ACC_CONTEXT: {"bindings": {"scope_catalog": {"verb": VERB_CLAIM}}}})
    resolution = resolve(PANEL_CONTEXT_CHAINS[PANEL_GENERIC], "scope_catalog", merged)

    assert resolution.claimed_only is True


def test_an_explicit_unbind_leaves_the_carve_out_standing() -> None:
    # null is "do not bind this", which is the state the carve-out is written for: the action
    # is unbound, so it falls through rather than being swallowed by the claiming base.
    merged = merge_contexts({ACC_BPC2_CONTEXT: {"bindings": {"scope_catalog": None}}})

    assert resolve(PANEL_CONTEXT_CHAINS[PANEL_BPC2], "scope_catalog", merged) is None


def test_the_popup_gated_carve_out_wins_over_an_explicit_binding_of_x() -> None:
    # Where the two carve-outs part company. Menu's is a default an explicit binding beats,
    # but a popup is modal and X is the only way down from it, so a context that took X while
    # one was up would be a panel the pad could not leave -- the dead end the carve-out exists
    # for. The binding is what X means with nothing open, which is the case below.
    #
    # Not hypothetical: the Sensor Track context binds X for its revert (A-7), so a rule that
    # let a binding through here would cost that panel its popup button.
    merged = merge_contexts({ACC_BPC2_CONTEXT: {"bindings": {"reset": {"verb": VERB_LCS_ON}}}})

    assert resolve(PANEL_CONTEXT_CHAINS[PANEL_BPC2], "reset", merged, popup_visible=True) is None

    resolution = resolve(PANEL_CONTEXT_CHAINS[PANEL_BPC2], "reset", merged)

    assert resolution.context.name == ACC_BPC2_CONTEXT
    assert resolution.dispatch.verb == VERB_LCS_ON


def test_an_explicit_unbind_of_x_leaves_the_popup_gated_carve_out_standing() -> None:
    # And null is not a binding for this purpose either: unbound is the state the carve-out is
    # written for, so X still falls through to close the popup.
    merged = merge_contexts({ACC_BPC2_CONTEXT: {"bindings": {"reset": None}}})

    assert resolve(PANEL_CONTEXT_CHAINS[PANEL_BPC2], "reset", merged, popup_visible=True) is None
    assert resolve(PANEL_CONTEXT_CHAINS[PANEL_BPC2], "reset", merged).claimed_only is True


# Every action name that can reach a context: what a profile may bind, the four D-pad names
# the router synthesises, the runtime forms a long-press trigger emits, and the directional
# axis variants. Enumerated rather than sampled, because the failure the carve-out invites is
# a widening nobody notices -- one more name exempted, and a control the pane has no engine
# for reaches whatever engine it held before. The equality below is against the sets, and the
# sets themselves are pinned to their literal members further up, so a widening has to get
# past both to go unnoticed.
_EVERY_ACTION = frozenset(
    steam_deck_input.SUPPORTED_ACTIONS
    | DPAD_ACTION_NAMES
    | steam_deck_input.LONG_PRESS_RUNTIME_ACTIONS
    | AXIS_VARIANT_ACTIONS
)


@pytest.mark.parametrize("panel", [PANEL_GENERIC, PANEL_BPC2, PANEL_ASC2, PANEL_SENSOR_TRACK])
@pytest.mark.parametrize("popup_visible", [False, True])
def test_exactly_the_carve_out_falls_through_and_nothing_else(panel, popup_visible) -> None:
    # The swallow FR-0 asks for, stated as an equality rather than as a spot check: every
    # action either resolves to something or is claimed, and the only ones that reach the
    # handling they have everywhere else are the ones the table names.
    chain = PANEL_CONTEXT_CHAINS[panel]
    fell_through = {action for action in _EVERY_ACTION if resolve(chain, action, popup_visible=popup_visible) is None}

    assert fell_through == NEVER_CLAIMED_ACTIONS | (POPUP_ONLY_ACTIONS if popup_visible else frozenset())


@pytest.mark.parametrize(
    "context", [ACC_CONTEXT, ACC_GENERIC_CONTEXT, ACC_BPC2_CONTEXT, ACC_ASC2_CONTEXT, ACC_SENSOR_TRACK_CONTEXT]
)
def test_every_accessory_context_hands_the_whole_dpad_to_an_open_catalog(context) -> None:
    # An accessory context is the only kind that binds a D-pad direction, and an open catalog
    # needs all four back: up and down scroll it, right confirms and left closes.
    assert DPAD_ACTION_NAMES <= DEFAULT_CONTEXTS[context].yields_to_catalog


@pytest.mark.parametrize(
    "context", [ACC_CONTEXT, ACC_GENERIC_CONTEXT, ACC_BPC2_CONTEXT, ACC_ASC2_CONTEXT, ACC_SENSOR_TRACK_CONTEXT]
)
def test_the_face_buttons_still_yield_alongside_the_dpad(context) -> None:
    # The D-pad is added to that carve-out rather than put in place of it.
    assert {"sequence_control", "horn"} <= DEFAULT_CONTEXTS[context].yields_to_catalog


@pytest.mark.parametrize("context", [SWITCH_CONTEXT, ROUTE_CONTEXT])
def test_the_switch_and_route_contexts_are_left_alone(context) -> None:
    # Neither binds a D-pad action and neither claims what it has not bound, so neither has
    # the defect -- and handing them a carve-out they do not need would be noise in the table.
    spec = DEFAULT_CONTEXTS[context]

    assert not DPAD_ACTION_NAMES & spec.yields_to_catalog
    assert not DPAD_ACTION_NAMES & set(spec.bindings)
    assert spec.claims_unbound is False


def test_the_dpad_action_names_agree_with_the_router() -> None:
    # Spelled out here for the reason the long-press names are, and safe only while they agree.
    assert DPAD_ACTION_NAMES == {
        steam_deck_input.DPAD_UP,
        steam_deck_input.DPAD_DOWN,
        steam_deck_input.DPAD_LEFT,
        steam_deck_input.DPAD_RIGHT,
    }


@pytest.mark.parametrize("context", [ACC_BPC2_CONTEXT, ACC_ASC2_CONTEXT])
def test_neither_power_district_context_chains_through_the_generic_one(context) -> None:
    seen = set()
    name = context
    while name is not None:
        seen.add(name)
        name = DEFAULT_CONTEXTS[name].inherits

    assert ACC_GENERIC_CONTEXT not in seen
    assert ACC_CONTEXT in seen
