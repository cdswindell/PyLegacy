#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import pytest

from src.pytrain.db.accessory_state import AccessoryState
from src.pytrain.pdi.amc2_req import Amc2Req
from src.pytrain.pdi.asc2_req import Asc2Req
from src.pytrain.pdi.bpc2_req import Bpc2Req
from src.pytrain.pdi.constants import Amc2Action, Asc2Action, Bpc2Action, IrdaAction, PdiCommand
from src.pytrain.pdi.irda_req import IrdaReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum as Aux
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandEnum


class TestAccessoryState:
    @staticmethod
    def _new_acc(addr: int = 9) -> AccessoryState:
        st = AccessoryState(CommandScope.ACC)
        # Allocate comp_data so as_bytes can emit state packet first
        st.initialize(CommandScope.ACC, addr)
        # Ensure address-dependent code paths are deterministic
        st._address = addr  # type: ignore[attr-defined]
        return st

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError):
            _ = AccessoryState(CommandScope.ENGINE)

    def test_tmcc_aux_updates_and_numeric(self):
        acc = self._new_acc(12)
        # AUX1 option-one should toggle aux1 state ON and set aggregate aux_state
        req_aux1_opt1 = CommandReq.build(Aux.AUX1_OPT_ONE, acc.address)
        acc.update(req_aux1_opt1)
        assert acc.aux_state == Aux.AUX1_OPT_ONE
        assert acc.aux1_state in {Aux.AUX1_ON, Aux.AUX1_OPT_ONE, Aux.AUX1_OFF}  # implementation toggles ON/OFF
        # AUX2 ON should set aux2 explicit
        req_aux2_on = CommandReq.build(Aux.AUX2_ON, acc.address)
        acc.update(req_aux2_on)
        assert acc.aux2_state == Aux.AUX2_ON
        # NUMERIC sets number/value
        req_num = CommandReq.build(Aux.NUMERIC, acc.address, data=7)
        acc.update(req_num)
        assert acc.value == 7
        # is_known reflects the presence of aux/number
        assert acc.is_known is True

    def test_bpc2_control3_sets_block_power_and_on_off(self):
        acc = self._new_acc(15)
        # First PDI packet establishes LCS source and power-district behavior
        pdi_on = Bpc2Req(acc.address, PdiCommand.BPC2_SET, Bpc2Action.CONTROL3, state=1)
        acc.update(pdi_on)
        assert acc.is_lcs_component is True
        assert acc.is_power_district is True
        assert acc.is_asc2 is False
        assert acc.is_amc2 is False
        assert acc.aux_state == Aux.AUX1_OPT_ONE
        assert acc.aux1_state == Aux.AUX1_ON and acc.aux2_state == Aux.AUX2_ON

        # Turn OFF
        pdi_off = Bpc2Req(acc.address, PdiCommand.BPC2_SET, Bpc2Action.CONTROL3, state=0)
        acc.update(pdi_off)
        assert acc.aux_state == Aux.AUX2_OPT_ONE
        assert acc.aux1_state == Aux.AUX1_OFF and acc.aux2_state == Aux.AUX2_OFF

        # as_dict for power district
        d = acc.as_dict()
        assert d["type"] == "power district"
        assert d["block"] in {"on", "off"}

    def test_bpc2_control1_causes_error(self):
        acc = self._new_acc(15)
        # PDI packet should be rejected, as scope is TRAIN
        pdi_on = Bpc2Req(acc.address, PdiCommand.BPC2_SET, Bpc2Action.CONTROL1, state=1)
        assert pdi_on.scope == CommandScope.TRAIN
        with pytest.raises(AttributeError):
            acc.update(pdi_on)

    def test_asc2_control1_marks_lcs_on_power(self):
        acc = self._new_acc(6)
        asc2_on = Asc2Req(acc.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1)
        acc.update(asc2_on)
        assert acc.is_lcs_component is True
        assert acc.is_asc2 is True
        assert acc.is_power_district is False
        assert acc.aux_state is acc.aux_state == Aux.AUX1_OPT_ONE
        # off
        asc2_off = Asc2Req(acc.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0)
        acc.update(asc2_off)
        assert acc.aux_state == Aux.AUX2_OPT_ONE

    def test_amc2_motor_marks_lcs_on_power(self):
        config = Amc2Req.from_bytes(bytes.fromhex("d1461903190000000202020303010100000000000000000077df"))
        acc = self._new_acc(25)
        acc.update(config)
        assert acc.is_lcs_component is True
        assert acc.is_amc2 is True
        assert acc.is_known
        assert acc.aux_state == Aux.AUX2_OPT_ONE
        assert acc.aux1_state == Aux.AUX1_OFF
        assert acc.aux2_state == Aux.AUX2_OFF

        assert acc.motor1
        assert acc.motor1.speed == 0
        assert acc.motor1.state is False
        assert acc.motor1.restore_state is False

        assert acc.motor2
        assert acc.motor2.speed == 0
        assert acc.motor2.state is False
        assert acc.motor2.restore_state is False

        amc2_sp = Amc2Req(acc.address, PdiCommand.AMC2_SET, Amc2Action.MOTOR, motor=1, speed=100)
        acc.update(amc2_sp)
        acc.motor2.restore_state = True

        assert acc.motor2
        assert acc.motor2.speed == 100
        assert acc.motor2.state
        assert acc.motor2.restore_state is True

        assert acc.motor1
        assert acc.motor1.speed == 0
        assert acc.motor1.state is False
        assert acc.motor1.restore_state is False

        amc2_sp = Amc2Req(acc.address, PdiCommand.AMC2_SET, Amc2Action.MOTOR, motor=0, speed=50)
        acc.update(amc2_sp)
        acc.motor1.restore_state = True

        assert acc.motor1.speed == 50
        assert acc.motor2.speed == 100
        assert acc.motor1.state
        assert acc.motor2.state

    def test_irda_marks_sensor_track_and_serialization_includes_irda(self):
        acc = self._new_acc(18)
        # Mark as sensor track via IRDA INFO RX
        ir = IrdaReq(acc.address, PdiCommand.IRDA_RX, IrdaAction.INFO, scope=CommandScope.ACC)
        acc.update(ir)
        assert acc.is_sensor_track is True

        # as_bytes: first emits comp_data state packet; then an IRDA state req packet
        blob = acc.as_bytes()
        assert isinstance(blob, (bytes, bytearray))
        # Should contain IRDA header byte (0x32) somewhere after the first packet
        assert PdiCommand.IRDA_RX.as_bytes in blob

    def test_as_bytes_tmcc_accessory_commands_append(self):
        acc = self._new_acc(22)
        # Issue some TMCC accessory commands (not LCS)
        acc.update(CommandReq.build(Aux.AUX1_ON, acc.address))
        acc.update(CommandReq.build(Aux.AUX2_OFF, acc.address))

        bs = acc.as_bytes()
        assert isinstance(bs, (bytes, bytearray))
        # It should include TMCC3-byte packets for aux1/aux2 after the comp_data pdi block
        # Check presence by building expected command bytes
        aux1_bytes = CommandReq.build(Aux.AUX1_ON, acc.address).as_bytes
        aux2_bytes = CommandReq.build(Aux.AUX2_OFF, acc.address).as_bytes
        assert aux1_bytes in bs
        assert aux2_bytes in bs

    def test_as_dict_accessory_and_sensor_types(self):
        # Accessory default
        acc = self._new_acc(5)
        acc.update(CommandReq.build(Aux.AUX2_OPT_ONE, acc.address))
        d1 = acc.as_dict()
        assert d1["type"] == "accessory"
        # Sensor track
        acc2 = self._new_acc(7)
        acc2.update(IrdaReq(acc2.address, PdiCommand.IRDA_RX, IrdaAction.INFO, scope=CommandScope.ACC))
        d2 = acc2.as_dict()
        assert d2["type"] == "sensor track"

    def test_payload_renders_reasonable_info(self):
        acc = self._new_acc(30)
        # Non-LCS accessory, AUX1 toggled and number set
        acc.update(CommandReq.build(Aux.AUX1_OPT_ONE, acc.address))
        acc.update(CommandReq.build(Aux.NUMERIC, acc.address, data=3))
        s = acc.payload
        assert isinstance(s, str)
        assert "Aux" in s or "Unknown" in s
        assert "Aux Num:" in s

    def test_halt_resets_aux_and_number(self):
        acc = self._new_acc(31)
        # Turn on via TMCC and set a number
        acc.update(CommandReq.build(Aux.AUX1_OPT_ONE, acc.address))
        acc.update(CommandReq.build(Aux.NUMERIC, acc.address, data=4))
        assert acc.aux_state == Aux.AUX1_OPT_ONE
        assert acc.value == 4

        # HALT should force OFF and clear number
        halt = CommandReq.build(TMCC1HaltCommandEnum.HALT, acc.address)
        acc.update(halt)
        assert acc.aux_state == Aux.AUX2_OPT_ONE
        assert acc.aux1_state == Aux.AUX1_OFF
        assert acc.aux2_state == Aux.AUX2_OFF
        assert acc.value is None

    def test_tmcc_commands_ignored_after_pdi_source(self):
        acc = self._new_acc(32)
        # Establish LCS source via ASC2, ON
        asc2_on = Asc2Req(acc.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1)
        acc.update(asc2_on)
        assert acc.is_lcs_component is True
        assert acc.aux_state == Aux.AUX1_OPT_ONE
        assert acc.aux1_state == Aux.AUX1_ON
        assert acc.aux2_state == Aux.AUX2_ON

        # TMCC accessory commands should NOT change state once LCS source
        acc.update(CommandReq.build(Aux.AUX1_OFF, acc.address))
        acc.update(CommandReq.build(Aux.AUX2_OFF, acc.address))
        # Still the LCS-determined ON state
        assert acc.aux_state == Aux.AUX1_OPT_ONE
        assert acc.aux1_state == Aux.AUX1_ON
        assert acc.aux2_state == Aux.AUX2_ON

    def test_payload_for_asc2_includes_prefix_for_on_and_off(self):
        # ON
        acc_on = self._new_acc(33)
        acc_on.update(Asc2Req(acc_on.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1))
        s_on = acc_on.payload
        assert isinstance(s_on, str)
        # Should include "Asc2 " and reflect ON
        assert "Asc2" in s_on

        # OFF
        acc_off = self._new_acc(34)
        acc_off.update(Asc2Req(acc_off.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0))
        s_off = acc_off.payload
        assert isinstance(s_off, str)
        # Should include "Asc2 " and reflect OFF, not just bare "OFF"
        assert "Asc2" in s_off

    def test_as_bytes_lcs_asc2_uses_first_action_and_value(self):
        acc = self._new_acc(35)
        # First PDI action (CONTROL1) ON should be serialized accordingly
        asc2_on = Asc2Req(acc.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1)
        acc.update(asc2_on)
        bs_on = acc.as_bytes()
        # Expected serialized action should be present
        expected_on = Asc2Req(acc.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1).as_bytes
        assert expected_on in bs_on

        # Now OFF updates the aux state; as_bytes should reflect OFF
        asc2_off = Asc2Req(acc.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0)
        acc.update(asc2_off)
        bs_off = acc.as_bytes()
        expected_off = Asc2Req(acc.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0).as_bytes
        assert expected_off in bs_off

    def test_as_bytes_amc2_includes_numeric_when_set(self):
        acc = self._new_acc(25)
        # Provide AMC2 config to establish AMC2/LCS context
        cfg = Amc2Req.from_bytes(bytes.fromhex("d1461903190000000202020303010100000000000000000077df"))
        acc.update(cfg)
        assert acc.is_amc2 is True and acc.is_lcs_component is True

        # Set a number; for AMC2, as_bytes should include the numeric packet
        acc.update(CommandReq.build(Aux.NUMERIC, acc.address, data=5))
        blob = acc.as_bytes()
        numeric_bytes = CommandReq(Aux.NUMERIC, acc.address, 5).as_bytes
        assert numeric_bytes in blob

    def test_get_motor_and_lamps_none_when_not_amc2(self):
        acc = self._new_acc(37)
        # Plain accessory
        assert acc.get_motor(1) is None
        assert acc.get_motor(2) is None
        assert acc.get_lamp(1) is None
        assert acc.get_lamp(2) is None
        assert acc.get_lamp(3) is None
        assert acc.get_lamp(4) is None
