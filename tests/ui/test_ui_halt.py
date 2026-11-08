"""Verify layout-wide ALL STOP independently of the selected cab target."""

from unittest.mock import Mock

import pytest

from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain_ui.adapters.commands import PyTrainCabCommandAdapter
from pytrain_ui.adapters.state import PyTrainCabStateAdapter


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_all_stop_sends_system_halt(scope: CommandScope, monkeypatch: pytest.MonkeyPatch) -> None:
    state_adapter = Mock(spec=PyTrainCabStateAdapter)
    state_adapter.state.scope = scope
    state_adapter.state.tmcc_id = 31
    packets: list[bytes] = []

    def capture_send(request: CommandReq) -> None:
        packets.append(request.as_bytes)

    monkeypatch.setattr(CommandReq, "send", capture_send)
    PyTrainCabCommandAdapter(state_adapter).halt()

    assert packets == [bytes.fromhex("fe ff ff")]
