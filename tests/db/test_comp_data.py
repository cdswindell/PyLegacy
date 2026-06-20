#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
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
    FIRST_DATUM_ADDR,
    RouteData,
    SwitchData,
    TrainData,
    UpdatePkg,
)
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.protocol.constants import LEGACY_CONTROL_TYPE, CommandScope
from src.pytrain.protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum


CLEAR_ROAD_NAME_NUMBER_DATA = b"\x00" + (b"\xff" * 31) + b"\x00" + (b"\xff" * 4)


def road_number_update_data(road_number_text: str | None) -> bytes:
    road_number_len = len(road_number_text) if road_number_text else 0
    return road_number_len.to_bytes(1, "big") + PdiReq.encode_text(road_number_text, 4)


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
        # smoke tests conversion callback
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
        # Force legacy and tests TMCC2 smoke mapping via _tmcc attribute access
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

    @pytest.mark.parametrize(
        ("scope", "tmcc_id"),
        [
            (CommandScope.ENGINE, 1234),
            (CommandScope.TRAIN, 1234),
            (CommandScope.ACC, 55),
            (CommandScope.SWITCH, 55),
            (CommandScope.ROUTE, 55),
        ],
    )
    def test_comp_data_mixin_initialized_records_serialize(self, scope, tmcc_id):
        class Holder(CompDataMixin):
            def __init__(self):
                super().__init__()

        h = Holder()
        h.initialize(scope, tmcc_id=tmcc_id)

        out = h.comp_data.as_bytes()

        assert len(out) == PdiReq.scope_record_length(scope)

    def test_comp_data_mixin_initialized_route_and_train_have_empty_component_blocks(self):
        class Holder(CompDataMixin):
            def __init__(self):
                super().__init__()

        route = Holder()
        route.initialize(CommandScope.ROUTE, tmcc_id=55)
        route_data = route.comp_data.as_bytes()
        assert route.comp_data.components is None
        assert route.comp_data.payload() == ""
        assert route_data[0x60:0x80] == b"\xff" * 32

        train = Holder()
        train.initialize(CommandScope.TRAIN, tmcc_id=55)
        train_data = train.comp_data.as_bytes()
        assert train.comp_data.consist_comps is None
        assert train_data[0x70:0x90] == b"\xff" * 32

    @pytest.mark.parametrize(
        ("scope", "tmcc_id", "expected_defaults"),
        [
            (
                CommandScope.ENGINE,
                1234,
                {
                    "_record_type": 4,
                    "_bt_id": 0,
                    "_unk_6": 0,
                    "_speed": 0,
                    "_target_speed": 0,
                    "_train_brake": 0,
                    "_control_id": 0,
                    "_unk_b": 0,
                    "_rpm_labor": 0,
                    "_labor_level": 0,
                    "_unk_12": 0,
                    "_unk_13": 0,
                    "_momentum": 0,
                    "_road_name_len": 0,
                    "_road_number_len": 0,
                },
            ),
            (
                CommandScope.TRAIN,
                1234,
                {
                    "_record_type": 3,
                    "_bt_id": 0,
                    "_unk_6": 0,
                    "_speed": 0,
                    "_target_speed": 0,
                    "_train_brake": 0,
                    "_control_id": 0,
                    "_unk_b": 0,
                    "_rpm_labor": 0,
                    "_labor_level": 0,
                    "_unk_12": 0,
                    "_unk_13": 0,
                    "_momentum": 0,
                    "_road_name_len": 0,
                    "_road_number_len": 0,
                },
            ),
            (
                CommandScope.ACC,
                55,
                {
                    "_record_type": 1,
                    "_road_name_len": 0,
                    "_road_number_len": 0,
                },
            ),
            (
                CommandScope.SWITCH,
                55,
                {
                    "_record_type": 0,
                    "_road_name_len": 0,
                    "_road_number_len": 0,
                },
            ),
            (
                CommandScope.ROUTE,
                55,
                {
                    "_record_type": 2,
                    "_road_name_len": 0,
                    "_road_number_len": 0,
                },
            ),
        ],
    )
    def test_comp_data_mixin_initialize_sets_handler_defaults(self, scope, tmcc_id, expected_defaults):
        class Holder(CompDataMixin):
            def __init__(self):
                super().__init__()

        h = Holder()
        h.initialize(scope, tmcc_id=tmcc_id)

        for field, expected_value in expected_defaults.items():
            assert getattr(h.comp_data, field) == expected_value

    @pytest.mark.parametrize(
        ("data_cls", "expected_scope", "expected_start"),
        [
            (EngineData, CommandScope.ENGINE, 0x1E),
            (TrainData, CommandScope.TRAIN, 0x1E),
            (AccessoryData, CommandScope.ACC, 0x1E),
            (SwitchData, CommandScope.SWITCH, 0x04),
            (RouteData, CommandScope.ROUTE, 0x04),
        ],
    )
    def test_clear_road_name_number_req_builds_base_memory_update(
        self,
        data_cls,
        expected_scope,
        expected_start,
    ):
        req = data_cls.clear_road_name_number_req(55)

        assert isinstance(req, BaseReq)
        assert req.pdi_command == PdiCommand.BASE_MEMORY
        assert req.tmcc_id == 55
        assert req.scope == expected_scope
        assert req.flags == 0xC3
        assert req.start == expected_start
        assert req.data_length == len(CLEAR_ROAD_NAME_NUMBER_DATA)
        assert req.data_bytes == CLEAR_ROAD_NAME_NUMBER_DATA

    @pytest.mark.parametrize(
        ("data_cls", "expected_scope", "expected_pdi_command"),
        [
            (EngineData, CommandScope.ENGINE, PdiCommand.D4_ENGINE),
            (TrainData, CommandScope.TRAIN, PdiCommand.D4_TRAIN),
        ],
    )
    def test_clear_road_name_number_req_builds_d4_update_for_four_digit_entries(
        self,
        monkeypatch,
        data_cls,
        expected_scope,
        expected_pdi_command,
    ):
        calls = []

        def get_state(scope, tmcc_id, create):
            calls.append((scope, tmcc_id, create))
            return types.SimpleNamespace(record_no=321)

        monkeypatch.setattr(ComponentStateStore, "get_state", staticmethod(get_state))

        req = data_cls.clear_road_name_number_req(1234)

        assert calls == [(expected_scope, 1234, False)]
        assert isinstance(req, D4Req)
        assert req.pdi_command == expected_pdi_command
        assert req.action == D4Action.UPDATE
        assert req.record_no == 321
        assert req.scope == expected_scope
        assert req.start == 0x1E
        assert req.data_length == len(CLEAR_ROAD_NAME_NUMBER_DATA)
        assert req._data_bytes == CLEAR_ROAD_NAME_NUMBER_DATA  # pylint: disable=protected-access

    def test_clear_road_name_number_req_rejects_unmapped_class(self):
        with pytest.raises(AttributeError, match="Invalid CompData"):
            CompData.clear_road_name_number_req(55)

    @pytest.mark.parametrize(
        ("data_cls", "scope"),
        [
            (EngineData, CommandScope.ENGINE),
            (TrainData, CommandScope.TRAIN),
        ],
    )
    def test_clear_record_reqs_include_full_record_clear_for_engine_train(self, data_cls, scope):
        state = types.SimpleNamespace(scope=scope, address=55)

        reqs = data_cls.clear_record_reqs(state)

        assert len(reqs) == 3
        assert reqs[-1] is state
        clear_req = reqs[1]
        assert isinstance(clear_req, BaseReq)
        assert clear_req.tmcc_id == 55
        assert clear_req.scope == scope
        assert clear_req.start == FIRST_DATUM_ADDR
        assert clear_req.data_length == PdiReq.scope_record_length(scope) - FIRST_DATUM_ADDR

    @pytest.mark.parametrize(
        ("data_cls", "scope"),
        [
            (EngineData, CommandScope.ENGINE),
            (TrainData, CommandScope.TRAIN),
            (AccessoryData, CommandScope.ACC),
            (SwitchData, CommandScope.SWITCH),
            (RouteData, CommandScope.ROUTE),
        ],
    )
    def test_clear_record_reqs_full_clear_payload_matches_scope_record_size(self, data_cls, scope):
        state = types.SimpleNamespace(scope=scope, address=42)

        clear_req = data_cls.clear_record_reqs(state)[1]

        assert clear_req.data_length == len(clear_req.data_bytes)
        assert clear_req.start + clear_req.data_length == PdiReq.scope_record_length(scope)

    def test_clear_record_reqs_route_uses_state_address_without_raising(self):
        state = types.SimpleNamespace(scope=CommandScope.ROUTE, address=42)

        reqs = RouteData.clear_record_reqs(state)

        assert reqs[-1] is state
        assert isinstance(reqs[0], BaseReq)
        assert reqs[0].tmcc_id == 42
        assert reqs[0].scope == CommandScope.ROUTE
        assert reqs[0].start == 0x04

    @pytest.mark.parametrize(
        ("data_cls", "scope", "expected_start"),
        [
            (EngineData, CommandScope.ENGINE, 0x3E),
            (TrainData, CommandScope.TRAIN, 0x3E),
            (AccessoryData, CommandScope.ACC, 0x3E),
            (SwitchData, CommandScope.SWITCH, 0x24),
            (RouteData, CommandScope.ROUTE, 0x24),
        ],
    )
    def test_set_road_number_req_builds_base_memory_update(self, data_cls, scope, expected_start):
        data = b"\xff" * PdiReq.scope_record_length(scope)
        comp_data = data_cls(data, tmcc_id=55)

        req = comp_data.set_road_number_req(7)

        assert isinstance(req, BaseReq)
        assert req.pdi_command == PdiCommand.BASE_MEMORY
        assert req.tmcc_id == 55
        assert req.scope == scope
        assert req.flags == 0xC3
        assert req.start == expected_start
        assert req.data_length == 5
        assert req.data_bytes == road_number_update_data("0007")
        assert comp_data.road_number == "0007"
        assert comp_data.road_number_len == 4

    @pytest.mark.parametrize(
        ("data_cls", "scope", "expected_pdi_command"),
        [
            (EngineData, CommandScope.ENGINE, PdiCommand.D4_ENGINE),
            (TrainData, CommandScope.TRAIN, PdiCommand.D4_TRAIN),
        ],
    )
    def test_set_road_number_req_builds_d4_update_for_four_digit_entries(
        self,
        monkeypatch,
        data_cls,
        scope,
        expected_pdi_command,
    ):
        calls = []

        def get_state(state_scope, tmcc_id, create):
            calls.append((state_scope, tmcc_id, create))
            return types.SimpleNamespace(record_no=654)

        monkeypatch.setattr(ComponentStateStore, "get_state", staticmethod(get_state))
        comp_data = data_cls(b"\xff" * PdiReq.scope_record_length(scope), tmcc_id=1234)

        req = comp_data.set_road_number_req(7)

        assert calls == [(scope, 1234, False)]
        assert isinstance(req, D4Req)
        assert req.pdi_command == expected_pdi_command
        assert req.action == D4Action.UPDATE
        assert req.record_no == 654
        assert req.scope == scope
        assert req.start == 0x3E
        assert req.data_length == 5
        assert req._data_bytes == road_number_update_data("0007")  # pylint: disable=protected-access
        assert comp_data.road_number == "0007"
        assert comp_data.road_number_len == 4

    def test_set_road_number_req_with_none_clears_road_number(self):
        comp_data = EngineData(b"\xff" * PdiReq.scope_record_length(CommandScope.ENGINE), tmcc_id=55)

        req = comp_data.set_road_number_req(None)

        assert req.data_bytes == road_number_update_data(None)
        assert comp_data.road_number == ""
        assert comp_data.road_number_len == 0

    def test_set_road_number_req_rejects_out_of_range_value(self):
        comp_data = EngineData(b"\xff" * PdiReq.scope_record_length(CommandScope.ENGINE), tmcc_id=55)

        with pytest.raises(ValueError, match="Road Number must be less than or equal to 9999"):
            comp_data.set_road_number_req(10000)

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
