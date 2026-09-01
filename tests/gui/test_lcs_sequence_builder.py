from __future__ import annotations

import pytest

import src.pytrain.gui.controller.lcs_device_registry as reg
from src.pytrain.gui.controller.lcs_sequence_builder import build_program
from src.pytrain.pdi.irda_req import IrdaSequence
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
    TMCC1SwitchCommandEnum,
)


def _signature(program):
    return [(req.command, req.scope, req.address) for req in program.presses]


class TestAsc2:
    def test_acc_eight_id(self):
        program = build_program(reg.ASC2, reg.ASC2.mode("acc_8"), 9)
        assert _signature(program) == [
            (TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC, 9),
            (TMCC1AuxCommandEnum.AUX_NUMBER_0, CommandScope.ACC, 9),
        ]

    def test_acc_single_id(self):
        program = build_program(reg.ASC2, reg.ASC2.mode("acc_1"), 9)
        assert _signature(program)[1] == (TMCC1AuxCommandEnum.AUX_NUMBER_1, CommandScope.ACC, 9)

    def test_sw_momentary(self):
        program = build_program(reg.ASC2, reg.ASC2.mode("sw_momentary"), 20)
        assert _signature(program) == [
            (TMCC1SwitchCommandEnum.SET_ADDRESS, CommandScope.SWITCH, 20),
            (TMCC1SwitchCommandEnum.THRU, CommandScope.SWITCH, 20),
        ]

    def test_sw_latching(self):
        program = build_program(reg.ASC2, reg.ASC2.mode("sw_latching"), 20)
        assert _signature(program)[1] == (TMCC1SwitchCommandEnum.OUT, CommandScope.SWITCH, 20)


class TestBpc2:
    def test_train_restore_on(self):
        mode = reg.BPC2.mode("tr_8")
        program = build_program(reg.BPC2, mode, 12, {"restore": True})
        assert _signature(program) == [
            (TMCC1EngineCommandEnum.SET_ADDRESS, CommandScope.TRAIN, 12),
            (TMCC1EngineCommandEnum.REAR_COUPLER, CommandScope.TRAIN, 12),
            (TMCC1EngineCommandEnum.AUX_NUMBER_0, CommandScope.TRAIN, 12),
        ]
        assert "Coupler R (restore on)" in program.display[1]

    def test_train_restore_off_omits_coupler(self):
        mode = reg.BPC2.mode("tr_8")
        program = build_program(reg.BPC2, mode, 12, {"restore": False})
        assert _signature(program) == [
            (TMCC1EngineCommandEnum.SET_ADDRESS, CommandScope.TRAIN, 12),
            (TMCC1EngineCommandEnum.AUX_NUMBER_0, CommandScope.TRAIN, 12),
        ]
        assert not any("Coupler" in line for line in program.display)

    def test_restore_defaults_off(self):
        program = build_program(reg.BPC2, reg.BPC2.mode("tr_8"), 12)
        assert len(program.presses) == 2

    def test_accessory_scope(self):
        program = build_program(reg.BPC2, reg.BPC2.mode("acc_8"), 64, {"restore": True})
        assert _signature(program) == [
            (TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC, 64),
            (TMCC1AuxCommandEnum.REAR_COUPLER, CommandScope.ACC, 64),
            (TMCC1AuxCommandEnum.AUX_NUMBER_0, CommandScope.ACC, 64),
        ]


class TestStm2:
    def test_single_wire(self):
        program = build_program(reg.STM2, reg.STM2.mode("single_wire"), 33)
        assert _signature(program) == [
            (TMCC1SwitchCommandEnum.SET_ADDRESS, CommandScope.SWITCH, 33),
            (TMCC1SwitchCommandEnum.THRU, CommandScope.SWITCH, 33),
        ]

    def test_two_wire(self):
        program = build_program(reg.STM2, reg.STM2.mode("two_wire"), 33)
        assert _signature(program)[1] == (TMCC1SwitchCommandEnum.OUT, CommandScope.SWITCH, 33)


class TestSensorTrack:
    @pytest.mark.parametrize("digit", list(range(10)))
    def test_every_action(self, digit):
        mode = reg.SENSOR_TRACK.modes[0]
        program = build_program(reg.SENSOR_TRACK, mode, 3, {"action": IrdaSequence(digit)})
        assert _signature(program) == [
            (TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC, 3),
            (reg.ACC_AUX_NUMBERS[digit], CommandScope.ACC, 3),
        ]
        assert program.display[1].startswith(f"2. AUX1 then {digit}")

    def test_action_press_never_omitted_by_default(self):
        program = build_program(reg.SENSOR_TRACK, reg.SENSOR_TRACK.modes[0], 3)
        assert len(program.presses) == 2
        assert program.presses[1].command == TMCC1AuxCommandEnum.AUX_NUMBER_0


class TestVerifyAndDisplay:
    def test_verify_requests(self):
        program = build_program(reg.ASC2, reg.ASC2.mode("acc_8"), 9)
        expected = [reg.ASC2.pdi_device.config(9).as_bytes, reg.ASC2.pdi_device.info(9).as_bytes]
        assert [req.as_bytes for req in program.verify] == expected

    def test_display_order_matches_presses(self):
        program = build_program(reg.BPC2, reg.BPC2.mode("tr_8"), 12, {"restore": True})
        assert len(program.display) == len(program.presses)
        assert program.display[0] == "1. TR 12 SET"
        assert program.display[2].startswith("3. AUX1 then 0")

    def test_program_instruction(self):
        assert "PGM" in build_program(reg.ASC2, reg.ASC2.mode("acc_8"), 9).program_instruction
        st = build_program(reg.SENSOR_TRACK, reg.SENSOR_TRACK.modes[0], 3)
        assert "PROGRAM" in st.program_instruction


class TestValidation:
    def test_mode_must_belong_to_device(self):
        with pytest.raises(ValueError):
            build_program(reg.STM2, reg.ASC2.mode("acc_8"), 9)

    @pytest.mark.parametrize("base_id", [0, 99, -1])
    def test_bad_base_id(self, base_id):
        with pytest.raises(ValueError):
            build_program(reg.ASC2, reg.ASC2.mode("acc_8"), base_id)

    def test_base_id_above_max_base(self):
        with pytest.raises(ValueError):
            build_program(reg.ASC2, reg.ASC2.mode("acc_8"), 92)
        assert build_program(reg.ASC2, reg.ASC2.mode("acc_8"), 91).base_id == 91

    def test_required_option_missing(self):
        with pytest.raises(ValueError):
            build_program(reg.SENSOR_TRACK, reg.SENSOR_TRACK.modes[0], 3, {"action": None})
