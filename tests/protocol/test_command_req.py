#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#
#

import re
from unittest import mock

# noinspection PyPackageRequirements
import pytest

from src.pytrain.comm.comm_buffer import CommBuffer, CommBufferSingleton
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT
from src.pytrain.protocol.multibyte.dcds_command_req import VariableCommandReq
from src.pytrain.protocol.multibyte.multibyte_constants import *
from src.pytrain.protocol.multibyte.param_command_req import PARAMETER_ENUM_TO_INDEX_MAP, ParameterCommandReq
from src.pytrain.protocol.multibyte.ramp_command_req import RampCommandReq
from src.pytrain.protocol.tmcc1.tmcc1_constants import *
from src.pytrain.protocol.tmcc2.tmcc2_constants import *

from ..test_base import TestBase

RAMP_COMMANDS = (TMCC2EngineCommandEnumEx.RAMP_CLAIM, TMCC2EngineCommandEnumEx.RAMP_RELEASE)
RAMP_PAYLOAD = bytes.fromhex("c0a801071234abcd")


# noinspection PyMethodMayBeStatic
class TestCommandReq(TestBase):
    def teardown_method(self, test_method):
        super().teardown_method(test_method)
        CommBuffer.stop()

    def build_request(
        self, cmd, address: int = None, data: int | bytes = None, scope: CommandScope = None
    ) -> CommandReq:
        if cmd in RAMP_COMMANDS and data in (None, 0):
            # TestBase generates scalar zero for commands without data bits.
            data = RAMP_PAYLOAD
        return super().build_request(cmd, address, data, scope)

    def generate_random_address(self, cmd: CommandDefEnum, scope: CommandScope = None) -> int:
        address = super().generate_random_address(cmd, scope)
        while cmd in RAMP_COMMANDS and address == DEFAULT_ADDRESS:
            address = super().generate_random_address(cmd, scope)
        return address

    def test_send_command(self):
        with mock.patch.object(CommandReq, "_enqueue_command") as mk_enqueue_command:
            # tests TMCC1 commands, beginning with HALT
            req = CommandReq.send_request(TMCC1HaltCommandEnum.HALT)
            mk_enqueue_command.assert_called_once_with(
                0xFEFFFF.to_bytes(3, byteorder="big"),
                1,
                0,
                0,
                DEFAULT_BAUDRATE,
                DEFAULT_PORT,
                None,
                request=req,
            )
            mk_enqueue_command.reset_mock()

            # Route command
            req = CommandReq.send_request(TMCC1RouteCommandEnum.FIRE, 10)
            mk_enqueue_command.assert_called_once_with(
                0xFED51F.to_bytes(3, byteorder="big"),
                1,
                0,
                0,
                DEFAULT_BAUDRATE,
                DEFAULT_PORT,
                None,
                request=req,
            )
            mk_enqueue_command.reset_mock()

            # tests all TMCC1 command defs
            address = 23
            for cdef in [TMCC1AuxCommandEnum, TMCC1SwitchCommandEnum, TMCC1EngineCommandEnum]:
                for cmd in cdef:
                    if cmd in [
                        TMCC1EngineCommandEnum.RELATIVE_SPEED,
                        TMCC1AuxCommandEnum.RELATIVE_SPEED,
                        TMCC1AuxCommandEnum.REVERSE_SPEED,
                    ]:
                        continue  # can't tests defs that map data, yet
                    data = self.generate_random_data(cmd)
                    if cmd == TMCC1EngineCommandEnum.TARGET_SPEED:
                        with pytest.raises(ValueError, match="TARGET_SPEED.*cannot be sent"):
                            CommandReq.send_request(cmd, address, data)
                        mk_enqueue_command.assert_not_called()
                        continue
                    req = CommandReq.send_request(cmd, address, data)
                    bits = cmd.command_def.bits | (int.from_bytes(cmd.command_def.first_byte, byteorder="big") << 16)
                    bits |= address << 7
                    if data != 0:
                        bits |= data
                    mk_enqueue_command.assert_called_once_with(
                        bits.to_bytes(3, byteorder="big"),
                        1,
                        0,
                        0,
                        DEFAULT_BAUDRATE,
                        DEFAULT_PORT,
                        None,
                        request=req,
                    )
                    mk_enqueue_command.reset_mock()

            # tests engine defs again with TRAIN scope
            address = 1
            for cmd in TMCC1EngineCommandEnum:
                if cmd == TMCC1EngineCommandEnum.RELATIVE_SPEED:
                    continue  # can't tests defs that map data, yet
                data = self.generate_random_data(cmd)
                if cmd == TMCC1EngineCommandEnum.TARGET_SPEED:
                    with pytest.raises(ValueError, match="TARGET_SPEED.*cannot be sent"):
                        CommandReq.send_request(cmd, address, data, CommandScope.TRAIN)
                    mk_enqueue_command.assert_not_called()
                    continue
                req = CommandReq.send_request(cmd, address, data, CommandScope.TRAIN)
                bits = cmd.command_def.bits
                bits |= address << 7
                bits &= TMCC1_TRAIN_COMMAND_PURIFIER
                bits |= TMCC1_TRAIN_COMMAND_MODIFIER
                bits |= int.from_bytes(cmd.command_def.first_byte, byteorder="big") << 16
                if cmd.command_def.num_data_bits > 0:
                    bits |= data
                mk_enqueue_command.assert_called_once_with(
                    bits.to_bytes(3, byteorder="big"),
                    1,
                    0,
                    0,
                    DEFAULT_BAUDRATE,
                    DEFAULT_PORT,
                    None,
                    request=req,
                )
                mk_enqueue_command.reset_mock()

            # random switch command
            req = CommandReq.send_request(TMCC1SwitchCommandEnum.THRU, 15)
            mk_enqueue_command.assert_called_once_with(
                0xFE4780.to_bytes(3, byteorder="big"),
                1,
                0,
                0,
                DEFAULT_BAUDRATE,
                DEFAULT_PORT,
                None,
                request=req,
            )
            mk_enqueue_command.reset_mock()

            # random acc command
            req = CommandReq.send_request(TMCC1AuxCommandEnum.AUX2_OPT_ONE, 15)
            mk_enqueue_command.assert_called_once_with(
                0xFE878D.to_bytes(3, byteorder="big"),
                1,
                0,
                0,
                DEFAULT_BAUDRATE,
                DEFAULT_PORT,
                None,
                request=req,
            )
            mk_enqueue_command.reset_mock()

            # random engine command
            req = CommandReq.send_request(TMCC1EngineCommandEnum.RELATIVE_SPEED, 28, -5)
            mk_enqueue_command.assert_called_once_with(
                0xFE0E40.to_bytes(3, byteorder="big"),
                1,
                0,
                0,
                DEFAULT_BAUDRATE,
                DEFAULT_PORT,
                None,
                request=req,
            )
            mk_enqueue_command.reset_mock()

            # tests TMCC2 commands
            for cdef in [TMCC2RouteCommandEnum, TMCC2EngineCommandEnum]:
                for cmd in cdef:
                    if cmd == TMCC2EngineCommandEnum.RELATIVE_SPEED:
                        continue  # can't tests defs that map data, yet
                    data = self.generate_random_data(cmd)
                    bits = cmd.command_def.bits
                    bits |= address << 9
                    bits |= int.from_bytes(cmd.command_def.first_byte, byteorder="big") << 16
                    req = CommandReq.send_request(cmd, address, data)
                    if cmd.command_def.num_data_bits > 0:
                        bits |= data
                    mk_enqueue_command.assert_called_once_with(
                        bits.to_bytes(3, byteorder="big"),
                        1,
                        0,
                        0,
                        DEFAULT_BAUDRATE,
                        DEFAULT_PORT,
                        None,
                        request=req,
                    )
                    mk_enqueue_command.reset_mock()

            req = CommandReq.send_request(TMCC2RouteCommandEnum.FIRE, 10)
            mk_enqueue_command.assert_called_once_with(
                0xFA14FD.to_bytes(3, byteorder="big"),
                1,
                0,
                0,
                DEFAULT_BAUDRATE,
                DEFAULT_PORT,
                None,
                request=req,
            )
            mk_enqueue_command.reset_mock()

    @pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
    @pytest.mark.parametrize(
        "command, address",
        [
            (TMCC1EngineCommandEnum.TARGET_SPEED, 7),
            (TMCC2EngineCommandEnumEx.TARGET_SPEED, 7),
            (TMCC2EngineCommandEnumEx.TARGET_SPEED, 3180),
        ],
    )
    @pytest.mark.parametrize("api", ["send", "send_request", "as_action", "build_action", "enqueue"])
    def test_retired_target_speed_cannot_reach_the_buffer(self, command, address, scope, api):
        req = CommandReq.build(command, address, 7, scope)
        parsed = CommandReq.from_bytes(req.as_bytes)
        assert parsed.command == command
        assert parsed.data == 7
        assert parsed.address == address
        assert parsed.scope == scope
        if isinstance(command, TMCC2VariableEnum):
            assert isinstance(req, VariableCommandReq)
            assert isinstance(parsed, VariableCommandReq)
            assert not isinstance(req, (ParameterCommandReq, RampCommandReq))
            assert not isinstance(parsed, (ParameterCommandReq, RampCommandReq))
            assert parsed.data_bytes == req.data_bytes == [7]
        with mock.patch.object(CommBuffer, "build") as build_buffer:
            with pytest.raises(ValueError, match="TARGET_SPEED.*cannot be sent"):
                if api == "send":
                    parsed.send(repeat=3, delay=1, duration=2)
                elif api == "send_request":
                    CommandReq.send_request(command, address, 7, scope, repeat=3, delay=1, duration=2)
                elif api == "as_action":
                    parsed.as_action(repeat=3, delay=1, duration=2)()
                elif api == "build_action":
                    CommandReq.build_action(command, address, 7, scope)()
                else:
                    CommandReq._enqueue_command(req, 3, 1, 2, DEFAULT_BAUDRATE, DEFAULT_PORT, None)
            build_buffer.assert_not_called()

    @pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
    @pytest.mark.parametrize("address", [1, 99, 100, 3180, 9999])
    @pytest.mark.parametrize("data", [0, 7, 199])
    def test_variable_target_speed_data(self, address, data, scope):
        command = TMCC2EngineCommandEnumEx.TARGET_SPEED
        assert isinstance(command, TMCC2VariableEnum)
        assert command.num_data_bytes == 1
        req = CommandReq.build(command, address, data, scope)
        parsed = CommandReq.from_bytes(req.as_bytes)
        assert isinstance(req, VariableCommandReq)
        assert isinstance(parsed, VariableCommandReq)
        assert not isinstance(req, (ParameterCommandReq, RampCommandReq))
        assert not isinstance(parsed, (ParameterCommandReq, RampCommandReq))
        assert parsed.command == req.command == command
        assert parsed.data == req.data == data
        assert parsed.data_bytes == req.data_bytes == [data]
        assert parsed.address == req.address == address
        assert parsed.scope == req.scope == scope
        assert req.is_tmcc4 is False
        assert parsed.is_tmcc4 is (address > 99)
        assert parsed.as_bytes == req.as_bytes
        assert len(req.as_bytes) == req.num_bytes == (42 if address > 99 else 18)

    @pytest.mark.parametrize("data", [-1, 200, 255])
    def test_variable_target_speed_invalid_data(self, data):
        with pytest.raises(ValueError):
            CommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, data)

    @pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
    @pytest.mark.parametrize("address", [7, 3180, 9999])
    @pytest.mark.parametrize("command", RAMP_COMMANDS)
    @pytest.mark.parametrize("api", ["send", "send_request", "as_action", "build_action", "enqueue", "enqueue_bytes"])
    def test_state_only_ramp_cannot_reach_the_buffer(self, command, address, scope, api):
        req = self.build_request(command, address, scope=scope)
        parsed = CommandReq.from_bytes(req.as_bytes)
        assert isinstance(req, RampCommandReq)
        assert isinstance(parsed, RampCommandReq)
        assert parsed.command == command
        assert parsed.address == address
        assert parsed.scope == scope
        assert parsed.data_bytes == req.data_bytes == RAMP_PAYLOAD
        assert parsed.as_bytes == req.as_bytes
        assert len(req.as_bytes) == req.num_bytes == 45
        assert parsed.is_tmcc4 is req.is_tmcc4 is False
        with mock.patch.object(CommBuffer, "build") as build_buffer:
            with pytest.raises(ValueError, match=rf"{command.name}.*state-only.*CommBuffer\.update_state"):
                if api == "send":
                    parsed.send(repeat=3, delay=1, duration=2)
                elif api == "send_request":
                    CommandReq.send_request(command, address, RAMP_PAYLOAD, scope, repeat=3, delay=1, duration=2)
                elif api == "as_action":
                    parsed.as_action(repeat=3, delay=1, duration=2)()
                elif api == "build_action":
                    CommandReq.build_action(command, address, RAMP_PAYLOAD, scope)()
                elif api == "enqueue":
                    CommandReq._enqueue_command(parsed, 3, 1, 2, DEFAULT_BAUDRATE, DEFAULT_PORT, None)
                else:
                    CommandReq._enqueue_command(
                        parsed.as_bytes, 3, 1, 2, DEFAULT_BAUDRATE, DEFAULT_PORT, None, request=parsed
                    )
            build_buffer.assert_not_called()

    @pytest.mark.parametrize("target", [TMCC1EngineCommandEnum.TARGET_SPEED, TMCC2EngineCommandEnumEx.TARGET_SPEED])
    def test_synthetic_target_effects_are_not_sent(self, monkeypatch, target):
        req = CommandReq.build(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 7, 20)
        monkeypatch.setattr(CommandReq, "results_in", staticmethod(lambda _req: {(target, 7)}))
        with mock.patch.object(CommBuffer, "build") as build_buffer:
            req.send(repeat=2, duration=0.2, interval=100)
            queued = [call.args[0] for call in build_buffer.return_value.enqueue_command.call_args_list]
            assert len(queued) == 4
            assert all(command is req for command in queued)

    def test_determine_first_byte(self):
        for cdef in self.all_command_enums:
            for cmd in cdef:
                assert isinstance(cmd.value, CommandDef)
                assert cmd.value.first_byte == CommandReq._determine_first_byte(cmd.value, cmd.value.scope)

        # retest for Trains
        for cdef in self.all_command_enums:
            for cmd in cdef:
                data = self.generate_random_data(cmd)
                req = self.build_request(cmd, 1, data, CommandScope.TRAIN)
                cmd_bytes = req.as_bytes
                fb = cmd_bytes[0].to_bytes(1, byteorder="big")
                assert fb == CommandReq._determine_first_byte(cmd.value, CommandScope.TRAIN)

    def test_vet_request(self):
        # all command defs should pass
        for cdef in self.all_command_enums:
            for cmd in cdef:
                CommandReq._vet_request(cmd, 1, 0, CommandScope.ENGINE)

        # tests that non-CommandDefEnums fail
        with pytest.raises(TypeError, match="Command def not recognized: 'invalid_command'"):
            # noinspection PyTypeChecker
            CommandReq._vet_request("invalid_command", 1, 0, CommandScope.ENGINE)

    def test_enqueue_command(self):
        with mock.patch.object(CommBufferSingleton, "enqueue_command") as mk_enqueue_command:
            # tests _enqueue_command with byte string
            CommandReq._enqueue_command(b"\x01\x02\x03", 1, 0, 0, DEFAULT_BAUDRATE, DEFAULT_PORT, None)
            mk_enqueue_command.assert_called_once_with(b"\x01\x02\x03", 0)
            mk_enqueue_command.reset_mock()

            # tests repeat argument
            CommandReq._enqueue_command(b"\x01\x02\x03", 5, 0, 0, DEFAULT_BAUDRATE, DEFAULT_PORT, None)
            assert mk_enqueue_command.call_count == 5
            mk_enqueue_command.reset_mock()

        # tests for invalid arguments
        with pytest.raises(ValueError, match=re.escape("repeat must be equal to or greater than 1 (-5)")):
            CommandReq._enqueue_command(b"\x01\x02\x03", -5, 0, 0, DEFAULT_BAUDRATE, DEFAULT_PORT, None)
        with pytest.raises(ValueError, match=re.escape("delay must be equal to or greater than 0 (-6)")):
            CommandReq._enqueue_command(b"\x01\x02\x03", 1, -6, 0, DEFAULT_BAUDRATE, DEFAULT_PORT, None)

    def test_address(self):
        for cdef in self.all_command_enums:
            for cmd in cdef:
                address = self.generate_random_address(cmd)
                data = self.generate_random_data(cmd)
                req = self.build_request(cmd, address, data)
                if req.command_def.is_addressable:
                    assert req.address == address
                else:
                    assert req.address == DEFAULT_ADDRESS
                if isinstance(req, VariableCommandReq):
                    assert req.is_tmcc4 is False

    def test_data(self):
        for cdef in self.all_command_enums:
            for cmd in cdef:
                data = self.generate_random_data(cmd)
                req = self.build_request(cmd, 1, data)
                assert req.data == data
                if isinstance(cmd, TMCC2VariableEnum):
                    assert isinstance(req, VariableCommandReq)
                    if cmd in RAMP_COMMANDS:
                        assert isinstance(req, RampCommandReq)
                        assert req.data == 0
                        assert req.data_bytes == RAMP_PAYLOAD
                        assert cmd.num_data_bytes == len(req.data_bytes) + 2
                    else:
                        assert not isinstance(req, RampCommandReq)
                        assert bytes(req.data_bytes) == data.to_bytes(cmd.num_data_bytes, "big")
                        assert cmd.num_data_bytes == len(req.data_bytes)

    def test_scope(self):
        for cdef in self.all_command_enums:
            for cmd in cdef:
                address = self.generate_random_address(cmd)
                data = self.generate_random_data(cmd)
                req = self.build_request(cmd, address, data)
                assert req.scope == cmd.scope

    def test_command_def(self):
        for cdef in self.all_command_enums:
            for cmd in cdef:
                req = self.build_request(cmd)
                assert req.command_def == cmd.command_def

    def test_bits(self):
        for cdef in self.all_command_enums:
            for cmd in cdef:
                address = self.generate_random_address(cmd)
                data = self.generate_random_data(cmd)
                req = self.build_request(cmd, address, data)
                if isinstance(cmd, TMCC2VariableEnum):
                    word_size = 7 if req.address > 99 and not isinstance(req, RampCommandReq) else 3
                    assert req.as_bytes[2 * word_size + 2] | (req.as_bytes[3 * word_size + 2] << 8) == cmd.value.bits
                elif isinstance(cmd, TMCC2MultiByteEnum):
                    pass
                else:
                    # make sure all bits in the definition are also in the request
                    # the other bits in the request are the address and data values
                    assert req.bits & cmd.value.bits == cmd.value.bits

    def test_num_data_bits(self):
        for cdef in self.all_command_enums:
            for cmd in cdef:
                data = self.generate_random_data(cmd)
                req = self.build_request(cmd, 1, data, CommandScope.TRAIN)
                assert req.num_data_bits == cmd.command_def.num_data_bits

    def test_syntax(self):
        for cdef in self.all_command_enums:
            for cmd in cdef:
                req = self.build_request(cmd)
                assert req.syntax == cmd.syntax

    def test_identifier(self):
        for cdef in self.all_command_enums:
            for cmd in cdef:
                req = self.build_request(cmd)
                assert req.identifier == cmd.value.identifier

    # noinspection DuplicatedCode
    def test_build_tmcc1_command_req(self):
        """
        Build all the TMCC1 CommandReqs and verify that their command bytes
        map back to the sane request
        """
        for tmcc_enums in [
            TMCC1HaltCommandEnum,
            TMCC1SwitchCommandEnum,
            TMCC1AuxCommandEnum,
            TMCC1RouteCommandEnum,
            TMCC1EngineCommandEnum,
        ]:
            for tmcc_enum in tmcc_enums:
                if tmcc_enum.command_def.is_data:
                    n_times = 10
                else:
                    n_times = 1
                if tmcc_enums == TMCC1EngineCommandEnum:
                    scopes = [None, CommandScope.TRAIN]
                else:
                    scopes = [None]
                for scope in scopes:
                    for _ in range(n_times):
                        req = self.build_request(tmcc_enum, scope=scope)
                        # do reverse lookup
                        req_from_bytes = CommandReq.from_bytes(req.as_bytes)
                        if tmcc_enum.command_def.is_alias:
                            # if the enum is an alias for another command,
                            # check results against that command_def
                            alias_enum = tmcc_enum.command_def.alias
                            if isinstance(alias_enum, tuple):
                                alias_enum = alias_enum[0]
                                alias_data = tmcc_enum.command_def.alias[1]
                            else:
                                alias_data = req_from_bytes.data
                            assert req_from_bytes.command == alias_enum
                            assert req_from_bytes.command_def == alias_enum.command_def
                            assert req_from_bytes.num_data_bits == alias_enum.command_def.num_data_bits
                            assert alias_enum.command_def.is_valid_data(req_from_bytes.data)
                            assert alias_enum.command_def.is_valid_data(alias_data)
                        else:
                            assert req_from_bytes.command == req.command
                            assert req_from_bytes.command_def == req.command_def
                            assert req_from_bytes.num_data_bits == req.num_data_bits
                            assert req_from_bytes.data == req.data
                        assert req_from_bytes.address == req.address
                        assert req_from_bytes.syntax == req.syntax
                        assert req_from_bytes.identifier == req.identifier
                        assert req_from_bytes.scope == req.scope
                        assert req_from_bytes.is_tmcc1 == req.is_tmcc1
                        assert req_from_bytes.is_tmcc2 == req.is_tmcc2
                        assert req_from_bytes.as_bytes == req.as_bytes

    # noinspection DuplicatedCode
    def test_build_tmcc2_command_req(self):
        """
        Build all the TMCC2 CommandReqs and verify that their command bytes
        map back to the sane request
        """
        for tmcc_enums in [TMCC2HaltCommandEnum, TMCC2EngineCommandEnum, TMCC2RouteCommandEnum]:
            for tmcc_enum in tmcc_enums:
                if tmcc_enum.command_def.is_data:
                    n_times = 10
                else:
                    n_times = 1
                if tmcc_enums == TMCC2EngineCommandEnum:
                    scopes = [None, CommandScope.TRAIN]
                else:
                    scopes = [None]
                for scope in scopes:
                    for _ in range(n_times):
                        req = self.build_request(tmcc_enum, scope=scope)
                        # do reverse lookup
                        req_from_bytes = CommandReq.from_bytes(req.as_bytes)
                        if tmcc_enum.command_def.is_alias:
                            # if the enum is an alias for another command,
                            # check results against that command_def
                            alias_enum = tmcc_enum.command_def.alias
                            if isinstance(alias_enum, tuple):
                                alias_data = alias_enum[1]
                                alias_enum = alias_enum[0]
                            else:
                                alias_data = None
                            assert req_from_bytes.command == alias_enum
                            assert req_from_bytes.command_def == alias_enum.command_def
                            assert req_from_bytes.num_data_bits == alias_enum.command_def.num_data_bits
                            assert alias_enum.command_def.is_data is False or alias_enum.command_def.is_valid_data(
                                alias_data
                            )
                        else:
                            assert req_from_bytes.command == req.command
                            assert req_from_bytes.command_def == req.command_def
                            assert req_from_bytes.num_data_bits == req.num_data_bits
                            assert req_from_bytes.data == req.data
                        assert req_from_bytes.address == req.address
                        assert req_from_bytes.syntax == req.syntax
                        assert req_from_bytes.identifier == req.identifier
                        assert req_from_bytes.scope == req.scope
                        assert req_from_bytes.is_tmcc1 == req.is_tmcc1
                        assert req_from_bytes.is_tmcc2 == req.is_tmcc2
                        assert req_from_bytes.as_bytes == req.as_bytes

    # noinspection DuplicatedCode
    def test_build_parameter_command_req(self):
        """
        Build all parameter and extended CommandReqs and verify that their command bytes
        map back to the same request
        """
        scopes = [None, CommandScope.ENGINE, CommandScope.TRAIN]
        for tmcc_enums in [
            TMCC2RailSoundsDialogControl,
            TMCC2RailSoundsEffectsControl,
            TMCC2EffectsControl,
            TMCC2LightingControl,
            TMCC2MaskingControl,
            TMCC2EngineCommandEnumEx,
        ]:
            for tmcc_enum in tmcc_enums:
                for scope in scopes:
                    req = self.build_request(tmcc_enum, scope=scope)
                    # do reverse lookup
                    req_from_bytes = CommandReq.from_bytes(req.as_bytes)
                    assert req_from_bytes.command == req.command
                    assert req_from_bytes.command_def == req.command_def
                    assert req_from_bytes.num_data_bits == req.num_data_bits
                    assert req_from_bytes.data == req.data
                    assert req_from_bytes.address == req.address
                    assert req_from_bytes.syntax == req.syntax
                    assert req_from_bytes.identifier == req.identifier
                    assert req_from_bytes.scope == req.scope
                    assert req_from_bytes.is_tmcc1 == req.is_tmcc1
                    assert req_from_bytes.is_tmcc2 == req.is_tmcc2
                    assert req_from_bytes.as_bytes == req.as_bytes
                    if isinstance(tmcc_enum, TMCC2VariableEnum):
                        assert isinstance(req, VariableCommandReq)
                        assert isinstance(req_from_bytes, VariableCommandReq)
                        assert req.index_byte == b"\x6f"
                        if tmcc_enum in RAMP_COMMANDS:
                            assert isinstance(req, RampCommandReq)
                            assert isinstance(req_from_bytes, RampCommandReq)
                            assert len(req.as_bytes) == req.num_bytes == 45
                            assert req.as_bytes[1:3] == b"\x03\x6f"
                            assert req.as_bytes[5] == tmcc_enum.num_data_bytes == 10
                            assert req.as_bytes[14:-3:3] == req.address.to_bytes(2, "big") + RAMP_PAYLOAD
                            assert req_from_bytes.data_bytes == req.data_bytes == RAMP_PAYLOAD
                            assert req_from_bytes.host == req.host == "192.168.1.7"
                            assert req_from_bytes.port == req.port == 0x1234
                            assert req_from_bytes.claim_id == req.claim_id == 0xABCD
                            assert req_from_bytes.is_tmcc4 is req.is_tmcc4 is False
                        else:
                            assert not isinstance(req, (ParameterCommandReq, RampCommandReq))
                            assert not isinstance(req_from_bytes, (ParameterCommandReq, RampCommandReq))
                            word_size = 7 if req.address > 99 else 3
                            assert len(req.as_bytes) == req.num_bytes == (5 + tmcc_enum.num_data_bytes) * word_size
                            assert req.as_bytes[word_size + 2] == tmcc_enum.num_data_bytes == 1
                            assert req.as_bytes[4 * word_size + 2 : -word_size : word_size] == bytes(req.data_bytes)
                            assert req_from_bytes.data_bytes == req.data_bytes == [req.data]
                            assert 0 <= req.data <= 199
                            assert req.is_tmcc4 is False
                            assert req_from_bytes.is_tmcc4 is (req.address > 99)
                    else:
                        assert isinstance(req, ParameterCommandReq)
                        assert isinstance(req_from_bytes, ParameterCommandReq)
                        assert req.index_byte == PARAMETER_ENUM_TO_INDEX_MAP[type(tmcc_enum)].to_bytes(1, "big")
                        assert len(req.as_bytes) == req.num_bytes == (21 if req.address > 99 else 9)
                        assert len(req.data_byte) == 1
                        assert req.as_bytes[9 if req.address > 99 else 5] == req.data_byte[0]
