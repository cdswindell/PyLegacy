#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

import logging
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from src.pytrain.comm.comm_buffer import CommBuffer
from src.pytrain.db.comp_data import CompDataMixin
from src.pytrain.db.component_state import SCOPE_TO_STATE_MAP, UpdateResult
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.irda_state import IrdaState
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import PDI_EOP, PDI_SOP, IrdaAction, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.irda_req import IrdaReq, IrdaSequence
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.protocol.constants import CommandScope, Direction


def received_packet(action, payload=b"", address=12):
    body = PdiCommand.IRDA_RX.as_bytes + bytes([address]) + action.as_bytes + payload
    body, checksum = PdiReq._calculate_checksum(body)
    return bytes([PDI_SOP]) + body + checksum + bytes([PDI_EOP])


def data_request(*, engine_id=42, train_id=0, direction=0, bt_id=0xABCD, number="X", product_id=4):
    payload = bytearray(66)
    payload[4:8] = bytes([direction, engine_id, train_id, 1])
    payload[15] = product_id
    payload[16:18] = bt_id.to_bytes(2, "big")
    payload[18:21] = b"26\x00"
    payload[21:27] = b"Engine"
    road_number = number.encode("ascii") + b"\x00"
    payload[54 : 54 + len(road_number)] = road_number
    return IrdaReq(received_packet(IrdaAction.DATA, bytes(payload)))


@pytest.fixture
def io(monkeypatch):
    collaborators = SimpleNamespace(
        bluetooth=Mock(return_value=None),
        get_state=Mock(return_value=None),
        set_state=Mock(),
        server=Mock(return_value=False),
        ramp=Mock(),
    )
    monkeypatch.setattr(ComponentStateStore, "by_bluetooth_id", collaborators.bluetooth)
    monkeypatch.setattr(ComponentStateStore, "get_state", collaborators.get_state)
    monkeypatch.setattr(ComponentStateStore, "set_state", collaborators.set_state)
    monkeypatch.setattr(CommBuffer, "is_server", collaborators.server)
    monkeypatch.setattr("src.pytrain.protocol.sequence.ramp_speed_req.RampSpeedReq", collaborators.ramp)
    return collaborators


@pytest.fixture
def sensor():
    return IrdaState()


def configure(sensor, sequence, loco_rl=255, loco_lr=255):
    command = IrdaReq(12, PdiCommand.IRDA_RX, IrdaAction.CONFIG, sequence=sequence, loco_rl=loco_rl, loco_lr=loco_lr)
    sensor.update(command)
    return command


class TestIrdaStateBasics:
    def test_defaults_and_registration(self, sensor):
        assert SCOPE_TO_STATE_MAP[CommandScope.IRDA] is IrdaState
        assert sensor.scope is CommandScope.IRDA
        assert sensor.is_lcs is True
        assert sensor.sequence is None
        assert sensor.mode is None
        assert sensor.sequence_str == "NA"
        assert sensor.last_engine_id is None
        assert sensor.last_train_id is None
        assert sensor.product_type is None
        assert sensor.last_direction is Direction.UNKNOWN
        assert sensor.is_left_to_right is False
        assert sensor.is_right_to_left is False
        assert sensor.is_engine is False
        assert sensor.is_train is False
        assert repr(sensor) == "Sensor Track None: Sequence: NA"
        assert sensor.as_dict()["sequence"] == "none"
        assert sensor.as_dict()["last_direction"] == "unknown"

    @pytest.mark.parametrize("scope", [s for s in CommandScope if s != CommandScope.IRDA])
    def test_invalid_scope(self, scope):
        with pytest.raises(ValueError, match="Invalid scope:.*expected IRDA"):
            IrdaState(scope)

    @pytest.mark.parametrize("sequence", list(IrdaSequence))
    def test_configuration_updates_sequence_and_filters(self, sensor, sequence):
        command = configure(sensor, sequence, loco_rl=23, loco_lr=45)
        assert sensor.address == 12
        assert sensor.sequence is sequence
        assert sensor.mode == sequence.value
        assert sensor.sequence_str == sequence.name.title()
        assert sensor.last_command is command
        assert sensor.changed.is_set()
        assert sensor.as_dict()["sequence"] == sequence.name.lower()
        if sequence is IrdaSequence.NONE:
            assert "When Engine ID" not in repr(sensor)
        else:
            assert "When Engine ID (R -> L): 23" in repr(sensor)
            assert "When Engine ID (L -> R): 45" in repr(sensor)

    @pytest.mark.parametrize("loco_id", [0, 255, None])
    def test_repr_any_engine_filters(self, sensor, loco_id):
        configure(sensor, IrdaSequence.BELL_NONE, loco_id, loco_id)
        assert "When Engine ID (R -> L): Any" in repr(sensor)
        assert "When Engine ID (L -> R): Any" in repr(sensor)

    def test_sequence_update_preserves_configuration_filters(self, sensor):
        configure(sensor, IrdaSequence.BELL_NONE, 23, 45)
        command = IrdaReq(received_packet(IrdaAction.SEQUENCE, bytes([IrdaSequence.NONE_BELL.value])))
        sensor.update(command)
        assert sensor.sequence is IrdaSequence.NONE_BELL
        assert sensor._sequence_req is command
        assert "(R -> L): 23" in repr(sensor)
        assert "(L -> R): 45" in repr(sensor)

    @pytest.mark.parametrize("pdi_command", [PdiCommand.IRDA_GET, PdiCommand.IRDA_SET])
    def test_outgoing_commands_do_not_change_sequence(self, sensor, pdi_command):
        configure(sensor, IrdaSequence.NONE)
        previous = sensor.last_command
        sensor.update(IrdaReq(12, pdi_command, IrdaAction.SEQUENCE, sequence=IrdaSequence.BELL_NONE))
        assert sensor.sequence is IrdaSequence.NONE
        assert sensor.last_command is previous
        assert not sensor.changed.is_set()

    def test_unrelated_command_is_ignored(self, sensor):
        assert sensor._update_state(object()) is UpdateResult.IGNORED

    def test_other_received_action_is_accepted_without_sequence_change(self, sensor):
        configure(sensor, IrdaSequence.NONE)
        command = IrdaReq(received_packet(IrdaAction.RECORD, b"\x01"))
        assert sensor._update_state(command) is UpdateResult.UPDATED
        assert sensor.sequence is IrdaSequence.NONE

    @pytest.mark.parametrize("direction, expected", [(0, Direction.R2L), (1, Direction.L2R), (2, Direction.UNKNOWN)])
    def test_data_updates_direction_and_identity(self, sensor, io, direction, expected):
        command = data_request(direction=direction)
        sensor.update(command)
        assert sensor.last_direction is expected
        assert sensor.is_left_to_right is (expected is Direction.L2R)
        assert sensor.is_right_to_left is (expected is Direction.R2L)
        assert sensor.last_engine_id == 42
        assert sensor.last_train_id == 0
        assert sensor.product_type == "Steam"
        assert sensor.is_engine is True
        assert sensor.is_train is False
        assert sensor.last_command is command
        assert sensor.changed.is_set()
        assert sensor.as_dict() == {
            "tmcc_id": 12,
            "road_name": "Engine",
            "road_number": "X",
            "scope": "irda",
            "last_direction": expected.name.lower(),
            "last_engine_id": 42,
            "last_train_id": 0,
            "sequence": "none",
        }
        assert "Last Engine ID: 42" in repr(sensor)
        assert "Last Train ID" not in repr(sensor)
        if direction in (0, 1):
            assert (" R --> L" if direction == 0 else " L --> R") in repr(sensor)
        io.ramp.assert_not_called()

    @pytest.mark.parametrize("engine_id, train_id", [(0, 0), (42, 0), (0, 7), (42, 7)])
    def test_engine_and_train_classification(self, sensor, io, engine_id, train_id):
        io.get_state.return_value = Mock(address=7)
        sensor.update(data_request(engine_id=engine_id, train_id=train_id, bt_id=0))
        assert sensor.is_train is bool(train_id)
        assert sensor.is_engine is bool(engine_id and not train_id)
        assert ("Last Train ID: 7" in repr(sensor)) is bool(train_id)

    def test_train_disappearing_after_packet_parse_is_cleared(self, sensor, io):
        io.get_state.return_value = Mock(address=7)
        command = data_request(train_id=7)
        assert command.train_id == 7
        io.get_state.return_value = None
        sensor.update(command)
        assert sensor.last_train_id == 0
        assert sensor.is_train is False
        assert sensor.is_engine is True
        io.get_state.assert_called_with(CommandScope.TRAIN, 7, False)

    def test_serialization_preserves_lcs_packets_and_only_latest_data(self, sensor, io):
        config = configure(sensor, IrdaSequence.NONE)
        firmware = IrdaReq(received_packet(IrdaAction.FIRMWARE, b"\x01\x02\x03"))
        info = IrdaReq(received_packet(IrdaAction.INFO, b"\x04\x08\x01\x78"))
        sensor.update(firmware)
        sensor.update(info)
        assert sensor.as_bytes() == config.as_bytes + firmware.as_bytes + info.as_bytes
        sensor.update(data_request(engine_id=23))
        latest = data_request(engine_id=45)
        sensor.update(latest)
        assert sensor.as_bytes() == config.as_bytes + firmware.as_bytes + info.as_bytes + latest.as_bytes


class TestIrdaStateIdLookup:
    @pytest.mark.parametrize("engine_id", [0, 1, 42])
    def test_bluetooth_lookup_takes_precedence_over_engine_id_and_road_number(self, io, engine_id):
        command = data_request(engine_id=engine_id, number="9999")
        io.bluetooth.reset_mock()
        io.bluetooth.return_value = Mock(address=3456)
        io.get_state.return_value = Mock(address=9999)
        assert IrdaState.harvest_tmcc_id(command) == 3456
        io.bluetooth.assert_called_once_with(0xABCD)
        io.get_state.assert_not_called()

    @pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
    @pytest.mark.parametrize("number, found, expected", [("3456", True, 72), ("3456", False, 1), ("0034", True, 72)])
    def test_default_id_uses_road_number_fallback(self, io, scope, number, found, expected):
        io.get_state.return_value = Mock(address=1)
        command = data_request(engine_id=1, train_id=1, number=number)
        io.get_state.reset_mock()
        io.get_state.return_value = Mock(address=72) if found else None
        io.bluetooth.reset_mock()
        assert IrdaState.harvest_tmcc_id(command, scope) == expected
        io.get_state.assert_called_once_with(scope, int(number), False)
        if scope is CommandScope.TRAIN:
            io.bluetooth.assert_not_called()
        else:
            io.bluetooth.assert_called_once_with(0xABCD)

    @pytest.mark.parametrize("number", ["", "X", "12A", "-12", "1.2"])
    def test_nonnumeric_road_number_keeps_unresolved_default(self, io, number):
        command = data_request(engine_id=1, number=number)
        assert IrdaState.harvest_tmcc_id(command) == 1
        io.get_state.assert_not_called()

    @pytest.mark.parametrize("engine_id", [0, 42, 99])
    def test_nondefault_id_does_not_use_road_number(self, io, engine_id):
        command = data_request(engine_id=engine_id, number="3456")
        assert IrdaState.harvest_tmcc_id(command) == engine_id
        io.get_state.assert_not_called()

    def test_zero_bluetooth_id_skips_state_lookup(self, io):
        command = data_request(bt_id=0)
        assert IrdaState.harvest_tmcc_id(command) == 42
        io.bluetooth.assert_not_called()

    def test_packet_without_bluetooth_field_preserves_engine_id(self, io):
        command = IrdaReq(received_packet(IrdaAction.DATA, bytes([0, 0, 0, 0, 0, 42])))
        assert command.bt_id is None
        assert IrdaState.harvest_tmcc_id(command) == 42
        io.bluetooth.assert_not_called()

    def test_non_irda_command_uses_ids_without_bluetooth_lookup(self, io):
        command = SimpleNamespace(engine_id=42, train_id=7, number="3456", bt_id=0xABCD)
        assert IrdaState.harvest_tmcc_id(command) == 42
        assert IrdaState.harvest_tmcc_id(command, CommandScope.TRAIN) == 7
        io.bluetooth.assert_not_called()
        io.get_state.assert_not_called()

    def test_non_data_action_does_not_lookup_bluetooth(self, io):
        command = IrdaReq(12, PdiCommand.IRDA_RX, IrdaAction.CONFIG)
        command._engine_id = 42
        command._bluetooth_id = b"\xab\xcd"
        assert IrdaState.harvest_tmcc_id(command) == 42
        io.bluetooth.assert_not_called()

    @pytest.mark.parametrize("addresses", [(1, 3456), (3456, 1)])
    def test_real_bluetooth_index_resolves_default_id_to_four_digit_engine(self, monkeypatch, addresses):
        monkeypatch.setattr(ComponentStateStore, "_instance", None)
        monkeypatch.setattr(CommBuffer, "is_server", lambda: False)
        store = ComponentStateStore(listeners=())
        for address in addresses:
            record = CompDataMixin()
            record.initialize(CommandScope.ENGINE, address)
            record.comp_data._bt_id = 0xABCD
            data = record.comp_data.as_bytes()
            if address > 99:
                request = D4Req(123, PdiCommand.D4_ENGINE, data_length=len(data), data_bytes=data, timestamp=0)
                store(D4Req(request.as_bytes))
            else:
                request = BaseReq(address, PdiCommand.BASE_MEMORY, scope=CommandScope.ENGINE, data_bytes=data)
                store(BaseReq(request.as_bytes))

        command = data_request(engine_id=1, number="9999")
        assert command.engine_id == 3456
        assert IrdaState.harvest_tmcc_id(command) == 3456
        sensor = IrdaState()
        sensor.update(command)
        assert sensor.last_engine_id == 3456
        assert sensor.as_dict()["last_engine_id"] == 3456
        assert "Last Engine ID: 3456" in repr(sensor)
        assert store.by_bluetooth_id(0xABCD) is store.query(CommandScope.ENGINE, 3456)
        assert store.query(CommandScope.ENGINE, 9999) is None


class TestIrdaStateSpeedControl:
    def test_bluetooth_match_arriving_after_parse_resolves_speed_target(self, sensor, io, caplog):
        configure(sensor, IrdaSequence.SLOW_SPEED_NORMAL_SPEED)
        command = data_request(engine_id=1)
        assert command.engine_id == 1
        io.server.return_value = True
        engine = Mock(address=3456)
        io.bluetooth.return_value = engine
        io.get_state.return_value = engine
        observed = []
        engine.update.side_effect = lambda request: observed.append((request.scope, request.tmcc_id))
        with caplog.at_level(logging.DEBUG, logger="src.pytrain.db.component_state"):
            sensor.update(command)
        assert sensor.last_engine_id == 3456
        io.ramp.assert_called_once_with(3456, "slow", scope=CommandScope.ENGINE)
        io.ramp.return_value.send.assert_called_once_with()
        assert observed == [(CommandScope.ENGINE, 3456)]
        assert command.engine_id == 1
        assert command.scope is CommandScope.IRDA
        assert command.tmcc_id == 12
        assert "IRDA 12 Sequence:" in caplog.text

    @pytest.mark.parametrize(
        "sequence, direction, speed",
        [
            (IrdaSequence.SLOW_SPEED_NORMAL_SPEED, 0, "slow"),
            (IrdaSequence.SLOW_SPEED_NORMAL_SPEED, 1, "normal"),
            (IrdaSequence.NORMAL_SPEED_SLOW_SPEED, 0, "normal"),
            (IrdaSequence.NORMAL_SPEED_SLOW_SPEED, 1, "slow"),
        ],
    )
    @pytest.mark.parametrize("train_id", [0, 7])
    def test_speed_and_propagation_target_resolved_ids(self, sensor, io, sequence, direction, speed, train_id):
        configure(sensor, sequence)
        io.server.return_value = True
        engine = Mock(address=3456, tmcc_id=3456)
        io.bluetooth.return_value = engine
        io.get_state.return_value = engine
        observed = []
        engine.update.side_effect = lambda command: observed.append((command, command.scope, command.tmcc_id))
        command = data_request(engine_id=1, train_id=train_id, direction=direction, number="9999")
        sensor.update(command)
        scope = CommandScope.TRAIN if train_id else CommandScope.ENGINE
        io.ramp.assert_called_once_with(train_id or 3456, speed, scope=scope)
        io.ramp.return_value.send.assert_called_once_with()
        assert observed == [(command, CommandScope.ENGINE, 3456)]
        assert sensor.last_engine_id == 3456
        assert sensor.last_train_id == train_id
        assert command.scope is CommandScope.IRDA
        assert command.tmcc_id == 12
        assert call(scope, train_id or 3456, False) in io.get_state.call_args_list

    @pytest.mark.parametrize("sequence", [s for s in IrdaSequence if s.value not in (7, 8)] + [None])
    def test_other_sequences_do_not_send_or_propagate(self, sensor, io, sequence):
        configure(sensor, sequence)
        io.server.return_value = True
        engine = Mock(address=42)
        io.get_state.return_value = engine
        sensor.update(data_request())
        io.ramp.assert_not_called()
        engine.update.assert_not_called()

    @pytest.mark.parametrize("engine_id, train_id, server", [(42, 0, False), (1, 0, True), (42, 1, True)])
    def test_client_or_unresolved_default_ids_suppress_speed_and_propagation(
        self, sensor, io, engine_id, train_id, server
    ):
        configure(sensor, IrdaSequence.SLOW_SPEED_NORMAL_SPEED)
        io.server.return_value = server
        engine = Mock(address=42)
        io.get_state.return_value = engine
        sensor.update(data_request(engine_id=engine_id, train_id=train_id))
        io.ramp.assert_not_called()
        engine.update.assert_not_called()
        assert sensor.last_engine_id == engine_id

    def test_unknown_direction_does_not_send_speed_but_propagates(self, sensor, io):
        configure(sensor, IrdaSequence.SLOW_SPEED_NORMAL_SPEED)
        io.server.return_value = True
        engine = Mock(address=42)
        io.get_state.return_value = engine
        command = data_request(direction=2)
        sensor.update(command)
        io.ramp.assert_not_called()
        engine.update.assert_called_once_with(command)
        assert command.scope is CommandScope.IRDA
        assert command.tmcc_id == 12

    def test_missing_speed_target_does_not_send(self, sensor, io):
        configure(sensor, IrdaSequence.SLOW_SPEED_NORMAL_SPEED)
        io.server.return_value = True
        engine = Mock(address=42)
        io.get_state.side_effect = lambda scope, address, create=True: engine if create else None
        command = data_request()
        sensor.update(command)
        io.ramp.assert_not_called()
        engine.update.assert_called_once_with(command)

    def test_missing_engine_id_does_not_propagate(self, sensor, io):
        configure(sensor, IrdaSequence.SLOW_SPEED_NORMAL_SPEED)
        io.server.return_value = True
        sensor.update(data_request(engine_id=0, bt_id=0))
        io.ramp.assert_not_called()
        io.get_state.assert_called_once_with(CommandScope.ENGINE, None, False)

    def test_propagation_exception_restores_request_identity(self, sensor, io):
        configure(sensor, IrdaSequence.SLOW_SPEED_NORMAL_SPEED)
        io.server.return_value = True
        engine = Mock(address=3456, tmcc_id=3456)
        engine.update.side_effect = RuntimeError("engine update failed")
        io.bluetooth.return_value = engine
        io.get_state.return_value = engine
        command = data_request(engine_id=1)
        with pytest.raises(RuntimeError, match="engine update failed"):
            sensor.update(command)
        engine.update.assert_called_once_with(command)
        assert command.scope is CommandScope.IRDA
        assert command.tmcc_id == 12
