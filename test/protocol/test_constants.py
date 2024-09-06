import pytest

from src.protocol.constants import *
from ..test_base import TestBase


class TestConstants(TestBase):
    def test_by_name_mixin(self) -> None:
        # assert all enums are found
        for ss in SwitchState:
            assert SwitchState.by_name(ss.name) == ss

        # assert by_name is case-insensitive
        assert SwitchState.by_name('through') == SwitchState.THROUGH
        assert SwitchState.by_name('THROUGH') == SwitchState.THROUGH

        # assert non-members return None
        assert SwitchState.by_name('NOT_PRESENT') is None

        # assert None return None
        assert SwitchState.by_name(str(None)) is None

        # check ValueError is thrown
        with pytest.raises(ValueError, match="'NOT_PRESENT' is not a valid SwitchState"):
            SwitchState.by_name('NOT_PRESENT', raise_exception=True)

        # check ValueError is thrown
        with pytest.raises(ValueError, match="None is not a valid SwitchState"):
            SwitchState.by_name(None, raise_exception=True)  # noqa

        # check ValueError is thrown
        with pytest.raises(ValueError, match="Empty is not a valid SwitchState"):
            SwitchState.by_name("  ", raise_exception=True)

    def test_by_name_mixin_in_enums(self) -> None:
        """
            Test that all defined enums have ByNameMixin
        """
        enums = [SwitchState,
                 CommandFormat,
                 AuxChoice,
                 AuxOption,
                 TMCC2CommandScope,
                 TMCC1EngineOption,
                 TMCC2EngineOption
                 ]
        for env in enums:
            for en in env:
                assert env.by_name(en.name) == en

    def test_tmcc1_constants(self) -> None:
        """
            All bit patterns are from the Lionel LCS Partner Documentation,
            Legacy Command Protocol, rev 1.21
        """
        assert TMCC1_COMMAND_PREFIX == 0b11111110

        assert TMCC1_HALT_COMMAND == 0b1111111111111111

        assert TMCC1_ROUTE_COMMAND == 0b1101000000011111

        assert TMCC1_SWITCH_THROUGH_COMMAND == 0b0100000000000000
        assert TMCC1_SWITCH_OUT_COMMAND == 0b0100000000011111
        assert TMCC1_SWITCH_SET_ADDRESS_COMMAND == 0b0100000000101011

        # test tmcc1 acc commands
        acc_cmd_prefix = 0x8000
        assert TMCC1_ACC_ON_COMMAND == acc_cmd_prefix | 0b0101111
        assert TMCC1_ACC_OFF_COMMAND == acc_cmd_prefix | 0b0100000
        assert TMCC1_ACC_NUMERIC_COMMAND == acc_cmd_prefix | 0b0010000
        assert TMCC1_ACC_SET_ADDRESS_COMMAND == acc_cmd_prefix | 0b0101011

        assert TMCC1_ACC_AUX_2_OFF_COMMAND == acc_cmd_prefix | 0b0001100
        assert TMCC1_ACC_AUX_2_OPTION_1_COMMAND == acc_cmd_prefix | 0b0001101
        assert TMCC1_ACC_AUX_2_OPTION_2_COMMAND == acc_cmd_prefix | 0b0001110
        assert TMCC1_ACC_AUX_2_ON_COMMAND == acc_cmd_prefix | 0b0001111

        assert TMCC1_ACC_AUX_1_OFF_COMMAND == acc_cmd_prefix | 0b0001000
        assert TMCC1_ACC_AUX_1_OPTION_1_COMMAND == acc_cmd_prefix | 0b0001001
        assert TMCC1_ACC_AUX_1_OPTION_2_COMMAND == acc_cmd_prefix | 0b0001010
        assert TMCC1_ACC_AUX_1_ON_COMMAND == acc_cmd_prefix | 0b0001011

        # test tmcc1 engine/train commands
        eng_cmd_prefix = 0x0000
        assert TMCC1_ENG_ABSOLUTE_SPEED_COMMAND == eng_cmd_prefix | 0b1100000
        assert TMCC1_ENG_RELATIVE_SPEED_COMMAND == eng_cmd_prefix | 0b1000000
        assert TMCC1_ENG_FORWARD_DIRECTION_COMMAND == eng_cmd_prefix | 0b0000000
        assert TMCC1_ENG_TOGGLE_DIRECTION_COMMAND == eng_cmd_prefix | 0b0000001
        assert TMCC1_ENG_REVERSE_DIRECTION_COMMAND == eng_cmd_prefix | 0b0000011
        assert TMCC1_ENG_BOOST_SPEED_COMMAND == eng_cmd_prefix | 0b0000100
        assert TMCC1_ENG_BRAKE_SPEED_COMMAND == eng_cmd_prefix | 0b0000111
        assert TMCC1_ENG_OPEN_FRONT_COUPLER_COMMAND == eng_cmd_prefix | 0b0000101
        assert TMCC1_ENG_OPEN_REAR_COUPLER_COMMAND == eng_cmd_prefix | 0b0000110
        assert TMCC1_ENG_BLOW_HORN_ONE_COMMAND == eng_cmd_prefix | 0b0011100
        assert TMCC1_ENG_RING_BELL_COMMAND == eng_cmd_prefix | 0b0011101
        assert TMCC1_ENG_LET_OFF_SOUND_COMMAND == eng_cmd_prefix | 0b0011110
        assert TMCC1_ENG_BLOW_HORN_TWO_COMMAND == eng_cmd_prefix | 0b0011111

        assert TMCC1_ENG_AUX1_OFF_COMMAND == eng_cmd_prefix | 0b0001000
        assert TMCC1_ENG_AUX1_OPTION_ONE_COMMAND == eng_cmd_prefix | 0b0001001
        assert TMCC1_ENG_AUX1_OPTION_TWO_COMMAND == eng_cmd_prefix | 0b0001010
        assert TMCC1_ENG_AUX1_ON_COMMAND == eng_cmd_prefix | 0b0001011

        assert TMCC1_ENG_AUX2_OFF_COMMAND == eng_cmd_prefix | 0b0001100
        assert TMCC1_ENG_AUX2_OPTION_ONE_COMMAND == eng_cmd_prefix | 0b0001101
        assert TMCC1_ENG_AUX2_OPTION_TWO_COMMAND == eng_cmd_prefix | 0b0001110
        assert TMCC1_ENG_AUX2_ON_COMMAND == eng_cmd_prefix | 0b0001111

        assert TMCC1_ENG_SET_MOMENTUM_LOW_COMMAND == eng_cmd_prefix | 0b0101000
        assert TMCC1_ENG_SET_MOMENTUM_MEDIUM_COMMAND == eng_cmd_prefix | 0b0101001
        assert TMCC1_ENG_SET_MOMENTUM_HIGH_COMMAND == eng_cmd_prefix | 0b0101010

        assert TMCC1_ENG_NUMERIC_COMMAND == eng_cmd_prefix | 0b0010000

        assert TMCC1_ENG_SET_ADDRESS_COMMAND == eng_cmd_prefix | 0b0101011
