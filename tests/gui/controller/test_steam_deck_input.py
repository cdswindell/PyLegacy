from __future__ import annotations

import os
import queue
import struct
from types import SimpleNamespace

import pytest

from src.pytrain.gui.controller.accessory_bindings import (
    ACC_ASC2_CONTEXT,
    ACC_BPC2_CONTEXT,
    ACC_GENERIC_CONTEXT,
    DEFAULT_CONTEXTS,
    PANEL_ASC2,
    PANEL_BPC2,
    PANEL_CONTEXT_CHAINS,
    PANEL_GENERIC,
)
from src.pytrain.gui.controller.steam_deck_input import (
    DPAD_DOWN,
    DPAD_LEFT,
    DPAD_RIGHT,
    ADMIN_COMMANDS,
    CATALOG_JUMP_MODIFIER,
    DEFAULT_PROFILE,
    DPAD_UP,
    HORN_COMMAND,
    PANEL_COMMANDS,
    QUILLING_HORN,
    SELECT_BUTTON,
    SEQUENCE_CONTROL,
    SEQUENCE_CONTROL_COMMAND,
    SEQUENCE_CONTROL_DURATION,
    SHUTDOWN_DELAYED,
    SHUTDOWN_IMMEDIATE,
    STARTUP_DELAYED,
    STARTUP_IMMEDIATE,
    STARTUP_LONG_PRESS_SECONDS,
    ControlProfile,
    ControllerUnavailable,
    DeckAction,
    DeckInputRouter,
    ProfileError,
    SteamDeckInputProvider,
    TouchpadBinding,
    _DECK_PADDLE_BUTTONS,
    _decode_deck_paddles,
    _decode_deck_pads,
    _deck_pad_y_fraction,
    _find_deck_hidraw_paths,
)


def _profile(**overrides) -> ControlProfile:
    data = {
        "dead_zone": 0.15,
        "hysteresis": 0.05,
        "throttle_rate": 20.0,
        "repeat_interval": 0.1,
        "direction_threshold": 0.75,
        "axes": {
            "1": {"action": "throttle", "target": "left", "invert": True},
            "3": {"action": "throttle", "target": "right", "invert": True},
            "0": {"action": "direction", "target": "left"},
            "2": {"action": "direction", "target": "right"},
        },
        "buttons": {
            "0": {"action": "bell", "target": "focused"},
            "1": {"action": "reset", "target": "right"},
        },
        "chords": [{"buttons": [4, 5], "action": "halt", "target": "global"}],
    }
    data.update(overrides)
    return ControlProfile.from_dict(data)


def _gui(
    speed: int = 0,
    *,
    target_speed: int | None = 0,
    is_cab1: bool = False,
    is_forward: bool = False,
    is_reverse: bool = False,
):
    state = SimpleNamespace(
        speed=speed,
        target_speed=target_speed,
        speed_max=199,
        is_cab1=is_cab1,
        is_forward=is_forward,
        is_reverse=is_reverse,
    )
    gui = SimpleNamespace(throttle_state=state, speed_calls=[], command_calls=[])
    gui.on_speed_command = lambda speed: gui.speed_calls.append(speed)
    gui.on_engine_command = lambda command: gui.command_calls.append(command)
    return gui


def _router(profile: ControlProfile | None = None, *, left=None, right=None):
    left = left or _gui()
    right = right or _gui()
    focused = SimpleNamespace(value=left)
    global_calls: list[str] = []
    router = DeckInputRouter(
        profile or _profile(),
        left=lambda: left,
        right=lambda: right,
        focused=lambda: focused.value,
        global_actions={"halt": lambda: global_calls.append("halt")},
    )
    return router, left, right, focused, global_calls


def test_profile_rejects_unknown_actions_and_unsafe_axis_targets() -> None:
    with pytest.raises(ProfileError, match="Unknown action"):
        _profile(buttons={"0": {"action": "launch_missiles", "target": "left"}})
    with pytest.raises(ProfileError, match="fixed panel"):
        _profile(axes={"1": {"action": "throttle", "target": "focused"}})
    with pytest.raises(ProfileError, match="dead_zone"):
        _profile(dead_zone=1.0)


def test_invalid_external_profile_falls_back_to_bundled_default(tmp_path) -> None:
    profile_path = tmp_path / "invalid.json"
    profile_path.write_text('{"dead_zone": "wide open"}', encoding="utf-8")

    profile = ControlProfile.load(profile_path)

    assert profile.axes[1].action == "throttle"
    assert profile.axes[1].target == "left"


def test_bundled_profile_maps_right_stick_to_steam_input_axes() -> None:
    profile = ControlProfile.load()

    assert profile.axes[0].action == "direction"
    assert profile.axes[1].action == "throttle"
    assert profile.axes[3].action == "direction"
    assert profile.axes[3].target == "right"
    assert profile.axes[4].action == "throttle"
    assert profile.axes[4].target == "right"
    assert profile.axes[4].invert is True
    # Axes 2 and 5 (the L2/R2 triggers) act as buttons carrying the
    # shutdown/startup short-vs-long-press commands.
    assert profile.axes[2].action == "shutdown"
    assert profile.axes[5].action == "startup"


def test_bundled_profile_binds_view_button_to_focus_toggle() -> None:
    profile = ControlProfile.load()

    assert profile.buttons[6].action == "focus_toggle"
    assert profile.buttons[6].target == "global"


def test_focus_toggle_requires_global_target() -> None:
    with pytest.raises(ProfileError, match="focus_toggle must target global"):
        _profile(buttons={"6": {"action": "focus_toggle", "target": "focused"}})


def test_focus_toggle_routes_to_registered_global_action() -> None:
    global_calls: list[str] = []
    router = DeckInputRouter(
        _profile(buttons={"6": {"action": "focus_toggle", "target": "global"}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: _gui(),
        global_actions={"focus_toggle": lambda: global_calls.append("toggle")},
    )

    router.handle(DeckAction("focus_toggle", "global", 1.0, "pressed"))
    router.handle(DeckAction("focus_toggle", "global", 0.0, "released"))

    assert global_calls == ["toggle"]


def test_bundled_profile_binds_menu_button_to_scope_catalog() -> None:
    profile = ControlProfile.load()

    assert profile.buttons[7].action == "scope_catalog"
    assert profile.buttons[7].target == "focused"


def test_bundled_profile_binds_shoulder_buttons_to_couplers() -> None:
    # The L1/R1 shoulder buttons (indices 4 and 5) open the couplers: L1 the
    # rear coupler and R1 the front coupler, each targeting the focused panel.
    profile = ControlProfile.load()

    assert profile.buttons[4].action == "rear_coupler"
    assert profile.buttons[4].target == "focused"
    assert profile.buttons[5].action == "front_coupler"
    assert profile.buttons[5].target == "focused"


def test_rear_coupler_button_opens_rear_coupler() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _profile(buttons={"9": {"action": "rear_coupler", "target": "focused"}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("rear_coupler", "focused", 1.0, "pressed", button=9))
    router.handle(DeckAction("rear_coupler", "focused", 0.0, "released", button=9))

    assert focused_gui.command_calls == ["REAR_COUPLER"]


def test_front_coupler_button_opens_front_coupler() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _profile(buttons={"10": {"action": "front_coupler", "target": "focused"}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("front_coupler", "focused", 1.0, "pressed", button=10))
    router.handle(DeckAction("front_coupler", "focused", 0.0, "released", button=10))

    assert focused_gui.command_calls == ["FRONT_COUPLER"]


def test_dpad_scrolls_catalog_in_focused_panel_when_visible() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.scroll_calls = []
    focused_gui.scroll_catalog = lambda delta: focused_gui.scroll_calls.append(delta)
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))
    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed"))

    assert focused_gui.scroll_calls == [-1, 1]


def test_dpad_up_down_boost_brake_when_catalog_hidden() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = False
    focused_gui.scroll_catalog = lambda delta: pytest.fail("should not scroll when catalog hidden")
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    # With the catalog hidden, D-pad up boosts the engine/train speed
    # (``BOOST_SPEED``) and D-pad down brakes it (``BRAKE_SPEED``); both resolve
    # for Legacy and TMCC engines alike.
    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))
    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed"))

    assert focused_gui.command_calls == ["BOOST_SPEED", "BRAKE_SPEED"]


def test_dpad_up_repeats_catalog_scroll_after_initial_delay() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.scroll_calls = []
    focused_gui.scroll_catalog = lambda delta: focused_gui.scroll_calls.append(delta)
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))  # immediate scroll
    router.tick(10.0)  # primes the repeat clock
    router.tick(10.1)  # arms the 500 ms auto-repeat delay (next at 10.6)
    router.tick(10.4)  # only 300 ms held: still no auto-repeat
    assert focused_gui.scroll_calls == [-1]

    router.tick(10.6)  # 500 ms elapsed: first auto-repeat (next at 10.8)
    router.tick(10.7)  # only 100 ms since last repeat: no scroll
    router.tick(10.8)  # 200 ms later: second auto-repeat

    assert focused_gui.scroll_calls == [-1, -1, -1]


def test_dpad_down_repeats_catalog_scroll_after_initial_delay() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.scroll_calls = []
    focused_gui.scroll_catalog = lambda delta: focused_gui.scroll_calls.append(delta)
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed"))  # immediate scroll
    router.tick(10.0)  # primes the repeat clock
    router.tick(10.1)  # arms the 500 ms auto-repeat delay (next at 10.6)
    router.tick(10.6)  # 500 ms elapsed: first auto-repeat

    assert focused_gui.scroll_calls == [1, 1]


def test_dpad_release_stops_catalog_scroll_repeat() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.scroll_calls = []
    focused_gui.scroll_catalog = lambda delta: focused_gui.scroll_calls.append(delta)
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))  # immediate scroll
    router.tick(10.0)  # primes the repeat clock
    router.tick(10.1)  # arms the 500 ms auto-repeat delay (next at 10.6)
    router.tick(10.6)  # 500 ms elapsed: first auto-repeat
    router.handle(DeckAction(DPAD_UP, "focused", 0.0, "released"))
    router.tick(10.8)  # released: no further scroll

    assert focused_gui.scroll_calls == [-1, -1]
    assert router._scrolls == {}


def test_dpad_scroll_repeat_stops_when_catalog_closes() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.scroll_calls = []
    focused_gui.scroll_catalog = lambda delta: focused_gui.scroll_calls.append(delta)
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))  # immediate scroll
    router.tick(10.0)  # primes the repeat clock
    router.tick(10.1)  # arms the 500 ms auto-repeat delay (next at 10.6)
    router.tick(10.6)  # 500 ms elapsed: first auto-repeat
    # The catalog panel closes (e.g. an entry was selected) while the key is
    # still held; the repeat must stop rather than scroll a hidden panel.
    focused_gui.catalog_visible = False
    router.tick(10.8)

    assert focused_gui.scroll_calls == [-1, -1]
    assert router._scrolls == {}


def test_dpad_left_right_smoke_does_not_repeat_when_catalog_hidden() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = False
    focused_gui.scroll_catalog = lambda delta: pytest.fail("should not scroll when catalog hidden")
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_RIGHT, "focused", 1.0, "pressed"))  # one-shot smoke
    router.tick(10.0)  # primes the repeat clock
    router.tick(10.1)  # no repeat expected for smoke
    router.tick(10.6)  # even past the catalog auto-repeat delay: no repeat

    assert focused_gui.command_calls == ["SMOKE_ON"]
    assert router._scrolls == {}
    assert router._boosts == {}


def test_dpad_right_selects_catalog_entry_when_visible() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.select_calls = 0
    focused_gui.select_catalog_entry = lambda: setattr(focused_gui, "select_calls", focused_gui.select_calls + 1)
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_RIGHT, "focused", 1.0, "pressed"))

    assert focused_gui.select_calls == 1


def test_dpad_left_closes_catalog_when_visible() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.hide_calls = 0
    focused_gui.hide_scope_catalog = lambda: setattr(focused_gui, "hide_calls", focused_gui.hide_calls + 1)
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_LEFT, "focused", 1.0, "pressed"))

    assert focused_gui.hide_calls == 1


def test_dpad_left_right_adjust_smoke_when_catalog_hidden() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = False
    focused_gui.select_catalog_entry = lambda: pytest.fail("should not select when catalog hidden")
    focused_gui.hide_scope_catalog = lambda: pytest.fail("should not close when catalog hidden")
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    # With the catalog hidden, D-pad right raises smoke (``SMOKE_ON``) and D-pad
    # left lowers it (``SMOKE_OFF``) as one-shots.
    router.handle(DeckAction(DPAD_RIGHT, "focused", 1.0, "pressed"))
    router.handle(DeckAction(DPAD_LEFT, "focused", 1.0, "pressed"))

    assert focused_gui.command_calls == ["SMOKE_ON", "SMOKE_OFF"]


def test_dpad_up_boosts_engine_speed_when_catalog_hidden() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = False
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))

    assert focused_gui.command_calls == ["BOOST_SPEED"]


def test_dpad_down_brakes_engine_speed_when_catalog_hidden() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = False
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed"))

    assert focused_gui.command_calls == ["BRAKE_SPEED"]


def test_dpad_left_right_do_not_boost_or_brake_when_catalog_visible() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.select_catalog_entry = lambda: None
    focused_gui.hide_scope_catalog = lambda: None
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_RIGHT, "focused", 1.0, "pressed"))
    router.handle(DeckAction(DPAD_LEFT, "focused", 1.0, "pressed"))

    assert focused_gui.command_calls == []


def test_dpad_up_repeats_boost_every_tick_while_held() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = False
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))  # immediate
    router.tick(10.0)  # primes the repeat clock
    router.tick(10.1)  # first repeat
    router.tick(10.2)  # second repeat

    assert focused_gui.command_calls == ["BOOST_SPEED", "BOOST_SPEED", "BOOST_SPEED"]


def test_dpad_down_repeats_brake_every_tick_while_held() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = False
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed"))  # immediate
    router.tick(10.0)  # primes the repeat clock
    router.tick(10.1)  # first repeat

    assert focused_gui.command_calls == ["BRAKE_SPEED", "BRAKE_SPEED"]


def test_dpad_release_stops_boost_repeat() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = False
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))  # immediate
    router.tick(10.0)  # primes the repeat clock
    router.tick(10.1)  # first repeat
    router.handle(DeckAction(DPAD_UP, "focused", 0.0, "released"))
    router.tick(10.2)  # released: no further boost

    assert focused_gui.command_calls == ["BOOST_SPEED", "BOOST_SPEED"]
    assert router._boosts == {}


def test_dpad_up_down_do_not_boost_or_brake_when_catalog_visible() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.scroll_catalog = lambda delta: None
    router = DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    # While the catalog is open, up/down scroll it and must never boost/brake.
    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))
    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed"))

    assert focused_gui.command_calls == []
    assert router._boosts == {}


def _catalog_gui(*, allow_jump: bool = True) -> SimpleNamespace:
    # A focused GUI with the catalog open that records catalog scroll/jump calls.
    gui = _gui()
    gui.catalog_visible = True
    gui.scroll_calls = []
    gui.scroll_catalog = lambda delta: gui.scroll_calls.append(delta)
    gui.scroll_end_calls = []
    if allow_jump:
        gui.scroll_catalog_to_end = lambda to_top: gui.scroll_end_calls.append(to_top)
    else:
        gui.scroll_catalog_to_end = lambda to_top: pytest.fail("must not jump to the end of the catalog")
    gui.select_catalog_entry = lambda: pytest.fail("the jump chord must not select the entry")
    return gui


def _catalog_router(focused_gui: SimpleNamespace) -> DeckInputRouter:
    return DeckInputRouter(
        _profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )


def _coupler_profile() -> ControlProfile:
    # L1/R1 carry the couplers, as in the bundled profile. R1 doubles as the
    # catalog-jump modifier while the catalog is open.
    return _profile(
        buttons={
            "4": {"action": "rear_coupler", "target": "focused"},
            "5": {"action": "front_coupler", "target": "focused"},
        }
    )


def test_r1_plus_dpad_up_jumps_to_catalog_top_without_selecting() -> None:
    focused_gui = _catalog_gui()
    router = _catalog_router(focused_gui)

    # R1 held + D-pad up jumps the highlight to the first entry, without selecting it
    # (so the catalog stays open) and without the ordinary one-entry scroll.
    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed", jump_modifier=True))

    assert focused_gui.scroll_end_calls == [True]
    assert focused_gui.scroll_calls == []


def test_r1_plus_dpad_down_jumps_to_catalog_end_without_selecting() -> None:
    focused_gui = _catalog_gui()
    router = _catalog_router(focused_gui)

    # R1 held + D-pad down jumps the highlight to the last entry.
    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed", jump_modifier=True))

    assert focused_gui.scroll_end_calls == [False]
    assert focused_gui.scroll_calls == []


def test_r1_opens_no_coupler_while_the_catalog_is_open() -> None:
    focused_gui = _catalog_gui(allow_jump=False)
    router = _catalog_router(focused_gui)

    # R1 is the modifier while browsing, so it performs no action of its own -- holding
    # it must not fire the front coupler.
    router.handle(DeckAction("front_coupler", "focused", 1.0, "pressed", button=5))

    assert focused_gui.command_calls == []


def test_l1_still_opens_its_coupler_while_the_catalog_is_open() -> None:
    focused_gui = _catalog_gui(allow_jump=False)
    router = _catalog_router(focused_gui)

    # Only the modifier button changes meaning; L1 keeps its coupler throughout.
    router.handle(DeckAction("rear_coupler", "focused", 1.0, "pressed", button=4))

    assert focused_gui.command_calls == [PANEL_COMMANDS["rear_coupler"]]


def test_shoulder_buttons_open_couplers_when_catalog_closed() -> None:
    focused_gui = _catalog_gui(allow_jump=False)
    focused_gui.catalog_visible = False
    router = DeckInputRouter(
        _coupler_profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    # With no catalog on screen there is nothing to jump to, so both shoulder buttons
    # keep their ordinary coupler behavior.
    router.handle(DeckAction("rear_coupler", "focused", 1.0, "pressed", button=4))
    router.handle(DeckAction("front_coupler", "focused", 1.0, "pressed", button=5))

    assert focused_gui.command_calls == [
        PANEL_COMMANDS["rear_coupler"],
        PANEL_COMMANDS["front_coupler"],
    ]


def test_catalog_jump_cancels_pending_auto_repeat() -> None:
    focused_gui = _catalog_gui()
    router = _catalog_router(focused_gui)

    # A held D-pad arms the auto-repeat; jumping then cancels it so a still-held
    # D-pad does not keep scrolling away from the entry just jumped to.
    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed"))
    assert router._scrolls != {}
    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed", jump_modifier=True))

    assert focused_gui.scroll_end_calls == [False]
    assert router._scrolls == {}


def test_dpad_without_the_modifier_only_ever_scrolls_one_entry() -> None:
    focused_gui = _catalog_gui(allow_jump=False)
    router = _catalog_router(focused_gui)

    # Without R1 held, presses scroll one entry each however fast they arrive: there is
    # no timed gesture that could be mistaken for a jump.
    for _ in range(4):
        router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))
        router.handle(DeckAction(DPAD_UP, "focused", 0.0, "released"))

    assert focused_gui.scroll_calls == [-1, -1, -1, -1]


def test_jump_modifier_still_boosts_when_catalog_closed() -> None:
    focused_gui = _catalog_gui(allow_jump=False)
    focused_gui.catalog_visible = False
    router = _catalog_router(focused_gui)

    # With no catalog there is nothing to jump to, so the modifier is ignored and the
    # D-pad still boosts/brakes.
    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed", jump_modifier=True))
    router.handle(DeckAction(DPAD_UP, "focused", 0.0, "released"))
    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed", jump_modifier=True))

    assert focused_gui.command_calls == ["BOOST_SPEED", "BRAKE_SPEED"]
    assert focused_gui.scroll_calls == []


def test_bundled_profile_binds_the_catalog_jump_modifier() -> None:
    # The modifier is keyed by action, so it follows whichever button carries the front
    # coupler -- button 5 (R1) in the bundled profile.
    profile = ControlProfile.load(DEFAULT_PROFILE, fallback=False)

    assert profile.catalog_jump_modifier_buttons == frozenset({5})
    assert CATALOG_JUMP_MODIFIER in PANEL_COMMANDS


def test_bundled_profile_binds_the_back_paddles() -> None:
    # The Deck's joystick reports 20 buttons; 16-19 are the back paddles, measured
    # with scripts/deckinfo.py (16 = R4, 17 = L4, 18 = R5, 19 = L5). Volume repeats
    # while held at its own slower cadence; the chatter commands are one-shot.
    profile = ControlProfile.load(DEFAULT_PROFILE, fallback=False)

    assert {index: profile.buttons[index].action for index in (16, 17, 18, 19)} == {
        16: "volume_up",
        17: "volume_down",
        18: "tower_chatter",
        19: "engineer_chatter",
    }
    assert [profile.buttons[index].repeat for index in (16, 17)] == [True, True]
    assert [profile.buttons[index].repeat_interval for index in (16, 17)] == [0.2, 0.2]
    assert [profile.buttons[index].repeat for index in (18, 19)] == [False, False]
    assert [profile.buttons[index].repeat_interval for index in (18, 19)] == [None, None]


def test_button_repeat_interval_overrides_the_profile_cadence() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _profile(buttons={"16": {"action": "volume_up", "target": "focused", "repeat": True, "repeat_interval": 0.2}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    # tick() runs every 100 ms (the profile cadence); a 200 ms button must send on
    # every other tick, not every one.
    router.handle(DeckAction("volume_up", "focused", 1.0, "pressed", button=16))
    router.tick(10.0)  # primes the repeat clock
    for step in range(1, 7):
        router.tick(10.0 + step * 0.1)

    assert focused_gui.command_calls == ["VOLUME_UP"] * 4  # immediate + 3 repeats over 600 ms


def test_button_without_an_override_uses_the_profile_cadence() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _repeat_button_profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))
    router.tick(10.0)
    for step in range(1, 4):
        router.tick(10.0 + step * 0.1)

    assert focused_gui.command_calls == ["BLOW_HORN_ONE"] * 4  # immediate + one per tick


def test_profile_rejects_repeat_interval_without_repeat() -> None:
    with pytest.raises(ProfileError, match="repeat_interval but is not flagged repeat"):
        _profile(buttons={"16": {"action": "volume_up", "target": "focused", "repeat_interval": 0.2}})


def test_profile_rejects_an_out_of_range_repeat_interval() -> None:
    with pytest.raises(ProfileError, match="repeat_interval must be between"):
        _profile(buttons={"16": {"action": "volume_up", "target": "focused", "repeat": True, "repeat_interval": 9.0}})


@pytest.mark.parametrize(
    "action_name, command",
    [
        ("volume_up", "VOLUME_UP"),
        ("volume_down", "VOLUME_DOWN"),
        ("engineer_chatter", "ENGINEER_CHATTER"),
        ("tower_chatter", "TOWER_CHATTER"),
    ],
)
def test_paddle_actions_send_their_engine_command(action_name, command) -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        ControlProfile.load(DEFAULT_PROFILE, fallback=False),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(action_name, "focused", 1.0, "pressed", button=16))

    assert focused_gui.command_calls == [command]


def test_paddle_commands_resolve_for_both_engine_generations() -> None:
    # Each paddle command must exist in both command sets, or the button would do
    # nothing on one generation of engine.
    from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
    from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

    for action in ("volume_up", "volume_down", "engineer_chatter", "tower_chatter"):
        command = PANEL_COMMANDS[action]
        assert TMCC1EngineCommandEnum.by_name(command) is not None, command
        assert TMCC2EngineCommandEnum.by_name(command) is not None, command


def test_provider_flags_jump_modifier_while_r1_held() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYHATMOTION=6, JOYDEVICEADDED=4)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=2, button=5),
            SimpleNamespace(type=6, value=(0, 1)),
            SimpleNamespace(type=6, value=(0, 0)),
            SimpleNamespace(type=6, value=(0, -1)),
        ]
    )
    provider = SteamDeckInputProvider(_coupler_profile(), pygame_module=pygame)

    actions = provider.poll()

    # Both D-pad presses made while R1 is held carry the flag; the release does not.
    assert [(a.name, a.phase, a.jump_modifier) for a in actions] == [
        ("front_coupler", "pressed", False),
        (DPAD_UP, "pressed", True),
        (DPAD_UP, "released", False),
        (DPAD_DOWN, "pressed", True),
    ]


def test_provider_does_not_flag_jump_modifier_once_r1_released() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYHATMOTION=6, JOYDEVICEADDED=4)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=2, button=5),
            SimpleNamespace(type=3, button=5),
            SimpleNamespace(type=6, value=(0, 1)),
        ]
    )
    provider = SteamDeckInputProvider(_coupler_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert [(a.name, a.phase, a.jump_modifier) for a in actions if a.name == DPAD_UP] == [(DPAD_UP, "pressed", False)]


def test_provider_does_not_flag_jump_modifier_for_l1() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYHATMOTION=6, JOYDEVICEADDED=4)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=2, button=4),
            SimpleNamespace(type=6, value=(0, 1)),
        ]
    )
    provider = SteamDeckInputProvider(_coupler_profile(), pygame_module=pygame)

    actions = provider.poll()

    # Only the front coupler's button is the modifier; L1 is not.
    assert [(a.name, a.phase, a.jump_modifier) for a in actions] == [
        ("rear_coupler", "pressed", False),
        (DPAD_UP, "pressed", False),
    ]


def _admin_gui(*, admin_visible: bool = True):
    gui = _gui()
    gui.admin_visible = admin_visible
    gui.admin_calls = []
    gui.on_admin_command = lambda command, pressed=True: gui.admin_calls.append((command, pressed))
    return gui


def _bundled_router(focused_gui) -> DeckInputRouter:
    return DeckInputRouter(
        ControlProfile.load(DEFAULT_PROFILE, fallback=False),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )


@pytest.mark.parametrize(
    "action_name, command",
    [
        ("admin_quit", "QUIT"),
        ("admin_update", "UPDATE"),
        ("admin_reboot", "REBOOT"),
        ("admin_shutdown", "SHUTDOWN"),
    ],
)
def test_admin_chord_press_and_release_drive_the_panel_button(action_name, command) -> None:
    focused_gui = _admin_gui()
    router = _bundled_router(focused_gui)

    # The chord stands in for pressing and holding the panel button: the press starts
    # that button's hold and the release cancels it. The command itself fires from the
    # button's own on_hold once hold_threshold elapses, so the dwell and the progress
    # bar are the button's, not a second implementation here.
    router.handle(DeckAction(action_name, "focused", 1.0, "pressed"))
    router.handle(DeckAction(action_name, "focused", 0.0, "released"))

    assert focused_gui.admin_calls == [(command, True), (command, False)]
    assert focused_gui.command_calls == []


def test_admin_chord_is_dropped_by_a_gui_that_has_no_admin_panel() -> None:
    focused_gui = _gui()  # no on_admin_command attribute at all
    router = _bundled_router(focused_gui)

    router.handle(DeckAction("admin_shutdown", "focused", 1.0, "pressed"))

    assert focused_gui.command_calls == []


def test_l1_opens_no_coupler_while_the_admin_panel_is_open() -> None:
    focused_gui = _admin_gui()
    router = _bundled_router(focused_gui)

    router.handle(DeckAction("rear_coupler", "focused", 1.0, "pressed", button=4))

    assert focused_gui.command_calls == []


def test_l1_still_opens_its_coupler_when_the_admin_panel_is_closed() -> None:
    focused_gui = _admin_gui(admin_visible=False)
    router = _bundled_router(focused_gui)

    router.handle(DeckAction("rear_coupler", "focused", 1.0, "pressed", button=4))

    assert focused_gui.command_calls == [PANEL_COMMANDS["rear_coupler"]]


@pytest.mark.parametrize(
    "second_button, action_name",
    [(2, "admin_quit"), (3, "admin_update"), (1, "admin_reboot"), (0, "admin_shutdown")],
)
def test_provider_emits_admin_chord_and_suppresses_the_second_button(second_button, action_name) -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYHATMOTION=6, JOYDEVICEADDED=4)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=2, button=4),  # hold L1
            SimpleNamespace(type=2, button=second_button),
        ]
    )
    provider = SteamDeckInputProvider(ControlProfile.load(DEFAULT_PROFILE, fallback=False), pygame_module=pygame)

    actions = provider.poll()

    # L1 reports its own action (the router drops it while the panel is open), then the
    # chord fires -- but the face button's own command does not, so L1+A cannot shut
    # down the machine *and* run sequence control on the engine.
    assert [(a.name, a.phase) for a in actions] == [
        ("rear_coupler", "pressed"),
        (action_name, "pressed"),
    ]


def test_admin_chord_reports_press_and_release_and_rearms() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYHATMOTION=6, JOYDEVICEADDED=4)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=2, button=4),
            SimpleNamespace(type=2, button=0),
            SimpleNamespace(type=3, button=0),
            SimpleNamespace(type=2, button=0),
        ]
    )
    provider = SteamDeckInputProvider(ControlProfile.load(DEFAULT_PROFILE, fallback=False), pygame_module=pygame)

    actions = provider.poll()

    # Holding does not repeat; releasing cancels the hold and re-arms the chord.
    assert [(a.name, a.phase) for a in actions if a.name == "admin_shutdown"] == [
        ("admin_shutdown", "pressed"),
        ("admin_shutdown", "released"),
        ("admin_shutdown", "pressed"),
    ]


def test_bundled_profile_defines_the_admin_chords() -> None:
    profile = ControlProfile.load(DEFAULT_PROFILE, fallback=False)

    chords = {chord.action: sorted(chord.buttons) for chord in profile.chords}
    # L1 (4) plus a face button: X=2 quit, Y=3 update, B=1 reboot, A=0 shutdown.
    # Asserted exhaustively so a new chord cannot be added without being considered here;
    # show_controls is L3+R3 (the stick clicks) because their own actions are harmless.
    assert chords == {
        "halt": [4, 5],
        "show_controls": [9, 10],
        "admin_quit": [2, 4],
        "admin_update": [3, 4],
        "admin_reboot": [1, 4],
        "admin_shutdown": [0, 4],
    }
    assert set(ADMIN_COMMANDS) == {"admin_quit", "admin_update", "admin_reboot", "admin_shutdown"}


def test_provider_translates_dpad_hat_to_one_shot_scroll_actions() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYHATMOTION=6, JOYDEVICEADDED=4)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=6, value=(0, 1)),
            SimpleNamespace(type=6, value=(0, 1)),
            SimpleNamespace(type=6, value=(0, 0)),
            SimpleNamespace(type=6, value=(0, -1)),
        ]
    )
    provider = SteamDeckInputProvider(_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [
        (DPAD_UP, "focused", "pressed"),
        (DPAD_UP, "focused", "released"),
        (DPAD_DOWN, "focused", "pressed"),
    ]


def test_provider_translates_dpad_hat_to_one_shot_left_right_actions() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYHATMOTION=6, JOYDEVICEADDED=4)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=6, value=(1, 0)),
            SimpleNamespace(type=6, value=(1, 0)),
            SimpleNamespace(type=6, value=(0, 0)),
            SimpleNamespace(type=6, value=(-1, 0)),
        ]
    )
    provider = SteamDeckInputProvider(_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [
        (DPAD_RIGHT, "focused", "pressed"),
        (DPAD_RIGHT, "focused", "released"),
        (DPAD_LEFT, "focused", "pressed"),
    ]


def test_scope_catalog_invokes_scope_hold_on_focused_panel() -> None:
    focused_gui = _gui()
    focused_gui.catalog_calls = []
    focused_gui.show_scope_catalog = lambda: focused_gui.catalog_calls.append("catalog")
    router = DeckInputRouter(
        _profile(buttons={"7": {"action": "scope_catalog", "target": "focused"}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("scope_catalog", "focused", 1.0, "pressed"))
    router.handle(DeckAction("scope_catalog", "focused", 0.0, "released"))

    assert focused_gui.catalog_calls == ["catalog"]


def test_select_button_confirms_catalog_entry_when_catalog_visible() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.select_calls = 0
    focused_gui.select_catalog_entry = lambda: setattr(focused_gui, "select_calls", focused_gui.select_calls + 1)
    router = DeckInputRouter(
        _profile(buttons={"0": {"action": "reset", "target": "focused"}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("reset", "focused", 1.0, "pressed", button=0))

    assert focused_gui.select_calls == 1
    assert focused_gui.command_calls == []


def test_select_button_performs_assigned_action_when_catalog_hidden() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = False
    focused_gui.select_catalog_entry = lambda: focused_gui.command_calls.append("select")
    router = DeckInputRouter(
        _profile(buttons={"0": {"action": "reset", "target": "focused"}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("reset", "focused", 1.0, "pressed", button=0))

    assert focused_gui.command_calls == ["RESET"]


def test_non_select_button_ignores_catalog_visibility() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.select_catalog_entry = lambda: focused_gui.command_calls.append("select")
    router = DeckInputRouter(
        _profile(buttons={"1": {"action": "bell", "target": "focused"}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("bell", "focused", 1.0, "pressed", button=1))

    assert focused_gui.command_calls == ["RING_BELL"]


def test_close_popup_button_closes_popup_when_popup_visible() -> None:
    focused_gui = _gui()
    focused_gui.popup_visible = True
    focused_gui.close_calls = 0
    focused_gui.close_popup = lambda: setattr(focused_gui, "close_calls", focused_gui.close_calls + 1)
    router = DeckInputRouter(
        _profile(buttons={"2": {"action": "reset", "target": "focused"}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("reset", "focused", 1.0, "pressed", button=2))

    assert focused_gui.close_calls == 1
    assert focused_gui.command_calls == []


def test_close_popup_button_performs_assigned_action_when_no_popup() -> None:
    focused_gui = _gui()
    focused_gui.popup_visible = False
    focused_gui.close_popup = lambda: focused_gui.command_calls.append("close")
    router = DeckInputRouter(
        _profile(buttons={"2": {"action": "reset", "target": "focused"}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("reset", "focused", 1.0, "pressed", button=2))

    assert focused_gui.command_calls == ["RESET"]


def test_non_close_button_ignores_popup_visibility() -> None:
    focused_gui = _gui()
    focused_gui.popup_visible = True
    focused_gui.close_popup = lambda: focused_gui.command_calls.append("close")
    router = DeckInputRouter(
        _profile(buttons={"1": {"action": "bell", "target": "focused"}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("bell", "focused", 1.0, "pressed", button=1))

    assert focused_gui.command_calls == ["RING_BELL"]


def test_provider_reports_button_index_for_button_actions() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=2, button=0)])
    provider = SteamDeckInputProvider(
        _profile(buttons={"0": {"action": "reset", "target": "focused"}}), pygame_module=pygame
    )

    actions = provider.poll()

    assert [(a.name, a.button, a.phase) for a in actions] == [("reset", 0, "pressed")]


def test_provider_applies_dead_zone_hysteresis_and_axis_inversion() -> None:
    pygame = SimpleNamespace(
        JOYAXISMOTION=1,
        JOYBUTTONDOWN=2,
        JOYBUTTONUP=3,
        JOYDEVICEADDED=4,
        JOYDEVICEREMOVED=5,
    )
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=1, axis=1, value=-0.10),
            SimpleNamespace(type=1, axis=1, value=-0.60),
            SimpleNamespace(type=1, axis=1, value=-0.12),
            SimpleNamespace(type=1, axis=1, value=-0.09),
        ]
    )
    provider = SteamDeckInputProvider(_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert [action.value for action in actions] == pytest.approx([0.0, 0.5294118, 0.0, 0.0])
    assert all(action.name == "throttle" and action.target == "left" for action in actions)


def test_provider_start_isolates_sdl_video_from_tk_touchscreen(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    pygame = SimpleNamespace(
        JOYAXISMOTION=1,
        JOYBUTTONDOWN=2,
        JOYBUTTONUP=3,
        JOYHATMOTION=6,
        JOYDEVICEADDED=4,
        JOYDEVICEREMOVED=5,
        init=lambda: calls.append("pygame.init"),
        display=SimpleNamespace(init=lambda: calls.append(("display.init", os.environ.get("SDL_VIDEODRIVER")))),
        event=SimpleNamespace(
            set_blocked=lambda event_type: calls.append(("blocked", event_type)),
            set_allowed=lambda event_types: calls.append(("allowed", tuple(event_types))),
        ),
        joystick=SimpleNamespace(init=lambda: calls.append("joystick.init"), get_count=lambda: 0),
    )
    monkeypatch.setenv("SDL_VIDEODRIVER", "wayland")
    provider = SteamDeckInputProvider(_profile(), pygame_module=pygame)

    provider.start()

    assert "pygame.init" not in calls
    assert ("display.init", "dummy") in calls
    assert ("blocked", None) in calls
    assert ("allowed", (1, 2, 3, 6, 4, 5)) in calls
    assert os.environ["SDL_VIDEODRIVER"] == "wayland"


def test_provider_start_wraps_only_sdl_runtime_errors() -> None:
    def sdl_failure() -> None:
        raise RuntimeError("SDL failed")

    pygame = SimpleNamespace(display=SimpleNamespace(init=sdl_failure))
    provider = SteamDeckInputProvider(_profile(), pygame_module=pygame)

    with pytest.raises(ControllerUnavailable, match="SDL controller initialization failed: SDL failed"):
        provider.start()

    def programming_failure() -> None:
        raise ValueError("programming error")

    pygame.display.init = programming_failure
    with pytest.raises(ValueError, match="programming error"):
        provider.start()


def test_rate_throttle_is_proportional_bounded_and_center_holds_speed() -> None:
    router, left, right, _, _ = _router()
    router.handle(DeckAction("throttle", "left", 0.5, "changed"))
    router.handle(DeckAction("throttle", "right", 1.0, "changed"))

    router.tick(10.0)
    router.tick(10.2)

    assert left.speed_calls == [2]
    assert right.speed_calls == [4]
    router.handle(DeckAction("throttle", "left", 0.0, "changed"))
    router.tick(10.4)
    assert left.speed_calls == [2]
    assert right.speed_calls == [4, 8]


def test_cab1_rate_throttle_emits_bounded_relative_steps() -> None:
    left = _gui(is_cab1=True)
    router, _, _, _, _ = _router(left=left)
    router.handle(DeckAction("throttle", "left", -0.8, "changed"))

    router.tick(1.0)
    router.tick(1.1)

    assert left.speed_calls == [-4]


@pytest.mark.parametrize("target", ["left", "right"])
def test_direction_uses_hysteresis(target: str) -> None:
    panel = _gui()
    router, _, _, _, _ = _router(**{target: panel})

    router.handle(DeckAction("direction", target, 0.5, "changed"))
    router.handle(DeckAction("direction", target, 1.0, "changed"))
    router.handle(DeckAction("direction", target, 0.9, "changed"))
    router.handle(DeckAction("direction", target, 0.0, "changed"))
    router.handle(DeckAction("direction", target, -1.0, "changed"))

    assert panel.command_calls == ["FORWARD_DIRECTION", "REVERSE_DIRECTION"]


@pytest.mark.parametrize(
    ("value", "is_forward", "is_reverse"),
    [(1.0, True, False), (-1.0, False, True)],
)
def test_moving_current_direction_is_noop(value: float, is_forward: bool, is_reverse: bool) -> None:
    left = _gui(speed=10, target_speed=10, is_forward=is_forward, is_reverse=is_reverse)
    router, _, _, _, _ = _router(left=left)

    router.handle(DeckAction("direction", "left", value, "changed"))

    assert left.command_calls == []


@pytest.mark.parametrize(
    ("value", "is_forward", "is_reverse", "command"),
    [
        (1.0, False, True, "FORWARD_DIRECTION"),
        (-1.0, True, False, "REVERSE_DIRECTION"),
    ],
)
def test_moving_opposite_direction_executes_command(
    value: float, is_forward: bool, is_reverse: bool, command: str
) -> None:
    left = _gui(speed=10, target_speed=10, is_forward=is_forward, is_reverse=is_reverse)
    router, _, _, _, _ = _router(left=left)

    router.handle(DeckAction("direction", "left", value, "changed"))

    assert left.command_calls == [command]


def test_buttons_route_to_focused_fixed_and_global_targets() -> None:
    router, left, right, focused, global_calls = _router()
    focused.value = right

    router.handle(DeckAction("bell", "focused", 1.0, "pressed"))
    router.handle(DeckAction("reset", "right", 1.0, "pressed"))
    router.handle(DeckAction("halt", "global", 1.0, "pressed"))
    router.handle(DeckAction("bell", "left", 0.0, "released"))

    assert left.command_calls == []
    assert right.command_calls == ["RING_BELL", "RESET"]
    assert global_calls == ["halt"]


def test_disconnect_clears_active_throttle_without_issuing_stop() -> None:
    router, left, _, _, _ = _router()
    router.handle(DeckAction("throttle", "left", 1.0, "changed"))
    router.tick(2.0)
    router.handle(DeckAction("disconnect", "global", 0.0, "disconnected"))
    router.tick(2.2)

    assert left.speed_calls == []


def test_provider_reports_unavailable_configured_controls() -> None:
    warnings = SteamDeckInputProvider(_profile(), pygame_module=SimpleNamespace()).capability_warnings(
        axis_count=3, button_count=2
    )

    assert "axis 3" in warnings
    assert "button 4" in warnings
    assert "button 5" in warnings


def test_emergency_chord_fires_once_until_released() -> None:
    pygame = SimpleNamespace(
        JOYAXISMOTION=1,
        JOYBUTTONDOWN=2,
        JOYBUTTONUP=3,
        JOYDEVICEADDED=4,
        JOYDEVICEREMOVED=5,
    )
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=2, button=4),
            SimpleNamespace(type=2, button=5),
            SimpleNamespace(type=2, button=5),
            SimpleNamespace(type=3, button=5),
            SimpleNamespace(type=2, button=5),
        ]
    )
    provider = SteamDeckInputProvider(_profile(), pygame_module=pygame)

    actions = provider.poll()

    # The chord reports its release too, so a chord standing in for a
    # press-and-hold can cancel the hold it started.
    assert [(action.name, action.phase) for action in actions] == [
        ("halt", "pressed"),
        ("halt", "released"),
        ("halt", "pressed"),
    ]


def _startup_profile() -> ControlProfile:
    return _profile(
        buttons={
            "0": {"action": "bell", "target": "focused"},
            "5": {"action": "startup", "target": "focused"},
        }
    )


def _clock(*values: float):
    remaining = list(values)
    return lambda: remaining.pop(0)


def test_bundled_profile_binds_right_stick_click_to_focus_right() -> None:
    # The right stick click (button index 10) focuses the right panel.
    profile = ControlProfile.load()

    assert profile.buttons[10].action == "focus_right"
    assert profile.buttons[10].target == "global"


def test_startup_requires_a_panel_target() -> None:
    with pytest.raises(ProfileError, match="startup must target a panel"):
        _profile(buttons={"5": {"action": "startup", "target": "global"}})


def test_startup_immediate_action_starts_engine_immediately() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _startup_profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(STARTUP_IMMEDIATE, "focused", 1.0, "pressed", button=5))

    assert focused_gui.command_calls == ["START_UP_IMMEDIATE"]


def test_startup_delayed_action_requests_delayed_startup_with_fallback() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _startup_profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(STARTUP_DELAYED, "focused", 1.0, "pressed", button=5))

    assert focused_gui.command_calls == [["START_UP_DELAYED", "START_UP_IMMEDIATE"]]


def test_provider_short_press_emits_startup_immediate() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=2, button=5), SimpleNamespace(type=3, button=5)])
    provider = SteamDeckInputProvider(
        _startup_profile(),
        pygame_module=pygame,
        clock=_clock(0.0, STARTUP_LONG_PRESS_SECONDS - 0.5),
    )

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [(STARTUP_IMMEDIATE, "focused", "pressed")]


def test_provider_long_press_emits_startup_delayed() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=2, button=5), SimpleNamespace(type=3, button=5)])
    provider = SteamDeckInputProvider(
        _startup_profile(),
        pygame_module=pygame,
        clock=_clock(0.0, STARTUP_LONG_PRESS_SECONDS + 0.5),
    )

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [(STARTUP_DELAYED, "focused", "pressed")]


def test_provider_startup_button_press_alone_emits_nothing() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=2, button=5)])
    provider = SteamDeckInputProvider(_startup_profile(), pygame_module=pygame, clock=_clock(0.0))

    assert provider.poll() == []


def test_provider_suppresses_startup_when_halt_chord_fires() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=2, button=4),
            SimpleNamespace(type=2, button=5),
            SimpleNamespace(type=3, button=5),
            SimpleNamespace(type=3, button=4),
        ]
    )
    provider = SteamDeckInputProvider(
        _startup_profile(),
        pygame_module=pygame,
        clock=_clock(0.0, STARTUP_LONG_PRESS_SECONDS + 0.5),
    )

    actions = provider.poll()

    assert [(action.name, action.phase) for action in actions] == [("halt", "pressed"), ("halt", "released")]


def _shutdown_profile() -> ControlProfile:
    return _profile(
        buttons={
            "0": {"action": "bell", "target": "focused"},
            "4": {"action": "shutdown", "target": "focused"},
        }
    )


def test_bundled_profile_binds_left_stick_click_to_focus_left() -> None:
    # The left stick click (button index 9) focuses the left panel.
    profile = ControlProfile.load()

    assert profile.buttons[9].action == "focus_left"
    assert profile.buttons[9].target == "global"


def test_shutdown_requires_a_panel_target() -> None:
    with pytest.raises(ProfileError, match="shutdown must target a panel"):
        _profile(buttons={"4": {"action": "shutdown", "target": "global"}})


def test_shutdown_immediate_action_shuts_engine_down_immediately() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _shutdown_profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(SHUTDOWN_IMMEDIATE, "focused", 1.0, "pressed", button=4))

    assert focused_gui.command_calls == ["SHUTDOWN_IMMEDIATE"]


def test_shutdown_delayed_action_requests_delayed_shutdown_with_fallback() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _shutdown_profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(SHUTDOWN_DELAYED, "focused", 1.0, "pressed", button=4))

    assert focused_gui.command_calls == [["SHUTDOWN_DELAYED", "SHUTDOWN_IMMEDIATE"]]


def test_provider_short_press_emits_shutdown_immediate() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=2, button=4), SimpleNamespace(type=3, button=4)])
    provider = SteamDeckInputProvider(
        _shutdown_profile(),
        pygame_module=pygame,
        clock=_clock(0.0, STARTUP_LONG_PRESS_SECONDS - 0.5),
    )

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [(SHUTDOWN_IMMEDIATE, "focused", "pressed")]


def test_provider_long_press_emits_shutdown_delayed() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=2, button=4), SimpleNamespace(type=3, button=4)])
    provider = SteamDeckInputProvider(
        _shutdown_profile(),
        pygame_module=pygame,
        clock=_clock(0.0, STARTUP_LONG_PRESS_SECONDS + 0.5),
    )

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [(SHUTDOWN_DELAYED, "focused", "pressed")]


def test_provider_shutdown_button_press_alone_emits_nothing() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=2, button=4)])
    provider = SteamDeckInputProvider(_shutdown_profile(), pygame_module=pygame, clock=_clock(0.0))

    assert provider.poll() == []


def test_provider_suppresses_shutdown_when_halt_chord_fires() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=2, button=5),
            SimpleNamespace(type=2, button=4),
            SimpleNamespace(type=3, button=4),
            SimpleNamespace(type=3, button=5),
        ]
    )
    provider = SteamDeckInputProvider(
        _shutdown_profile(),
        pygame_module=pygame,
        clock=_clock(0.0, STARTUP_LONG_PRESS_SECONDS + 0.5),
    )

    actions = provider.poll()

    assert [(action.name, action.phase) for action in actions] == [("halt", "pressed"), ("halt", "released")]


def test_provider_handles_disconnect_and_reconnect() -> None:
    joystick = SimpleNamespace(
        init_calls=0,
        quit_calls=0,
        init=lambda: setattr(joystick, "init_calls", joystick.init_calls + 1),
        quit=lambda: setattr(joystick, "quit_calls", joystick.quit_calls + 1),
        get_instance_id=lambda: 7,
        get_numaxes=lambda: 4,
        get_numbuttons=lambda: 11,
        get_name=lambda: "Steam Deck",
        get_guid=lambda: "deck-guid",
    )
    events = [SimpleNamespace(type=4, device_index=0), SimpleNamespace(type=5, instance_id=7)]
    pygame = SimpleNamespace(
        JOYAXISMOTION=1,
        JOYBUTTONDOWN=2,
        JOYBUTTONUP=3,
        JOYHATMOTION=6,
        JOYDEVICEADDED=4,
        JOYDEVICEREMOVED=5,
        event=SimpleNamespace(get=lambda: list(events)),
        joystick=SimpleNamespace(Joystick=lambda _index: joystick),
    )
    provider = SteamDeckInputProvider(_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert [action.name for action in actions] == ["disconnect"]
    assert joystick.init_calls == 1
    assert joystick.quit_calls == 1
    events[:] = [SimpleNamespace(type=4, device_index=0)]
    assert provider.poll() == []
    assert joystick.init_calls == 2
    assert provider._joysticks == {7: joystick}


def _horn_gui():
    gui = SimpleNamespace(command_calls=[])
    gui.on_engine_command = lambda command, data=0: gui.command_calls.append((command, data))
    return gui


def _horn_profile() -> ControlProfile:
    return _profile(axes={"5": {"action": "quilling_horn", "target": "right", "trigger": True}})


def test_bundled_profile_binds_triggers_to_startup_shutdown() -> None:
    # The L2/R2 analog triggers (axes 2 and 5) act as buttons: L2 carries the
    # shutdown short/long-press command and R2 carries startup, each targeting
    # the focused panel. They are trigger axes but are treated as buttons, and
    # they are not the quilling horn (that lives on the trackpads).
    profile = ControlProfile.load()

    assert profile.axes[2].action == "shutdown"
    assert profile.axes[2].target == "focused"
    assert profile.axes[2].trigger is True
    assert profile.axes[5].action == "startup"
    assert profile.axes[5].target == "focused"
    assert profile.axes[5].trigger is True


def _trigger_long_press_profile() -> ControlProfile:
    return _profile(
        axes={
            "1": {"action": "throttle", "target": "left", "invert": True},
            "2": {"action": "shutdown", "target": "focused", "trigger": True},
            "5": {"action": "startup", "target": "focused", "trigger": True},
        }
    )


def test_axis_shutdown_action_requires_trigger_flag() -> None:
    # startup/shutdown only make sense on a trigger (which rests at one
    # extreme); binding them to a plain axis is rejected.
    with pytest.raises(ProfileError, match="requires trigger"):
        _profile(axes={"2": {"action": "shutdown", "target": "focused"}})


def test_axis_startup_action_requires_panel_target() -> None:
    with pytest.raises(ProfileError, match="startup must target a panel"):
        _profile(axes={"5": {"action": "startup", "target": "global", "trigger": True}})


def test_provider_trigger_short_press_emits_shutdown_immediate() -> None:
    # A quick squeeze-and-release of the L2 trigger (axis 2) behaves like a
    # short button press and emits the immediate shutdown command on release.
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=1, axis=2, value=1.0),  # squeezed
            SimpleNamespace(type=1, axis=2, value=-1.0),  # released
        ]
    )
    provider = SteamDeckInputProvider(
        _trigger_long_press_profile(),
        pygame_module=pygame,
        clock=_clock(0.0, STARTUP_LONG_PRESS_SECONDS - 0.5),
    )

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [(SHUTDOWN_IMMEDIATE, "focused", "pressed")]


def test_provider_trigger_long_press_emits_shutdown_delayed() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=1, axis=2, value=1.0),
            SimpleNamespace(type=1, axis=2, value=-1.0),
        ]
    )
    provider = SteamDeckInputProvider(
        _trigger_long_press_profile(),
        pygame_module=pygame,
        clock=_clock(0.0, STARTUP_LONG_PRESS_SECONDS + 0.5),
    )

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [(SHUTDOWN_DELAYED, "focused", "pressed")]


def test_provider_trigger_short_press_emits_startup_immediate() -> None:
    # A quick squeeze of the R2 trigger (axis 5) emits the immediate startup.
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=1, axis=5, value=1.0),
            SimpleNamespace(type=1, axis=5, value=-1.0),
        ]
    )
    provider = SteamDeckInputProvider(
        _trigger_long_press_profile(),
        pygame_module=pygame,
        clock=_clock(0.0, STARTUP_LONG_PRESS_SECONDS - 0.5),
    )

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [(STARTUP_IMMEDIATE, "focused", "pressed")]


def test_provider_trigger_long_press_emits_startup_delayed() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=1, axis=5, value=1.0),
            SimpleNamespace(type=1, axis=5, value=-1.0),
        ]
    )
    provider = SteamDeckInputProvider(
        _trigger_long_press_profile(),
        pygame_module=pygame,
        clock=_clock(0.0, STARTUP_LONG_PRESS_SECONDS + 0.5),
    )

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [(STARTUP_DELAYED, "focused", "pressed")]


def test_provider_trigger_long_press_squeeze_alone_emits_nothing() -> None:
    # Squeezing the trigger without releasing it emits nothing; the command is
    # only decided on release (mirroring the startup/shutdown buttons).
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=1, axis=2, value=1.0)])
    provider = SteamDeckInputProvider(_trigger_long_press_profile(), pygame_module=pygame, clock=_clock(0.0))

    assert provider.poll() == []


def test_provider_trigger_long_press_ignores_resting_position() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=1, axis=2, value=-1.0)])
    provider = SteamDeckInputProvider(_trigger_long_press_profile(), pygame_module=pygame, clock=_clock(0.0))

    assert provider.poll() == []


def _focus_trigger_profile() -> ControlProfile:
    return _profile(
        axes={
            "1": {"action": "throttle", "target": "left", "invert": True},
            "2": {"action": "focus_left", "target": "global", "trigger": True},
            "5": {"action": "focus_right", "target": "global", "trigger": True},
        }
    )


def test_axis_focus_action_requires_trigger_flag() -> None:
    # A discrete navigation action only makes sense on a trigger (which rests at
    # one extreme); binding it to a plain axis is rejected.
    with pytest.raises(ProfileError, match="requires trigger"):
        _profile(axes={"2": {"action": "focus_left", "target": "global"}})


def test_axis_focus_action_requires_global_target() -> None:
    with pytest.raises(ProfileError, match="focus_left must target global"):
        _profile(axes={"2": {"action": "focus_left", "target": "left", "trigger": True}})


def test_provider_trigger_button_fires_focus_once_per_squeeze() -> None:
    # A discrete action bound to an analog trigger fires a single one-shot
    # "pressed" action when the trigger crosses its dead zone and only fires
    # again after the trigger returns to rest.
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=1, axis=2, value=-1.0),  # resting -> nothing
            SimpleNamespace(type=1, axis=2, value=1.0),  # squeezed -> focus_left once
            SimpleNamespace(type=1, axis=2, value=0.9),  # still held -> nothing
            SimpleNamespace(type=1, axis=2, value=-1.0),  # released -> nothing (rearms)
            SimpleNamespace(type=1, axis=2, value=1.0),  # squeezed again -> focus_left again
        ]
    )
    provider = SteamDeckInputProvider(_focus_trigger_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert [(a.name, a.target, a.phase, a.value, a.button) for a in actions] == [
        ("focus_left", "global", "pressed", 1.0, None),
        ("focus_left", "global", "pressed", 1.0, None),
    ]


def test_provider_right_trigger_fires_focus_right() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=1, axis=5, value=1.0)])
    provider = SteamDeckInputProvider(_focus_trigger_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [("focus_right", "global", "pressed")]


def test_provider_trigger_button_ignores_resting_position() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=1, axis=2, value=-1.0)])
    provider = SteamDeckInputProvider(_focus_trigger_profile(), pygame_module=pygame)

    assert provider.poll() == []


def test_trigger_focus_routes_to_registered_global_action() -> None:
    global_calls: list[str] = []
    router = DeckInputRouter(
        _focus_trigger_profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: _gui(),
        global_actions={
            "focus_left": lambda: global_calls.append("left"),
            "focus_right": lambda: global_calls.append("right"),
        },
    )

    router.handle(DeckAction("focus_left", "global", 1.0, "pressed"))
    router.handle(DeckAction("focus_right", "global", 1.0, "pressed"))

    assert global_calls == ["left", "right"]


def test_stick_axes_are_not_flagged_as_triggers() -> None:
    profile = ControlProfile.load()

    assert profile.axes[1].trigger is False
    assert profile.axes[3].trigger is False


def test_bundled_profile_uses_small_trigger_dead_zone() -> None:
    profile = ControlProfile.load()

    # The triggers get their own, much smaller dead zone than the sticks so the
    # horn responds almost as soon as the trigger leaves its resting position.
    assert profile.trigger_dead_zone == 0.02
    assert profile.trigger_dead_zone < profile.dead_zone


def test_trigger_dead_zone_defaults_when_omitted() -> None:
    profile = _profile()

    assert profile.trigger_dead_zone == 0.02


def test_profile_rejects_out_of_range_trigger_dead_zone() -> None:
    with pytest.raises(ProfileError, match="trigger_dead_zone"):
        _profile(trigger_dead_zone=1.0)


def test_provider_sounds_horn_just_past_trigger_rest() -> None:
    # A light press that would fall inside the stick dead zone (0.15) still
    # sounds the horn now that the triggers use a much smaller dead zone.
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=1, axis=5, value=-0.8)])
    provider = SteamDeckInputProvider(_horn_profile(), pygame_module=pygame)

    actions = provider.poll()

    # value -0.8 -> fraction 0.1 -> (0.1 - 0.02) / (1 - 0.02).
    assert [a.value for a in actions] == pytest.approx([0.0816327])


def test_provider_normalizes_trigger_axis_from_resting_to_full() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=1, axis=5, value=-1.0),  # resting -> 0.0
            SimpleNamespace(type=1, axis=5, value=-0.98),  # inside the small dead zone -> 0.0
            SimpleNamespace(type=1, axis=5, value=1.0),  # fully depressed -> 1.0
            SimpleNamespace(type=1, axis=5, value=-1.0),  # released -> 0.0
        ]
    )
    provider = SteamDeckInputProvider(_horn_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert all(a.name == QUILLING_HORN and a.target == "right" and a.phase == "changed" for a in actions)
    assert [a.value for a in actions] == pytest.approx([0.0, 0.0, 1.0, 0.0])


def test_provider_emits_fractional_quilling_horn_for_partial_press() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(get=lambda: [SimpleNamespace(type=1, axis=5, value=0.0)])
    provider = SteamDeckInputProvider(_horn_profile(), pygame_module=pygame)

    actions = provider.poll()

    # value 0.0 maps to fraction 0.5; the small trigger dead zone rescales it to
    # (0.5 - 0.02) / (1 - 0.02).
    assert [a.value for a in actions] == pytest.approx([0.4897959])


def test_quilling_horn_press_and_release_update_router_state() -> None:
    router, _, _, _, _ = _router()

    router.handle(DeckAction(QUILLING_HORN, "right", 0.5, "changed"))
    assert router._quills == {"right": 0.5}

    router.handle(DeckAction(QUILLING_HORN, "right", 0.0, "changed"))
    assert router._quills == {}


def test_tick_repeats_quilling_horn_with_scaled_intensity() -> None:
    left = _horn_gui()
    router, _, _, _, _ = _router(left=left)

    router.handle(DeckAction(QUILLING_HORN, "left", 1.0, "changed"))
    router.tick(10.0)  # primes the repeat clock
    router.tick(10.1)  # first repeat
    router.tick(10.2)  # second repeat

    assert left.command_calls == [(HORN_COMMAND, 15), (HORN_COMMAND, 15)]


def test_tick_scales_quilling_horn_intensity_to_trigger_fraction() -> None:
    left = _horn_gui()
    router, _, _, _, _ = _router(left=left)

    router.handle(DeckAction(QUILLING_HORN, "left", 0.8, "changed"))
    router.tick(10.0)
    router.tick(10.1)

    assert left.command_calls == [(HORN_COMMAND, 12)]


def test_tick_clamps_light_quilling_horn_press_to_minimum_intensity() -> None:
    left = _horn_gui()
    router, _, _, _, _ = _router(left=left)

    router.handle(DeckAction(QUILLING_HORN, "left", 0.02, "changed"))
    router.tick(10.0)
    router.tick(10.1)

    assert left.command_calls == [(HORN_COMMAND, 1)]


def test_tick_stops_quilling_horn_after_release() -> None:
    left = _horn_gui()
    router, _, _, _, _ = _router(left=left)

    router.handle(DeckAction(QUILLING_HORN, "left", 0.8, "changed"))
    router.tick(10.0)
    router.tick(10.1)  # sounds once
    router.handle(DeckAction(QUILLING_HORN, "left", 0.0, "changed"))
    router.tick(10.2)  # released: no further horn

    assert left.command_calls == [(HORN_COMMAND, 12)]


def test_bundled_profile_binds_a_button_to_sequence_control() -> None:
    profile = ControlProfile.load()

    assert profile.buttons[0].action == SEQUENCE_CONTROL
    assert profile.buttons[0].target == "focused"
    assert profile.buttons[0].repeat is False


def test_bundled_profile_flags_x_and_y_buttons_as_repeat() -> None:
    profile = ControlProfile.load()

    assert profile.buttons[2].action == "reset"
    assert profile.buttons[2].repeat is True
    assert profile.buttons[3].action == "horn"
    assert profile.buttons[3].repeat is True


def test_button_repeat_flag_defaults_to_false() -> None:
    profile = _profile()

    assert profile.buttons[0].repeat is False


def _sequence_profile(**overrides) -> ControlProfile:
    return _profile(
        buttons={"0": {"action": "sequence_control", "target": "focused"}},
        **overrides,
    )


def test_sequence_control_constants_match_automatic_sequence_spec() -> None:
    assert SEQUENCE_CONTROL_COMMAND == "AUX1_OPTION_ONE"
    assert SEQUENCE_CONTROL_DURATION == pytest.approx(3.1)


def test_sequence_control_fires_immediately_and_schedules_full_burst() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = False
    router = DeckInputRouter(
        _sequence_profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=0))

    # Fired once immediately; the remaining emits (31 total at 100 ms over 3.1 s,
    # minus the immediate one) are scheduled for tick().
    assert focused_gui.command_calls == [SEQUENCE_CONTROL_COMMAND]
    assert router._sequences == {"focused": 30}


def test_sequence_control_repeats_across_ticks_then_stops() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = False
    router = DeckInputRouter(
        _sequence_profile(repeat_interval=1.0),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    # repeat_interval 1.0 s -> round(3.1 / 1.0) = 3 total emits.
    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=0))  # emit 1
    router.tick(0.0)  # primes the repeat clock
    router.tick(1.0)  # emit 2
    router.tick(2.0)  # emit 3 (burst complete)
    router.tick(3.0)  # nothing further

    assert focused_gui.command_calls == [SEQUENCE_CONTROL_COMMAND] * 3
    assert router._sequences == {}


def test_sequence_control_confirms_catalog_entry_when_visible() -> None:
    focused_gui = _gui()
    focused_gui.catalog_visible = True
    focused_gui.select_calls = 0
    focused_gui.select_catalog_entry = lambda: setattr(focused_gui, "select_calls", focused_gui.select_calls + 1)
    router = DeckInputRouter(
        _sequence_profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=0))

    assert focused_gui.select_calls == 1
    assert focused_gui.command_calls == []
    assert router._sequences == {}


def _repeat_button_profile(**overrides) -> ControlProfile:
    return _profile(
        buttons={"3": {"action": "horn", "target": "focused", "repeat": True}},
        **overrides,
    )


def test_repeat_button_repeats_command_each_tick_while_held() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _repeat_button_profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))  # immediate
    router.tick(10.0)  # primes the repeat clock
    router.tick(10.1)  # first repeat
    router.tick(10.2)  # second repeat

    assert focused_gui.command_calls == ["BLOW_HORN_ONE", "BLOW_HORN_ONE", "BLOW_HORN_ONE"]
    # [target, command, interval, seconds waited since the last send]
    assert router._held_commands == {3: ["focused", "BLOW_HORN_ONE", pytest.approx(0.1), pytest.approx(0.0)]}


def test_repeat_button_stops_on_release() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _repeat_button_profile(),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))  # immediate
    router.tick(10.0)  # primes
    router.tick(10.1)  # first repeat
    router.handle(DeckAction("horn", "focused", 0.0, "released", button=3))
    router.tick(10.2)  # released: no further horn

    assert focused_gui.command_calls == ["BLOW_HORN_ONE", "BLOW_HORN_ONE"]
    assert router._held_commands == {}


def test_repeat_close_popup_button_closes_popup_without_repeating() -> None:
    focused_gui = _gui()
    focused_gui.popup_visible = True
    focused_gui.close_calls = 0
    focused_gui.close_popup = lambda: setattr(focused_gui, "close_calls", focused_gui.close_calls + 1)
    router = DeckInputRouter(
        _profile(buttons={"2": {"action": "reset", "target": "focused", "repeat": True}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("reset", "focused", 1.0, "pressed", button=2))
    router.tick(10.0)
    router.tick(10.1)

    assert focused_gui.close_calls == 1
    assert focused_gui.command_calls == []
    assert router._held_commands == {}


def test_non_repeat_button_fires_once_and_is_not_stored() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _profile(buttons={"3": {"action": "horn", "target": "focused"}}),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))
    router.tick(10.0)
    router.tick(10.1)

    assert focused_gui.command_calls == ["BLOW_HORN_ONE"]
    assert router._held_commands == {}


def test_clear_resets_sequence_and_held_command_state() -> None:
    focused_gui = _gui()
    router = DeckInputRouter(
        _profile(
            buttons={
                "0": {"action": "sequence_control", "target": "focused"},
                "3": {"action": "horn", "target": "focused", "repeat": True},
            }
        ),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={},
    )

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=0))
    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))
    assert router._sequences and router._held_commands

    router.clear()

    assert router._sequences == {}
    assert router._held_commands == {}


def test_provider_ignores_duplicate_add_event_for_enumerated_device(caplog: pytest.LogCaptureFixture) -> None:
    def joystick(name: str):
        device = SimpleNamespace(name=name, init_calls=0, quit_calls=0)
        device.init = lambda: setattr(device, "init_calls", device.init_calls + 1)
        device.quit = lambda: setattr(device, "quit_calls", device.quit_calls + 1)
        device.get_instance_id = lambda: 7
        device.get_numaxes = lambda: 6
        device.get_numbuttons = lambda: 20
        device.get_name = lambda: "Steam Deck"
        device.get_guid = lambda: "deck-guid"
        return device

    enumerated = joystick("enumerated")
    duplicate = joystick("duplicate")
    devices = iter((enumerated, duplicate))
    pygame = SimpleNamespace(joystick=SimpleNamespace(Joystick=lambda _index: next(devices)))
    provider = SteamDeckInputProvider(_profile(), pygame_module=pygame)

    with caplog.at_level("INFO"):
        provider._add_device(0)
        provider._add_device(0)

    assert provider._joysticks == {7: enumerated}
    assert duplicate.quit_calls == 1
    assert caplog.messages.count("SDL controller connected: name=Steam Deck guid=deck-guid axes=6 buttons=20") == 1


# ---------------------------------------------------------------------------
# Trackpad (SDL Game Controller touchpad) horn
# ---------------------------------------------------------------------------


def _touchpad_profile(**overrides) -> ControlProfile:
    return _profile(
        touchpads={
            "0": {"action": "quilling_horn", "target": "left"},
            "1": {"action": "quilling_horn", "target": "right"},
        },
        **overrides,
    )


def _touchpad_pygame(events):
    return SimpleNamespace(
        JOYAXISMOTION=1,
        JOYBUTTONDOWN=2,
        JOYBUTTONUP=3,
        JOYHATMOTION=6,
        JOYDEVICEADDED=4,
        JOYDEVICEREMOVED=5,
        CONTROLLERTOUCHPADDOWN=7,
        CONTROLLERTOUCHPADMOTION=8,
        CONTROLLERTOUCHPADUP=9,
        event=SimpleNamespace(get=lambda: list(events)),
    )


def _touch_event(event_type: int, touch_id: int, finger: int, y: float):
    return SimpleNamespace(type=event_type, touch_id=touch_id, finger=finger, x=0.5, y=y, pressure=1.0)


def test_bundled_profile_binds_touchpads_to_quilling_horn() -> None:
    profile = ControlProfile.load()

    assert profile.touchpads[0].action == "quilling_horn"
    assert profile.touchpads[0].target == "left"
    assert profile.touchpads[1].action == "quilling_horn"
    assert profile.touchpads[1].target == "right"


def test_bundled_profile_uses_small_touch_dead_zone() -> None:
    profile = ControlProfile.load()

    assert profile.touch_dead_zone == 0.05


def test_touch_dead_zone_defaults_when_omitted() -> None:
    profile = _profile()

    assert profile.touch_dead_zone == 0.05
    assert profile.touchpads == {}


def test_profile_rejects_out_of_range_touch_dead_zone() -> None:
    with pytest.raises(ProfileError, match="touch_dead_zone"):
        _touchpad_profile(touch_dead_zone=1.0)


def test_profile_rejects_non_quilling_touchpad_action() -> None:
    with pytest.raises(ProfileError, match="cannot be assigned to a touchpad"):
        _profile(touchpads={"0": {"action": "bell", "target": "left"}})


def test_profile_rejects_touchpad_without_fixed_panel_target() -> None:
    with pytest.raises(ProfileError, match="fixed panel target"):
        _profile(touchpads={"0": {"action": "quilling_horn", "target": "focused"}})


def test_touchpad_binding_is_parsed_into_dataclass() -> None:
    profile = _touchpad_profile()

    assert profile.touchpads[0] == TouchpadBinding("quilling_horn", "left")
    assert profile.touchpads[1] == TouchpadBinding("quilling_horn", "right")


def test_normalize_touch_y_maps_top_to_off_and_bottom_to_full() -> None:
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=_touchpad_pygame([]))

    # Top edge and anything inside the small dead zone is off.
    assert provider._normalize_touch_y(0.0) == 0.0
    assert provider._normalize_touch_y(0.05) == 0.0
    # Mid-pad and the bottom edge ramp up to full.
    assert provider._normalize_touch_y(0.5) == pytest.approx((0.5 - 0.05) / (1.0 - 0.05))
    assert provider._normalize_touch_y(1.0) == pytest.approx(1.0)
    # Values are clamped to the [0, 1] range.
    assert provider._normalize_touch_y(2.0) == pytest.approx(1.0)


def test_provider_touch_down_then_motion_emits_quilling_horn_on_left_pad() -> None:
    pygame = _touchpad_pygame(
        [
            _touch_event(7, touch_id=0, finger=0, y=0.5),  # DOWN
            _touch_event(8, touch_id=0, finger=0, y=1.0),  # MOTION to bottom
        ]
    )
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert all(a.name == QUILLING_HORN and a.target == "left" and a.phase == "changed" for a in actions)
    assert [a.value for a in actions] == pytest.approx([(0.5 - 0.05) / 0.95, 1.0])


def test_provider_touch_on_right_pad_targets_right_panel() -> None:
    pygame = _touchpad_pygame([_touch_event(7, touch_id=1, finger=0, y=0.8)])
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert [(a.name, a.target) for a in actions] == [(QUILLING_HORN, "right")]
    assert actions[0].value == pytest.approx((0.8 - 0.05) / 0.95)


def test_provider_touch_up_stops_the_horn_when_last_finger_lifts() -> None:
    pygame = _touchpad_pygame(
        [
            _touch_event(7, touch_id=0, finger=0, y=0.6),  # DOWN
            _touch_event(9, touch_id=0, finger=0, y=0.6),  # UP (last finger)
        ]
    )
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert actions[-1].name == QUILLING_HORN
    assert actions[-1].target == "left"
    assert actions[-1].value == 0.0
    assert provider._touch_fingers == {}


def test_provider_multi_finger_keeps_horn_until_last_finger_lifts() -> None:
    pygame = _touchpad_pygame(
        [
            _touch_event(7, touch_id=0, finger=0, y=0.3),  # finger 0 DOWN
            _touch_event(7, touch_id=0, finger=1, y=0.9),  # finger 1 DOWN
            _touch_event(9, touch_id=0, finger=1, y=0.9),  # finger 1 UP (one remains)
            _touch_event(9, touch_id=0, finger=0, y=0.3),  # finger 0 UP (last one)
        ]
    )
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=pygame)

    actions = provider.poll()

    # Lifting one of two fingers keeps sounding (tracks the remaining finger);
    # only the final lift emits the 0.0 stop.
    assert actions[2].value == pytest.approx((0.3 - 0.05) / 0.95)
    assert actions[3].value == 0.0
    assert provider._touch_fingers == {}


def test_provider_ignores_touch_events_for_unmapped_pad() -> None:
    pygame = _touchpad_pygame([_touch_event(7, touch_id=5, finger=0, y=0.5)])
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=pygame)

    assert provider.poll() == []


def test_touch_drag_drives_router_quilling_horn_end_to_end() -> None:
    left = _horn_gui()
    router, _, _, _, _ = _router(profile=_touchpad_profile(), left=left)
    pygame = _touchpad_pygame([_touch_event(7, touch_id=0, finger=0, y=1.0)])
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=pygame)

    for action in provider.poll():
        router.handle(action)
    router.tick(10.0)  # primes the repeat clock
    router.tick(10.1)  # first repeat

    # A finger dragged to the bottom sounds the horn at full intensity; the
    # fallback list lets a Legacy engine use the intensity and a non-Legacy
    # engine fall through to the plain Blow Horn.
    assert left.command_calls == [(HORN_COMMAND, 15)]


def test_touch_release_stops_router_repeat() -> None:
    left = _horn_gui()
    router, _, _, _, _ = _router(profile=_touchpad_profile(), left=left)

    router.handle(DeckAction(QUILLING_HORN, "left", 0.8, "changed"))
    router.tick(10.0)
    router.tick(10.1)  # sounds once
    router.handle(DeckAction(QUILLING_HORN, "left", 0.0, "changed"))
    router.tick(10.2)  # released: no further horn

    assert left.command_calls == [(HORN_COMMAND, 12)]


def test_provider_without_touchpad_support_processes_joystick_only() -> None:
    # A pygame build lacking the CONTROLLERTOUCHPAD* constants (and thus the
    # touchpad horn) still handles the joystick controls without error.
    pygame = SimpleNamespace(
        JOYAXISMOTION=1,
        JOYBUTTONDOWN=2,
        JOYBUTTONUP=3,
        JOYHATMOTION=6,
        JOYDEVICEADDED=4,
        JOYDEVICEREMOVED=5,
        event=SimpleNamespace(get=lambda: [SimpleNamespace(type=1, axis=1, value=-1.0)]),
    )
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=pygame)

    actions = provider.poll()

    assert [a.name for a in actions] == ["throttle"]


def test_provider_start_allows_touchpad_events_and_opens_controller() -> None:
    calls: list[object] = []
    opened: list[int] = []

    class FakeController:
        def __init__(self, index: int) -> None:
            opened.append(index)

        def init(self) -> None:
            calls.append("controller.opened")

        def quit(self) -> None:
            calls.append("controller.quit")

    def joystick(_index: int):
        device = SimpleNamespace()
        device.init = lambda: None
        device.get_instance_id = lambda: 7
        device.get_numaxes = lambda: 6
        device.get_numbuttons = lambda: 20
        device.get_name = lambda: "Steam Deck"
        device.get_guid = lambda: "deck-guid"
        return device

    controller_module = SimpleNamespace(init=lambda: calls.append("subsystem.init"), Controller=FakeController)
    pygame = SimpleNamespace(
        JOYAXISMOTION=1,
        JOYBUTTONDOWN=2,
        JOYBUTTONUP=3,
        JOYHATMOTION=6,
        JOYDEVICEADDED=4,
        JOYDEVICEREMOVED=5,
        CONTROLLERTOUCHPADDOWN=7,
        CONTROLLERTOUCHPADMOTION=8,
        CONTROLLERTOUCHPADUP=9,
        display=SimpleNamespace(init=lambda: None),
        event=SimpleNamespace(
            set_blocked=lambda _t: None,
            set_allowed=lambda event_types: calls.append(("allowed", tuple(event_types))),
        ),
        joystick=SimpleNamespace(init=lambda: None, get_count=lambda: 1, Joystick=joystick),
        _sdl2=SimpleNamespace(controller=controller_module),
    )
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=pygame)

    provider.start()

    assert ("allowed", (1, 2, 3, 6, 4, 5, 7, 8, 9)) in calls
    assert "subsystem.init" in calls
    assert "controller.opened" in calls
    assert opened == [0]
    assert provider._controllers == {7: provider._controllers[7]}


def test_provider_start_without_controller_module_leaves_touchpad_disabled() -> None:
    pygame = SimpleNamespace(
        JOYAXISMOTION=1,
        JOYBUTTONDOWN=2,
        JOYBUTTONUP=3,
        JOYHATMOTION=6,
        JOYDEVICEADDED=4,
        JOYDEVICEREMOVED=5,
        display=SimpleNamespace(init=lambda: None),
        event=SimpleNamespace(set_blocked=lambda _t: None, set_allowed=lambda _types: None),
        joystick=SimpleNamespace(init=lambda: None, get_count=lambda: 0),
    )
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=pygame)

    provider.start()

    assert provider._controller_module is None
    assert provider._controllers == {}


def test_remove_device_resets_touch_finger_state() -> None:
    pygame = _touchpad_pygame([_touch_event(7, touch_id=0, finger=0, y=0.5)])
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=pygame)

    provider.poll()
    assert provider._touch_fingers  # a finger is being tracked

    provider._remove_device(instance_id=7)

    assert provider._touch_fingers == {}


# ---------------------------------------------------------------------------
# Raw hidraw trackpad reader (Steam Deck built-in pads)
# ---------------------------------------------------------------------------


def _deck_state_report(*, lpad: tuple[int, int] | None = None, rpad: tuple[int, int] | None = None) -> bytes:
    # Build a 64-byte Deck "state" input report with the given pad coordinates.
    # A pad with coordinates is marked touched via its bit in the touch byte.
    report = bytearray(64)
    report[0] = 0x01
    report[2] = 0x09  # ucType = state packet
    report[3] = 0x40  # ucLength
    touch = 0
    if lpad is not None:
        touch |= 1 << 3
        struct.pack_into("<hh", report, 16, lpad[0], lpad[1])
    if rpad is not None:
        touch |= 1 << 4
        struct.pack_into("<hh", report, 20, rpad[0], rpad[1])
    report[10] = touch
    return bytes(report)


def test_decode_deck_pads_reads_touch_bits_and_coordinates() -> None:
    report = _deck_state_report(lpad=(100, -200), rpad=(-300, 400))

    decoded = _decode_deck_pads(report)

    assert decoded == (True, (100, -200), True, (-300, 400))


def test_decode_deck_pads_reports_untouched_pads() -> None:
    # No pad marked touched: the touch flags are False and coordinates default 0.
    decoded = _decode_deck_pads(_deck_state_report())

    assert decoded == (False, (0, 0), False, (0, 0))


def test_decode_deck_pads_rejects_non_state_and_short_reports() -> None:
    not_a_state = bytearray(_deck_state_report(rpad=(0, 0)))
    not_a_state[2] = 0x05  # a different report type
    assert _decode_deck_pads(bytes(not_a_state)) is None
    assert _decode_deck_pads(b"\x01\x00\x09") is None  # too short


def test_deck_pad_y_fraction_maps_top_off_and_bottom_full() -> None:
    # The pad's y runs +32767 (top) .. -32768 (bottom); the fraction runs the
    # other way so a downward drag increases the horn.
    assert _deck_pad_y_fraction(32767) == pytest.approx(0.0)
    assert _deck_pad_y_fraction(-32768) == pytest.approx(1.0)
    assert _deck_pad_y_fraction(0) == pytest.approx(0.5, abs=1e-4)


def _paddle_report(*pressed_indices: int) -> bytes:
    # A Deck state report with the given back paddles held down.
    report = bytearray(_deck_state_report())
    for index in pressed_indices:
        byte, mask = _DECK_PADDLE_BUTTONS[index]
        report[byte] |= mask
    return bytes(report)


def _paddle_provider() -> SteamDeckInputProvider:
    # Paddles carry the bundled profile's actions: 16 = R4, 17 = L4, 18 = R5, 19 = L5.
    profile = _profile(
        buttons={
            "16": {"action": "engineer_chatter", "target": "focused"},
            "17": {"action": "volume_down", "target": "focused", "repeat": True},
            "18": {"action": "tower_chatter", "target": "focused"},
            "19": {"action": "volume_up", "target": "focused", "repeat": True},
        }
    )
    provider = SteamDeckInputProvider(profile, pygame_module=_touchpad_pygame([]))
    provider._hidraw_queue = queue.Queue()
    return provider


def test_decode_deck_paddles_reads_each_paddle_bit() -> None:
    # Steam Input never forwards these in Gaming Mode, so the raw report is the only
    # source; the bits were measured with scripts/deckinfo.py.
    for index in _DECK_PADDLE_BUTTONS:
        decoded = _decode_deck_paddles(_paddle_report(index))
        assert decoded is not None
        assert [held for held, state in decoded.items() if state] == [index]


def test_decode_deck_paddles_rejects_non_state_and_short_reports() -> None:
    not_a_state = bytearray(_deck_state_report())
    not_a_state[2] = 0x05
    assert _decode_deck_paddles(bytes(not_a_state)) is None
    assert _decode_deck_paddles(b"\x01\x00\x09") is None


def test_hidraw_paddle_press_and_release_emit_one_action_each() -> None:
    provider = _paddle_provider()

    provider._hidraw_queue.put(("report", "/dev/hidraw3", _paddle_report(16)))
    pressed = provider._drain_hidraw_pads()
    provider._hidraw_queue.put(("report", "/dev/hidraw3", _paddle_report(16)))
    held = provider._drain_hidraw_pads()
    provider._hidraw_queue.put(("report", "/dev/hidraw3", _paddle_report()))
    released = provider._drain_hidraw_pads()

    assert [(a.name, a.phase, a.button) for a in pressed] == [("engineer_chatter", "pressed", 16)]
    assert held == []  # only edges are emitted
    assert [(a.name, a.phase, a.button) for a in released] == [("engineer_chatter", "released", 16)]


def test_hidraw_paddles_are_independent() -> None:
    provider = _paddle_provider()

    provider._hidraw_queue.put(("report", "/dev/hidraw3", _paddle_report(17, 19)))
    actions = provider._drain_hidraw_pads()

    assert sorted((a.name, a.button) for a in actions) == [("volume_down", 17), ("volume_up", 19)]


def test_paddle_reported_by_both_routes_fires_once() -> None:
    # In Desktop Mode SDL also reports the paddles, so the same press can arrive twice.
    # _held_buttons is the single source of truth: the second route is a no-op.
    provider = _paddle_provider()

    sdl = provider._button_actions(16, True)
    provider._hidraw_queue.put(("report", "/dev/hidraw3", _paddle_report(16)))
    hidraw = provider._drain_hidraw_pads()

    assert [(a.name, a.phase) for a in sdl] == [("engineer_chatter", "pressed")]
    assert hidraw == []


def test_capability_warning_ignores_paddles_sdl_does_not_report() -> None:
    # Steam Input's virtual pad reports 11 buttons, but the paddles come from hidraw,
    # so they must not be reported as unavailable.
    provider = _paddle_provider()

    assert provider.capability_warnings(axis_count=6, button_count=11) == ""


def _hidraw_provider() -> SteamDeckInputProvider:
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=_touchpad_pygame([]))
    provider._hidraw_queue = queue.Queue()
    return provider


def test_hidraw_pad_motion_emits_quilling_horn_for_bound_pads() -> None:
    provider = _hidraw_provider()
    # Right pad touched near the bottom (-32768) -> full horn on the right panel.
    provider._hidraw_queue.put(("report", "/dev/hidraw3", _deck_state_report(rpad=(0, -32768))))

    actions = provider._drain_hidraw_pads()

    assert [(a.name, a.target, a.phase) for a in actions] == [(QUILLING_HORN, "right", "changed")]
    assert actions[0].value == pytest.approx(1.0)


def test_hidraw_uses_only_latest_report_per_node() -> None:
    provider = _hidraw_provider()
    # Two stale reports followed by the current one; only the last is applied.
    provider._hidraw_queue.put(("report", "/dev/hidraw3", _deck_state_report(rpad=(0, 32767))))
    provider._hidraw_queue.put(("report", "/dev/hidraw3", _deck_state_report(rpad=(0, 0))))

    actions = provider._drain_hidraw_pads()

    # y = 0 is mid-pad -> fraction 0.5, then the touch dead zone is applied.
    assert [(a.name, a.target) for a in actions] == [(QUILLING_HORN, "right")]
    assert actions[0].value == pytest.approx((0.5 - 0.05) / 0.95, abs=1e-3)


def test_hidraw_release_emits_single_stop_when_finger_lifts() -> None:
    provider = _hidraw_provider()
    provider._hidraw_queue.put(("report", "/dev/hidraw3", _deck_state_report(rpad=(0, -32768))))
    provider._drain_hidraw_pads()  # finger down

    # Next drain sees the pad released (no touched pads in the report).
    provider._hidraw_queue.put(("report", "/dev/hidraw3", _deck_state_report()))
    first = provider._drain_hidraw_pads()
    # A second empty drain must not emit another release.
    provider._hidraw_queue.put(("report", "/dev/hidraw3", _deck_state_report()))
    second = provider._drain_hidraw_pads()

    assert [(a.name, a.target, a.value) for a in first] == [(QUILLING_HORN, "right", 0.0)]
    assert second == []


def test_hidraw_ignores_unbound_pad() -> None:
    # A profile with only the right pad bound ignores left-pad motion.
    provider = SteamDeckInputProvider(
        _profile(touchpads={"1": {"action": "quilling_horn", "target": "right"}}),
        pygame_module=_touchpad_pygame([]),
    )
    provider._hidraw_queue = queue.Queue()
    provider._hidraw_queue.put(("report", "/dev/hidraw3", _deck_state_report(lpad=(0, -32768))))

    assert provider._drain_hidraw_pads() == []


def test_hidraw_reports_open_error_once() -> None:
    provider = _hidraw_provider()
    provider._hidraw_queue.put(("error", "/dev/hidraw3", "cannot open (permission denied)"))
    provider._hidraw_queue.put(("error", "/dev/hidraw3", "cannot open (permission denied)"))

    assert provider._drain_hidraw_pads() == []
    assert "/dev/hidraw3" in provider._hidraw_errors


def test_drain_hidraw_pads_is_noop_without_reader() -> None:
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=_touchpad_pygame([]))

    assert provider._hidraw_queue is None
    assert provider._drain_hidraw_pads() == []


def test_start_hidraw_readers_skips_when_no_touchpads_bound() -> None:
    provider = SteamDeckInputProvider(_profile(), pygame_module=_touchpad_pygame([]))

    provider._start_hidraw_readers()

    assert provider._hidraw_queue is None
    assert provider._hidraw_readers == []


def test_start_hidraw_readers_starts_thread_when_deck_node_present(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.pytrain.gui.controller.steam_deck_input as module

    monkeypatch.setattr(module, "_find_deck_hidraw_paths", lambda: ["/dev/hidraw-fake"])
    started: list[str] = []

    class _FakeReader:
        def __init__(self, path: str, out_queue: queue.Queue) -> None:
            self.path = path
            self.stopped = False

        def start(self) -> None:
            started.append(self.path)

        def stop(self) -> None:
            self.stopped = True

    monkeypatch.setattr(module, "_HidrawTrackpadReader", _FakeReader)
    provider = SteamDeckInputProvider(_touchpad_profile(), pygame_module=_touchpad_pygame([]))

    provider._start_hidraw_readers()

    assert started == ["/dev/hidraw-fake"]
    assert provider._hidraw_queue is not None

    provider._stop_hidraw_readers()

    assert provider._hidraw_readers == []
    assert provider._hidraw_queue is None


def test_find_deck_hidraw_paths_returns_list() -> None:
    # Off the Deck this is empty; the contract is simply a list of device paths.
    paths = _find_deck_hidraw_paths()

    assert isinstance(paths, list)
    assert all(p.startswith("/dev/hidraw") for p in paths)


def _controls_gui(*, controls_visible: bool = True):
    gui = _gui()
    gui.controls_visible = controls_visible
    gui.pages = []
    gui.page_controls = lambda forward: gui.pages.append(forward)
    return gui


def _controls_router(focused_gui, opened: list[str]) -> DeckInputRouter:
    # show_controls targets global, so it arrives through global_actions the same way
    # halt and the focus actions do -- not through the focused gui.
    return DeckInputRouter(
        ControlProfile.load(DEFAULT_PROFILE, fallback=False),
        left=lambda: _gui(),
        right=lambda: _gui(),
        focused=lambda: focused_gui,
        global_actions={"show_controls": lambda: opened.append("open")},
    )


def test_show_controls_opens_the_panel_on_press_only() -> None:
    opened: list[str] = []
    router = _controls_router(_controls_gui(controls_visible=False), opened)

    router.handle(DeckAction("show_controls", "global", 1.0, "pressed"))
    router.handle(DeckAction("show_controls", "global", 0.0, "released"))

    # No hold to cancel, unlike the admin chords, so the release is ignored.
    assert opened == ["open"]


def test_show_controls_still_opens_while_the_screen_is_already_up() -> None:
    # The gate must not swallow the action that opens it, or the "..." button would be
    # dead the second time it is pressed.
    opened: list[str] = []
    router = _controls_router(_controls_gui(controls_visible=True), opened)

    router.handle(DeckAction("show_controls", "global", 1.0, "pressed"))

    assert opened == ["open"]


def test_show_controls_is_dropped_when_no_handler_is_registered() -> None:
    focused_gui = _gui()
    router = _bundled_router(focused_gui)  # global_actions={}

    router.handle(DeckAction("show_controls", "global", 1.0, "pressed"))

    assert focused_gui.command_calls == []


def test_engine_commands_are_dropped_while_the_controls_screen_is_up() -> None:
    # Reading the help screen must not drive the train.
    focused_gui = _controls_gui()
    router = _bundled_router(focused_gui)

    router.handle(DeckAction("bell", "focused", 1.0, "pressed", button=1))
    router.handle(DeckAction("throttle", "focused", 0.8, "pressed"))
    router.handle(DeckAction(DPAD_LEFT, "focused", 1.0, "pressed"))

    assert focused_gui.command_calls == []
    assert focused_gui.speed_calls == []


def test_dpad_up_down_pages_the_controls_screen() -> None:
    focused_gui = _controls_gui()
    router = _bundled_router(focused_gui)

    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed"))
    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))

    assert focused_gui.pages == [True, False]
    # And emphatically not boost/brake.
    assert focused_gui.command_calls == []


def test_close_button_closes_the_controls_screen() -> None:
    # The screen is owned by the host GUI, not this pane's popup manager, so the
    # popup_visible path would never see it -- the gate closes it directly.
    focused_gui = _controls_gui()
    focused_gui.closed = []
    focused_gui.close_controls = lambda: focused_gui.closed.append(True)
    router = _bundled_router(focused_gui)

    router.handle(DeckAction("reset", "focused", 1.0, "pressed", button=2))

    assert focused_gui.closed == [True]
    assert focused_gui.command_calls == []


def test_close_button_is_tolerated_when_the_gui_cannot_close_it() -> None:
    focused_gui = _controls_gui()  # no close_controls attribute
    router = _bundled_router(focused_gui)

    router.handle(DeckAction("reset", "focused", 1.0, "pressed", button=2))

    assert focused_gui.command_calls == []


def test_engine_commands_flow_normally_once_the_screen_is_closed() -> None:
    focused_gui = _controls_gui(controls_visible=False)
    router = _bundled_router(focused_gui)

    router.handle(DeckAction("bell", "focused", 1.0, "pressed", button=1))

    assert focused_gui.command_calls == ["RING_BELL"]


def test_bundled_profile_binds_show_controls_to_the_stick_clicks() -> None:
    profile = ControlProfile.load(DEFAULT_PROFILE, fallback=False)

    chord = next(chord for chord in profile.chords if chord.action == "show_controls")
    assert chord.buttons == frozenset({9, 10})
    assert chord.target == "global"


def test_the_misc_button_is_left_unbound() -> None:
    # Steam's Quick Settings eats "..." -- the app never sees it, confirmed on-device.
    # A binding there would be listed on the help screen as though it worked.
    profile = ControlProfile.load(DEFAULT_PROFILE, fallback=False)

    assert 15 not in profile.buttons


def test_show_controls_must_target_global() -> None:
    # The bindings it lists are identical either side, so a per-pane target is a mistake.
    with pytest.raises(ProfileError):
        ControlProfile.from_dict(
            {
                "dead_zone": 0.15,
                "hysteresis": 0.05,
                "throttle_rate": 36.0,
                "repeat_interval": 0.1,
                "direction_threshold": 0.75,
                "axes": {},
                "buttons": {"15": {"action": "show_controls", "target": "focused"}},
                "chords": [],
            }
        )


def _chooser_gui():
    """A pane with a choice list open, recording what the D-pad asks of it."""
    gui = _gui()
    gui.chooser_visible = True
    gui.chooser_calls: list[str] = []
    gui.move_chooser = lambda forward=True: gui.chooser_calls.append(f"move:{'down' if forward else 'up'}")
    gui.select_chooser = lambda: gui.chooser_calls.append("select")
    gui.cancel_chooser = lambda: gui.chooser_calls.append("cancel")
    return gui


def test_dpad_drives_an_open_chooser_instead_of_the_engine() -> None:
    # A choice list is modal: up/down pick an option rather than boosting, right commits and left
    # abandons. Without this the D-pad would be changing speed behind the list.
    focused = _chooser_gui()
    router, _left, _right, _focused, _global = _router(left=focused)

    for name in (DPAD_DOWN, DPAD_UP, DPAD_RIGHT, DPAD_LEFT):
        router.handle(DeckAction(name, "focused", 1.0, "pressed"))

    assert focused.chooser_calls == ["move:down", "move:up", "select", "cancel"]
    assert focused.speed_calls == [], "nothing reached the engine"
    assert focused.command_calls == []


def test_the_a_button_commits_an_open_chooser() -> None:
    # Same as the catalog panel, where A confirms the highlighted entry.
    focused = _chooser_gui()
    router, _left, _right, _focused, _global = _router(
        _profile(buttons={str(SELECT_BUTTON): {"action": "front_coupler", "target": "focused"}}),
        left=focused,
    )

    router.handle(DeckAction("front_coupler", "focused", 1.0, "pressed", button=SELECT_BUTTON))

    assert focused.chooser_calls == ["select"]
    assert focused.command_calls == [], "its assigned command did not fire"


def test_a_release_is_swallowed_while_a_chooser_is_open() -> None:
    # Not merely ignored: a release reaching the layout would clear a throttle or latch that the
    # press never set.
    focused = _chooser_gui()
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction(DPAD_DOWN, "focused", 0.0, "released"))

    assert focused.chooser_calls == []
    assert focused.speed_calls == []


def test_halt_still_works_while_a_chooser_is_open() -> None:
    # A global-target action resolves no gui, so it is never gated. HALT has to work whatever is
    # on screen.
    focused = _chooser_gui()
    router, _left, _right, _focused, global_calls = _router(
        _profile(buttons={"3": {"action": "halt", "target": "global"}}),
        left=focused,
    )

    router.handle(DeckAction("halt", "global", 1.0, "pressed", button=3))

    assert global_calls == ["halt"]


def test_the_dpad_reaches_the_engine_again_once_the_chooser_closes() -> None:
    focused = _chooser_gui()
    focused.chooser_visible = False
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))
    router.tick(1.0)

    assert focused.chooser_calls == []
    assert focused.speed_calls or focused.command_calls, "the D-pad went back to driving"


def _switch_gui(*, switch_active: bool = True):
    """A pane showing a track switch, recording the throws asked of it.

    It keeps a ``throttle_state`` deliberately: a pane that was driving an engine before a
    switch was picked in it still has one, so a stick pushed here would move that engine if
    the switch handling did not claim the action first.
    """
    gui = _gui(speed=20)
    gui.switch_active = switch_active
    gui.switch_calls: list[bool] = []
    gui.on_switch_command = lambda thru: gui.switch_calls.append(thru)
    return gui


@pytest.mark.parametrize(
    ("name", "thru"),
    [
        # L2 carries shutdown in the bundled profile and throws through; R2 carries startup
        # and throws out. Both the name the trigger reports on the squeeze and the
        # immediate/delayed pair a button would report are covered.
        ("shutdown", True),
        (SHUTDOWN_IMMEDIATE, True),
        (SHUTDOWN_DELAYED, True),
        ("startup", False),
        (STARTUP_IMMEDIATE, False),
        (STARTUP_DELAYED, False),
    ],
)
def test_triggers_throw_the_switch_rather_than_starting_an_engine(name, thru) -> None:
    focused = _switch_gui()
    router, _left, _right, _focused, _global = _router(_trigger_long_press_profile(), left=focused)

    router.handle(DeckAction(name, "focused", 1.0, "pressed"))

    assert focused.switch_calls == [thru]
    assert focused.command_calls == [], "no engine command reached the panel"


def test_triggers_still_start_and_stop_an_engine_in_an_engine_panel() -> None:
    # The remap is scoped to a panel showing a switch; everywhere else L2/R2 are unchanged.
    focused = _switch_gui(switch_active=False)
    router, _left, _right, _focused, _global = _router(_trigger_long_press_profile(), left=focused)

    router.handle(DeckAction(SHUTDOWN_IMMEDIATE, "focused", 1.0, "pressed"))

    assert focused.command_calls == ["SHUTDOWN_IMMEDIATE"]
    assert focused.switch_calls == []


def _face_button_profile() -> ControlProfile:
    """A and Y as the bundled profile binds them: sequence control on A, the horn on Y.

    The horn keeps its ``repeat`` flag, which is what makes the release matter: without the
    switch or route claim stopping it, ``tick()`` goes on sounding a horn at a panel with no
    engine.
    """
    return _profile(
        buttons={
            "0": {"action": "sequence_control", "target": "focused"},
            "3": {"action": "horn", "target": "focused", "repeat": True},
        }
    )


@pytest.mark.parametrize(
    ("name", "button", "thru"),
    [
        # A carries sequence control in the bundled profile and throws through; Y carries the
        # horn and throws out. Keyed on the action rather than on the index, so a profile that
        # moves either binding moves the throw with it.
        (SEQUENCE_CONTROL, 0, True),
        ("horn", 3, False),
    ],
)
def test_the_face_buttons_throw_the_switch_rather_than_working_an_engine(name, button, thru) -> None:
    focused = _switch_gui()
    router, _left, _right, _focused, _global = _router(_face_button_profile(), left=focused)

    router.handle(DeckAction(name, "focused", 1.0, "pressed", button=button))
    router.handle(DeckAction(name, "focused", 0.0, "released", button=button))
    router.tick(0.0)
    router.tick(1.0)

    assert focused.switch_calls == [thru], "one throw on the press, and the release adds none"
    assert focused.command_calls == [], "no engine command reached the panel"


def test_the_face_buttons_still_work_the_engine_in_an_engine_panel() -> None:
    # The remap is scoped to a panel showing a switch; everywhere else A and Y are unchanged.
    focused = _switch_gui(switch_active=False)
    router, _left, _right, _focused, _global = _router(_face_button_profile(), left=focused)

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=0))
    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))

    assert focused.command_calls == [SEQUENCE_CONTROL_COMMAND, PANEL_COMMANDS["horn"]]
    assert focused.switch_calls == []


def test_the_face_buttons_stand_aside_while_the_switch_catalog_is_open() -> None:
    # A switch is picked from the catalog and A is how an entry in it is confirmed, so a panel
    # already holding a switch must not take that button back while the list is up: the reader
    # is re-scoping the panel rather than working the switch behind it.
    focused = _switch_gui()
    focused.catalog_visible = True
    focused.select_calls = 0
    focused.select_catalog_entry = lambda: setattr(focused, "select_calls", focused.select_calls + 1)
    router, _left, _right, _focused, _global = _router(_face_button_profile(), left=focused)

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=0))
    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))

    assert focused.select_calls == 1, "A confirmed the highlighted entry"
    assert focused.switch_calls == [], "neither face button threw the switch behind the list"

    # Only the face buttons stand aside. L2/R2 have no job in the catalog, so holding them
    # back would cost a throw for nothing.
    router.handle(DeckAction(SHUTDOWN_IMMEDIATE, "focused", 1.0, "pressed"))

    assert focused.switch_calls == [True]


@pytest.mark.parametrize(
    ("name", "button", "command"),
    [
        (SEQUENCE_CONTROL, 0, SEQUENCE_CONTROL_COMMAND),
        ("horn", 3, PANEL_COMMANDS["horn"]),
    ],
)
def test_a_face_button_held_as_the_panel_became_a_switch_stops_repeating(name, button, command) -> None:
    # Both of these outlive their press -- Y re-sends the horn every repeat_interval while it
    # is held, A runs a sequence-control burst -- and the release that would stop them is
    # swallowed once the panel is showing a switch. So the claim has to stop them, the way the
    # stick path drops a throttle the panel had pending.
    focused = _switch_gui(switch_active=False)
    router, _left, _right, _focused, _global = _router(_face_button_profile(), left=focused)

    router.handle(DeckAction(name, "focused", 1.0, "pressed", button=button))
    focused.switch_active = True
    router.handle(DeckAction(name, "focused", 0.0, "released", button=button))
    router.tick(0.0)
    router.tick(1.0)

    assert focused.command_calls == [command], "the press did its engine job once and nothing repeated"
    assert focused.switch_calls == [], "a release throws nothing"


def test_a_stick_pushed_sideways_throws_the_switch_thru_once_per_deflection() -> None:
    # Left and right both throw through, and holding the stick over throws once: it stands in
    # for a press of the on-screen key, not for holding that key down.
    left = _switch_gui()
    router, _left, _right, _focused, _global = _router(left=left)

    router.handle(DeckAction("direction", "left", 0.9, "changed"))
    router.handle(DeckAction("direction", "left", 1.0, "changed"))

    assert left.switch_calls == [True], "held over, so a single throw"

    router.handle(DeckAction("direction", "left", 0.0, "changed"))
    router.handle(DeckAction("direction", "left", -0.9, "changed"))

    assert left.switch_calls == [True, True], "re-armed at center, and left throws thru too"
    assert left.command_calls == [], "no direction command reached the panel"


def test_a_stick_pushed_vertically_throws_the_switch_out() -> None:
    left = _switch_gui()
    router, _left, _right, _focused, _global = _router(left=left)

    router.handle(DeckAction("throttle", "left", -0.9, "changed"))

    assert left.switch_calls == [False]


def test_a_stick_short_of_the_threshold_does_not_throw_the_switch() -> None:
    # Same threshold the direction handling uses, so a resting thumb cannot throw a switch.
    left = _switch_gui()
    router, _left, _right, _focused, _global = _router(left=left)

    router.handle(DeckAction("throttle", "left", 0.5, "changed"))

    assert left.switch_calls == []


def test_a_stick_on_a_switch_panel_does_not_drive_the_engine_it_last_held() -> None:
    # The throttle axis, which is the one that would have moved it: it throws the switch out
    # rather than ramping a speed.
    left = _switch_gui()
    router, _left, _right, _focused, _global = _router(left=left)

    router.handle(DeckAction("throttle", "left", 0.9, "changed"))
    router.tick(0.0)
    router.tick(1.0)

    assert left.switch_calls == [False]
    assert left.speed_calls == [], "the stick threw the switch instead of moving an engine"


def test_each_stick_throws_the_switch_in_its_own_panel() -> None:
    left = _switch_gui()
    right = _switch_gui()
    router, _left, _right, _focused, _global = _router(left=left, right=right)

    router.handle(DeckAction("direction", "left", 0.9, "changed"))

    assert left.switch_calls == [True]
    assert right.switch_calls == [], "the other panel's switch was left alone"


def test_a_stick_keeps_driving_the_engine_in_the_other_panel() -> None:
    # One panel showing a switch must not stop the other from being driven.
    left = _switch_gui()
    right = _gui(speed=10)
    router, _left, _right, _focused, _global = _router(left=left, right=right)

    router.handle(DeckAction("direction", "left", 0.9, "changed"))
    router.handle(DeckAction("throttle", "right", 0.9, "changed"))
    router.tick(0.0)
    router.tick(1.0)

    assert left.switch_calls == [True]
    assert right.speed_calls, "the engine panel's stick still ramps its throttle"


def _route_gui(*, route_active: bool = True):
    """A pane showing a route, recording the fires asked of it.

    Keeps a ``throttle_state`` for the reason _switch_gui does: a pane that was driving an
    engine before a route was picked in it still has one, so a stick pushed here would move
    that engine if the route handling did not claim the action first.
    """
    gui = _gui(speed=20)
    gui.route_active = route_active
    gui.route_calls: list[bool] = []
    gui.on_route_command = lambda: gui.route_calls.append(True)
    return gui


@pytest.mark.parametrize(
    "name",
    [
        # Both triggers fire, where for a switch L2 throws through and R2 out: a route has
        # no un-fire for the second of them to mean. Both the name a trigger reports on the
        # squeeze and the immediate/delayed pair a button would report are covered.
        "shutdown",
        SHUTDOWN_IMMEDIATE,
        SHUTDOWN_DELAYED,
        "startup",
        STARTUP_IMMEDIATE,
        STARTUP_DELAYED,
    ],
)
def test_triggers_fire_the_route_rather_than_starting_an_engine(name) -> None:
    focused = _route_gui()
    router, _left, _right, _focused, _global = _router(_trigger_long_press_profile(), left=focused)

    router.handle(DeckAction(name, "focused", 1.0, "pressed"))

    assert focused.route_calls == [True]
    assert focused.command_calls == [], "no engine command reached the panel"


def test_triggers_still_start_and_stop_an_engine_in_a_panel_holding_no_route() -> None:
    # The remap is scoped to a panel showing a route; everywhere else L2/R2 are unchanged.
    focused = _route_gui(route_active=False)
    router, _left, _right, _focused, _global = _router(_trigger_long_press_profile(), left=focused)

    router.handle(DeckAction(SHUTDOWN_IMMEDIATE, "focused", 1.0, "pressed"))

    assert focused.command_calls == ["SHUTDOWN_IMMEDIATE"]
    assert focused.route_calls == []


def test_the_a_button_fires_the_route_rather_than_working_an_engine() -> None:
    # The face button that throws a switch through fires a route: A in the bundled profile,
    # keyed on the action it carries there rather than on its index, so a profile that moves
    # sequence control moves the fire with it. One fire on the press, and the release adds
    # none -- a route stands in for a press of the on-screen key, not for holding it down.
    focused = _route_gui()
    router, _left, _right, _focused, _global = _router(_face_button_profile(), left=focused)

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=0))
    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 0.0, "released", button=0))
    router.tick(0.0)
    router.tick(1.0)

    assert focused.route_calls == [True], "one fire on the press, and the release adds none"
    assert focused.command_calls == [], "no engine command reached the panel"


def test_the_horn_button_is_swallowed_rather_than_firing_the_route() -> None:
    # A switch has two things to do, so both face buttons throw it; a route has no un-fire for
    # the second to mean. Y is claimed all the same rather than passed on -- the swallow the
    # down and left stick deflections get, and taken for their reason: the panel has no engine
    # in it, so the horn would sound at whichever engine it held before the route was picked.
    focused = _route_gui()
    router, _left, _right, _focused, _global = _router(_face_button_profile(), left=focused)

    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))
    router.handle(DeckAction("horn", "focused", 0.0, "released", button=3))
    router.tick(0.0)
    router.tick(1.0)

    assert focused.route_calls == [], "it is not a second way to fire"
    assert focused.command_calls == [], "and no horn reached the engine the panel last held"


def test_the_face_buttons_still_work_the_engine_in_a_panel_holding_no_route() -> None:
    # The remap is scoped to a panel showing a route; everywhere else A and Y are unchanged.
    focused = _route_gui(route_active=False)
    router, _left, _right, _focused, _global = _router(_face_button_profile(), left=focused)

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=0))
    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))

    assert focused.command_calls == [SEQUENCE_CONTROL_COMMAND, PANEL_COMMANDS["horn"]]
    assert focused.route_calls == []


def test_the_face_buttons_stand_aside_while_the_route_catalog_is_open() -> None:
    # A route is picked from the catalog and A is how an entry in it is confirmed, exactly as
    # on a switch panel: a reader looking at that list is re-scoping the panel rather than
    # working the route it already holds, so neither face button is claimed while it is up.
    focused = _route_gui()
    focused.catalog_visible = True
    focused.select_calls = 0
    focused.select_catalog_entry = lambda: setattr(focused, "select_calls", focused.select_calls + 1)
    router, _left, _right, _focused, _global = _router(_face_button_profile(), left=focused)

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=0))
    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))

    assert focused.select_calls == 1, "A confirmed the highlighted entry"
    assert focused.route_calls == [], "and neither button fired the route behind the list"

    # Only the face buttons stand aside. The triggers have no job in the catalog, so holding
    # them back would cost a fire for nothing.
    router.handle(DeckAction(SHUTDOWN_IMMEDIATE, "focused", 1.0, "pressed"))

    assert focused.route_calls == [True]


@pytest.mark.parametrize(
    ("name", "button", "command"),
    [
        (SEQUENCE_CONTROL, 0, SEQUENCE_CONTROL_COMMAND),
        ("horn", 3, PANEL_COMMANDS["horn"]),
    ],
)
def test_a_face_button_held_as_the_panel_became_a_route_stops_repeating(name, button, command) -> None:
    # Both of these outlive their press -- Y re-sends the horn every repeat_interval while it
    # is held, A runs a sequence-control burst -- and the release that would stop them is
    # swallowed once the panel is showing a route. So the claim has to stop them, the way the
    # stick path drops a throttle the panel had pending. Y is claimed here despite firing
    # nothing, which is the whole of why it can be stopped at all.
    focused = _route_gui(route_active=False)
    router, _left, _right, _focused, _global = _router(_face_button_profile(), left=focused)

    router.handle(DeckAction(name, "focused", 1.0, "pressed", button=button))
    focused.route_active = True
    router.handle(DeckAction(name, "focused", 0.0, "released", button=button))
    router.tick(0.0)
    router.tick(1.0)

    assert focused.command_calls == [command], "the press did its engine job once and nothing repeated"
    assert focused.route_calls == [], "a release fires nothing"


def test_a_stick_pushed_up_fires_the_route_once_per_deflection() -> None:
    # The axis is inverted in the profile, so stick up arrives positive. Holding it up fires
    # once: it stands in for a press of the on-screen key, not for holding that key down.
    left = _route_gui()
    router, _left, _right, _focused, _global = _router(left=left)

    router.handle(DeckAction("throttle", "left", 0.9, "changed"))
    router.handle(DeckAction("throttle", "left", 1.0, "changed"))

    assert left.route_calls == [True], "held up, so a single fire"

    router.handle(DeckAction("throttle", "left", 0.0, "changed"))
    router.handle(DeckAction("throttle", "left", 0.9, "changed"))

    assert left.route_calls == [True, True], "re-armed at center"


def test_a_stick_pushed_right_fires_the_route() -> None:
    # Positive direction is the way _handle_direction reads as forward, which is the stick
    # pushed right.
    left = _route_gui()
    router, _left, _right, _focused, _global = _router(left=left)

    router.handle(DeckAction("direction", "left", 0.9, "changed"))

    assert left.route_calls == [True]
    assert left.command_calls == [], "no direction command reached the panel"


@pytest.mark.parametrize("name", ["throttle", "direction"])
def test_a_stick_pulled_the_other_way_fires_nothing_and_drives_nothing(name) -> None:
    # Down and left are claimed but do nothing: a route has no un-fire to give them, and a
    # pane showing one has no engine for them to ramp or reverse either. Unlike a switch,
    # where sign is ignored and every deflection acts.
    left = _route_gui()
    router, _left, _right, _focused, _global = _router(left=left)

    router.handle(DeckAction(name, "left", -0.9, "changed"))
    router.tick(0.0)
    router.tick(1.0)

    assert left.route_calls == []
    assert left.speed_calls == [], "the pulled-back stick did not ramp the engine it last held"
    assert left.command_calls == []


def test_a_stick_short_of_the_threshold_does_not_fire_the_route() -> None:
    # Same threshold the switch throws use, so a resting thumb cannot fire a route.
    left = _route_gui()
    router, _left, _right, _focused, _global = _router(left=left)

    router.handle(DeckAction("throttle", "left", 0.5, "changed"))

    assert left.route_calls == []


def test_each_stick_fires_the_route_in_its_own_panel() -> None:
    # And a panel showing a route must not stop the other from being driven.
    left = _route_gui()
    right = _gui(speed=10)
    router, _left, _right, _focused, _global = _router(left=left, right=right)

    router.handle(DeckAction("throttle", "left", 0.9, "changed"))
    router.handle(DeckAction("throttle", "right", 0.9, "changed"))
    router.tick(0.0)
    router.tick(1.0)

    assert left.route_calls == [True]
    assert left.speed_calls == [], "the stick fired the route instead of moving an engine"
    assert right.speed_calls, "the engine panel's stick still ramps its throttle"


def test_fires_on_press_resolves_the_panel_a_target_names() -> None:
    # What the provider asks before deciding whether a trigger acts on the squeeze. Both
    # panel types answer yes: the question is about the timing, and neither a throw nor a
    # fire has a held variant worth waiting for.
    left = _switch_gui()
    right = _gui()
    router, _left, _right, focused, _global = _router(left=left, right=right)

    assert router.fires_on_press("left") is True
    assert router.fires_on_press("right") is False
    assert router.fires_on_press("focused") is True, "the focused pane is the left one here"

    focused.value = _route_gui()

    assert router.fires_on_press("focused") is True
    assert router.fires_on_press("global") is False, "a global action resolves no panel"


def test_provider_trigger_throws_a_switch_on_the_squeeze() -> None:
    # Waiting for the release only exists to tell a short startup/shutdown press from a held
    # one, and a switch has no such pair: the throw happens as the trigger moves.
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    events = [SimpleNamespace(type=1, axis=2, value=1.0)]
    pygame.event = SimpleNamespace(get=lambda: list(events))
    provider = SteamDeckInputProvider(
        _trigger_long_press_profile(),
        pygame_module=pygame,
        clock=_clock(),
        fires_on_press=lambda target: target == "focused",
    )

    squeezed = provider.poll()
    events[:] = [SimpleNamespace(type=1, axis=2, value=-1.0)]
    released = provider.poll()

    assert [(a.name, a.target, a.phase) for a in squeezed] == [("shutdown", "focused", "pressed")]
    assert released == [], "the release adds nothing; the throw already happened"


def test_provider_trigger_keeps_its_hold_behaviour_for_an_engine_panel() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=1, axis=2, value=1.0),
            SimpleNamespace(type=1, axis=2, value=-1.0),
        ]
    )
    provider = SteamDeckInputProvider(
        _trigger_long_press_profile(),
        pygame_module=pygame,
        clock=_clock(0.0, STARTUP_LONG_PRESS_SECONDS - 0.5),
        fires_on_press=lambda target: False,
    )

    actions = provider.poll()

    assert [(a.name, a.target, a.phase) for a in actions] == [(SHUTDOWN_IMMEDIATE, "focused", "pressed")]


# --------------------------------------------------------------------------------------- #
# The D-pad as a profile section rather than a hard-coded branch.
# --------------------------------------------------------------------------------------- #


def test_a_profile_with_no_dpad_section_keeps_what_the_dpad_always_did() -> None:
    # The default is the old behavior verbatim, so every hand-written profile predating the
    # section is unaffected by its arrival.
    profile = _profile()

    assert profile.dpad[DPAD_UP].action == "boost"
    assert profile.dpad[DPAD_UP].repeat is True
    assert profile.dpad[DPAD_DOWN].action == "brake"
    assert profile.dpad[DPAD_RIGHT].action == "smoke_up"
    assert profile.dpad[DPAD_RIGHT].repeat is False
    assert profile.dpad[DPAD_LEFT].action == "smoke_down"


def test_a_dpad_section_rebinds_one_direction_and_leaves_the_others() -> None:
    profile = _profile(dpad={"left": {"action": "bell", "target": "right"}})

    assert profile.dpad[DPAD_LEFT].action == "bell"
    assert profile.dpad[DPAD_LEFT].target == "right"
    assert profile.dpad[DPAD_UP].action == "boost"


def test_a_dpad_direction_bound_to_null_is_switched_off_entirely() -> None:
    profile = _profile(dpad={"right": None})
    router, left, _right, _focused, _global_calls = _router(profile)

    router.handle(DeckAction(DPAD_RIGHT, "focused", 1.0, "pressed"))

    assert left.command_calls == []


def test_a_dpad_section_rejects_a_bad_direction_action_or_target() -> None:
    with pytest.raises(ProfileError, match="Unknown dpad direction"):
        _profile(dpad={"diagonal": {"action": "boost", "target": "focused"}})
    with pytest.raises(ProfileError, match="cannot be assigned to the dpad"):
        _profile(dpad={"up": {"action": "halt", "target": "global"}})
    with pytest.raises(ProfileError, match="requires a panel target"):
        _profile(dpad={"up": {"action": "boost", "target": "global"}})


def test_a_rebound_dpad_direction_sends_what_the_profile_says() -> None:
    profile = _profile(dpad={"up": {"action": "bell", "target": "focused"}})
    router, left, _right, _focused, _global_calls = _router(profile)

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))

    assert left.command_calls == ["RING_BELL"]


def test_a_repeat_flag_on_a_dpad_direction_is_what_makes_it_repeat() -> None:
    # Boost repeats because the profile says so, not because the router knows it is boost.
    profile = _profile(dpad={"right": {"action": "smoke_up", "target": "focused", "repeat": True}})
    router, left, _right, _focused, _global_calls = _router(profile)

    router.handle(DeckAction(DPAD_RIGHT, "focused", 1.0, "pressed"))
    router.tick(0.0)
    router.tick(0.2)

    assert left.command_calls == ["SMOKE_ON", "SMOKE_ON"]

    router.handle(DeckAction(DPAD_RIGHT, "focused", 0.0, "released"))
    router.tick(0.4)

    assert left.command_calls == ["SMOKE_ON", "SMOKE_ON"]


def test_an_unrepeated_direction_release_does_not_cancel_a_repeat_running_on_the_other_axis() -> None:
    router, left, _right, _focused, _global_calls = _router()

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))
    router.handle(DeckAction(DPAD_RIGHT, "focused", 1.0, "pressed"))
    router.handle(DeckAction(DPAD_RIGHT, "focused", 0.0, "released"))
    router.tick(0.0)
    router.tick(0.2)

    assert left.command_calls == ["BOOST_SPEED", "SMOKE_ON", "BOOST_SPEED"]


def test_a_dpad_target_in_the_profile_is_the_target_the_provider_reports() -> None:
    profile = _profile(dpad={"up": {"action": "boost", "target": "right"}})
    provider = SteamDeckInputProvider(profile, pygame_module=SimpleNamespace())

    actions = provider._hat_actions((0, 1))

    assert [(a.name, a.target) for a in actions] == [(DPAD_UP, "right")]


# --------------------------------------------------------------------------------------- #
# The context tables as a profile section.
# --------------------------------------------------------------------------------------- #


def test_a_profile_context_override_changes_what_a_control_does_on_a_panel() -> None:
    profile = _profile(
        contexts={"switch": {"bindings": {"horn": {"verb": "switch_thru"}}}},
    )
    router, left, _right, _focused, _global_calls = _router(profile)
    left.switch_active = True
    left.switch_calls = []
    left.on_switch_command = lambda thru: left.switch_calls.append(thru)

    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))

    # Out by default; the profile says through.
    assert left.switch_calls == [True]


def test_a_profile_may_unbind_a_context_entry() -> None:
    # "Unbind this" has to be expressible, which is why null is a value rather than an
    # omission. The switch context claims only what it binds, so an unbound horn falls
    # through to the ordinary engine handling -- exactly as it would on an engine panel.
    profile = _profile(contexts={"switch": {"bindings": {"horn": None}}})
    router, left, _right, _focused, _global_calls = _router(profile)
    left.switch_active = True
    left.switch_calls = []
    left.on_switch_command = lambda thru: left.switch_calls.append(thru)

    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))

    assert left.switch_calls == []
    assert left.command_calls == ["BLOW_HORN_ONE"]


def test_an_unbound_entry_is_still_swallowed_where_the_context_claims_what_it_has_not_bound() -> None:
    profile = _profile(
        contexts={"switch": {"claims_unbound": True, "bindings": {"horn": None}}},
    )
    router, left, _right, _focused, _global_calls = _router(profile)
    left.switch_active = True
    left.switch_calls = []
    left.on_switch_command = lambda thru: left.switch_calls.append(thru)

    router.handle(DeckAction("horn", "focused", 1.0, "pressed", button=3))

    assert left.switch_calls == []
    assert left.command_calls == []


def test_a_malformed_contexts_section_is_logged_and_the_defaults_stand() -> None:
    profile = _profile(contexts={"switch": {"bindings": {"horn": {"verb": "teleport"}}}})

    assert profile.contexts["switch"].bindings["horn"].verb == "switch_out"


# --------------------------------------------------------------------------------------- #
# The generic accessory panel.
# --------------------------------------------------------------------------------------- #


def _acc_gui(kind: str = PANEL_GENERIC):
    """A pane showing an accessory panel, recording what is asked of the accessory.

    Keeps a ``throttle_state`` for the reason ``_switch_gui`` and ``_route_gui`` do: a pane
    that was driving an engine before an accessory was picked in it still has one, so a stick
    or a shoulder button pushed here would reach that engine if the accessory context did not
    claim the action first.

    The chain comes from ``PANEL_CONTEXT_CHAINS`` rather than being written out, so the stub
    reports exactly what ``EngineGui.input_contexts`` reports for the same panel: the point of
    naming the panel in one place is that a test cannot disagree with the screen either.
    """
    gui = _gui(speed=20)
    gui.input_contexts = PANEL_CONTEXT_CHAINS.get(kind, ())
    gui.acc_calls: list[tuple[str, int | None]] = []
    gui.acc_speed_calls: list[int] = []
    gui.on_acc_command = lambda command, data=None: gui.acc_calls.append((command, data))
    gui.on_acc_speed_command = lambda value: gui.acc_speed_calls.append(value)
    gui.lcs_calls: list[bool] = []
    gui.momentary_calls: list[bool] = []
    gui.on_lcs_command = lambda on: gui.lcs_calls.append(on)
    gui.on_asc2_momentary = lambda pressed: gui.momentary_calls.append(pressed)
    return gui


def _coupler_profile() -> ControlProfile:
    """L1 and R1 as the bundled profile binds them: the rear coupler on L1, the front on R1."""
    return _profile(
        buttons={
            "4": {"action": "rear_coupler", "target": "focused"},
            "5": {"action": "front_coupler", "target": "focused"},
        }
    )


def test_the_stick_drives_the_accessorys_speed_rather_than_an_engines() -> None:
    # The vertical stick works the panel's speed slider: a relative step, re-sent while the
    # stick is held over, exactly as the on-screen slider repeats while it is held off zero.
    focused = _acc_gui()
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("throttle", "focused", 1.0, "changed"))
    router.tick(0.0)
    router.tick(0.2)

    assert focused.acc_speed_calls == [5, 5], "one step on the push, and tick re-sent it"
    assert focused.speed_calls == [], "no engine speed reached the panel"

    router.handle(DeckAction("throttle", "focused", 0.0, "changed"))
    router.tick(0.4)

    assert focused.acc_speed_calls == [5, 5], "back at center, the sending stops"


def test_a_light_push_of_the_stick_is_still_a_step() -> None:
    # The shaping the Cab-1 throttle uses: a stick past its dead zone asks for movement, so a
    # light push must not round down to a request for none.
    focused = _acc_gui()
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("throttle", "focused", -0.2, "changed"))

    assert focused.acc_speed_calls == [-1]


@pytest.mark.parametrize("value", [0.9, -0.9])
def test_the_horizontal_stick_toggles_the_accessorys_direction_either_way(value) -> None:
    # TOGGLE_DIRECTION has no left-hand or right-hand form, so the sign is ignored: a push
    # either way is one toggle, which is what the on-screen toggle key does.
    focused = _acc_gui()
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("direction", "focused", value, "changed"))

    assert focused.acc_calls == [("TOGGLE_DIRECTION", None)]
    assert focused.command_calls == [], "no engine direction reached the panel"


def test_a_held_stick_toggles_the_accessory_once_and_re_arms_only_near_center() -> None:
    # A thumb resting on the stick would otherwise flip a crane back and forth for as long as
    # it rested there. The latch is the one the direction handling already uses: one fire per
    # deflection, re-armed only inside direction_threshold - hysteresis.
    focused = _acc_gui()
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("direction", "focused", 0.9, "changed"))
    router.handle(DeckAction("direction", "focused", 1.0, "changed"))
    router.tick(0.0)
    router.tick(0.2)

    assert focused.acc_calls == [("TOGGLE_DIRECTION", None)], "one toggle while it is held"

    router.handle(DeckAction("direction", "focused", 0.72, "changed"))
    router.handle(DeckAction("direction", "focused", 0.9, "changed"))

    assert focused.acc_calls == [("TOGGLE_DIRECTION", None)], "0.72 is not yet near center"

    router.handle(DeckAction("direction", "focused", 0.1, "changed"))
    router.handle(DeckAction("direction", "focused", -0.9, "changed"))

    assert focused.acc_calls == [("TOGGLE_DIRECTION", None), ("TOGGLE_DIRECTION", None)]


@pytest.mark.parametrize("kind", [PANEL_BPC2, PANEL_ASC2])
@pytest.mark.parametrize(
    ("value", "expected"),
    [(-0.9, [False]), (0.9, [True])],
)
def test_the_power_district_stick_selects_off_or_on_by_sign(kind, value, expected) -> None:
    focused = _acc_gui(kind)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("direction", "focused", value, "changed"))

    assert focused.lcs_calls == expected
    assert focused.command_calls == []


@pytest.mark.parametrize("kind", [PANEL_BPC2, PANEL_ASC2])
def test_the_power_district_stick_latches_by_physical_axis_and_rearms_after_center(kind) -> None:
    focused = _acc_gui(kind)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("direction", "focused", 0.9, "changed"))
    router.handle(DeckAction("direction", "focused", 1.0, "changed"))
    router.handle(DeckAction("direction", "focused", -0.9, "changed"))
    assert focused.lcs_calls == [True], "crossing directly to the other side does not re-fire"

    router.handle(DeckAction("direction", "focused", 0.1, "changed"))
    router.handle(DeckAction("direction", "focused", -0.9, "changed"))

    assert focused.lcs_calls == [True, False]


@pytest.mark.parametrize(
    ("name", "button", "command"),
    [
        ("rear_coupler", 4, "REAR_COUPLER"),
        ("front_coupler", 5, "FRONT_COUPLER"),
    ],
)
def test_the_shoulder_buttons_open_the_accessorys_couplers(name, button, command) -> None:
    focused = _acc_gui()
    router, _left, _right, _focused, _global = _router(_coupler_profile(), left=focused)

    router.handle(DeckAction(name, "focused", 1.0, "pressed", button=button))
    router.handle(DeckAction(name, "focused", 0.0, "released", button=button))

    assert focused.acc_calls == [(command, None)], "one on the press, and the release adds none"
    assert focused.command_calls == [], "no engine coupler reached the panel"


@pytest.mark.parametrize(
    ("name", "command"),
    [
        (DPAD_UP, "BOOST"),
        (DPAD_DOWN, "BRAKE"),
    ],
)
def test_the_dpad_boosts_and_brakes_the_accessory_and_repeats_while_held(name, command) -> None:
    # The context entry wins over the profile's own D-pad binding because _handle_contexts runs
    # ahead of the D-pad branches, and it repeats through its own loop: the profile's boost goes
    # to an engine this pane does not have.
    focused = _acc_gui()
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction(name, "focused", 1.0, "pressed"))
    router.tick(0.0)
    router.tick(0.2)

    assert focused.acc_calls == [(command, None), (command, None)]
    assert focused.command_calls == [], "no engine boost or brake reached the panel"

    router.handle(DeckAction(name, "focused", 0.0, "released"))
    router.tick(0.4)

    assert focused.acc_calls == [(command, None), (command, None)], "the release stopped it"


def test_a_dpad_repeat_started_on_an_accessory_panel_stops_when_the_pane_changes_scope() -> None:
    # The press is claimed by the accessory context and the release arrives after the pane has
    # been re-scoped, so the release is the only word that the key is no longer held.
    focused = _acc_gui()
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))
    focused.input_contexts = ()
    router.handle(DeckAction(DPAD_UP, "focused", 0.0, "released"))
    router.tick(0.0)
    router.tick(0.2)

    assert focused.acc_calls == [("BOOST", None)], "nothing was left repeating at the accessory"


def test_an_engine_only_control_is_claimed_and_dropped_on_the_accessory_panel() -> None:
    # The acc base claims what it has not bound, so a control the panel has no key for cannot
    # reach whatever engine the pane held before the accessory was picked.
    focused = _acc_gui()
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("bell", "focused", 1.0, "pressed", button=0))

    assert focused.command_calls == []
    assert focused.acc_calls == []


def test_an_lcs_port_showing_the_generic_panel_takes_the_whole_set() -> None:
    # Amendment A-1: the bindings follow the panel, not the device. An STM2 is an LCS component
    # and matches none of Sensor Track, AMC2, BPC2 or ASC2, so it shows the generic panel and is
    # bound here like any other accessory -- rather than showing a full set of keys on screen
    # and answering to nothing on the pad.
    focused = _acc_gui()
    focused.is_lcs_component = True
    router, _left, _right, _focused, _global = _router(_coupler_profile(), left=focused)

    router.handle(DeckAction("rear_coupler", "focused", 1.0, "pressed", button=4))
    router.handle(DeckAction("direction", "focused", 0.9, "changed"))
    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))
    router.handle(DeckAction("throttle", "focused", 1.0, "changed"))

    assert focused.acc_calls == [
        ("REAR_COUPLER", None),
        ("TOGGLE_DIRECTION", None),
        ("BOOST", None),
    ]
    assert focused.acc_speed_calls == [5]


def test_the_generic_panel_leaves_set_address_alone() -> None:
    # SET_ADDRESS and AUX1_OPT_ONE are keys on this panel and are deliberately unbound: nothing
    # a thumb can brush should re-address an accessory.
    spec = DEFAULT_CONTEXTS[ACC_GENERIC_CONTEXT]
    commands = {dispatch.command for dispatch in spec.bindings.values() if dispatch is not None and dispatch.command}

    assert "SET_ADDRESS" not in commands
    assert "AUX1_OPT_ONE" not in commands


def test_an_engine_panel_is_untouched_by_the_accessory_context() -> None:
    focused = _acc_gui(kind="sensor_track")
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("throttle", "focused", 1.0, "changed"))
    router.tick(0.0)
    router.tick(0.2)

    assert focused.acc_speed_calls == [], "no accessory context is reported for Sensor Track"
    assert focused.speed_calls, "the stick still ramps the engine the pane holds"


# --------------------------------------------------------------------------------------- #
# Power districts and ASC2 outputs.
# --------------------------------------------------------------------------------------- #


@pytest.mark.parametrize("kind", [PANEL_BPC2, PANEL_ASC2])
@pytest.mark.parametrize(
    ("name", "on"),
    [
        ("startup", True),
        (STARTUP_IMMEDIATE, True),
        (STARTUP_DELAYED, True),
        (DPAD_RIGHT, True),
        ("shutdown", False),
        (SHUTDOWN_IMMEDIATE, False),
        (SHUTDOWN_DELAYED, False),
        (DPAD_LEFT, False),
    ],
)
def test_the_triggers_and_the_dpad_switch_a_power_district(kind, name, on) -> None:
    # Both ways of reaching the panel's On and Off keys, and the ASC2 panel gets them by
    # inheriting acc_bpc2 rather than by restating them.
    focused = _acc_gui(kind=kind)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction(name, "focused", 1.0, "pressed", button=6))
    router.handle(DeckAction(name, "focused", 0.0, "released", button=6))

    assert focused.lcs_calls == [on], "one on the press, and the release adds none"
    assert focused.command_calls == [], "no engine startup or shutdown reached the panel"


def test_the_asc2_panel_inherits_the_power_district_pair_rather_than_restating_it() -> None:
    assert ACC_ASC2_CONTEXT in PANEL_CONTEXT_CHAINS[PANEL_ASC2]
    assert DEFAULT_CONTEXTS[ACC_ASC2_CONTEXT].inherits == ACC_BPC2_CONTEXT
    assert "startup" not in DEFAULT_CONTEXTS[ACC_ASC2_CONTEXT].bindings


@pytest.mark.parametrize(("name", "button"), [(SEQUENCE_CONTROL, 3), (DPAD_UP, None)])
def test_a_held_button_energises_the_asc2_output_and_the_release_drops_it(name, button) -> None:
    # The only binding in the table that needs both phases: the on-screen key holds the output
    # on while it is held, and a button that did only the press would leave it on.
    focused = _acc_gui(kind=PANEL_ASC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction(name, "focused", 1.0, "pressed", button=button))
    router.tick(0.0)
    router.tick(0.2)

    assert focused.momentary_calls == [True], "held, not repeated"

    router.handle(DeckAction(name, "focused", 0.0, "released", button=button))

    assert focused.momentary_calls == [True, False]


def test_an_asc2_output_is_not_left_on_when_the_pane_changes_scope_under_the_thumb() -> None:
    # The press is claimed by the ASC2 context and the pane is re-scoped before the release
    # arrives. Resolving the chain again would find nothing, and the output would stay on.
    focused = _acc_gui(kind=PANEL_ASC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=3))
    focused.input_contexts = ()
    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 0.0, "released", button=3))

    assert focused.momentary_calls == [True, False]
    assert focused.command_calls == [], "and the release did not reach the engine either"


@pytest.mark.parametrize("value", [0.9, -0.9])
def test_the_vertical_stick_energises_the_asc2_output_while_it_is_held(value) -> None:
    # A momentary output has to stay on for as long as the stick is away from center, and the
    # sign is not consulted: there is one output, so up and down both energise it.
    focused = _acc_gui(kind=PANEL_ASC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("throttle", "focused", value, "changed"))
    router.handle(DeckAction("throttle", "focused", value, "changed"))
    router.tick(0.0)
    router.tick(0.2)

    assert focused.momentary_calls == [True], "once on the push, not once per poll"

    router.handle(DeckAction("throttle", "focused", 0.0, "changed"))

    assert focused.momentary_calls == [True, False], "recentered, and the output drops"
    assert focused.speed_calls == [], "no engine speed reached the panel"
    assert focused.acc_speed_calls == [], "and no accessory speed either"


def test_the_asc2_stick_uses_the_same_hysteresis_band_as_the_latch() -> None:
    # A stick too light to throw a switch is too light to energise an output, and a value
    # wandering either side of the threshold must not chatter it.
    focused = _acc_gui(kind=PANEL_ASC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("throttle", "focused", 0.7, "changed"))

    assert focused.momentary_calls == [], "0.7 is under direction_threshold"

    router.handle(DeckAction("throttle", "focused", 0.8, "changed"))
    router.handle(DeckAction("throttle", "focused", 0.72, "changed"))
    router.handle(DeckAction("throttle", "focused", 0.8, "changed"))

    assert focused.momentary_calls == [True], "0.72 is inside the band, so it stays on"

    router.handle(DeckAction("throttle", "focused", 0.7, "changed"))

    assert focused.momentary_calls == [True, False], "back inside the band, and it drops once"


def test_a_stick_resting_under_the_threshold_energises_nothing() -> None:
    # A small resting offset must neither switch the output on nor accumulate a hold for a
    # later recenter to release.
    focused = _acc_gui(kind=PANEL_ASC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("throttle", "focused", 0.1, "changed"))
    router.handle(DeckAction("throttle", "focused", 0.0, "changed"))

    assert focused.momentary_calls == []


def test_the_asc2_output_stays_on_until_the_last_holder_lets_go() -> None:
    # FR-3a: the button and the stick drive the same output. Releasing either while the other
    # is held must not switch it off, and the off belongs to whichever lets go last.
    focused = _acc_gui(kind=PANEL_ASC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=3))
    router.handle(DeckAction("throttle", "left", 0.9, "changed"))
    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 0.0, "released", button=3))

    assert focused.momentary_calls == [True, True], "the stick is still holding it"

    router.handle(DeckAction("throttle", "left", 0.0, "changed"))

    assert focused.momentary_calls == [True, True, False], "and the last holder switched it off"


def test_the_asc2_output_survives_the_stick_letting_go_first() -> None:
    # The other order, which is the one that would kill an output the operator still has a
    # thumb on the button for.
    focused = _acc_gui(kind=PANEL_ASC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("throttle", "left", 0.9, "changed"))
    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=3))
    router.handle(DeckAction("throttle", "left", 0.0, "changed"))

    assert focused.momentary_calls == [True, True], "the button is still holding it"

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 0.0, "released", button=3))

    assert focused.momentary_calls == [True, True, False]


def test_a_held_stick_drops_the_asc2_output_even_after_the_pane_changes_scope() -> None:
    # The release of a stick is a value rather than an event, so it is delivered from the hold
    # record rather than by resolving the chain again: re-scoped under the thumb, the chain
    # would say something else entirely and the output would stay energised.
    focused = _acc_gui(kind=PANEL_ASC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("throttle", "focused", 0.9, "changed"))
    focused.input_contexts = ()
    router.handle(DeckAction("throttle", "focused", 0.0, "changed"))

    assert focused.momentary_calls == [True, False]


def test_a_pad_that_disconnects_with_the_stick_pushed_over_does_not_leave_the_output_on() -> None:
    # The one case where no further input arrives to correct the state: clear() has to switch
    # a held output off rather than merely forget that it held one.
    focused = _acc_gui(kind=PANEL_ASC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("throttle", "focused", 0.9, "changed"))
    router.handle(DeckAction("disconnect", "global", 0.0, "disconnected"))

    assert focused.momentary_calls == [True, False]

    router.handle(DeckAction("throttle", "focused", 0.0, "changed"))

    assert focused.momentary_calls == [True, False], "and it is not switched off twice"


def test_clear_switches_off_an_output_held_by_two_controls_once() -> None:
    focused = _acc_gui(kind=PANEL_ASC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction(SEQUENCE_CONTROL, "focused", 1.0, "pressed", button=3))
    router.handle(DeckAction("throttle", "left", 0.9, "changed"))
    router.clear()

    assert focused.momentary_calls == [True, True, False]


def test_the_vertical_stick_does_nothing_on_a_bare_power_district() -> None:
    # A power district has no momentary output for a held stick to hold, so the action is
    # claimed by the acc base and dropped -- not passed to the engine the pane held before.
    focused = _acc_gui(kind=PANEL_BPC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("throttle", "focused", 0.9, "changed"))
    router.tick(0.0)
    router.tick(0.2)
    router.handle(DeckAction("throttle", "focused", 0.0, "changed"))

    assert focused.momentary_calls == []
    assert focused.lcs_calls == []
    assert focused.speed_calls == []
    assert focused.acc_speed_calls == []


def test_a_diagonal_stick_holds_the_asc2_output_and_switches_the_district_at_once() -> None:
    # Two independent axis actions from one physical stick: neither may consume the other's
    # hold or latch.
    focused = _acc_gui(kind=PANEL_ASC2)
    router, _left, _right, _focused, _global = _router(left=focused)

    router.handle(DeckAction("throttle", "focused", 0.9, "changed"))
    router.handle(DeckAction("direction", "focused", 0.9, "changed"))

    assert focused.momentary_calls == [True]
    assert focused.lcs_calls == [True]

    router.handle(DeckAction("throttle", "focused", 0.95, "changed"))

    assert focused.momentary_calls == [True], "the vertical movement did not re-arm anything"
    assert focused.lcs_calls == [True]

    router.handle(DeckAction("throttle", "focused", 0.0, "changed"))
    router.handle(DeckAction("direction", "focused", 0.0, "changed"))
    router.handle(DeckAction("direction", "focused", -0.9, "changed"))

    assert focused.momentary_calls == [True, False]
    assert focused.lcs_calls == [True, False]


@pytest.mark.parametrize("kind", [PANEL_BPC2, PANEL_ASC2])
@pytest.mark.parametrize("name", ["rear_coupler", "front_coupler", DPAD_DOWN])
def test_the_generic_aux_keys_are_absent_from_a_power_district_or_asc2_panel(kind, name) -> None:
    # Neither context inherits acc_generic: there is no coupler and no Brake key on these
    # panels, so the action is claimed by the acc base and sent nowhere.
    focused = _acc_gui(kind=kind)
    router, _left, _right, _focused, _global = _router(_coupler_profile(), left=focused)

    router.handle(DeckAction(name, "focused", 1.0, "pressed", button=4))
    router.tick(0.0)
    router.tick(0.2)

    assert focused.acc_calls == []
    assert focused.command_calls == []
    assert focused.speed_calls == []


@pytest.mark.parametrize("context", [ACC_BPC2_CONTEXT, ACC_ASC2_CONTEXT])
def test_neither_power_district_context_inherits_the_generic_one(context) -> None:
    assert ACC_GENERIC_CONTEXT not in PANEL_CONTEXT_CHAINS[PANEL_BPC2]
    assert ACC_GENERIC_CONTEXT not in PANEL_CONTEXT_CHAINS[PANEL_ASC2]
    assert DEFAULT_CONTEXTS[context].inherits != ACC_GENERIC_CONTEXT
