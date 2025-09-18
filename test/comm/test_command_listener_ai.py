#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL

import time
from typing import Any, List

import pytest

from src.pytrain.comm.command_listener import CommandListener
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.multibyte.multibyte_constants import TMCC2EffectsControl as Effects
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1HaltCommandEnum as Halt1,
)
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1SyncCommandEnum,
)
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as Engine2, TMCC2_MEDIUM_SPEED


class DummyDispatcher:
    def __init__(self):
        self.offered: List[tuple[Any, bool]] = []

    def offer(self, req, from_pdi: bool = False):
        self.offered.append((req, from_pdi))

    # Stubs to satisfy CommandListener API calls
    def shutdown(self): ...
    def subscribe(self, *args, **kwargs): ...
    def unsubscribe(self, *args, **kwargs): ...
    def subscribe_any(self, *args, **kwargs): ...
    def unsubscribe_any(self, *args, **kwargs): ...


def wait_for(predicate, timeout=1.0):
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(0.01)
    return False


# noinspection PyProtectedMember
@pytest.fixture(autouse=True)
def reset_listener_singleton(monkeypatch):
    # Do not stub run here; we want the real decoding loop
    # Avoid any startup sync activity
    monkeypatch.setattr(CommandListener, "sync_state", lambda self: None)
    CommandListener._instance = None
    yield
    try:
        if CommandListener._instance is not None:
            CommandListener._instance.shutdown()
    finally:
        CommandListener._instance = None


def build_listener_with_dummy_dispatcher(monkeypatch) -> tuple[CommandListener, DummyDispatcher]:
    dd = DummyDispatcher()
    monkeypatch.setattr(
        "src.pytrain.comm.command_listener.CommandDispatcher.build",
        lambda *a, **k: dd,
    )
    # Important: prevent SerialReader creation by disabling ser2_receiver
    listener = CommandListener(ser2_receiver=False, base3_receiver=False)
    return listener, dd


def test_decode_tmcc1_three_byte_command(monkeypatch):
    listener, dd = build_listener_with_dummy_dispatcher(monkeypatch)

    halt_req = CommandReq.build(Halt1.HALT)
    listener.offer(halt_req.as_bytes)

    assert wait_for(lambda: len(dd.offered) >= 1)
    offered_cmd = dd.offered[0][0]
    assert isinstance(offered_cmd, CommandReq)
    assert offered_cmd.command == Halt1.HALT
    assert offered_cmd.is_halt is True


def test_decode_tmcc2_three_byte_engine_command(monkeypatch):
    listener, dd = build_listener_with_dummy_dispatcher(monkeypatch)

    ring = CommandReq.build(Engine2.RING_BELL, 7)
    listener.offer(ring.as_bytes)

    assert wait_for(lambda: len(dd.offered) >= 1)
    offered_cmd = dd.offered[0][0]
    assert isinstance(offered_cmd, CommandReq)
    assert offered_cmd.command == Engine2.RING_BELL
    assert offered_cmd.address == 7


def test_decode_tmcc2_four_digit_address_command_sets_tmcc4(monkeypatch):
    listener, dd = build_listener_with_dummy_dispatcher(monkeypatch)

    # Build a command with a 4-digit engine id; listener should append the 4 ASCII digits
    cmd_4d = CommandReq.build(Engine2.SPEED_MEDIUM, 1234)
    listener.offer(cmd_4d.as_bytes)

    assert wait_for(lambda: len(dd.offered) >= 1)
    offered_cmd = dd.offered[0][0]
    assert isinstance(offered_cmd, CommandReq)
    assert offered_cmd.command == Engine2.ABSOLUTE_SPEED
    assert offered_cmd.data == TMCC2_MEDIUM_SPEED
    assert offered_cmd.address == 1234  # Decoded as TMCC4 (4-digit) address


def test_decode_tmcc2_multibyte_parameter_command(monkeypatch):
    listener, dd = build_listener_with_dummy_dispatcher(monkeypatch)

    # Effects multibyte command (encodes as >= 9 bytes with multibyte markers)
    # Choose a simple, well-defined effect
    mb_req = CommandReq.build(Effects.SMOKE_HIGH, 22)
    listener.offer(mb_req.as_bytes)

    assert wait_for(lambda: len(dd.offered) >= 1)
    offered_cmd = dd.offered[0][0]
    # MultiByteReq is a subclass of CommandReq; we only validate essential fields here
    assert isinstance(offered_cmd, CommandReq)
    assert offered_cmd.command == Effects.SMOKE_HIGH
    assert offered_cmd.address == 22


def test_decode_admin_sync_command_restart_flows_through_deque(monkeypatch):
    listener, dd = build_listener_with_dummy_dispatcher(monkeypatch)

    restart = CommandReq(TMCC1SyncCommandEnum.RESTART)
    # Only SYNC_BEGIN/SYNC_COMPLETE are handled specially by offer(); others must pass through run()
    listener.offer(restart.as_bytes)

    assert wait_for(lambda: len(dd.offered) >= 1)
    offered_cmd = dd.offered[0][0]
    assert isinstance(offered_cmd, CommandReq)
    assert offered_cmd.command == TMCC1SyncCommandEnum.RESTART
