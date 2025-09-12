#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import re
import types

import pytest

from src.pytrain.db.comp_data import (
    AccessoryData,
    CompData,
    CompDataHandler,
    CompDataMixin,
    EngineData,
    RouteData,
    SwitchData,
    TrainData,
    UpdatePkg,
)
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.protocol.constants import LEGACY_CONTROL_TYPE, CommandScope
from src.pytrain.protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum


class TestCompData:
    def test_comp_data_handler(self):
        # default handler
        h = CompDataHandler("_speed")
        assert h.field == "_speed"
        assert h.length == 1
        assert callable(h.from_bytes)
        assert callable(h.to_bytes)
        assert h.is_d4_only is False

        # custom handler (multibyte, d4_only)
        to_bytes_called = []

        def _to_bytes(x: int) -> bytes:
            to_bytes_called.append(True)
            return x.to_bytes(2, "little")

        h2 = CompDataHandler("_bt_id", length=2, to_bytes=_to_bytes, d4_only=True)
        assert h2.field == "_bt_id"
        assert h2.length == 2
        assert h2.is_d4_only is True
        # smoke test conversion callback
        bts = h2.to_bytes(513)  # 0x0201
        assert bts == b"\x01\x02"
        assert to_bytes_called, "custom to_bytes must be invoked"

    def test_update_pkg(self):
        pkg = UpdatePkg("speed", 0x07, 1, b"\x2a")
        s = repr(pkg)
        # format: "<field>: Address: <hex> Length: <len> data: <hex data>"
        assert "speed" in s
        assert "Address: 0x7" in s
        assert "Length: 1" in s
        assert re.search(r"data:\s*2a", s) is not None

    def test_comp_data_from_bytes_factory(self):
        # Build a buffer of correct length for each scope and ensure subclass is returned
        for scope, expected_cls in [
            (CommandScope.ENGINE, EngineData),
            (CommandScope.TRAIN, TrainData),
            (CommandScope.ACC, AccessoryData),
            (CommandScope.SWITCH, SwitchData),
            (CommandScope.ROUTE, RouteData),
        ]:
            buf = b"\xff" * PdiReq.scope_record_length(scope)
            tmcc_id = 1234 if scope in {CommandScope.ENGINE, CommandScope.TRAIN} else 12
            obj = CompData.from_bytes(buf, scope, tmcc_id=tmcc_id)
            assert isinstance(obj, expected_cls)
            assert obj._scope == scope  # internal scope set by base class

        with pytest.raises(ValueError):
            # Invalid scope must raise
            CompData.from_bytes(b"", types.SimpleNamespace(name="BOGUS"), tmcc_id=1)  # type: ignore[arg-type]

    def test_engine_data_is_legacy_flag_and_smoke_mapping(self):
        # Initialize with padded bytes so all fields get some numeric defaults
        buf = b"\xff" * PdiReq.scope_record_length(CommandScope.ENGINE)
        eng = EngineData(buf, tmcc_id=1000)

        # Default: not legacy unless control_type matches constant
        assert eng.is_legacy is False
        # Force legacy and test TMCC2 smoke mapping via _tmcc attribute access
        eng._control_type = LEGACY_CONTROL_TYPE

        # Set raw base smoke value (0..3) and read TMCC2 enum via property mapping
        eng.smoke = 3  # sets _smoke directly via overridden __setattr__
        assert eng.smoke_tmcc == TMCC2EffectsControl.SMOKE_HIGH

        # Now flip to non-legacy mapping (TMCC1). Reading should map to TMCC1 enums.
        eng._control_type = 0x00  # anything different
        eng.smoke = 0
        assert eng.smoke_tmcc == TMCC1EngineCommandEnum.SMOKE_OFF

        # Setting smoke via TMCC mapping should store base value correctly
        eng._control_type = LEGACY_CONTROL_TYPE  # legacy again => use TMCC2 -> base map
        eng.smoke_tmcc = TMCC2EffectsControl.SMOKE_MEDIUM
        assert eng.smoke == 2

        eng._control_type = 0x00  # non-legacy => TMCC1 -> base map
        eng.smoke_tmcc = TMCC1EngineCommandEnum.SMOKE_ON
        assert eng.smoke == 1

    def test_engine_data_conversions_basic(self):
        buf = b"\xff" * PdiReq.scope_record_length(CommandScope.ENGINE)
        eng = EngineData(buf, tmcc_id=1000)

        # momentum conversion: external "tmcc" value <-> base value
        eng.momentum_tmcc = 6
        # base value should be roughly round(6 * 18.14) = 3 (capped 0..127)
        assert eng.momentum == 109
        # reading back should invert: round(109 * 0.05512) -> ~54 (capped 0..7)
        assert eng.momentum_tmcc == 6

        # train_brake conversion
        eng.train_brake_tmcc = 5
        # base ~ round(5 * 2.143)=11
        assert eng.train_brake == 11
        # invert
        assert eng.train_brake_tmcc == 5

        # rpm/labor combined conversion
        eng.rpm_tmcc = 5
        eng.labor_tmcc = 14
        # verify combined field was encoded
        assert isinstance(eng._rpm_labor, int)
        # accessing rpm/labor again returns masked/decoded
        assert eng.rpm_tmcc == 5
        assert eng.labor_tmcc == 14

    def test_repr_formats_by_scope(self):
        # Engine/Train use 4 digits, others 2, include payload, name, and number
        ebuf = b"\xff" * PdiReq.scope_record_length(CommandScope.ENGINE)
        eng = EngineData(ebuf, tmcc_id=7)
        eng.road_name = "abc railroad"
        eng.road_number = "123"
        s_eng = repr(eng)
        assert "Engine 0007:" in s_eng
        assert "#123" in s_eng
        # Title-cased road name
        assert "ABC Railroad" in s_eng

        sbuf = b"\xff" * PdiReq.scope_record_length(CommandScope.SWITCH)
        sw = SwitchData(sbuf, tmcc_id=7)
        sw.road_name = "yard"
        sw.road_number = "5"
        s_sw = repr(sw)
        assert "Switch  7:" in s_sw
        assert "Yard" in s_sw
        assert "#5" in s_sw

    def test_as_bytes_round_length_and_padding(self):
        # For each scope, ensure as_bytes returns a buffer sized to scope_record_length
        for scope, cls in [
            (CommandScope.ENGINE, EngineData),
            (CommandScope.TRAIN, TrainData),
            (CommandScope.ACC, AccessoryData),
            (CommandScope.SWITCH, SwitchData),
            (CommandScope.ROUTE, RouteData),
        ]:
            data_len = PdiReq.scope_record_length(scope)
            b = b"\xff" * data_len
            # tmcc_id: >99 for engine/train to keep 4-digit fields present, <=99 for others
            tmcc_id = 1234 if scope in {CommandScope.ENGINE, CommandScope.TRAIN} else 12
            obj = cls(b, tmcc_id=tmcc_id)  # type: ignore[call-arg]
            out = obj.as_bytes()
            assert isinstance(out, bytes)
            assert len(out) == data_len

    def test_route_payload_renders_components(self):
        # Build a RouteData and inject simple components with the required attributes
        buf = b"\xff" * PdiReq.scope_record_length(CommandScope.ROUTE)
        route = RouteData(buf, tmcc_id=42)

        class _FakeSwitch:
            is_route = False
            is_switch = True

            def __init__(self, tid: int, thru: bool):
                self.tmcc_id = tid
                self.is_thru = thru

        class _FakeRoute:
            is_route = True
            is_switch = False

            def __init__(self, tid: int):
                self.tmcc_id = tid

        # Set via CompData __setattr__ (non-underscore attribute supported)
        route.components = [
            _FakeRoute(3),
            _FakeSwitch(7, True),
            _FakeSwitch(9, False),
            _FakeRoute(11),
        ]
        payload = route.payload()
        # Expected fragments appear
        assert "Routes:" in payload and " 3" in payload and "11" in payload
        assert "Switches:" in payload and " 7 [thru]" in payload and " 9 [out]" in payload

    def test_comp_data_mixin_initialize_sets_types_and_flag(self):
        class Holder(CompDataMixin):
            def __init__(self):
                super().__init__()

        for scope, expected_cls in [
            (CommandScope.ENGINE, EngineData),
            (CommandScope.TRAIN, TrainData),
            (CommandScope.ACC, AccessoryData),
            (CommandScope.SWITCH, SwitchData),
            (CommandScope.ROUTE, RouteData),
        ]:
            h = Holder()
            h.initialize(scope, tmcc_id=55 if scope != CommandScope.ENGINE else 1234)
            assert h.is_comp_data_record is True
            assert isinstance(h.comp_data, expected_cls)

    def test_comp_data_encode_rpm_labor_and_pkg(self):
        # Encode rpm/labor -> combined byte and into UpdatePkg
        val = CompData.encode_rpm_labor(rpm=5, labor=14)
        assert isinstance(val, int)
        pkg = CompData.rpm_labor_to_pkg(rpm=5, labor=14)
        assert isinstance(pkg, UpdatePkg)
        # data_bytes should be 1 byte representing encoded value
        assert len(pkg.data_bytes) == 1
        assert pkg.length == 1

    def test_missing_attribute_raises_attribute_error(self):
        buf = b"\xff" * PdiReq.scope_record_length(CommandScope.ENGINE)
        eng = EngineData(buf, tmcc_id=1000)
        with pytest.raises(AttributeError):
            _ = eng.this_attribute_does_not_exist  # noqa: B018
