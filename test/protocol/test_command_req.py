import re
from unittest import mock

# noinspection PyPackageRequirements
import pytest

from src.pytrain.comm.comm_buffer import CommBuffer, CommBufferSingleton
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT
from src.pytrain.protocol.multibyte.multibyte_constants import *
from src.pytrain.protocol.tmcc1.tmcc1_constants import *
from src.pytrain.protocol.tmcc2.tmcc2_constants import *

from ..test_base import TestBase


# noinspection PyMethodMayBeStatic
class TestCommandReq(TestBase):
    def teardown_method(self, test_method):
        super().teardown_method(test_method)
        CommBuffer.build().shutdown()

    def test_send_command(self):
        with mock.patch.object(CommandReq, "_enqueue_command") as mk_enqueue_command:
            # test TMCC1 commands, beginning with HALT
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

            # test all TMCC1 command defs
            address = 23
            for cdef in [TMCC1AuxCommandEnum, TMCC1SwitchCommandEnum, TMCC1EngineCommandEnum]:
                for cmd in cdef:
                    if cmd in [
                        TMCC1EngineCommandEnum.RELATIVE_SPEED,
                        TMCC1AuxCommandEnum.RELATIVE_SPEED,
                        TMCC1AuxCommandEnum.REVERSE_SPEED,
                    ]:
                        continue  # can't test defs that map data, yet
                    data = self.generate_random_data(cmd)
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

            # test engine defs again with TRAIN scope
            address = 1
            for cmd in TMCC1EngineCommandEnum:
                if cmd == TMCC1EngineCommandEnum.RELATIVE_SPEED:
                    continue  # can't test defs that map data, yet
                data = self.generate_random_data(cmd)
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

            # test TMCC2 commands
            for cdef in [TMCC2RouteCommandEnum, TMCC2EngineCommandEnum]:
                for cmd in cdef:
                    if cmd == TMCC2EngineCommandEnum.RELATIVE_SPEED:
                        continue  # can't test defs that map data, yet
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

        # test that non-CommandDefEnums fail
        with pytest.raises(TypeError, match="Command def not recognized: 'invalid_command'"):
            # noinspection PyTypeChecker
            CommandReq._vet_request("invalid_command", 1, 0, CommandScope.ENGINE)

    def test_enqueue_command(self):
        with mock.patch.object(CommBufferSingleton, "enqueue_command") as mk_enqueue_command:
            # test _enqueue_command with byte string
            CommandReq._enqueue_command(b"\x01\x02\x03", 1, 0, 0, DEFAULT_BAUDRATE, DEFAULT_PORT, None)
            mk_enqueue_command.assert_called_once_with(b"\x01\x02\x03", 0)
            mk_enqueue_command.reset_mock()

            # test repeat argument
            CommandReq._enqueue_command(b"\x01\x02\x03", 5, 0, 0, DEFAULT_BAUDRATE, DEFAULT_PORT, None)
            assert mk_enqueue_command.call_count == 5
            mk_enqueue_command.reset_mock()

        # test for invalid arguments
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

    def test_data(self):
        for cdef in self.all_command_enums:
            for cmd in cdef:
                data = self.generate_random_data(cmd)
                req = self.build_request(cmd, 1, data)
                assert req.data == data

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
                if isinstance(cmd, TMCC2MultiByteEnum):
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
                                alias_data = None
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
        Build all the Parameter CommandReqs and verify that their command bytes
        map back to the sane request
        """
        scopes = [None, CommandScope.TRAIN]
        for tmcc_enums in [
            TMCC2RailSoundsDialogControl,
            TMCC2RailSoundsEffectsControl,
            TMCC2EffectsControl,
            TMCC2LightingControl,
            TMCC2MultiByteEnum,
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
