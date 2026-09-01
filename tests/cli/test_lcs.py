#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""The ``pylcs`` command line and the stand-alone LCS host.

Headless throughout: no window is ever opened. The argument surface is exercised through the
parser alone, ``main`` against a stand-in ``LcsCli``, and ``LcsGui`` with guizero's ``App``
and the PyTrain singletons patched out, exactly as ``tests/gui/test_guizero_base.py`` does.
"""

from __future__ import annotations

import threading
from threading import Event, Thread
from types import SimpleNamespace
from typing import Callable

import pytest

import src.pytrain.cli.lcs as mod
import src.pytrain.gui.controller.lcs_gui as gui_mod
import src.pytrain.gui.guizero_base as base_mod
from src.pytrain.cli.lcs import LcsCli, LcsGuiCmd, main
from src.pytrain.gui.controller.lcs_config_panel import LcsConfigPanel
from src.pytrain.gui.controller.lcs_gui import DEFAULT_HEIGHT, DEFAULT_WIDTH, LcsGui
from src.pytrain.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope


#
# Argument parsing
#
def test_parser_defaults_to_a_client_with_no_window_overrides() -> None:
    args = LcsCli.command_parser().parse_args([])

    assert args.width is None
    assert args.height is None
    assert args.scale_by == 1.0
    assert args.full_screen is False
    assert args.client is False
    assert args.server is None
    assert args.base is None
    assert args.port == DEFAULT_PORT
    assert args.baudrate == DEFAULT_BAUDRATE


@pytest.mark.parametrize(
    "cmd_line, attribute, expected",
    [
        (["-client"], "client", True),
        (["-server", "10.0.0.5"], "server", "10.0.0.5"),
        (["-base", "10.0.0.9"], "base", "10.0.0.9"),
        (["-width", "600"], "width", 600),
        (["-height", "900"], "height", 900),
        (["-scale_by", "1.5"], "scale_by", 1.5),
        (["-full_screen"], "full_screen", True),
    ],
)
def test_parser_accepts_each_connection_and_window_option(cmd_line, attribute, expected) -> None:
    args = LcsCli.command_parser().parse_args(cmd_line)

    assert getattr(args, attribute) == expected


#
# main
#
def test_main_returns_zero_and_passes_its_arguments_through(monkeypatch) -> None:
    seen: dict = {}

    class FakeCli:
        def __init__(self, cmd_line=None) -> None:
            seen["cmd_line"] = cmd_line

    monkeypatch.setattr(mod, "LcsCli", FakeCli, raising=True)

    assert main(["-client"]) == 0
    assert seen["cmd_line"] == ["-client"]


def test_main_reads_sys_argv_when_given_nothing(monkeypatch) -> None:
    seen: dict = {}

    class FakeCli:
        def __init__(self, cmd_line=None) -> None:
            seen["cmd_line"] = cmd_line

    monkeypatch.setattr(mod, "LcsCli", FakeCli, raising=True)
    monkeypatch.setattr(mod.sys, "argv", ["pylcs", "-base", "10.0.0.9"], raising=False)

    assert main() == 0
    assert seen["cmd_line"] == ["-base", "10.0.0.9"]


def test_main_exits_rather_than_raising_when_the_cli_fails(monkeypatch) -> None:
    class FakeCli:
        def __init__(self, cmd_line=None) -> None:
            raise RuntimeError("no base")

    monkeypatch.setattr(mod, "LcsCli", FakeCli, raising=True)

    with pytest.raises(SystemExit):
        main(["-client"])


#
# The command: window construction, no requests
#
class FakeGui:
    """Stands in for LcsGui: records how it was constructed and returns from its loop at once."""

    instances: list["FakeGui"] = []

    def __init__(self, width=None, height=None, scale_by=None, full_screen=None) -> None:
        self.width = width
        self.height = height
        self.scale_by = scale_by
        self.full_screen = full_screen
        self.destroy_complete = Event()
        self.destroy_complete.set()
        self.run_window_calls = 0
        FakeGui.instances.append(self)

    def run_window(self) -> None:
        self.run_window_calls += 1


def _command_for(cli) -> LcsGuiCmd:
    """An LcsGuiCmd without the PyTrain bring-up its constructor performs."""
    cmd = object.__new__(LcsGuiCmd)
    cmd._cli = cli
    cmd._scope = CommandScope.SYSTEM
    cmd._gui = None
    cmd._pytrain = None
    # is_synchronized() is False with no PyTrain, so wait_for_sync waits on this event.
    cmd._sc = Event()
    cmd._sc.set()
    return cmd


def test_send_opens_the_window_with_the_requested_geometry_and_runs_its_loop(monkeypatch) -> None:
    FakeGui.instances.clear()
    monkeypatch.setattr(gui_mod, "LcsGui", FakeGui, raising=True)
    cli = SimpleNamespace(gui_width=600, gui_height=900, scale_by=1.5, is_full_screen=True)

    cmd = _command_for(cli)
    cmd.send()

    assert len(FakeGui.instances) == 1
    gui = FakeGui.instances[0]
    assert (gui.width, gui.height, gui.scale_by, gui.full_screen) == (600, 900, 1.5, True)
    assert gui.run_window_calls == 1
    assert cmd.gui is gui


def test_send_does_not_wait_for_sync_and_shuts_pytrain_down_afterwards(monkeypatch) -> None:
    FakeGui.instances.clear()
    monkeypatch.setattr(gui_mod, "LcsGui", FakeGui, raising=True)
    calls: list[str] = []

    cmd = _command_for(SimpleNamespace(gui_width=None, gui_height=None, scale_by=1.0, is_full_screen=False))
    cmd._pytrain = SimpleNamespace(shutdown=lambda: calls.append("shutdown"))
    monkeypatch.setattr(LcsGuiCmd, "wait_for_sync", lambda self, *a, **k: calls.append("wait_for_sync"), raising=False)

    cmd.send()

    assert calls == ["shutdown"]
    assert FakeGui.instances[0].run_window_calls == 1


def test_send_builds_no_requests() -> None:
    cmd = _command_for(SimpleNamespace())

    assert cmd._build_command() is None
    assert cmd._command_prefix() is None
    assert cmd._encode_address(0) is None


#
# The stand-alone host
#
class _DummyTk:
    @staticmethod
    def geometry(_geometry: str) -> None:
        return

    @staticmethod
    def update_idletasks() -> None:
        return

    @staticmethod
    def after(_delay_ms: int, _func: Callable[[], None]) -> None:
        return

    @staticmethod
    def after_idle(_func: Callable[[], None]) -> None:
        return


class DummyApp:
    def __init__(self, title: str, width: int, height: int) -> None:
        self.title = title
        self.width = width
        self.height = height
        self.full_screen = False
        self.bg = "white"
        self.when_closed = None
        self.tk = _DummyTk()

    def repeat(self, _delay_ms: int, _func: Callable[[], None]) -> None:
        return

    @staticmethod
    def display() -> None:
        return

    @staticmethod
    def destroy() -> None:
        return


@pytest.fixture()
def _patch_runtime(monkeypatch):
    monkeypatch.setattr(base_mod, "App", DummyApp, raising=True)
    monkeypatch.setattr(
        base_mod.CommandDispatcher,
        "get",
        staticmethod(lambda: SimpleNamespace(version="PyTrain Test")),
        raising=True,
    )
    monkeypatch.setattr(base_mod.ComponentStateStore, "get", staticmethod(lambda: object()), raising=True)
    monkeypatch.setattr(base_mod.GpioHandler, "cache_handler", staticmethod(lambda *_: None), raising=True)
    yield


def _host(**kwargs) -> LcsGui:
    return LcsGui(stand_alone=False, **kwargs)


def test_host_defaults_to_the_portrait_overlay_geometry(_patch_runtime) -> None:
    gui = _host()
    try:
        assert (gui.width, gui.height) == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
        assert gui.compact is False
        assert gui.emergency_box_width == DEFAULT_WIDTH
        assert gui.popup_position == (0, 0)
    finally:
        gui.close()


def test_host_supplies_the_surface_the_panel_and_popup_manager_read(_patch_runtime) -> None:
    gui = _host()
    try:
        # What LcsConfigPanel itself reads
        for name in ("s_10", "s_12", "s_14", "s_16", "s_18", "s_20", "button_size", "width"):
            assert isinstance(getattr(gui, name), int)
        for name in ("cache", "submit_request", "queue_message", "locked", "show_popup", "calc_image_box_size"):
            assert callable(getattr(gui, name))
        assert gui.state_store is not None
        # What PopupManager reads off its host
        assert gui.popup_manager is gui._popup
        assert gui.root is gui.app
        for name in ("controller_box", "keypad_box", "amc2_ops_box", "sensor_track_box", "image_box", "acc_overlay"):
            assert getattr(gui, name) is None
        assert gui.calc_image_box_size() == (int(DEFAULT_HEIGHT / 2), DEFAULT_WIDTH)
    finally:
        gui.close()


def test_panel_is_constructible_against_the_stand_alone_host(_patch_runtime) -> None:
    gui = _host()
    try:
        panel = LcsConfigPanel(gui)

        assert panel.gui is gui
        assert panel.compact is False
        assert panel.base_id == 1
        assert panel.device is None
        # The panel's own store lookup resolves to the host's state store.
        assert panel._store is gui.state_store
    finally:
        gui.close()


def test_start_spawns_no_thread_and_queues_the_sync_callback(_patch_runtime) -> None:
    gui = _host()
    try:
        before = threading.active_count()

        gui.start()

        assert gui.is_alive() is False
        assert threading.active_count() == before
        # Exactly one callable was queued rather than invoked inline.
        assert gui._message_queue.qsize() == 1
        message, args = gui._message_queue.get_nowait()
        assert message == gui._on_synchronized
        assert args == ()
    finally:
        gui.close()


def test_run_window_runs_the_inherited_loop_on_the_calling_thread(_patch_runtime, monkeypatch) -> None:
    gui = _host()
    try:
        seen: list[object] = []
        monkeypatch.setattr(LcsGui, "run", lambda self: seen.append(threading.current_thread()), raising=True)

        gui.run_window()

        assert seen == [threading.main_thread()]
    finally:
        gui.close()


def test_run_window_refuses_a_worker_thread(_patch_runtime) -> None:
    gui = _host()
    try:
        errors: list[BaseException] = []

        def _call() -> None:
            try:
                gui.run_window()
            except BaseException as e:  # noqa: BLE001
                errors.append(e)

        worker = Thread(target=_call, daemon=True)
        worker.start()
        worker.join(timeout=5)

        assert len(errors) == 1
        assert isinstance(errors[0], RuntimeError)
    finally:
        gui.close()


def test_draining_the_queued_message_applies_the_title_and_notifies_the_panel(_patch_runtime) -> None:
    gui = _host()
    try:
        gui._app = DummyApp("stale", DEFAULT_WIDTH, DEFAULT_HEIGHT)
        gui.title = "Base 3 - LAYOUT"
        calls: list[str] = []
        gui._panel = SimpleNamespace(on_synchronized=lambda: calls.append("on_synchronized"))

        gui.start()
        message, args = gui._message_queue.get_nowait()
        message(*args)

        assert gui.app.title == "Base 3 - LAYOUT"
        assert calls == ["on_synchronized"]
    finally:
        gui.close()


def test_on_synchronized_is_safe_with_no_app_and_no_panel(_patch_runtime) -> None:
    gui = _host()
    try:
        gui._app = None
        gui._panel = None

        gui._on_synchronized()
    finally:
        gui.close()


@pytest.mark.parametrize("synchronized, expected", [(False, True), (True, False)])
def test_build_gui_seeds_sync_pending_from_the_hosts_synchronized_state(
    _patch_runtime, monkeypatch, synchronized, expected
) -> None:
    gui = _host()
    try:
        monkeypatch.setattr(LcsGui, "is_synchronized", property(lambda self: synchronized), raising=True)
        monkeypatch.setattr(LcsGui, "show_popup", lambda self, *a, **k: None, raising=True)
        seen: list[bool] = []

        class FakePanel:
            overlay = object()

            @staticmethod
            def configure(*_args, **_kwargs) -> None:
                return

            @staticmethod
            def set_sync_pending(pending: bool) -> None:
                seen.append(pending)

        monkeypatch.setattr(gui_mod, "LcsConfigPanel", lambda _gui: FakePanel(), raising=True)

        gui.build_gui()

        assert seen == [expected]
    finally:
        gui.close()


def test_host_destroy_gui_releases_the_panel(_patch_runtime) -> None:
    gui = _host()
    try:
        gui._panel = object()
        gui._overlay = object()

        gui.destroy_gui()

        assert gui.panel is None
        assert gui._overlay is None
    finally:
        gui.close()
