"""
The LCS device registry: its shape, its lookups, and the conventions it names modes by.

No mode's wording is written down here. A mode's name, its qualifier, its note and both
of its labels are read off the registry and asserted as *compositions* -- a label is the
mode's own name and the registry's one spelling of the block it claims, in that order --
so renaming a mode or rewording a note needs no edit in this file, while a mode that
breaks a naming rule fails wherever it is added.

Two pieces of vocabulary are written down, both deliberately and both in one place each:

* TestModeNames.CAB_KEYS -- ACC, SW, TR and ENG, which are printed on the Cab remote
  rather than chosen by this project.
* "TMCC ID" / "TMCC IDs", asserted by the rule tests in TestTmccIdText and
  TestModeLabels: the registry's docstring insists that what is counted is always a
  TMCC ID, never bare "IDs" and never "ports", and a convention is worth nothing if no
  test knows what it says.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

import src.pytrain.gui.controller.lcs_device_registry as reg
from src.pytrain.gui.controller.engine_gui_conf import SENSOR_TRACK_OPTS
from src.pytrain.pdi.amc2_req import AccessType, Amc2Motor, Amc2Req, Direction, OutputType
from src.pytrain.pdi.constants import Amc2Action, PdiCommand
from src.pytrain.pdi.irda_req import IrdaAction, IrdaSequence
from src.pytrain.pdi.pdi_device import PdiDevice
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum, TMCC1EngineCommandEnum


# noinspection PyProtectedMember
def amc2_config(tmcc_id: int = 5, access_type: AccessType = AccessType.ACC) -> Amc2Req:
    """A populated AMC2 CONFIG packet, as an AMC2 answers with one.

    Round-tripped through the module's own encoder, which is what puts real motors on it:
    the request built to *ask* for a config carries none, and an AMC2 reports each motor's
    settings on the motor itself, so a record without them answers nothing about either.
    The module's own class rather than a stand-in, because what is read off it here is what
    an AMC2 says about itself, and a fake would agree with the registry by construction.
    """
    request = Amc2Req(tmcc_id, PdiCommand.AMC2_RX, Amc2Action.CONFIG)
    request._access_type = access_type
    request._motor1 = Amc2Motor(1, OutputType.DELTA, Direction.FORWARD, True, False, 30)
    request._motor2 = Amc2Motor(2, OutputType.AC, Direction.AC, False, False, 0)
    return Amc2Req(request.as_bytes)


def config_record(device: reg.LcsDevice) -> Any:
    """
    The CONFIG record a module answers with, populated where the module needs it to be.
    """
    return amc2_config() if device is reg.AMC2 else device.pdi_device.config(1)


class TestRegistryShape:
    def test_the_registry_knows_five_modules(self):
        assert tuple(d.key for d in reg.LCS_DEVICES) == ("asc2", "bpc2", "stm2", "sensor_track", "amc2")

    def test_every_one_of_them_can_be_programmed(self):
        # The AMC2's modes and presses were the last to be written, so the flag for a module
        # the panel can name but not program is carried by nothing today. It stays for the
        # next module met on a layout before its manual has been read; see TestLookups.
        assert tuple(d.key for d in reg.configurable_devices()) == ("amc2", "asc2", "bpc2", "sensor_track", "stm2")
        assert all(device.configurable for device in reg.LCS_DEVICES)

    def test_they_are_offered_in_name_order(self):
        # The device page opens on the first of them, so the order has to be predictable.
        labels = [d.label for d in reg.configurable_devices()]
        assert labels == sorted(labels, key=str.upper)
        # Named by identity rather than by label, so a module renamed on the page is not a
        # test to fix -- what matters is which module the panel opens on.
        assert reg.configurable_devices()[0] is reg.AMC2

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
        reserved = [reg.BPC2.mode(key) for key in ("tr_1", "acc_1")]
        for mode in reserved:
            assert mode.enabled is False
            # Each says why it is not on offer -- the panel prints those words in its
            # "Not available" line -- and both say the same thing, since it is the same
            # reason. The sentence itself is the registry's to change.
            assert mode.note
        assert len({mode.note for mode in reserved}) == 1
        # ACC first: the manual numbers the modes the other way about, but the two are
        # identical in what they can do, so the order the rows are offered in is the
        # panel's to choose -- and it is chosen here, once, for the radios and the legend
        # and the row the page opens on alike.
        assert [m.key for m in reg.enabled_modes(reg.BPC2)] == ["acc_8", "tr_8"]
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

    def test_the_action_command_is_reported_as_the_sequence_of_the_config_record(self):
        # The option's key is the word the press is built from -- the mode's AUX1 press takes
        # its digit from "action" -- while the module reports the setting as the sequence
        # field of its own IRDA CONFIG record. Read by the key, the record answers with the
        # flavor it was built as, which is no Action Command at all: this is what left the
        # panel opening a configured Sensor Track on "No Action".
        option = reg.SENSOR_TRACK.option("action")
        record = reg.SENSOR_TRACK.pdi_device.config(1)

        assert option.reported_as == "sequence" != option.key
        assert isinstance(getattr(record, option.key), IrdaAction)
        assert not isinstance(getattr(record, option.key), IrdaSequence)


class TestReportedFields:
    """
    Where a module reports each of its settings; see LcsOption.reported_as and reported_by.
    """

    def test_an_option_is_reported_on_its_own_key_unless_another_field_is_named(self):
        # Which is the usual case: a BPC2's restore-on-power-up flag is "restore" to the
        # panel and to Bpc2Req alike, and only a module that words a setting differently
        # from the panel has anything to declare.
        for device in reg.configurable_devices():
            for option in device.options:
                expected = option.reported_key or option.key
                assert option.reported_as == expected, f"{device.label} {option.key}"
        assert reg.BPC2.option("restore").reported_key is None

    def test_every_option_is_reported_on_a_field_its_module_really_carries(self):
        # The field is read off the module's own CONFIG record, so a name nothing answers
        # to is a setting the panel can never read -- silently, since a missing attribute
        # reads as "the module said nothing" and the option keeps its default. Checked
        # against the request class the module actually answers with, so a rename in
        # pdi/*_req.py fails here rather than out on the layout.
        #
        # Walked a name at a time rather than asked for whole: a path is only as good as
        # every step in it, and nothing answers to a dotted name. The record is populated
        # where the module reports a setting on something it carries -- an AMC2's motors
        # are absent from the request that asks for a config -- since a step that answers
        # nothing would otherwise end the walk before the field being checked.
        for device in reg.configurable_devices():
            record = config_record(device)
            for option in device.options:
                carrier = record
                for name in option.reported_as.split("."):
                    assert carrier is not None, f"{device.label} {option.key}: nothing carries {name}"
                    assert hasattr(carrier, name), f"{type(carrier).__name__}.{name}"
                    carrier = getattr(carrier, name)

    def test_a_setting_reported_one_level_down_is_read_through_the_whole_path(self):
        # The AMC2 keeps each motor's settings on the motor itself, so what it calls the
        # field is a path and not a name -- and one path reads its CONFIG packet and the
        # accessory state built from that packet alike. Read a level too shallow, the
        # option would come back holding an entire motor and the panel would put it to a
        # radio row.
        packet = amc2_config()

        assert reg.AMC2.option("motor1_mode").reported_as == "motor1.output_type" != "motor1_mode"
        assert reg.AMC2.option("motor1_mode").reported_by(packet) is packet.motor1.output_type
        assert reg.AMC2.option("motor2_mode").reported_by(packet) is packet.motor2.output_type
        assert reg.AMC2.option("motor1_restore").reported_by(packet) is packet.motor1.restore is True
        assert reg.AMC2.option("motor2_restore").reported_by(packet) is packet.motor2.restore is False

    def test_an_option_that_names_no_field_is_read_by_its_own_key(self):
        # A path of one name is simply a field on the record, which is what every other
        # module's settings are: the option's own key, since only a module that words a
        # setting differently from the panel has anything to declare.
        plain = reg.LcsOption(key="restore", label="Remember", kind=reg.OptionKind.CHECKBOX)
        motor = amc2_config().motor1

        assert plain.reported_as == plain.key
        assert plain.reported_by(motor) is motor.restore is True

    def test_a_path_that_runs_out_partway_reports_nothing(self):
        # Which is what the request that asks for a config is -- no motors on it at all --
        # and what a record of some other flavor is. Nothing to report is not a setting
        # turned off, and the alternative to answering None is an AttributeError while the
        # options page is being drawn.
        asked_for = reg.AMC2.pdi_device.config(1)

        assert asked_for.motor1 is None
        for option in reg.AMC2.options:
            assert option.reported_by(asked_for) is None, option.key
            assert option.reported_by(None) is None, option.key
            assert option.reported_by(object()) is None, option.key


class TestReportedMode:
    """
    Which field a module says its mode on, and what counts as an answer; see reported_mode.
    """

    def test_a_module_is_asked_on_the_field_it_names(self):
        # An AMC2 publishes no mode byte at all: it says which of the three address types
        # it answers to, on a field of its own naming and as an AccessType rather than as a
        # number. Asked for "mode" it says nothing, and a module reported as being in no
        # mode is read as holding the accessory address of its number whichever key it is
        # really on.
        packet = amc2_config(5, AccessType.TRAIN)

        assert reg.AMC2.reported_mode_as == "access_type" != "mode"
        assert getattr(packet, "mode", None) is None
        assert not isinstance(packet.access_type, int), "the module answers with an AccessType"
        assert reg.reported_mode(reg.AMC2, packet) == AccessType.TRAIN.value
        assert reg.AMC2.mode_for_pdi_mode(reg.reported_mode(reg.AMC2, packet)).scope == CommandScope.TRAIN

    def test_a_module_says_its_mode_on_the_mode_byte_unless_another_field_is_named(self):
        # Which is the usual case: every other module publishes a mode byte, and its own
        # request class calls it "mode" too, so only a module that words it differently has
        # anything to declare.
        for device in reg.LCS_DEVICES:
            expected = device.reported_mode_key or "mode"
            assert device.reported_mode_as == expected, device.label
        assert reg.BPC2.reported_mode_key is None
        assert reg.BPC2.reported_mode_as == "mode"

    def test_a_record_that_says_nothing_reports_no_mode(self):
        # A module that has not answered yet, or one whose record carries no mode: read as
        # a mode nobody knows rather than as mode 0, which is a real mode of every module
        # in the registry and a block of eight addresses on two of them.
        assert reg.reported_mode(reg.BPC2, None) is None
        assert reg.reported_mode(reg.BPC2, object()) is None
        assert reg.reported_mode(reg.AMC2, reg.AMC2.pdi_device.config(1)) is None
        assert reg.BPC2.mode_for_pdi_mode(0).ports == 8, "which is what mode 0 would have claimed"

    def test_a_flag_is_not_a_mode(self):
        # A bool is an int in Python, so a record whose named field turns out to be a flag
        # would be understood as reporting mode 0 or mode 1 -- both real modes -- and the
        # module reported on whichever remote key that mode is on, sized to it.
        class _Flagged:
            mode = True

        assert reg.reported_mode(reg.BPC2, _Flagged()) is None
        assert reg.BPC2.mode_for_pdi_mode(1) is not None, "which is what a True would have been read as"


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
    The motor controller: one address for the whole module, two motors set up on it in a
    single gesture, and its own words for everything -- which is why it is the module the
    reported_as and reported_mode_as accessors exist for.
    """

    def test_it_is_in_the_registry(self):
        assert reg.AMC2 in reg.LCS_DEVICES
        # Named, because the panel reports it in the Currently Assigned box; which name is
        # the registry's business.
        assert reg.AMC2.label
        assert reg.AMC2.pdi_device == PdiDevice.AMC2

    def test_it_is_offered_as_a_choice(self):
        assert reg.AMC2.configurable is True
        assert reg.AMC2 in reg.configurable_devices()

    def test_it_is_recognized_from_its_own_state_flag(self):
        class _Amc2:
            is_asc2 = False
            is_bpc2 = False
            is_stm2 = False
            is_sensor_track = False
            is_amc2 = True

        assert reg.device_for_state(_Amc2()) is reg.AMC2

    def test_the_accessory_key_is_the_only_one_it_is_offered_on(self):
        # One address for the whole of it -- every motor and every light on the module
        # answers to the same one, and they cannot be told apart -- so choosing the mode is
        # choosing the key alone, and there is one key the rest of PyTrain can drive an AMC2
        # on.
        offered = reg.enabled_modes(reg.AMC2)

        assert [mode.key for mode in offered] == ["acc"]
        assert reg.AMC2.default_mode is offered[0]
        assert (offered[0].scope, offered[0].ports) == (CommandScope.ACC, 1)

    def test_the_two_keys_it_will_not_be_programmed_onto_are_written_down_anyway(self):
        # Real modes, and the manual programs them with the same sequence -- but nothing
        # else in PyTrain drives an AMC2 addressed as a train or an engine, and an address
        # the rest of the program cannot reach is not one to put a module on. Recorded all
        # the same because the module has them: one already out on such a key holds its
        # address, and the panel can only say so if it knows the key exists.
        recorded = [reg.AMC2.mode(key) for key in ("tr", "eng")]

        assert [mode.scope for mode in recorded] == [CommandScope.TRAIN, CommandScope.ENGINE]
        for mode in recorded:
            assert mode.enabled is False
            # Each says why it is not on offer -- the panel prints those words in its
            # "Not available" line -- and the two differ, the keys they name being
            # different. The sentences themselves are the registry's to change.
            assert mode.note
            # The one press that opens its sequence and nothing after it: what is not
            # offered is written down truthfully rather than left as an empty gesture or
            # guessed at from the accessory sequence.
            assert len(mode.presses) == 1
            assert mode.presses[0].scope == mode.scope
        assert len({mode.note for mode in recorded}) == 2

    def test_every_mode_is_one_of_the_address_types_the_module_reports(self):
        # An AMC2 publishes no mode byte: it says which of the three address types it
        # answers to, so the number a record is matched on is that very AccessType. All
        # three are accounted for, since the type a module reports is how the panel tells
        # which key it is sitting on; see TestReportedMode.
        assert [mode.pdi_mode for mode in reg.AMC2.modes] == [
            AccessType.ACC.value,
            AccessType.TRAIN.value,
            AccessType.ENGINE.value,
        ]
        for access_type in AccessType:
            assert reg.AMC2.mode_for_pdi_mode(access_type.value) is not None, access_type

    def test_both_motors_are_set_up_in_the_one_gesture(self):
        # The manual is explicit that configuring an AMC2 "is a single operation that sets
        # three distinct features": both motors are always sent, so each mode is a required
        # choice with something to send where the operator has said nothing. The two
        # remember flags are the operator's to leave alone, which is what off is.
        assert [option.key for option in reg.AMC2.options] == [
            "motor1_mode",
            "motor1_restore",
            "motor2_mode",
            "motor2_restore",
        ]
        for motor in (1, 2):
            mode = reg.AMC2.option(f"motor{motor}_mode")
            assert mode.kind == reg.OptionKind.RADIO
            assert mode.required is True
            assert mode.default == OutputType.NORMAL
            # Every kind of output the module has, valued as the module reports them, so
            # the choice the operator makes is the setting the module reads back.
            assert [value for _, value in mode.choices] == list(OutputType)
            assert all(label for label, _ in mode.choices)
            restore = reg.AMC2.option(f"motor{motor}_restore")
            assert restore.kind == reg.OptionKind.CHECKBOX
            assert restore.default is False
            # Which motor is being answered for. The two motors take the same four rows, so
            # something has to say -- and it is the heading, which is the mode's own label,
            # standing over that motor's rows with its remember box under them. The box does
            # not say it again: naming the motor there runs the label onto a second line at
            # a smaller size, and the two of them cost the Pi's page 54px. See the wording
            # note in the registry, and the presses below, which name the motor each tap is
            # for -- that being where the two have to be told apart in the panel's own terms.
            assert mode.label == f"Motor #{motor}"
            assert reg.AMC2.options.index(restore) == reg.AMC2.options.index(mode) + 1

    def test_the_accessory_sequence_is_the_flowchart_in_order(self):
        # The address, then each motor in turn: the AUX key that names the motor with the
        # digit for its mode, and a tap of the R key after it where that motor is to
        # remember its speed. Read in order and pinned by what each press does rather than
        # by its wording, because the module reads the presses as a sequence and a step out
        # of place configures something else.
        presses = reg.AMC2.mode("acc").presses

        assert presses[0].command is TMCC1AuxCommandEnum.SET_ADDRESS
        assert [(press.aux, press.digit_from, press.include_if) for press in presses[1:]] == [
            (1, "motor1_mode", None),
            (None, None, "motor1_restore"),
            (2, "motor2_mode", None),
            (None, None, "motor2_restore"),
        ]
        assert {press.command for press in presses[2::2]} == {TMCC1AuxCommandEnum.REAR_COUPLER}
        # And each gesture names the motor it acts on. Four of the five presses would read
        # as two identical pairs on the review page otherwise, and this is where an operator
        # checks that what is about to be sent is what they answered for.
        for press, motor in zip(presses[1:], (1, 1, 2, 2)):
            assert f"#{motor}" in (press.note or ""), press.note
        # And every setting the options page offers is sent by one of them: an option no
        # press reads is one the operator answers and the module never hears about.
        assert {press.digit_from or press.include_if for press in presses[1:]} == {
            option.key for option in reg.AMC2.options
        }

    def test_the_r_key_is_tapped_only_for_a_motor_that_is_to_remember(self):
        # It is the whole of what says so -- there is no press for "forget" -- so a tap
        # sent regardless would leave every AMC2 coming back up under power.
        presses = reg.AMC2.mode("acc").presses
        defaults = {option.key: option.default for option in reg.AMC2.options}

        assert [press.include_if for press in presses if press.is_included(defaults)] == [None, None, None]
        remembering = dict(defaults, motor1_restore=True, motor2_restore=True)
        assert [press.is_included(remembering) for press in presses] == [True] * len(presses)

    def test_each_motor_is_entered_under_its_own_aux_key(self):
        # The flowchart is explicit that motor 2 is programmed under AUX2, whatever the
        # running text repeating step 6 says. Entered under the same key, both digits land
        # on motor 1 and the second overwrites the first, leaving motor 2 as it was found.
        by_option = {press.digit_from: press for press in reg.AMC2.mode("acc").presses if press.digit_from}
        options = {"motor1_mode": OutputType.AC, "motor2_mode": OutputType.DELTA}

        assert by_option["motor1_mode"].keys(options) == (
            (TMCC1AuxCommandEnum.AUX1_OPT_ONE, 0),
            (TMCC1AuxCommandEnum.NUMERIC, OutputType.AC.value + 1),
        )
        assert by_option["motor2_mode"].keys(options) == (
            (TMCC1AuxCommandEnum.AUX2_OPT_ONE, 0),
            (TMCC1AuxCommandEnum.NUMERIC, OutputType.DELTA.value + 1),
        )

    def test_the_digit_pressed_is_the_reported_setting_counted_from_one(self):
        # The manual numbers the motor modes 1, 2 and 3 and the module reports them as
        # OutputType 0, 1 and 2: the same three modes counted from a different end. The
        # option holds what the module says about itself, so the press is what makes the
        # two agree, and a digit short by one sets every motor to the mode below the one
        # the operator chose -- with 0 pressed for the first of them, which is no mode.
        press = next(item for item in reg.AMC2.mode("acc").presses if item.digit_from == "motor1_mode")
        option = reg.AMC2.option("motor1_mode")

        for _, output_type in option.choices:
            assert press.digit({"motor1_mode": output_type}) == output_type.value + 1
        assert press.digit({"motor1_mode": option.default}) == 1


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
        # The default is the first row an operator can actually pick, which is the top row
        # of the radios -- the panel opens on it where the layout has nothing to say about
        # the address. Asserted over every module the panel programs, so a reserved mode
        # listed first would not quietly become one module's default.
        for device in reg.configurable_devices():
            assert device.default_mode is reg.enabled_modes(device)[0], device.label
        assert reg.BPC2.default_mode.key == "acc_8"

    def test_unknown_option_raises(self):
        with pytest.raises(ValueError):
            reg.ASC2.option("restore")

    def test_a_module_with_no_modes_says_why_rather_than_raising_index_error(self):
        # Nothing in the registry declares none today -- the AMC2's modes were the last to
        # be written -- but a module met on a layout before its manual has been read is
        # listed for recognition's sake, and the panel asks every module it is handed for
        # the row to open on. Stood up here rather than found, so the answer is pinned
        # against the next such module rather than against the last one.
        unread = reg.LcsDevice(key="unread", label="Unread", blurb="ACC", pdi_device=PdiDevice.SER2, modes=())

        with pytest.raises(ValueError, match="no modes"):
            _ = unread.default_mode


class TestDigitKeys:
    """
    The two keys a gesture that enters a digit presses; see "How a digit is pressed" in the
    registry's docstring.
    """

    def test_an_accessory_presses_the_accessory_keys(self):
        # The AUX buttons as the accessory commands send them, and no other key of theirs:
        # AUX1 ON latches an output on, which is a module doing something rather than being
        # told something.
        assert reg.aux_key(1, CommandScope.ACC) is TMCC1AuxCommandEnum.AUX1_OPT_ONE
        assert reg.aux_key(2, CommandScope.ACC) is TMCC1AuxCommandEnum.AUX2_OPT_ONE
        assert reg.number_key(4, CommandScope.ACC) == (TMCC1AuxCommandEnum.NUMERIC, 4)

    def test_an_engine_and_a_train_are_the_same_handset_keys(self):
        # One remote and one row of buttons: a mode addressed as a train and one addressed
        # as an engine are programmed with the very same presses, which is why each names
        # the pair rather than a scope of its own. Both are keys the AMC2 has modes on.
        for key in (1, 2):
            assert reg.aux_key(key, CommandScope.TRAIN) is reg.aux_key(key, CommandScope.ENGINE)
        assert reg.aux_key(1, CommandScope.TRAIN) is TMCC1EngineCommandEnum.AUX1_OPTION_ONE
        assert reg.aux_key(2, CommandScope.TRAIN) is TMCC1EngineCommandEnum.AUX2_OPTION_ONE
        assert reg.number_key(7, CommandScope.TRAIN) == reg.number_key(7, CommandScope.ENGINE)
        assert reg.number_key(7, CommandScope.ENGINE) == (TMCC1EngineCommandEnum.NUMERIC, 7)

    def test_a_number_is_one_command_carrying_the_digit_as_its_data(self):
        # Ten digits and one command between them, answered together so that neither half
        # can be sent without the other. Ten members apiece is what the AUX1-prefixed
        # numerics were -- one command emitting its own prefix, with no AUX2-prefixed set of
        # them to be had at all, which is where the AMC2's second motor stood.
        for scope in (CommandScope.ACC, CommandScope.ENGINE, CommandScope.TRAIN):
            pressed = [reg.number_key(digit, scope) for digit in range(10)]
            assert len({command for command, _ in pressed}) == 1, scope
            assert [data for _, data in pressed] == list(range(10)), scope

    def test_there_is_no_third_aux_key(self):
        # The handset has AUX1 and AUX2 and nothing else a digit is entered under, so a
        # press naming anything else is a gesture nobody can perform: said here rather than
        # sent as whichever key it happened to land on.
        for key in (0, 3):
            with pytest.raises(ValueError):
                reg.aux_key(key, CommandScope.ACC)

    def test_a_digit_is_one_of_the_ten_on_the_handset(self):
        # Nothing above 9 can be pressed at all, and a sub-mode number the module never
        # receives leaves it in the mode it was already in.
        for digit in (-1, 10):
            with pytest.raises(ValueError):
                reg.number_key(digit, CommandScope.ACC)

    def test_a_switch_is_programmed_with_neither(self):
        # A switch is programmed with THRU and OUT: there is no AUX button and no number on
        # its keys, so a mode declaring a digit in that scope has no sequence to send.
        with pytest.raises(ValueError):
            reg.aux_key(1, CommandScope.SWITCH)
        with pytest.raises(ValueError):
            reg.number_key(1, CommandScope.SWITCH)


class TestPressSequences:
    """
    What a mode's presses come to when they are built from the module's own defaults.
    """

    def test_every_offered_mode_presses_from_its_modules_own_defaults(self):
        # The options page opens on the defaults, so a mode taking its digit from an option
        # with nothing to give -- not required, and no default -- raises the first time
        # anyone presses Configure: out on the layout, with the address already entered and
        # the module waiting. Built here, where the answer costs nothing.
        for device in reg.configurable_devices():
            defaults = {option.key: option.default for option in device.options}
            for mode in reg.enabled_modes(device):
                sent = [press for press in mode.presses if press.is_included(defaults)]
                assert sent, f"{device.key}/{mode.key} sends nothing"
                for press in sent:
                    assert press.resolved_label(defaults), f"{device.key}/{mode.key}"
                    requests = press.build(12, defaults)
                    # One request per key the gesture presses, all of them addressed to the
                    # module being programmed and on the key its mode is on.
                    assert len(requests) == len(press.keys(defaults))
                    assert all(request.address == 12 for request in requests)
                    assert all(request.scope == press.scope for request in requests)

    def test_a_gesture_that_enters_a_digit_is_two_presses_and_every_other_is_one(self):
        # The AUX button and then the number, as the manuals describe the gesture and as the
        # handset performs it. Read over every mode, offered or not, so a press that grew a
        # second key -- or lost one -- is caught wherever it is written.
        for device in reg.LCS_DEVICES:
            defaults = {option.key: option.default for option in device.options}
            for mode in device.modes:
                for press in mode.presses:
                    if not press.is_included(defaults):
                        continue
                    expected = 2 if press.aux is not None else 1
                    assert len(press.build(1, defaults)) == expected, f"{device.key}/{mode.key}: {press.label}"


class TestTmccIdText:
    """
    The one spelling of a block of addresses, read by both label forms and by the panel's
    Currently Assigned and Overlaps rows.

    Asserted by its rules rather than by repeating the phrases it builds: a block names
    both of its ends, one address is never spoken of as several, and what is counted is
    always a TMCC ID. Reword the phrase and these still hold; break one of the rules and
    they do not.
    """

    def test_a_block_is_named_by_its_two_ends(self):
        assert re.findall(r"\d+", reg.tmcc_id_text(12, 19)) == ["12", "19"]

    def test_a_single_address_is_named_once(self):
        # Given as a block of one, or with no end at all: both are one address, and an
        # operator is not shown the two ends of a block of one.
        assert reg.tmcc_id_text(12, 12) == reg.tmcc_id_text(12)
        assert re.findall(r"\d+", reg.tmcc_id_text(12)) == ["12"]

    def test_an_end_below_the_base_is_a_single_address(self):
        # Nothing builds one, but a block cannot run backwards, and the alternative is a
        # row that counts down.
        assert reg.tmcc_id_text(12, 9) == reg.tmcc_id_text(12)

    def test_a_count_is_a_digit(self):
        assert re.findall(r"\d+", reg.tmcc_id_count(8)) == ["8"]

    def test_one_address_is_never_plural(self):
        for text in (reg.tmcc_id_text(12), reg.tmcc_id_text(12, 12), reg.tmcc_id_count(1)):
            assert not re.search(r"\bIDs\b", text), text

    def test_more_than_one_address_always_is(self):
        for text in (reg.tmcc_id_text(12, 19), reg.tmcc_id_count(8)):
            assert re.search(r"\bIDs\b", text), text

    def test_what_is_counted_is_always_a_tmcc_id(self):
        # The convention the registry's docstring sets out: never bare "IDs", never
        # "ports", either of which is ambiguous beside a PDI address or a port number.
        # One of the two places in this file where a term is written down at all.
        for text in (reg.tmcc_id_text(12), reg.tmcc_id_text(12, 19), reg.tmcc_id_count(1), reg.tmcc_id_count(8)):
            assert not re.findall(r"(?<!TMCC )\bIDs?\b", text), text

    def test_a_span_is_the_same_block_with_the_words_left_off(self):
        # For the line that has already named the remote key -- "ACC 12 - 19" -- so the two
        # spellings cannot come to disagree about where a block ends.
        for base, last in ((12, 19), (12, 12), (12, 9), (12, None)):
            assert reg.tmcc_id_text(base, last).endswith(reg.tmcc_id_span(base, last))
            assert not re.search(r"[A-Za-z]", reg.tmcc_id_span(base, last))

    def test_a_span_of_one_address_is_that_address_alone(self):
        # "5", never "5 - 5": the same rule the words in front of it follow.
        assert reg.tmcc_id_span(5) == reg.tmcc_id_span(5, 5) == "5"
        assert re.findall(r"\d+", reg.tmcc_id_span(12, 19)) == ["12", "19"]


class TestModeNames:
    """
    The naming conventions the module docstring sets out: a mode opens with the Cab key
    that begins its programming sequence, parenthesizes whatever tells it from the
    module's other modes on that key, and says nothing about how many addresses it takes.

    The names are read off the registry and the conventions asserted over them, so a mode
    renamed or a note reworded is not a test to fix -- and a mode added in breach of a
    rule fails here rather than on the Pi.
    """

    # The keys on the Cab remote a mode can open with. The one piece of vocabulary the
    # registry does not own -- they are printed on the handset -- and so the one written
    # down here. The panel's SCOPE_LABEL has to spell them the same way, which the panel's
    # own tests check by joining the legend above the Mode radios to the rows below it. ENG
    # is here for the AMC2's engine mode, which the panel records and never offers: a mode
    # off the radios is named by the same rules as one on them.
    CAB_KEYS = {
        CommandScope.ACC: "ACC",
        CommandScope.SWITCH: "SW",
        CommandScope.TRAIN: "TR",
        CommandScope.ENGINE: "ENG",
    }

    def test_every_offered_mode_is_named(self):
        for device in reg.configurable_devices():
            for mode in reg.enabled_modes(device):
                assert mode.name.strip(), f"{device.key}/{mode.key} goes unnamed"

    def test_no_two_modes_a_module_offers_are_named_alike(self):
        # Two radio rows reading the same thing are a choice the operator cannot make,
        # which is the whole reason a qualifier exists. Read over the modes the panel
        # offers: the BPC2's reserved single-ID modes do repeat the name of the eight-ID
        # mode on their key, and that is harmless because they are never on screen.
        for device in reg.configurable_devices():
            names = [mode.name for mode in reg.enabled_modes(device)]
            assert len(set(names)) == len(names), f"{device.key}: {names}"

    def test_a_name_opens_with_its_cab_key(self):
        # The key that begins the programming sequence, spelled the way the remote spells
        # it and standing alone at the head of the row, which is also how the legend above
        # the radios names it.
        for device in reg.configurable_devices():
            for mode in device.modes:
                assert mode.name.split()[0] == self.CAB_KEYS[mode.scope], f"{device.key}/{mode.key}: {mode.name}"

    def test_a_key_is_spelled_one_way_throughout(self):
        # However the keys come to be spelled, every mode addressed in a scope opens with
        # the same word for it: one module's rows are read down the Mode box, and the
        # Currently Assigned rows below them name the same keys over again.
        spellings: dict[CommandScope, set[str]] = {}
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                spellings.setdefault(mode.scope, set()).add(mode.name.split()[0])
        assert all(len(words) == 1 for words in spellings.values()), spellings

    def test_a_name_is_a_key_and_at_most_one_qualifier(self):
        # Whatever tells this mode from the module's others on its key follows the key in
        # parentheses, reads as the aside it is rather than as a second word of the key,
        # and is what `qualifier` reads back -- which is how the panel looks the mode's
        # note up under the very word the row it explains carries.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                key = mode.name.split()[0]
                expected = key if mode.qualifier is None else f"{key} ({mode.qualifier})"
                assert mode.name == expected, f"{device.key}/{mode.key}: {mode.name}"

    def test_a_mode_is_qualified_exactly_when_its_key_offers_a_choice(self):
        # A qualifier earns its room on the row by telling two modes on one key apart, so
        # a module offering one mode per key -- the BPC2, the Sensor Track -- has nothing
        # to tell apart and says nothing. Read over the modes the panel offers, for the
        # reason given above: a reserved mode is never beside anything.
        for device in reg.configurable_devices():
            offered = list(reg.enabled_modes(device))
            for mode in offered:
                shares_key = len([other for other in offered if other.scope is mode.scope]) > 1
                assert (mode.qualifier is not None) is shares_key, f"{device.key}/{mode.key}: {mode.name}"

    def test_a_qualifier_is_one_word(self):
        # A radio row is as wide as its label, so the qualifier can say which mode this is
        # and little else; what the mode is good for is the note's business.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                if mode.qualifier is None:
                    continue
                assert " " not in mode.qualifier, f"{device.key}/{mode.key}: {mode.name}"

    def test_the_asc2_accessory_modes_are_told_apart_by_what_they_are_for(self):
        # Neither purpose can be read off the block the mode claims, and the two modes are
        # on the same key: one address driving all eight outputs for uncoupling tracks,
        # against eight addresses for whatever is wired to them. So each is qualified by
        # what it is for, the count is left to the row's tail, and the rest is said by the
        # note the panel prints under the radios -- all three of them the registry's own
        # words, which is why what is asserted here is that each mode has them.
        mixed, uncouple = reg.ASC2.mode("acc_8"), reg.ASC2.mode("acc_1")

        assert mixed.scope is uncouple.scope, "the pair is on one key or there is nothing to tell apart"
        assert (mixed.ports, uncouple.ports) == (8, 1)
        assert (mixed.pdi_mode, uncouple.pdi_mode) == (0, 1)
        assert mixed.qualifier and uncouple.qualifier
        assert mixed.qualifier != uncouple.qualifier
        for mode in (mixed, uncouple):
            assert mode.note, f"{mode.key} says nothing about what it is for"

    def test_a_name_counts_nothing(self):
        # The count is the label's business, and a name that carried one would say it
        # twice beside the block ids_label names.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                assert not re.search(r"\d", mode.name), f"{device.key}/{mode.key}: {mode.name}"
                assert not re.search(r"\bIDs?\b", mode.name), f"{device.key}/{mode.key}: {mode.name}"

    def test_the_asc2_switch_modes_key_keeps_a_word_the_operator_never_reads(self):
        # The key keeps the word asc2_req.py and the flowchart use for mode 2, so the code
        # and the manual agree; what the operator reads is what the switch motor is
        # actually given. The word is taken off the key rather than written here, so a
        # rewording cannot leave this test quoting the old one.
        mode = reg.ASC2.mode("sw_momentary")
        key_word = mode.key.split("_")[-1]

        assert mode.qualifier
        for label in (mode.name, mode.ports_label, mode.ids_label(1)):
            assert key_word not in label.lower(), label
        # And the press that tells this mode from its latching sibling is the very thing
        # the qualifier names, so the row and the review page say one word between them.
        assert [press.note for press in mode.presses] == [None, mode.qualifier]

    def test_a_name_says_nothing_a_mode_does_besides_claiming_addresses(self):
        # A radio row is as wide as its label, and the panel is a portrait pane. The Sensor
        # Track's Action Command is set in the same gesture as its ID, and naming both asks
        # 751 px of the 714 px the pane gives a row at the Pi's 1.5x font scale -- even with
        # the key abbreviated -- losing 18 px off each end. It is the whole of the options
        # page that follows instead, so no mode's name says what its module's own options
        # say.
        for device in reg.configurable_devices():
            for mode in device.modes:
                assert len(mode.name.split()) <= 2, f"{device.key}/{mode.key}: {mode.name}"
                for option in device.options:
                    for word in option.label.split():
                        assert word.lower() not in mode.name.lower(), f"{device.key}/{mode.key}: {mode.name}"


class TestModeLabels:
    """
    The two labels built from a mode's name: the block it would claim from an entered
    address, and -- where there is no address to name it from -- the count alone.

    Asserted as compositions rather than as sentences repeated here: a label is the mode's
    own name and the registry's one spelling of what it claims, in that order. That stays
    true however either part comes to be worded, which is the whole point of building both
    labels in the registry instead of in the panel.
    """

    def test_every_mode_names_the_block_it_would_claim(self):
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                for base_id in (1, 12, mode.max_base):
                    last_id = base_id + mode.ports - 1
                    expected = f"{mode.name} {reg.tmcc_id_text(base_id, last_id)}"
                    assert mode.ids_label(base_id) == expected, f"{device.key}/{mode.key}"

    def test_every_mode_names_the_count_it_claims(self):
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                assert mode.ports_label == f"{mode.name}, {reg.tmcc_id_count(mode.ports)}", f"{device.key}/{mode.key}"

    def test_a_block_follows_the_address_it_is_based_at(self):
        # The arithmetic, spelled out at both ends of an 8-ID mode's range.
        mode = reg.ASC2.mode("acc_8")
        assert mode.ids_label(12) == f"{mode.name} {reg.tmcc_id_text(12, 19)}"
        assert mode.ids_label(91) == f"{mode.name} {reg.tmcc_id_text(91, 98)}"

    def test_a_mode_is_offered_at_the_highest_base_it_fits(self):
        # The Mode radios are labeled from the ID on the page, which a narrower mode can
        # have carried above this one's ceiling: the 4-ID modes reach 95, and an 8-ID mode
        # based there would run off the end. The label names where choosing it lands, which
        # is what the panel clamps the ID to.
        acc_8, single_wire = reg.ASC2.mode("acc_8"), reg.STM2.mode("single_wire")
        assert acc_8.ids_label(95) == acc_8.ids_label(acc_8.max_base)
        assert re.findall(r"\d+", acc_8.ids_label(95)) == ["91", "98"]
        assert single_wire.ids_label(98) == single_wire.ids_label(single_wire.max_base)
        assert re.findall(r"\d+", single_wire.ids_label(98)) == ["83", "98"]
        # And nothing is named below the first address, whatever it is handed.
        acc_1 = reg.ASC2.mode("acc_1")
        assert acc_1.ids_label(0) == acc_1.ids_label(1)

    def test_an_id_is_always_a_tmcc_id(self):
        # A bare "ID" is ambiguous beside a PDI address or a port number.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                for label in (mode.ports_label, mode.ids_label(1)):
                    assert not re.findall(r"(?<!TMCC )\bIDs?\b", label), f"{device.key}/{mode.key}: {label}"

    NUMBER_WORDS = ("one", "single", "two", "three", "four", "five", "six", "seven", "eight", "sixteen")

    def test_a_count_is_a_digit(self):
        # "Eight ID" was the old spelling; a digit is read at a glance.
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                for word in re.findall(r"(\w+)\s+TMCC IDs?\b", mode.ports_label):
                    assert word.lower() not in self.NUMBER_WORDS, f"{device.key}/{mode.key}: {mode.ports_label}"

    def test_a_counted_label_agrees_with_the_mode(self):
        for device in reg.LCS_DEVICES:
            for mode in device.modes:
                counted = re.search(r"(\d+) TMCC IDs?\b", mode.ports_label)
                assert counted, f"{device.key}/{mode.key}: {mode.ports_label}"
                assert int(counted.group(1)) == mode.ports, f"{device.key}/{mode.key}: {mode.ports_label}"

    def test_the_longest_row_is_the_stm2s_widest_block(self):
        # A radio row is as wide as its label and the panel is a portrait pane, so the
        # widest row any module can ask for is worth pinning: 33 characters as the modes
        # are worded today, which is 671 px of the 714 px the pane gives it at the Pi's
        # 1.5x font scale. The ceiling is what matters, so a shorter wording costs nothing
        # and a longer one has to be measured before it is adopted.
        widest = reg.STM2.mode("single_wire")
        longest = max(
            (mode.ids_label(mode.max_base) for device in reg.configurable_devices() for mode in device.modes),
            key=len,
        )
        assert longest == widest.ids_label(widest.max_base)
        assert len(longest) <= 33

    def test_a_block_covers_exactly_the_ids_the_mode_claims(self):
        # However the mode reads, the two ends of the block are the addresses that go with
        # its port count: an operator reserving them has to be told the truth. Read as the
        # numbers in the label rather than by matching the phrase around them -- a name
        # counts nothing, so every digit in a block label is one of the block's ends.
        for device in reg.configurable_devices():
            for mode in device.modes:
                label = mode.ids_label(1)
                ends = [int(number) for number in re.findall(r"\d+", label)]
                assert ends[-1] - ends[0] + 1 == mode.ports, f"{device.key}/{mode.key}: {label}"

    def test_every_switch_mode_names_the_ids_it_consumes(self):
        # A switch mode reserves a block just as an accessory mode does, and an operator
        # laying out switch IDs has to know which of them go with the choice.
        for device in reg.configurable_devices():
            for mode in device.modes:
                if mode.scope != CommandScope.SWITCH:
                    continue
                assert re.search(rf"\b{mode.ports} TMCC IDs?\b", mode.ports_label), f"{device.key}/{mode.key}"
                assert "TMCC ID" in mode.ids_label(1), f"{device.key}/{mode.key}"
