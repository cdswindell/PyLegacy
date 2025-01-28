# noinspection PyPackageRequirements
import pytest

from src.pytrain.protocol.multibyte.multibyte_constants import *
from src.pytrain.protocol.tmcc1.tmcc1_constants import *
from src.pytrain.protocol.tmcc2.tmcc2_constants import *
from ..test_base import TestBase


class TestConstants(TestBase):
    def test_by_name_mixin(self) -> None:
        # assert all enums are found
        for ss in TMCC1SwitchCommandEnum:
            assert TMCC1SwitchCommandEnum.by_name(ss.name) == ss

        # assert by_name is case-insensitive
        assert TMCC1SwitchCommandEnum.by_name("thru") == TMCC1SwitchCommandEnum.THRU
        assert TMCC1SwitchCommandEnum.by_name("THRU") == TMCC1SwitchCommandEnum.THRU

        # assert non-members return None
        assert TMCC1SwitchCommandEnum.by_name("NOT_PRESENT") is None

        # assert None return None
        assert TMCC1SwitchCommandEnum.by_name(str(None)) is None

        # check ValueError is thrown
        with pytest.raises(ValueError, match="'NOT_PRESENT' is not a valid TMCC1SwitchCommandEnum"):
            TMCC1SwitchCommandEnum.by_name("NOT_PRESENT", raise_exception=True)

        # check ValueError is thrown
        with pytest.raises(ValueError, match="None is not a valid TMCC1SwitchCommandEnum"):
            TMCC1SwitchCommandEnum.by_name(None, raise_exception=True)  # noqa

        # check ValueError is thrown
        with pytest.raises(ValueError, match="Empty is not a valid TMCC1SwitchCommandEnum"):
            TMCC1SwitchCommandEnum.by_name("  ", raise_exception=True)

    def test_by_name_mixin_in_enums(self) -> None:
        """
        Test that all defined enums have Mixins
        """
        enums = [
            CommandSyntax,
            CommandScope,
            TMCC1SwitchCommandEnum,
            TMCC1HaltCommandEnum,
            TMCC1RouteCommandEnum,
            TMCC1AuxCommandEnum,
            TMCC1EngineCommandEnum,
            TMCC2ParameterIndex,
            TMCC2EngineCommandEnum,
            TMCC2EffectsControl,
            TMCC2LightingControl,
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

        assert TMCC1_SWITCH_THRU_COMMAND == 0b0100000000000000
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

    def test_tmcc2_constants(self) -> None:
        """
        All bit patterns are from the Lionel LCS Partner Documentation,
        Legacy Command Protocol, rev 1.21
        """
        assert TMCC2_AUX1_OFF_COMMAND == 0b100001000
        assert TMCC2_AUX1_ON_COMMAND == 0b100001011
        assert TMCC2_AUX1_OPTION_ONE_COMMAND == 0b100001001
        assert TMCC2_AUX1_OPTION_TWO_COMMAND == 0b100001010
        assert TMCC2_AUX2_OFF_COMMAND == 0b100001100
        assert TMCC2_AUX2_ON_COMMAND == 0b100001111
        assert TMCC2_AUX2_OPTION_ONE_COMMAND == 0b100001101
        assert TMCC2_AUX2_OPTION_TWO_COMMAND == 0b100001110
        assert TMCC2_BELL_OFF_COMMAND == 0b111110100
        assert TMCC2_BELL_ONE_SHOT_DING_COMMAND == 0b111110000
        assert TMCC2_BELL_ON_COMMAND == 0b111110101
        assert TMCC2_BELL_SLIDER_POSITION_COMMAND == 0b110110000
        assert TMCC2_BLOW_HORN_ONE_COMMAND == 0b100011100
        assert TMCC2_BLOW_HORN_TWO_COMMAND == 0b100011111
        assert TMCC2_BOOST_SPEED_COMMAND == 0b100000100
        assert TMCC2_BRAKE_SPEED_COMMAND == 0b100000111
        assert TMCC2_DIESEL_RPM_SOUND_COMMAND == 0b110100000
        assert TMCC2_ENGINE_LABOR_COMMAND == 0b111000000
        assert TMCC2_ENG_AUGER_SOUND_COMMAND == 0b111110111
        assert TMCC2_ENG_BRAKE_AIR_RELEASE_SOUND_COMMAND == 0b111111000
        assert TMCC2_ENG_BRAKE_SQUEAL_SOUND_COMMAND == 0b111110110
        assert TMCC2_ENG_LET_OFF_LONG_SOUND_COMMAND == 0b111111010
        assert TMCC2_ENG_LET_OFF_SOUND_COMMAND == 0b111111001
        assert TMCC2_ENG_REFUELLING_SOUND_COMMAND == 0b100101101
        assert TMCC2_FORWARD_DIRECTION_COMMAND == 0b100000000
        assert TMCC2_HALT_COMMAND == 0b110101011
        assert TMCC2_NUMERIC_COMMAND == 0b100010000
        assert TMCC2_OPEN_FRONT_COUPLER_COMMAND == 0b100000101
        assert TMCC2_OPEN_REAR_COUPLER_COMMAND == 0b100000110
        assert TMCC2_QUILLING_HORN_COMMAND == 0b111100000
        assert TMCC2_REVERSE_DIRECTION_COMMAND == 0b100000011
        assert TMCC2_RING_BELL_COMMAND == 0b100011101
        assert TMCC2_SET_ABSOLUTE_SPEED_COMMAND == 0b000000000
        assert TMCC2_SET_ADDRESS_COMMAND == 0b100101011
        assert TMCC2_SET_BOOST_LEVEL_COMMAND == 0b011101000
        assert TMCC2_SET_BRAKE_LEVEL_COMMAND == 0b011100000
        assert TMCC2_SET_MOMENTUM_COMMAND == 0b011001000
        assert TMCC2_SET_MOMENTUM_HIGH_COMMAND == 0b100101010
        assert TMCC2_SET_MOMENTUM_LOW_COMMAND == 0b100101000
        assert TMCC2_SET_MOMENTUM_MEDIUM_COMMAND == 0b100101001
        assert TMCC2_SET_RELATIVE_SPEED_COMMAND == 0b101000000
        assert TMCC2_SET_TRAIN_BRAKE_COMMAND == 0b011110000
        assert TMCC2_SHUTDOWN_SEQ_ONE_COMMAND == 0b111111101
        assert TMCC2_SHUTDOWN_SEQ_TWO_COMMAND == 0b111111110
        assert TMCC2_SOUND_OFF_COMMAND == 0b101010000
        assert TMCC2_SOUND_ON_COMMAND == 0b101010001
        assert TMCC2_STALL_COMMAND == 0b011111000
        assert TMCC2_START_UP_SEQ_ONE_COMMAND == 0b111111011
        assert TMCC2_START_UP_SEQ_TWO_COMMAND == 0b111111100
        assert TMCC2_STOP_IMMEDIATE_COMMAND == 0b011111011
        assert TMCC2_TOGGLE_DIRECTION_COMMAND == 0b100000001
        assert TMCC2_WATER_INJECTOR_SOUND_COMMAND == 0b110101000
        assert TMCC2_MOTION_START_COMMAND == 0b011111010
        assert TMCC2_MOTION_STOP_COMMAND == 0b011111110
        assert TMCC2_ENG_CYLINDER_HISS_SOUND_COMMAND == 0b101010010
        assert TMCC2_ENG_POP_OFF_SOUND_COMMAND == 0b101010011

    def test_command_scope_enum(self) -> None:
        # check that engine and train elements are in TMCC1CommandIdentifier
        assert TMCC1CommandIdentifier.ENGINE == TMCC1CommandIdentifier(CommandScope.ENGINE.name)
        assert TMCC1CommandIdentifier.TRAIN == TMCC1CommandIdentifier(CommandScope.TRAIN.name)

        # check that engine and train elements are in TMCC2CommandPrefix
        assert TMCC2CommandPrefix.ENGINE == TMCC2CommandPrefix(CommandScope.ENGINE.name)
        assert TMCC2CommandPrefix.TRAIN == TMCC2CommandPrefix(CommandScope.TRAIN.name)

    def test_engine_option_enum(self) -> None:
        # should contain no elements
        assert len(CommandDefEnum) == 0

        # validate _missing_ method is present and throws exception
        with pytest.raises(ValueError, match="FOO is not a valid CommandDefEnum"):
            CommandDefEnum._missing_("foo")

    def test_engine_option(self) -> None:
        pass
