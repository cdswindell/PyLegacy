from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from src.pytrain.gui.controller.steam_deck_input import (
    DPAD_DOWN,
    DPAD_LEFT,
    DPAD_RIGHT,
    DPAD_UP,
    HORN_COMMAND,
    QUILLING_HORN,
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
    # Axes 2 and 5 are the L2/R2 triggers, bound to the quilling horn.
    assert profile.axes[2].action == "quilling_horn"
    assert profile.axes[5].action == "quilling_horn"


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


def test_dpad_is_noop_when_catalog_hidden() -> None:
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

    router.handle(DeckAction(DPAD_UP, "focused", 1.0, "pressed"))
    router.handle(DeckAction(DPAD_DOWN, "focused", 1.0, "pressed"))


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


def test_dpad_left_right_are_noop_when_catalog_hidden() -> None:
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

    router.handle(DeckAction(DPAD_RIGHT, "focused", 1.0, "pressed"))
    router.handle(DeckAction(DPAD_LEFT, "focused", 1.0, "pressed"))


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

    assert [action.name for action in actions] == ["halt", "halt"]


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


def test_bundled_profile_binds_right_bumper_to_startup() -> None:
    profile = ControlProfile.load()

    assert profile.buttons[5].action == "startup"
    assert profile.buttons[5].target == "focused"


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

    assert [action.name for action in actions] == ["halt"]


def _shutdown_profile() -> ControlProfile:
    return _profile(
        buttons={
            "0": {"action": "bell", "target": "focused"},
            "4": {"action": "shutdown", "target": "focused"},
        }
    )


def test_bundled_profile_binds_left_bumper_to_shutdown() -> None:
    profile = ControlProfile.load()

    assert profile.buttons[4].action == "shutdown"
    assert profile.buttons[4].target == "focused"


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

    assert [action.name for action in actions] == ["halt"]


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


def test_bundled_profile_binds_triggers_to_quilling_horn() -> None:
    profile = ControlProfile.load()

    assert profile.axes[2].action == "quilling_horn"
    assert profile.axes[2].target == "left"
    assert profile.axes[2].trigger is True
    assert profile.axes[5].action == "quilling_horn"
    assert profile.axes[5].target == "right"
    assert profile.axes[5].trigger is True


def test_stick_axes_are_not_flagged_as_triggers() -> None:
    profile = ControlProfile.load()

    assert profile.axes[1].trigger is False
    assert profile.axes[3].trigger is False


def test_provider_normalizes_trigger_axis_from_resting_to_full() -> None:
    pygame = SimpleNamespace(JOYAXISMOTION=1, JOYBUTTONDOWN=2, JOYBUTTONUP=3, JOYDEVICEADDED=4, JOYDEVICEREMOVED=5)
    pygame.event = SimpleNamespace(
        get=lambda: [
            SimpleNamespace(type=1, axis=5, value=-1.0),  # resting -> 0.0
            SimpleNamespace(type=1, axis=5, value=-0.8),  # inside dead zone -> 0.0
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

    # value 0.0 maps to fraction 0.5; the dead zone rescales it to 0.35 / 0.85.
    assert [a.value for a in actions] == pytest.approx([0.4117647])


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
