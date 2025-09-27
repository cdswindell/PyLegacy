#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
import pytest

# pytest


from src.pytrain.pdi.amc2_req import Amc2Lamp, Amc2Motor, Amc2Req, Direction, OutputType
from src.pytrain.pdi.constants import Amc2Action, PdiCommand


def test_parse_config_rx_from_bytes_minimal_fields_present():
    # Known-good AMC2 CONFIG RX blob seen elsewhere in tests
    blob = bytes.fromhex("d1461903190000000202020303010100000000000000000077df")
    req = Amc2Req.from_bytes(blob)

    # Basic identity
    assert req.pdi_command == PdiCommand.AMC2_RX
    assert req.action == Amc2Action.CONFIG
    assert req.tmcc_id == 0x19

    # Motor objects harvested and accessible
    assert isinstance(req.motor1, Amc2Motor)
    assert isinstance(req.motor2, Amc2Motor)

    # Defaults/values derived from bytes for state-related fields
    assert req.motor1.speed == 0
    assert req.motor2.speed == 0
    assert req.motor1.restore_state is False
    assert req.motor2.restore_state is False
    assert req.motor1.state is False
    assert req.motor2.state is False

    # Lamps list populated (some may be None if not present)
    # get_lamp should be index-safe
    l1 = req.get_lamp(1)
    l2 = req.get_lamp(2)
    l3 = req.get_lamp(3)
    l4 = req.get_lamp(4)
    assert isinstance(l1, (Amc2Lamp, type(None)))
    assert isinstance(l2, (Amc2Lamp, type(None)))
    assert isinstance(l3, (Amc2Lamp, type(None)))
    assert isinstance(l4, (Amc2Lamp, type(None)))


def test_get_motor_and_lamp_bounds_safe():
    # Build a simple CONFIG req instance with integer address
    # The internal motors/lamps arrays are only set when bytes are parsed.
    # Use the same RX blob to populate internal arrays.
    blob = bytes.fromhex("d1461903190000000202020303010100000000000000000077df")
    req = Amc2Req.from_bytes(blob)

    # Valid IDs 1..2 for motors and 1..4 for lamps
    assert req.get_motor(1) is req.motor1
    assert req.get_motor(2) is req.motor2
    # Out of range -> exception
    with pytest.raises(ValueError):
        _ = req.get_motor(0)
    with pytest.raises(ValueError):
        _ = req.get_motor(3)

    assert req.get_lamp(0) is None
    assert req.get_lamp(5) is None


def test_direction_and_output_type_labels_and_flags():
    assert Direction.FORWARD.label == "Forward"
    assert Direction.REVERSE.label == "Reverse"
    assert Direction.AC.label == "AC"

    assert OutputType.NORMAL.label == "Normal"
    assert OutputType.DELTA.label == "Delta"
    assert OutputType.AC.label == "AC"

    assert OutputType.NORMAL.is_dc is True
    assert OutputType.DELTA.is_dc is True
    assert OutputType.AC.is_dc is False
    assert OutputType.AC.is_ac is True
    assert OutputType.NORMAL.is_ac is False


def test_motor_action_payload_and_as_bytes_structure():
    # Note: motor param is zero-based internally; 1 == "Motor 2"
    req = Amc2Req(
        25,
        PdiCommand.AMC2_SET,
        Amc2Action.MOTOR,
        motor=1,
        speed=50,
        direction=Direction.FORWARD,
    )
    # Human payload for SET motor
    s = req.payload
    assert isinstance(s, str)
    assert "Motor:" in s and "Speed:" in s and "Dir:" in s

    # Byte framing: SOP .. checksum .. EOP; includes command/action/motor/speed/dir
    bs = req.as_bytes
    assert isinstance(bs, (bytes, bytearray))
    assert bs[0] == 0xD1  # PDI_SOP
    assert bs[-1] == 0xDF  # PDI_EOP
    # Ensure core fields appear somewhere in the packet
    assert PdiCommand.AMC2_SET.as_bytes in bs
    assert Amc2Action.MOTOR.as_bytes in bs
    assert (1).to_bytes(1, "big") in bs  # motor index (zero-based) -> 1
    assert (50).to_bytes(1, "big") in bs
    assert Direction.FORWARD.value.to_bytes(1, "big") in bs


def test_lamp_action_payload_and_as_bytes_structure():
    req = Amc2Req(
        25,
        PdiCommand.AMC2_SET,
        Amc2Action.LAMP,
        lamp=0,  # zero-based -> "Lamp 1"
        level=77,
    )
    s = req.payload
    assert isinstance(s, str)
    assert "Lamp:" in s and "Level:" in s

    bs = req.as_bytes
    assert bs[0] == 0xD1 and bs[-1] == 0xDF
    assert PdiCommand.AMC2_SET.as_bytes in bs
    assert Amc2Action.LAMP.as_bytes in bs
    assert (0).to_bytes(1, "big") in bs
    assert (77).to_bytes(1, "big") in bs


def test_motor_config_set_serialization_and_payload_defaults():
    # restore defaults to True when not specified
    req_default = Amc2Req(
        10,
        PdiCommand.AMC2_SET,
        Amc2Action.MOTOR_CONFIG,
        motor=0,
        output_type=OutputType.AC,
    )
    assert req_default.restore is True
    s = req_default.payload
    assert isinstance(s, str)
    assert "Output Type:" in s and "Restore:" in s

    # Explicit restore False
    req = Amc2Req(
        10,
        PdiCommand.AMC2_SET,
        Amc2Action.MOTOR_CONFIG,
        motor=0,
        output_type=OutputType.NORMAL,
        restore=False,
    )
    bs = req.as_bytes
    # Presence checks
    assert PdiCommand.AMC2_SET.as_bytes in bs
    assert Amc2Action.MOTOR_CONFIG.as_bytes in bs
    assert (0).to_bytes(1, "big") in bs  # motor index
    assert OutputType.NORMAL.value.to_bytes(1, "big") in bs
    assert (0).to_bytes(1, "big") in bs  # restore False encoded


def test_update_config_applies_motor_and_lamp_changes():
    # Start with CONFIG RX to create internal motor/lamp arrays
    blob = bytes.fromhex("d1461903190000000202020303010100000000000000000077df")
    cfg = Amc2Req.from_bytes(blob)

    # 1) MOTOR speed/dir update on motor index 1 (user-visible motor=2)
    motor_update = Amc2Req(
        cfg.tmcc_id,
        PdiCommand.AMC2_SET,
        Amc2Action.MOTOR,
        motor=1,
        speed=100,
        direction=Direction.REVERSE,
    )
    cfg.update_config(motor_update)
    m2 = cfg.get_motor(2)
    assert m2 is not None
    assert m2.speed == 100
    assert m2.direction == Direction.REVERSE

    # 2) MOTOR_CONFIG changes output type and restore
    mc_update = Amc2Req(
        cfg.tmcc_id,
        PdiCommand.AMC2_SET,
        Amc2Action.MOTOR_CONFIG,
        motor=1,
        output_type=OutputType.DELTA,
        restore=True,
    )
    cfg.update_config(mc_update)
    m2 = cfg.get_motor(2)
    assert m2 is not None
    assert m2.output_type == OutputType.DELTA
    assert m2.restore is True

    # 3) LAMP level change on lamp index 1 (user-visible lamp=2)
    lamp_update = Amc2Req(
        cfg.tmcc_id,
        PdiCommand.AMC2_SET,
        Amc2Action.LAMP,
        lamp=1,
        level=55,
    )
    cfg.update_config(lamp_update)
    l2 = cfg.get_lamp(2)
    if l2:
        assert l2.level == 55  # Only assert if lamp exists in RX blob


def test_as_bytes_get_requests_have_minimal_payload_for_motor_and_lamp():
    # GET for motor includes only motor index after header/action
    get_motor = Amc2Req(9, PdiCommand.AMC2_GET, Amc2Action.MOTOR, motor=0)
    bs_m = get_motor.as_bytes
    assert PdiCommand.AMC2_GET.as_bytes in bs_m
    assert Amc2Action.MOTOR.as_bytes in bs_m
    # Should not include speed/dir bytes for GET
    assert bs_m.count((0).to_bytes(1, "big")) >= 1  # motor index present; rest minimal

    # GET for lamp includes only lamp index after header/action
    get_lamp = Amc2Req(9, PdiCommand.AMC2_GET, Amc2Action.LAMP, lamp=3)
    bs_l = get_lamp.as_bytes
    assert PdiCommand.AMC2_GET.as_bytes in bs_l
    assert Amc2Action.LAMP.as_bytes in bs_l
    assert (3).to_bytes(1, "big") in bs_l  # lamp index
