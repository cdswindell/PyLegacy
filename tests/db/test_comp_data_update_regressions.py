"""Protect field encoding when adding support for raw memory writes."""

from unittest.mock import Mock

import pytest

from src.pytrain.db.comp_data import CompData, CompDataHandler, REQUEST_TO_UPDATES_MAP, SCOPE_TO_COMP_MAP
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.protocol.constants import CommandScope


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize(
    "field, expected_field, value, expected_offset, expected_data",
    [
        ("train_address", "train_tmcc_id", 42, 0x1C, b"\x2a"),
        ("train_unit", "train_unit", 3, 0x1D, b"\x03"),
        ("control_type", "control_type", 2, 0x44, b"\x02"),
        ("momentum", "momentum", 7, 0x18, b"\x7f"),
        ("train_brake", "train_brake", 3, 0x09, b"\x06"),
        ("engineer_fuel_refilled", "fuel_level", None, 0x0D, b"\xff"),
        ("engineer_water_refilled", "water_level", None, 0x0E, b"\xff"),
        ("road_name", "road_name", "  Pennsy  ", 0x1F, b"Pennsy" + b"\xff" * 25),
        ("road_name", "road_name", "", 0x1F, b"\xff" * 31),
        ("road_number", "road_number", "1234", 0x3F, b"1234"),
        ("road_number", "road_number", "7", 0x3F, b"7\xff\xff\xff"),
        ("road_number", "road_number", "", 0x3F, b"\xff" * 4),
    ],
)
def test_field_updates_preserve_encoding_and_wire_payload(
    scope, field, expected_field, value, expected_offset, expected_data
):
    packages = CompData.field_to_updates(f"  {field.upper()}  ", 7, scope, data=value)

    assert len(packages) == 1
    package = packages[0]
    assert package.field == expected_field
    assert package.offset == expected_offset
    assert package.length == len(expected_data)
    assert package.data_bytes == expected_data

    request = package.as_request(7, scope)
    assert isinstance(request, BaseReq)
    decoded = BaseReq(request.as_bytes)
    assert decoded.scope == scope
    assert decoded.tmcc_id == 7
    assert decoded.start == expected_offset
    assert decoded.data_length == len(expected_data)
    assert decoded.data_bytes == expected_data


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_integer_multibyte_field_keeps_little_endian_encoding(scope):
    # This private helper is the encoding boundary; bt_id has no request mapping.
    # noinspection PyProtectedMember
    package = CompData._create_update_pkg("bt_id", True, scope, 7, 0x1234)

    assert package is not None
    assert (package.field, package.offset, package.length, package.data_bytes) == ("bt_id", 0x04, 2, b"\x34\x12")


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_field_encoder_output_is_padded_to_declared_length(monkeypatch, scope):
    handler = SCOPE_TO_COMP_MAP[scope][0x3F]
    assert isinstance(handler, CompDataHandler)
    encoder = Mock(return_value=b"7")
    monkeypatch.setattr(handler, "to_bytes", encoder)

    packages = CompData.field_to_updates("road_number", 7, scope, data="7")

    encoder.assert_called_once_with("7")
    assert len(packages) == 1
    assert packages[0].length == 4
    assert packages[0].data_bytes == b"7\xff\xff\xff"


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_none_field_value_skips_encoding_and_update(monkeypatch, scope):
    encoder = Mock()
    handler = SCOPE_TO_COMP_MAP[scope][0x1C]
    assert isinstance(handler, CompDataHandler)
    monkeypatch.setattr(handler, "to_bytes", encoder)

    assert CompData.field_to_updates("train_address", 7, scope, data=None) == []
    encoder.assert_not_called()


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_unknown_request_field_produces_no_updates(scope):
    assert CompData.field_to_updates("unknown_field", 7, scope, data=1) == []


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize("address", [7, 1234])
def test_clear_train_info_writes_both_membership_bytes(scope, address):
    packages = CompData.field_to_updates("CLEAR_TRAIN_INFO_2D", address, scope)

    assert len(packages) == 1
    package = packages[0]
    assert (package.field, package.offset, package.length, package.data_bytes) == (
        "train_tmcc_id",
        0x1C,
        2,
        b"\xff\xff",
    )
    request = package.as_request(address, scope, record_no=654)
    assert isinstance(request, (BaseReq, D4Req))
    decoded = BaseReq(request.as_bytes) if address <= 99 else D4Req(request.as_bytes)
    assert decoded.scope == scope
    if isinstance(decoded, D4Req):
        assert decoded.record_no == 654
        # D4Req exposes its raw payload only through this private attribute.
        # noinspection PyProtectedMember
        assert decoded._data_bytes == b"\xff\xff"
    else:
        assert decoded.tmcc_id == address
        assert decoded.data_bytes == b"\xff\xff"
    assert decoded.start == 0x1C
    assert decoded.data_length == 2


@pytest.mark.parametrize("payload", [b"\x12", b"\x12\x34\x56\x78\x9a"])
def test_raw_transform_uses_exact_payload_without_field_encoding_or_padding(monkeypatch, payload):
    transform = Mock(return_value=payload)
    encoder = Mock(side_effect=AssertionError("Raw bytes must bypass the field encoder."))
    monkeypatch.setitem(REQUEST_TO_UPDATES_MAP, "TEST_RAW_WRITE", [("road_number", transform)])
    handler = SCOPE_TO_COMP_MAP[CommandScope.ENGINE][0x3F]
    assert isinstance(handler, CompDataHandler)
    monkeypatch.setattr(handler, "to_bytes", encoder)

    packages = CompData.field_to_updates("TEST_RAW_WRITE", 7, data=42)

    transform.assert_called_once_with(42)
    encoder.assert_not_called()
    assert len(packages) == 1
    assert (packages[0].offset, packages[0].length, packages[0].data_bytes) == (0x3F, len(payload), payload)


def test_empty_raw_transform_is_rejected(monkeypatch):
    monkeypatch.setitem(REQUEST_TO_UPDATES_MAP, "TEST_RAW_WRITE", [("train_tmcc_id", lambda _: b"")])

    with pytest.raises(ValueError, match="Memory update must contain at least one byte."):
        CompData.field_to_updates("TEST_RAW_WRITE", 7)


@pytest.mark.parametrize("payload", [b"\x12\x34", b""])
def test_direct_raw_field_data_uses_the_same_write_rules(payload):
    # Exercise direct input at the shared encoding boundary without a transform.
    if not payload:
        with pytest.raises(ValueError, match="Memory update must contain at least one byte."):
            # noinspection PyProtectedMember
            CompData._create_update_pkg("train_tmcc_id", True, CommandScope.ENGINE, 7, payload)
    else:
        # noinspection PyProtectedMember
        package = CompData._create_update_pkg("train_tmcc_id", True, CommandScope.ENGINE, 7, payload)
        assert package is not None
        assert (package.offset, package.length, package.data_bytes) == (0x1C, 2, payload)


@pytest.mark.parametrize("scope", list(CommandScope))
@pytest.mark.parametrize("address", [None, 0, 1, 99, 100, 1234, 9999, 10000])
def test_make_key_selects_d4_only_for_engine_and_train_addresses(scope, address):
    expected = scope
    if scope in (CommandScope.ENGINE, CommandScope.TRAIN) and address in (100, 1234, 9999):
        expected = (scope, "D4")

    # Test this private routing boundary directly, including its supported None sentinel.
    # noinspection PyProtectedMember
    assert CompData._make_key(scope, address) == expected


@pytest.mark.parametrize("address", [100, 1234, 9999])
def test_clear_train_info_4d_writes_record_reference_and_unit_in_one_packet(monkeypatch, address):
    handler = SCOPE_TO_COMP_MAP[(CommandScope.ENGINE, "D4")][0xB4]
    assert isinstance(handler, CompDataHandler)
    encoder = Mock(side_effect=AssertionError("The three-byte clear must bypass the two-byte field encoder."))
    monkeypatch.setattr(handler, "to_bytes", encoder)

    packages = CompData.field_to_updates("CLEAR_TRAIN_INFO_4D", address)

    encoder.assert_not_called()
    assert len(packages) == 1
    package = packages[0]
    assert (package.field, package.offset, package.length, package.data_bytes) == (
        "train_record_no",
        0xB4,
        3,
        b"\xff\xff\xff",
    )
    request = package.as_request(address, CommandScope.ENGINE, record_no=654)
    assert isinstance(request, D4Req)
    decoded = D4Req(request.as_bytes)
    assert decoded.pdi_command == PdiCommand.D4_ENGINE
    assert decoded.action == D4Action.UPDATE
    assert decoded.record_no == 654
    assert decoded.start == 0xB4
    assert decoded.data_length == 3
    # The D4 payload is private; inspect it to verify all three wire bytes.
    # noinspection PyProtectedMember
    assert decoded._data_bytes == b"\xff\xff\xff"


@pytest.mark.parametrize("scope, address", [(CommandScope.ENGINE, 99), (CommandScope.TRAIN, 1234)])
def test_clear_train_info_4d_does_not_write_other_record_layouts(scope, address):
    assert CompData.field_to_updates("CLEAR_TRAIN_INFO_4D", address, scope) == []


@pytest.mark.parametrize(
    "field, value, expected_offset, expected_payload",
    [("train_record_no", 0x1234, 0xB4, b"\x34\x12"), ("train_unit_4d", 3, 0xB6, b"\x03")],
)
def test_generated_d4_field_request_selects_maps_using_existing_address(
    field, value, expected_offset, expected_payload
):
    request = CompData.generate_update_req(field, value, scope=CommandScope.ENGINE, address=1234)

    assert isinstance(request, D4Req)
    assert request.start == expected_offset
    assert request.data_length == len(expected_payload)
    # The private D4 payload verifies encoding through the public request builder.
    # noinspection PyProtectedMember
    assert request._data_bytes == expected_payload


@pytest.mark.parametrize("scope", list(CommandScope))
@pytest.mark.parametrize("address", [None, 1, 99, 1234])
@pytest.mark.parametrize("d4", [False, True])
def test_make_key_explicit_d4_override_preserves_scope_and_address_routing(scope, address, d4):
    expected = scope
    if scope in (CommandScope.ENGINE, CommandScope.TRAIN) and (d4 or address == 1234):
        expected = (scope, "D4")

    # Exercise the private routing helper to verify channel and address selection independently.
    # noinspection PyProtectedMember
    assert CompData._make_key(scope, address, d4=d4) == expected
