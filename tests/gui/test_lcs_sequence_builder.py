from __future__ import annotations

import pytest

import src.pytrain.gui.controller.lcs_device_registry as reg
from src.pytrain.gui.controller.lcs_sequence_builder import build_program, included_presses
from src.pytrain.pdi.amc2_req import OutputType
from src.pytrain.pdi.irda_req import IrdaSequence
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
    TMCC1SwitchCommandEnum,
)


def _signature(program):
    """Every request the program sends, in send order, as the wire sees it.

    The data rides along with the command, because a number key is one command carrying
    the number it enters: without the data, "AUX1 then 3" and "AUX1 then 7" are the same
    two requests. A key that enters nothing carries 0.
    """
    return [(req.command, req.scope, req.address, req.data) for req in program.presses]


def _digit_keys(aux: int, digit: int, scope: CommandScope, base_id: int) -> list[tuple]:
    """The requests one gesture that enters a digit sends: the AUX key, then the number.

    Both are asked of the registry rather than named here, so which keys a handset sends
    is spelled in the one place that knows, and re-keying a gesture is not a test to fix.
    """
    number, data = reg.number_key(digit, scope)
    return [
        (reg.aux_key(aux, scope), scope, base_id, 0),
        (number, scope, base_id, data),
    ]


def _line(number: int, press, base_id: int = None, options=None) -> str:
    """One review line as the builder numbers it, worded by the press itself.

    The numbering and the parenthesized note are this module's own format, so they are
    written here; every word inside them belongs to the registry's Press and is read off
    it, so renaming a gesture is not a test to fix.
    """
    label = press.resolved_label(options)
    if base_id is not None:
        label = label.format(id=base_id)
    return f"{number}. {label} ({press.note})" if press.note else f"{number}. {label}"


class TestAsc2:
    def test_acc_eight_id(self):
        program = build_program(reg.ASC2, reg.ASC2.mode("acc_8"), 9)
        assert _signature(program) == [
            (TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC, 9, 0),
            *_digit_keys(1, 0, CommandScope.ACC, 9),
        ]

    def test_acc_single_id(self):
        program = build_program(reg.ASC2, reg.ASC2.mode("acc_1"), 9)
        assert _signature(program)[1:] == _digit_keys(1, 1, CommandScope.ACC, 9)

    def test_sw_momentary(self):
        program = build_program(reg.ASC2, reg.ASC2.mode("sw_momentary"), 20)
        assert _signature(program) == [
            (TMCC1SwitchCommandEnum.SET_ADDRESS, CommandScope.SWITCH, 20, 0),
            (TMCC1SwitchCommandEnum.THRU, CommandScope.SWITCH, 20, 0),
        ]

    def test_sw_latching(self):
        program = build_program(reg.ASC2, reg.ASC2.mode("sw_latching"), 20)
        assert _signature(program)[1] == (TMCC1SwitchCommandEnum.OUT, CommandScope.SWITCH, 20, 0)


class TestBpc2:
    def test_train_restore_on(self):
        mode = reg.BPC2.mode("tr_8")
        program = build_program(reg.BPC2, mode, 12, {"restore": True})
        assert _signature(program) == [
            (TMCC1EngineCommandEnum.SET_ADDRESS, CommandScope.TRAIN, 12, 0),
            (TMCC1EngineCommandEnum.REAR_COUPLER, CommandScope.TRAIN, 12, 0),
            *_digit_keys(1, 0, CommandScope.TRAIN, 12),
        ]
        assert program.display[1] == _line(2, mode.presses[1])

    def test_train_restore_off_omits_coupler(self):
        mode = reg.BPC2.mode("tr_8")
        program = build_program(reg.BPC2, mode, 12, {"restore": False})
        assert _signature(program) == [
            (TMCC1EngineCommandEnum.SET_ADDRESS, CommandScope.TRAIN, 12, 0),
            *_digit_keys(1, 0, CommandScope.TRAIN, 12),
        ]
        # The gesture the option gates, named by the press that declares it.
        assert not any(mode.presses[1].label in line for line in program.display)

    def test_restore_defaults_off(self):
        # Nothing was said about restore, so the module is left as its own manual leaves
        # it: the coupler tap is the whole of the difference, and it is not sent.
        program = build_program(reg.BPC2, reg.BPC2.mode("tr_8"), 12)
        assert _signature(program) == [
            (TMCC1EngineCommandEnum.SET_ADDRESS, CommandScope.TRAIN, 12, 0),
            *_digit_keys(1, 0, CommandScope.TRAIN, 12),
        ]

    def test_accessory_scope(self):
        program = build_program(reg.BPC2, reg.BPC2.mode("acc_8"), 64, {"restore": True})
        assert _signature(program) == [
            (TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC, 64, 0),
            (TMCC1AuxCommandEnum.REAR_COUPLER, CommandScope.ACC, 64, 0),
            *_digit_keys(1, 0, CommandScope.ACC, 64),
        ]

    def test_train_digit_is_entered_on_the_engine_keys(self):
        # The same "AUX1 then 0" gesture the module's ACC mode ends with, on the other key:
        # a train is addressed from the engine side of the handset, and the accessory pair
        # sent to a TR module programs nothing. This mode is the one place in the registry
        # where a digit is entered outside accessory scope.
        program = build_program(reg.BPC2, reg.BPC2.mode("tr_8"), 12)
        assert _signature(program)[1:] == _digit_keys(1, 0, CommandScope.TRAIN, 12)
        # ...and the two scopes really do send different keys, so the line above is a rule
        # about scope rather than the same pair spelled twice.
        train_number, _ = reg.number_key(0, CommandScope.TRAIN)
        acc_number, _ = reg.number_key(0, CommandScope.ACC)
        assert reg.aux_key(1, CommandScope.TRAIN) != reg.aux_key(1, CommandScope.ACC)
        assert train_number != acc_number


class TestStm2:
    def test_single_wire(self):
        program = build_program(reg.STM2, reg.STM2.mode("single_wire"), 33)
        assert _signature(program) == [
            (TMCC1SwitchCommandEnum.SET_ADDRESS, CommandScope.SWITCH, 33, 0),
            (TMCC1SwitchCommandEnum.THRU, CommandScope.SWITCH, 33, 0),
        ]

    def test_two_wire(self):
        program = build_program(reg.STM2, reg.STM2.mode("two_wire"), 33)
        assert _signature(program)[1] == (TMCC1SwitchCommandEnum.OUT, CommandScope.SWITCH, 33, 0)


class TestSensorTrack:
    @pytest.mark.parametrize("digit", list(range(10)))
    def test_every_action(self, digit):
        mode = reg.SENSOR_TRACK.modes[0]
        program = build_program(reg.SENSOR_TRACK, mode, 3, {"action": IrdaSequence(digit)})
        assert _signature(program) == [
            (TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC, 3, 0),
            *_digit_keys(1, digit, CommandScope.ACC, 3),
        ]
        assert program.display[1] == _line(2, mode.presses[1], options={"action": IrdaSequence(digit)})

    def test_action_press_never_omitted_by_default(self):
        program = build_program(reg.SENSOR_TRACK, reg.SENSOR_TRACK.modes[0], 3)
        assert _signature(program)[1:] == _digit_keys(1, 0, CommandScope.ACC, 3)


class TestAmc2:
    def test_acc_sequence_follows_the_flowchart(self):
        # Both motors are set in one pass, in the order the manual draws it: the address,
        # then each motor's mode with its remember tap behind it. There is no coming back
        # for the second motor -- leaving program mode is what ends the sequence.
        mode = reg.AMC2.mode("acc")
        options = {
            "motor1_mode": OutputType.DELTA,
            "motor1_restore": True,
            "motor2_mode": OutputType.AC,
            "motor2_restore": True,
        }
        program = build_program(reg.AMC2, mode, 5, options)
        assert _signature(program) == [
            (TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC, 5, 0),
            *_digit_keys(1, 2, CommandScope.ACC, 5),
            (TMCC1AuxCommandEnum.REAR_COUPLER, CommandScope.ACC, 5, 0),
            *_digit_keys(2, 3, CommandScope.ACC, 5),
            (TMCC1AuxCommandEnum.REAR_COUPLER, CommandScope.ACC, 5, 0),
        ]

    def test_each_motor_is_entered_under_its_own_aux_key(self):
        # Motor #1 answers under AUX1 and motor #2 under AUX2. Entering both under AUX1 --
        # which the manual's running text can be read as saying -- would set motor #1 twice
        # and leave motor #2 as it was found, and the sequence would still look complete.
        program = build_program(reg.AMC2, reg.AMC2.mode("acc"), 5)
        aux_pair = (reg.aux_key(1, CommandScope.ACC), reg.aux_key(2, CommandScope.ACC))
        assert [req.command for req in program.presses if req.command in aux_pair] == list(aux_pair)

    @pytest.mark.parametrize(
        "output_type, digit",
        [(OutputType.NORMAL, 1), (OutputType.DELTA, 2), (OutputType.AC, 3)],
    )
    def test_motor_mode_is_pressed_as_the_manual_numbers_it(self, output_type, digit):
        # The module counts its three output types from zero and the manual counts the keys
        # the operator taps from one, so the option holds what the module reports and the
        # press is one higher. Off by one here wires a motor for the wrong kind of power.
        mode = reg.AMC2.mode("acc")
        options = {"motor1_mode": output_type, "motor2_mode": output_type}
        program = build_program(reg.AMC2, mode, 5, options)
        assert _signature(program)[1:3] == _digit_keys(1, digit, CommandScope.ACC, 5)
        assert _signature(program)[3:5] == _digit_keys(2, digit, CommandScope.ACC, 5)
        # The review line says the same number the key does, so the operator following it
        # by hand and the panel sending it do not disagree.
        assert program.display[1] == _line(2, mode.presses[1], options=options)

    @pytest.mark.parametrize("motor2_restore", [False, True])
    @pytest.mark.parametrize("motor1_restore", [False, True])
    def test_each_motor_remembers_independently(self, motor1_restore, motor2_restore):
        # Two flags gating two taps of the one key, each behind its own motor: an
        # implementation reading one flag for both taps, or sending the tap unasked, is
        # right in some of these four cases and wrong in the rest.
        mode = reg.AMC2.mode("acc")
        options = {"motor1_restore": motor1_restore, "motor2_restore": motor2_restore}
        coupler = (TMCC1AuxCommandEnum.REAR_COUPLER, CommandScope.ACC, 5, 0)
        expected = [
            (TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC, 5, 0),
            *_digit_keys(1, 1, CommandScope.ACC, 5),
        ]
        if motor1_restore:
            expected.append(coupler)
        expected.extend(_digit_keys(2, 1, CommandScope.ACC, 5))
        if motor2_restore:
            expected.append(coupler)
        program = build_program(reg.AMC2, mode, 5, options)
        assert _signature(program) == expected

    def test_untouched_options_still_send_both_motor_modes(self):
        # Both mode options are required and both carry a default, so an operator who
        # changes nothing still programs a whole module: the sequence sets both motors or
        # neither, and a motor whose mode was skipped is left running as it was found.
        program = build_program(reg.AMC2, reg.AMC2.mode("acc"), 5)
        assert _signature(program) == [
            (TMCC1AuxCommandEnum.SET_ADDRESS, CommandScope.ACC, 5, 0),
            *_digit_keys(1, 1, CommandScope.ACC, 5),
            *_digit_keys(2, 1, CommandScope.ACC, 5),
        ]

    def test_display_names_the_motor_each_gesture_is_for(self):
        # Steps 2 and 4 are both an AUX key and a digit, and both R taps are the same key,
        # so without the notes the page cannot say which motor a step is setting. The
        # numbering counts what is actually sent: motor #2's omitted tap takes no number.
        mode = reg.AMC2.mode("acc")
        options = {"motor1_mode": OutputType.DELTA, "motor1_restore": True, "motor2_mode": OutputType.AC}
        program = build_program(reg.AMC2, mode, 5, options)
        assert program.display == [
            _line(1, mode.presses[0], base_id=5),
            _line(2, mode.presses[1], options=options),
            _line(3, mode.presses[2]),
            _line(4, mode.presses[3], options=options),
        ]

    @pytest.mark.parametrize(
        "key, scope",
        [("tr", CommandScope.TRAIN), ("eng", CommandScope.ENGINE)],
    )
    def test_modes_the_panel_will_not_offer_still_build(self, key, scope):
        # Written down rather than left out, because a module already sitting on one of
        # those keys has to be recognized there; what is recorded is the press that opens
        # the sequence, and it is truthful -- the address is set on the key the mode names.
        program = build_program(reg.AMC2, reg.AMC2.mode(key), 5)
        assert _signature(program) == [(TMCC1EngineCommandEnum.SET_ADDRESS, scope, 5, 0)]


class TestDigitGestures:
    def test_aux_key_is_sent_first_and_the_number_after_it(self):
        # The order is the gesture: a number arriving before the AUX button is an ordinary
        # numeric command, so the module never enters the step and the two requests are
        # told from the right pair by their order alone.
        mode = reg.SENSOR_TRACK.modes[0]
        program = build_program(reg.SENSOR_TRACK, mode, 3, {"action": IrdaSequence(4)})
        number, _ = reg.number_key(4, CommandScope.ACC)
        assert [req.command for req in program.presses[1:]] == [reg.aux_key(1, CommandScope.ACC), number]

    def test_number_key_carries_the_digit_as_its_data(self):
        # One command spells all ten digits, so what tells "AUX1 then 4" from "AUX1 then 7"
        # is the data the request carries and nothing else about it.
        mode = reg.SENSOR_TRACK.modes[0]
        four = build_program(reg.SENSOR_TRACK, mode, 3, {"action": IrdaSequence(4)})
        seven = build_program(reg.SENSOR_TRACK, mode, 3, {"action": IrdaSequence(7)})
        assert four.presses[2].command == seven.presses[2].command
        assert (four.presses[2].data, seven.presses[2].data) == (4, 7)

    def test_both_keys_are_addressed_to_the_module_being_programmed(self):
        # Two requests where there was one, and each is addressed in its own right: a
        # number key left at the default address is a command to whatever answers there,
        # and the module waiting in program mode never hears it.
        program = build_program(reg.ASC2, reg.ASC2.mode("acc_8"), 9)
        assert {(req.address, req.scope) for req in program.presses} == {(9, CommandScope.ACC)}


class TestVerifyAndDisplay:
    def test_verify_requests(self):
        program = build_program(reg.ASC2, reg.ASC2.mode("acc_8"), 9)
        expected = [reg.ASC2.pdi_device.config(9).as_bytes, reg.ASC2.pdi_device.info(9).as_bytes]
        assert [req.as_bytes for req in program.verify] == expected

    def test_display_order_matches_presses(self):
        mode = reg.BPC2.mode("tr_8")
        program = build_program(reg.BPC2, mode, 12, {"restore": True})
        # Numbered in send order, and each line carries the address the press is sent to
        # where the press asks for it.
        assert program.display[0] == _line(1, mode.presses[0], base_id=12)
        assert program.display[2] == _line(3, mode.presses[2])

    def test_display_counts_gestures_while_presses_count_keys(self):
        # The two lists are deliberately unequal. The operator has three things to do, and
        # the fourth request is the number key inside the last of them: numbering the keys
        # instead would tell them to press AUX1 and then press 0 as two separate steps,
        # which is neither what the manual says nor what the handset does.
        mode = reg.BPC2.mode("tr_8")
        options = {"restore": True}
        program = build_program(reg.BPC2, mode, 12, options)
        assert len(program.display) == len(included_presses(mode, options)) == 3
        assert len(program.presses) == 4
        # And the gesture that takes two keys still reads as the one step it is.
        assert program.display[2] == _line(3, mode.presses[2])

    def test_program_instruction(self):
        # Each module's instruction names the button the operator has to hold, which the
        # registry spells for it: a PGM key on most, a PROGRAM key on the Sensor Track.
        asc2 = build_program(reg.ASC2, reg.ASC2.mode("acc_8"), 9)
        assert reg.ASC2.program_button in asc2.program_instruction
        st = build_program(reg.SENSOR_TRACK, reg.SENSOR_TRACK.modes[0], 3)
        assert reg.SENSOR_TRACK.program_button in st.program_instruction
        assert reg.ASC2.program_button != reg.SENSOR_TRACK.program_button


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
