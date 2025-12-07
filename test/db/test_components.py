#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

from src.pytrain.db.components import ConsistComponent, RouteComponent, UnitBits
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum


class TestConsistComponent:
    def test_as_bytes_and_properties_single_forward(self):
        # flags: unit SINGLE (00), forward (bit 2 = 0), train_linked off, horn/dialog off, tmcc2 off, accessory off
        flags = 0b00000000
        c = ConsistComponent(tmcc_id=7, flags=flags)

        assert c.tmcc_id == 7
        assert c.flags == flags
        assert c.unit_type == UnitBits.SINGLE
        assert c.is_single is True
        assert c.is_head is False
        assert c.is_middle is False
        assert c.is_tail is False

        assert c.is_forward is True
        assert c.is_reverse is False

        assert c.is_train_link is False
        assert c.is_horn_masked is False
        assert c.is_dialog_masked is False
        assert c.is_tmcc2 is False
        assert c.is_accessory is False

        # as_bytes: [flags][tmcc_id]
        assert c.as_bytes == bytes([flags, 7])

        # info/repr should be non-empty strings
        assert isinstance(c.info, str) and c.info
        assert isinstance(repr(c), str) and repr(c)

    def test_flag_bits_combinations(self):
        # Compose flags: TAIL (11), reverse (bit2=1), train_linked (bit3), horn_masked (bit4),
        # dialog_masked (bit5), tmcc2(bit6), accessory(bit7)
        flags = 0b11111111  # all bits set
        c = ConsistComponent(tmcc_id=42, flags=flags)

        assert c.unit_type == UnitBits.TAIL
        assert c.is_tail is True
        assert c.is_reverse is True
        assert c.is_forward is False
        assert c.is_train_link is True
        assert c.is_horn_masked is True
        assert c.is_dialog_masked is True
        assert c.is_tmcc2 is True
        assert c.is_accessory is True

    def test_from_bytes_parses_until_ff_pairs_and_reverses_order(self):
        # Build byte stream of up to 32 bytes (16 pairs), using non-FF pairs, then terminator pairs
        comps = [
            ConsistComponent(1, 0x00),
            ConsistComponent(2, 0x11),
            ConsistComponent(3, 0x22),
        ]
        # to_bytes reverses components during output; we want the raw byte order here:
        raw = b""
        for comp in reversed(comps):
            raw += comp.as_bytes
        # pad to 32 bytes with 0xFF
        raw += b"\xff" * (32 - len(raw))

        parsed = ConsistComponent.from_bytes(raw)
        # from_bytes inserts at 0, meaning reverse of encounter; given iteration i=0..,
        # it ends up reversing to original logical order comps
        assert len(parsed) == 3
        for a, b in zip(parsed, comps):
            assert a.tmcc_id == b.tmcc_id
            assert a.flags == b.flags

    def test_to_bytes_serializes_reversed_and_pads(self):
        comps = [
            ConsistComponent(10, 0x01),
            ConsistComponent(20, 0x02),
        ]
        byt = ConsistComponent.to_bytes(comps)
        assert isinstance(byt, (bytes, bytearray))
        assert len(byt) == 32

        # Expect reversed order in the leading bytes
        # Reversed: [comp2, comp1]
        expected = comps[1].as_bytes + comps[0].as_bytes
        assert byt[: len(expected)] == expected
        assert byt[len(expected) :] == b"\xff" * (32 - len(expected))


class TestRouteComponent:
    def test_from_bytes_parses_sorts_by_tmcc_id(self):
        # Create 3 components with out-of-order tmcc_ids
        r1 = RouteComponent(5, 0x00)  # switch thru
        r2 = RouteComponent(2, 0x01)  # switch out
        r3 = RouteComponent(8, 0x03)  # route
        raw = r1.as_bytes + r2.as_bytes + r3.as_bytes
        raw += b"\xff" * (32 - len(raw))

        parsed = RouteComponent.from_bytes(raw)
        # Should be sorted by tmcc_id: 2, 5, 8
        assert [r.tmcc_id for r in parsed] == [2, 5, 8]
        assert parsed[0].is_out is True
        assert parsed[1].is_thru is True
        assert parsed[2].is_route is True

    def test_to_bytes_linear_and_padded(self):
        comps = [RouteComponent(1, 0x00), RouteComponent(2, 0x01)]
        byt = RouteComponent.to_bytes(comps)
        assert isinstance(byt, (bytes, bytearray))
        assert len(byt) == 32
        expected = comps[0].as_bytes + comps[1].as_bytes
        assert byt[: len(expected)] == expected
        assert byt[len(expected) :] == b"\xff" * (32 - len(expected))

    def test_as_signature_switch_and_route(self):
        s = RouteComponent(12, 0x00)  # thru -> switch
        r = RouteComponent(7, 0x03)  # route
        assert s.as_signature == {"S12": True}
        assert r.as_signature == {"R7": True}

    def test_as_request_builds_tmcc1_switch_command(self):
        thru = RouteComponent(3, 0x00)
        out = RouteComponent(4, 0x01)

        t_req = thru.as_request
        o_req = out.as_request

        assert isinstance(t_req, CommandReq)
        assert isinstance(o_req, CommandReq)

        assert t_req.command == TMCC1SwitchCommandEnum.THRU
        assert t_req.address == 3

        assert o_req.command == TMCC1SwitchCommandEnum.OUT
        assert o_req.address == 4

    def test_as_bytes_roundtrip(self):
        r = RouteComponent(9, 0x01)
        b = r.as_bytes
        assert b == bytes([0x01, 9])
