from unittest import mock

from src.protocol.command_req import CommandReq
from src.protocol.constants import TMCC2RouteCommandDef, TMCC1RouteCommandDef, DEFAULT_BAUDRATE, DEFAULT_PORT, \
    TMCC1HaltCommandDef, TMCC1SwitchState, TMCC1AuxCommandDef, TMCC1EngineCommandDef, CommandScope, \
    TMCC1_TRAIN_COMMAND_MODIFIER, TMCC1_TRAIN_COMMAND_PURIFIER, TMCC2EngineCommandDef
from ..test_base import TestBase


# noinspection PyMethodMayBeStatic
class TestCommandReq(TestBase):
    def test_send_command(self):
        with mock.patch.object(CommandReq, '_enqueue_command') as mk_enqueue_command:
            # test TMCC1 commands, beginning with HALT
            CommandReq.send_command(TMCC1HaltCommandDef.HALT)
            mk_enqueue_command.assert_called_once_with(0xfeffff.to_bytes(3, byteorder='big'),
                                                       1, 0, DEFAULT_BAUDRATE, DEFAULT_PORT)
            mk_enqueue_command.reset_mock()

            # Route command
            CommandReq.send_command(TMCC1RouteCommandDef.ROUTE, 10)
            mk_enqueue_command.assert_called_once_with(0xfed51f.to_bytes(3, byteorder='big'),
                                                       1, 0, DEFAULT_BAUDRATE, DEFAULT_PORT)
            mk_enqueue_command.reset_mock()

            # test all TMCC1 command defs
            address = 23
            for cdef in [TMCC1AuxCommandDef, TMCC1SwitchState, TMCC1EngineCommandDef]:
                for cmd in cdef:
                    if cmd.command_def.num_data_bits:
                        data = 1
                    else:
                        data = None
                    if cmd == TMCC1EngineCommandDef.RELATIVE_SPEED:
                        continue  # can't test defs that map data, yet
                    CommandReq.send_command(cmd, address, data)
                    bits = cmd.command_def.bits | (int.from_bytes(cmd.command_def.first_byte) << 16)
                    bits |= address << 7
                    if cmd.command_def.num_data_bits > 0:
                        bits |= data
                    mk_enqueue_command.assert_called_once_with(bits.to_bytes(3, byteorder='big'),
                                                               1, 0, DEFAULT_BAUDRATE, DEFAULT_PORT)
                    mk_enqueue_command.reset_mock()

            # test engine defs again with TRAIN scope
            address = 1
            for cmd in TMCC1EngineCommandDef:
                if cmd.command_def.num_data_bits:
                    data = 1
                else:
                    data = None
                if cmd == TMCC1EngineCommandDef.RELATIVE_SPEED:
                    continue  # can't test defs that map data, yet
                CommandReq.send_command(cmd, address, data, CommandScope.TRAIN)
                bits = cmd.command_def.bits
                bits |= address << 7
                bits &= TMCC1_TRAIN_COMMAND_PURIFIER
                bits |= TMCC1_TRAIN_COMMAND_MODIFIER
                bits |= (int.from_bytes(cmd.command_def.first_byte) << 16)
                if cmd.command_def.num_data_bits > 0:
                    bits |= data
                mk_enqueue_command.assert_called_once_with(bits.to_bytes(3, byteorder='big'),
                                                           1, 0, DEFAULT_BAUDRATE, DEFAULT_PORT)
                mk_enqueue_command.reset_mock()

            # random switch command
            CommandReq.send_command(TMCC1SwitchState.THROUGH, 15)
            mk_enqueue_command.assert_called_once_with(0xfe4780.to_bytes(3, byteorder='big'),
                                                       1, 0, DEFAULT_BAUDRATE, DEFAULT_PORT)
            mk_enqueue_command.reset_mock()

            # random acc command
            CommandReq.send_command(TMCC1AuxCommandDef.AUX2_OPTION_ONE, 15)
            mk_enqueue_command.assert_called_once_with(0xfe878d.to_bytes(3, byteorder='big'),
                                                       1, 0, DEFAULT_BAUDRATE, DEFAULT_PORT)
            mk_enqueue_command.reset_mock()

            # random engine command
            CommandReq.send_command(TMCC1EngineCommandDef.RELATIVE_SPEED, 28, -5)
            mk_enqueue_command.assert_called_once_with(0xfe0e40.to_bytes(3, byteorder='big'),
                                                       1, 0, DEFAULT_BAUDRATE, DEFAULT_PORT)
            mk_enqueue_command.reset_mock()

            # test TMCC2 commands
            for cdef in [TMCC2RouteCommandDef, TMCC2EngineCommandDef]:
                for cmd in cdef:
                    if cmd.command_def.num_data_bits:
                        data = 2  # BELL_SLIDER_POSITION, min data is 2
                    else:
                        data = None
                    if cmd == TMCC2EngineCommandDef.RELATIVE_SPEED:
                        continue  # can't test defs that map data, yet
                    bits = cmd.command_def.bits
                    bits |= address << 9
                    bits |= (int.from_bytes(cmd.command_def.first_byte) << 16)
                    CommandReq.send_command(cmd, address, data)
                    if cmd.command_def.num_data_bits > 0:
                        bits |= data

                    mk_enqueue_command.assert_called_once_with(bits.to_bytes(3, byteorder='big'),
                                                               1, 0, DEFAULT_BAUDRATE, DEFAULT_PORT)
                    mk_enqueue_command.reset_mock()

            CommandReq.send_command(TMCC2RouteCommandDef.ROUTE, 10)
            mk_enqueue_command.assert_called_once_with(0xfa14fd.to_bytes(3, byteorder='big'),
                                                       1, 0, DEFAULT_BAUDRATE, DEFAULT_PORT)
            mk_enqueue_command.reset_mock()

    # def test_build_action(self):
    #     assert False
    #
    # def test__determine_first_byte(self):
    #     assert False
    #
    # def test__vet_request(self):
    #     assert False
    #
    # def test__enqueue_command(self):
    #     assert False
    #
    # def test_address(self):
    #     assert False
    #
    # def test_data(self):
    #     assert False
    #
    # def test_scope(self):
    #     assert False
    #
    # def test_command_def(self):
    #     assert False
    #
    # def test_bits(self):
    #     assert False
    #
    # def test_num_data_bits(self):
    #     assert False
    #
    # def test_syntax(self):
    #     assert False
    #
    # def test_identifier(self):
    #     assert False
    #
    # def test_as_bytes(self):
    #     assert False
    #
    # def test_as_action(self):
    #     assert False
    #
    # def test__apply_address(self):
    #     assert False
    #
    # def test__apply_data(self):
    #     assert False
