#
# PyTrain: characterization tests for dispatcher Base 3 update forwarding.
# SPDX-License-Identifier: LGPL-3.0-only
#
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.comm.command_listener import CommandDispatcher, REQUIRE_BASE_UPDATE
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.multibyte.multibyte_constants import TMCC2R4LCEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


@pytest.mark.parametrize("command", [TMCC2R4LCEnum.TRAIN_ADDRESS, TMCC2R4LCEnum.TRAIN_UNIT])
def test_train_configuration_dispatch_currently_uses_sending_handler(command):
    # Baseline: the mapping currently selects the side-effecting handler.
    assert REQUIRE_BASE_UPDATE[command][0] == BaseReq.do_update_eng


@pytest.mark.parametrize("command", [TMCC2R4LCEnum.TRAIN_ADDRESS, TMCC2R4LCEnum.TRAIN_UNIT])
def test_train_configuration_updates_are_forwarded_to_clients(monkeypatch, command):
    packet = object()
    refresh_marker = object()
    generated = [packet, refresh_marker]
    sender = Mock(return_value=generated)
    processor = Mock()
    client_callback = Mock()
    dispatcher = SimpleNamespace(update_client_state=client_callback)
    monkeypatch.setitem(REQUIRE_BASE_UPDATE, command, (sender,))
    monkeypatch.setattr(BaseReq, "process_sync_reqs", processor)
    request = CommandReq.build(command, 7, data=1)

    CommandDispatcher.update_base_state(dispatcher, request, update_clients=True)

    sender.assert_called_once_with(request)
    processor.assert_called_once_with(generated, callback=client_callback)


@pytest.mark.parametrize("command", [TMCC2R4LCEnum.TRAIN_ADDRESS, TMCC2R4LCEnum.TRAIN_UNIT])
def test_train_configuration_without_client_forwarding(monkeypatch, command):
    sender = Mock(return_value=[object()])
    processor = Mock()
    dispatcher = SimpleNamespace(update_client_state=Mock())
    monkeypatch.setitem(REQUIRE_BASE_UPDATE, command, (sender,))
    monkeypatch.setattr(BaseReq, "process_sync_reqs", processor)
    request = CommandReq.build(command, 7, data=1)

    CommandDispatcher.update_base_state(dispatcher, request, update_clients=False)

    sender.assert_called_once_with(request)
    processor.assert_not_called()


def test_unmapped_command_does_not_trigger_base_updates(monkeypatch):
    sender = Mock()
    processor = Mock()
    dispatcher = SimpleNamespace(update_client_state=Mock())
    monkeypatch.setattr(BaseReq, "do_update_eng", sender)
    monkeypatch.setattr(BaseReq, "process_sync_reqs", processor)
    request = CommandReq.build(TMCC2EngineCommandEnum.BELL_OFF, 7)

    CommandDispatcher.update_base_state(dispatcher, request, update_clients=True)

    sender.assert_not_called()
    processor.assert_not_called()


def test_clear_consist_handler_mapping_is_preserved():
    assert REQUIRE_BASE_UPDATE[TMCC2EngineCommandEnum.CLEAR_CONSIST][0] == CommandDispatcher.on_clear_consist
