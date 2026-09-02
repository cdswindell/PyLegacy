from __future__ import annotations

import re

import pytest

import src.pytrain.gui.controller.lcs_device_registry as reg
from src.pytrain.gui.controller.engine_gui_conf import SENSOR_TRACK_OPTS
from src.pytrain.pdi.irda_req import IrdaSequence
from src.pytrain.pdi.pdi_device import PdiDevice
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum, TMCC1EngineCommandEnum


class TestRegistryShape:
    def test_the_registry_knows_five_modules(self):
        assert tuple(d.key for d in reg.LCS_DEVICES) == ("asc2", "bpc2", "stm2", "sensor_track", "amc2")

    def test_four_of_them_can_be_programmed(self):
        assert tuple(d.key for d in reg.configurable_devices()) == ("asc2", "bpc2", "sensor_track", "stm2")

    def test_they_are_offered_in_name_order(self):
        # The device page opens on the first of them, so the order has to be predictable.
        labels = [d.label for d in reg.configurable_devices()]
        assert labels == sorted(labels, key=str.upper)
        assert labels[0] == "ASC2"

    def test_the_recognition_order_is_left_alone(self):
        # LCS_DEVICES is walked to identify a module from its state flags. A module this
        # pass cannot program must not be recognized ahead of one it can, so it stays last
        # however the presentation order is sorted.
        assert reg.LCS_DEVICES[-1] is reg.AMC2

    def test_every_mode_is_complete(self):
        for device in reg.configurable_devices():
            assert device.modes
            for mode in device.modes:
                assert isinstance(mode.scope, CommandScope)
                assert mode.ports >= 1
                assert mode.presses, f"{device.key}/{mode.key} declares no presses"

    def test_asc2_has_four_modes(self):
        assert len(reg.ASC2.modes) == 4
        assert [m.ports for m in reg.ASC2.modes] == [8, 1, 4, 4]
        assert [m.pdi_mode for m in reg.ASC2.modes] == [0, 1, 2, 3]
        assert [m.scope for m in reg.ASC2.modes] == [
            CommandScope.ACC,
            CommandScope.ACC,
            CommandScope.SWITCH,
            CommandScope.SWITCH,
        ]

    def test_bpc2_one_id_modes_are_reserved(self):
        for key in ("tr_1", "acc_1"):
            mode = reg.BPC2.mode(key)
            assert mode.enabled is False
            assert mode.note == "reserved, no Cab support"
        assert [m.key for m in reg.enabled_modes(reg.BPC2)] == ["tr_8", "acc_8"]
        assert reg.BPC2.mode("tr_8").scope == CommandScope.TRAIN
        assert reg.BPC2.mode("acc_8").scope == CommandScope.ACC

    def test_stm2_modes(self):
        assert reg.STM2.mode("single_wire").ports == 16
        assert reg.STM2.mode("two_wire").ports == 8
        assert all(m.scope == CommandScope.SWITCH for m in reg.STM2.modes)

    def test_pdi_devices(self):
        assert reg.ASC2.pdi_device == PdiDevice.ASC2
        assert reg.BPC2.pdi_device == PdiDevice.BPC2
        assert reg.STM2.pdi_device == PdiDevice.STM2
        assert reg.SENSOR_TRACK.pdi_device == PdiDevice.IRDA


class TestSensorTrack:
    def test_single_acc_mode(self):
        assert len(reg.SENSOR_TRACK.modes) == 1
        mode = reg.SENSOR_TRACK.modes[0]
        assert mode.scope == CommandScope.ACC
        assert mode.ports == 1
        assert mode.pdi_mode is None

    def test_action_choices_track_sensor_track_opts(self):
        option = reg.SENSOR_TRACK.option("action")
        assert option.required is True
        assert option.kind == reg.OptionKind.RADIO
        assert len(option.choices) == 10
        assert [label for label, _ in option.choices] == [label for label, _ in SENSOR_TRACK_OPTS]
        assert [value.value for _, value in option.choices] == list(range(10))
        assert all(isinstance(value, IrdaSequence) for _, value in option.choices)

    def test_default_action_is_no_action(self):
        assert reg.SENSOR_TRACK.option("action").default == IrdaSequence.NONE


class TestMaxBase:
    @pytest.mark.parametrize(
        "device, mode_key, expected",
        [
            (reg.ASC2, "acc_8", 91),
            (reg.ASC2, "acc_1", 98),
            (reg.ASC2, "sw_momentary", 95),
            (reg.ASC2, "sw_latching", 95),
            (reg.STM2, "single_wire", 83),
            (reg.STM2, "two_wire", 91),
            (reg.SENSOR_TRACK, "acc", 98),
        ],
    )
    def test_max_base(self, device, mode_key, expected):
        mode = device.mode(mode_key)
        assert reg.max_base(mode) == expected
        assert mode.max_base == expected

    def test_never_above_98(self):
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                assert 1 <= reg.max_base(mode) <= 98


class TestAmc2:
    """
    Recognized so that the panel can name it and count the TMCC IDs it holds, but not
    programmable until its modes and presses are written.
    """

    def test_it_is_in_the_registry(self):
        assert reg.AMC2 in reg.LCS_DEVICES
        assert reg.AMC2.label == "AMC2"
        assert reg.AMC2.pdi_device == PdiDevice.AMC2

    def test_it_is_not_offered_as_a_choice(self):
        assert reg.AMC2.configurable is False
        assert reg.AMC2 not in reg.configurable_devices()

    def test_it_declares_no_modes_yet(self):
        assert reg.AMC2.modes == ()
        # Asking for a mode it does not have says why rather than raising IndexError.
        with pytest.raises(ValueError, match="no modes"):
            _ = reg.AMC2.default_mode

    def test_it_is_recognized_from_its_own_state_flag(self):
        class _Amc2:
            is_asc2 = False
            is_bpc2 = False
            is_stm2 = False
            is_sensor_track = False
            is_amc2 = True

        assert reg.device_for_state(_Amc2()) is reg.AMC2

    def test_every_other_module_is_still_programmable(self):
        assert all(device.configurable for device in reg.LCS_DEVICES if device is not reg.AMC2)


class TestLookups:
    def test_device_for_key(self):
        assert reg.device_for_key("bpc2") is reg.BPC2
        # Recognized modules are found by key too; only an unknown key raises.
        assert reg.device_for_key("amc2") is reg.AMC2
        with pytest.raises(ValueError):
            reg.device_for_key("asc3")

    def test_device_for_state(self):
        class _State:
            is_asc2 = False
            is_bpc2 = True
            is_stm2 = False
            is_sensor_track = False

        assert reg.device_for_state(_State()) is reg.BPC2
        assert reg.device_for_state(None) is None
        assert reg.device_for_state(object()) is None

    def test_devices_for_state_names_every_module_a_shared_record_identifies(self):
        # A component state is keyed by scope and address alone, so an AMC2 and a BPC2 both
        # answering to ACC 1 leave one record carrying both flags.
        class _Shared:
            is_asc2 = False
            is_bpc2 = True
            is_stm2 = False
            is_sensor_track = False
            is_amc2 = True

        assert reg.devices_for_state(_Shared()) == (reg.BPC2, reg.AMC2)
        assert reg.devices_for_state(None) == ()
        assert reg.devices_for_state(object()) == ()

    def test_device_for_pdi_device(self):
        assert reg.device_for_pdi_device(PdiDevice.IRDA) is reg.SENSOR_TRACK
        assert reg.device_for_pdi_device(PdiDevice.AMC2) is reg.AMC2
        assert reg.device_for_pdi_device(PdiDevice.BASE) is None

    def test_mode_for_pdi_mode(self):
        assert reg.ASC2.mode_for_pdi_mode(3).key == "sw_latching"
        assert reg.ASC2.mode_for_pdi_mode(7) is None

    def test_default_mode_skips_disabled(self):
        assert reg.BPC2.default_mode.key == "tr_8"

    def test_unknown_option_raises(self):
        with pytest.raises(ValueError):
            reg.ASC2.option("restore")


class TestAuxNumber:
    def test_acc_scope(self):
        assert reg.aux_number(0, CommandScope.ACC) == TMCC1AuxCommandEnum.AUX_NUMBER_0
        assert reg.aux_number(9, CommandScope.ACC) == TMCC1AuxCommandEnum.AUX_NUMBER_9

    def test_train_scope(self):
        assert reg.aux_number(0, CommandScope.TRAIN) == TMCC1EngineCommandEnum.AUX_NUMBER_0

    def test_invalid(self):
        with pytest.raises(ValueError):
            reg.aux_number(10, CommandScope.ACC)
        with pytest.raises(ValueError):
            reg.aux_number(1, CommandScope.SWITCH)


class TestModeLabels:
    """
    The label conventions the module docstring sets out: the addressing mode carries its
    Cab key inside the word, counts are digits, and what is counted is TMCC IDs.
    """

    EXPECTED = {
        "asc2": (
            "ACCessory, 8 TMCC IDs",
            "ACCessory, 1 TMCC ID",
            "SWitch, momentary, 4 TMCC IDs",
            "SWitch, latching, 4 TMCC IDs",
        ),
        "bpc2": ("TRack, 8 TMCC IDs", "TRack, 1 TMCC ID", "ACCessory, 8 TMCC IDs", "ACCessory, 1 TMCC ID"),
        "stm2": ("SWitch, single-wire, 16 TMCC IDs", "SWitch, two-wire, 8 TMCC IDs"),
        "sensor_track": ("ACCessory TMCC ID and Action Command",),
    }

    def test_every_label_is_as_the_operator_reads_it(self):
        assert {d.key: tuple(m.label for m in d.modes) for d in reg.configurable_devices()} == self.EXPECTED

    def test_an_id_is_always_a_tmcc_id(self):
        # A bare "ID" is ambiguous beside a PDI address or a port number.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                assert not re.findall(r"(?<!TMCC )\bIDs?\b", mode.label), f"{device.key}/{mode.key}: {mode.label}"

    NUMBER_WORDS = ("one", "single", "two", "three", "four", "five", "six", "seven", "eight", "sixteen")

    def test_a_count_is_a_digit(self):
        # "Eight ID" was the old spelling; a digit is read at a glance.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                for word in re.findall(r"(\w+)\s+TMCC IDs?\b", mode.label):
                    assert word.lower() not in self.NUMBER_WORDS, f"{device.key}/{mode.key}: {mode.label}"

    def test_a_counted_label_agrees_with_the_mode(self):
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                counted = re.search(r"(\d+) TMCC IDs?\b", mode.label)
                if counted:
                    assert int(counted.group(1)) == mode.ports, f"{device.key}/{mode.key}: {mode.label}"

    def test_every_switch_mode_names_the_ids_it_consumes(self):
        # A switch mode reserves a block just as an accessory mode does, and an operator
        # laying out switch IDs has to know how many of them go with the choice.
        for device in reg.configurable_devices():
            for mode in device.modes:
                if mode.scope != CommandScope.SWITCH:
                    continue
                assert re.search(rf"\b{mode.ports} TMCC IDs?\b", mode.label), f"{device.key}/{mode.key}"
