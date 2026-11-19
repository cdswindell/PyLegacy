"""Reject overflowing 2D addresses before they can corrupt command bits."""

import pytest

from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.multibyte.dcds_command_req import VariableCommandReq
from pytrain.protocol.multibyte.multibyte_constants import TMCC2DcdsCommandEnum, TMCC2EffectsControl
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


@pytest.mark.parametrize("address", (-1, 128, 255, 256, 9999))
@pytest.mark.parametrize("shift", (1, 7, 9))
def test_every_two_digit_packing_layout_rejects_overflow(address, shift):
    with pytest.raises(ValueError, match="between 0 and 127"):
        # Exercise the shared defensive boundary directly for every packing layout.
        # noinspection PyProtectedMember
        CommandReq._encode_2d_address(address, shift)


@pytest.mark.parametrize("shift, expected", ((1, 0xFE), (7, 0x3F80), (9, 0xFE00)))
def test_seven_bit_boundary_preserves_all_address_bits(shift, expected):
    # These literals independently specify the highest legal seven-bit address.
    # noinspection PyProtectedMember
    assert CommandReq._encode_2d_address(127, shift) == expected


@pytest.mark.parametrize("address", (128, 255, 9999))
def test_tmcc1_constructor_rejects_overflow(address):
    with pytest.raises(ValueError, match="between 0 and 127"):
        CommandReq(TMCC1EngineCommandEnum.BLOW_HORN_ONE, address)


@pytest.mark.parametrize("address", (128, 255, 9999))
def test_tmcc1_address_setter_rejects_overflow(address):
    request = CommandReq.build(TMCC1EngineCommandEnum.BLOW_HORN_ONE, 37)
    with pytest.raises(ValueError, match="between 0 and 127"):
        request.address = address
    # A failed assignment must also never permit subsequent serialization.
    with pytest.raises(ValueError, match="between 0 and 127"):
        _ = request.as_bytes


@pytest.mark.parametrize("address", (128, 255, 9999))
@pytest.mark.parametrize("scope", (CommandScope.ENGINE, CommandScope.TRAIN))
@pytest.mark.parametrize("kind", ("single", "fixed", "variable"))
def test_serialization_rejects_overflow_if_two_digit_format_is_selected(monkeypatch, address, scope, kind):
    if kind == "variable":
        request = VariableCommandReq.build(TMCC2DcdsCommandEnum.MASTER_VOLUME, address, 127, scope)
    else:
        command = TMCC2EngineCommandEnum.BLOW_HORN_ONE if kind == "single" else TMCC2EffectsControl.SMOKE_HIGH
        request = CommandReq.build(command, address, scope=scope)
    assert request.uses_d4_address
    assert f"{address:04d}".encode() in request.as_bytes
    # Force an erroneous format decision to verify the final serialization guard.
    monkeypatch.setattr(CommandReq, "uses_d4_address", property(lambda self: False))
    with pytest.raises(ValueError, match="between 0 and 127"):
        _ = request.as_bytes
