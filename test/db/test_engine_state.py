#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
import pytest

from src.pytrain import TMCC2EffectsControl, CommandScope
from src.pytrain.db.comp_data import CompData
from src.pytrain.db.components import ConsistComponent
from src.pytrain.db.engine_state import EngineState, TrainState
from src.pytrain.protocol.constants import LEGACY_CONTROL_TYPE, TMCC_CONTROL_TYPE
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum as TMCC1
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as TMCC2


class TestEngineStateBehavior:
    @staticmethod
    def _new_engine(addr: int = 7) -> EngineState:
        st = EngineState(CommandScope.ENGINE)
        # Simulate that component data is known/allocated
        st.initialize(CommandScope.ENGINE, addr)
        # Set address so properties relying on it work predictably
        st._address = addr  # type: ignore[attr-defined]
        return st

    def test_is_legacy_deduction_by_address_and_control_type(self):
        e1 = self._new_engine(addr=7)
        # No control type set, address <= 99 defaults to TMCC unless control_type marks Legacy
        assert e1.is_legacy is False

        # Force Legacy via control_type on base data
        e1.comp_data._control_type = LEGACY_CONTROL_TYPE  # type: ignore[attr-defined]
        assert e1.is_legacy is True

        # 4-digit address implies Legacy if _is_legacy not explicitly set
        e2 = self._new_engine(addr=2345)
        # Clear any control_type so the address rule applies
        e2.comp_data._control_type = None  # type: ignore[attr-defined]
        assert e2.is_legacy is True

    def test_engine_state_without_comp_data_no_exception(self):
        e = EngineState(CommandScope.ENGINE)
        e._address = 123
        assert e.tmcc_id == 123
        assert str(e) == "Engine 0123: no information provided from Base 2/3"

    def test_decode_speed_info_255_conversion(self):
        e = self._new_engine()
        # Explicitly force protocol flavor
        assert not e.is_legacy
        assert e.decode_speed_info(255) == 31
        e._comp_data._control_type = LEGACY_CONTROL_TYPE
        assert e.is_legacy
        assert e.decode_speed_info(255) == 195
        # Pass-through non-255
        assert e.decode_speed_info(20) == 20

    def test_speed_max_logic_limits(self):
        e = self._new_engine()
        e._comp_data._control_type = LEGACY_CONTROL_TYPE
        e.comp_data._speed_limit = 255  # type: ignore[attr-defined]
        assert e.speed_max == 199  # legacy default cap when limits unset (255)

        e.comp_data._max_speed = 200  # type: ignore[attr-defined]
        e.comp_data._speed_limit = 255  # type: ignore[attr-defined]
        assert e.speed_max == 200  # legacy default cap when limits unset (255)

        # Non-legacy should never exceed 31
        e._comp_data._control_type = TMCC_CONTROL_TYPE
        e._is_legacy = False  # type: ignore[attr-defined]
        e.comp_data._max_speed = 100  # type: ignore[attr-defined]
        e.comp_data._speed_limit = 100  # type: ignore[attr-defined]
        assert e.speed_max == 31

        # Both limits present -> pick min; still capped for TMCC
        e.comp_data._max_speed = 20  # type: ignore[attr-defined]
        e.comp_data._speed_limit = 25  # type: ignore[attr-defined]
        assert e.speed_max == 20

    def test_change_direction_toggle_tmcc1_and_tmcc2(self):
        e = self._new_engine()
        # Start in TMCC1; set a TMCC1 direction
        e._comp_data._control_type = TMCC_CONTROL_TYPE
        e._is_legacy = False  # type: ignore[attr-defined]
        e._direction = TMCC1.FORWARD_DIRECTION  # type: ignore[attr-defined]
        nd = e._change_direction(TMCC1.TOGGLE_DIRECTION)
        assert nd == TMCC1.REVERSE_DIRECTION

        nd2 = e._change_direction(TMCC1.TOGGLE_DIRECTION)
        # _change_direction doesn't mutate state; simulate applying result
        e._direction = nd2  # type: ignore[attr-defined]
        nd3 = e._change_direction(TMCC1.TOGGLE_DIRECTION)
        assert nd3 == TMCC1.FORWARD_DIRECTION

        # Now simulate Legacy/TMCC2 flavor and TMCC2 direction
        e._comp_data._control_type = LEGACY_CONTROL_TYPE
        e._is_legacy = True  # type: ignore[attr-defined]
        e._direction = TMCC2.FORWARD_DIRECTION  # type: ignore[attr-defined]
        nd4 = e._change_direction(TMCC2.TOGGLE_DIRECTION)
        assert nd4 == TMCC2.REVERSE_DIRECTION

    def test_as_bytes_yields_packets_list(self):
        e = self._new_engine(addr=12)  # <=99 so BaseReq BASE_MEMORY should be first
        # Provide some extra state that can be serialized if present
        e._start_stop = TMCC1.START_UP_IMMEDIATE  # type: ignore[attr-defined]
        # Use a smoke value the mapping will understand
        e.comp_data.smoke_tmcc = TMCC2EffectsControl.SMOKE_LOW

        packets = e.as_bytes()
        # EngineState.as_bytes returns list[bytes]
        assert isinstance(packets, list)
        assert len(packets) >= 1
        assert all(isinstance(p, (bytes, bytearray)) for p in packets)

    def test_smoke_label_mapping(self):
        e = self._new_engine()
        assert e.is_tmcc

        # force legacy mode
        e._comp_data._control_type = LEGACY_CONTROL_TYPE
        assert e.is_legacy
        e.comp_data.smoke_tmcc = TMCC2EffectsControl.SMOKE_OFF
        assert e.smoke_label == "-"
        e.comp_data.smoke_tmcc = TMCC2EffectsControl.SMOKE_LOW
        assert e.smoke_label == "L"
        e.comp_data.smoke_tmcc = TMCC2EffectsControl.SMOKE_MEDIUM
        assert e.smoke_label == "M"
        e.comp_data.smoke_tmcc = TMCC2EffectsControl.SMOKE_HIGH
        assert e.smoke_label == "H"

    def test_as_dict_includes_core_fields_engine(self):
        e = self._new_engine()
        # Populate some comp data fields
        e.comp_data._speed = 10  # type: ignore[attr-defined]
        e.comp_data._momentum = 73  # type: ignore[attr-defined]
        e.comp_data._rpm_labor = CompData.encode_rpm_labor(rpm=5, labor=14)  # type: ignore[attr-defined]
        e.comp_data._engine_type = 0  # type: ignore[attr-defined]
        e.comp_data._sound_type = 0  # type: ignore[attr-defined]
        e.comp_data._engine_class = 0  # type: ignore[attr-defined]
        e.comp_data._control_type = LEGACY_CONTROL_TYPE  # type: ignore[attr-defined]
        e._direction = TMCC2.FORWARD_DIRECTION  # type: ignore[attr-defined]
        e.comp_data.smoke_tmcc = TMCC2EffectsControl.SMOKE_LOW

        d = e.as_dict()
        # spot-check expected keys
        assert d["scope"] == "engine"
        assert d["tmcc_id"] == e.tmcc_id
        assert d["speed"] == 10
        assert d["direction"] == "forward_direction"
        assert d["smoke"] == "smoke_low"
        assert "engine_type" in d and "sound_type" in d and "engine_class" in d

    # noinspection PyUnresolvedReferences
    def test_can_not_define_out_of_scope_field(self):
        e = self._new_engine()
        with pytest.raises(AttributeError):
            _ = e.this_attribute_does_not_exist

    def test_train_state_as_dict_includes_consist(self):
        t = TrainState(CommandScope.TRAIN)
        t.initialize(CommandScope.TRAIN, tmcc_id=101)
        t._address = 101  # type: ignore[attr-defined]
        # Add some consist components
        t.comp_data._consist_flags = 0b10101010  # type: ignore[attr-defined]
        t.comp_data._consist_comps = [  # type: ignore[attr-defined]
            ConsistComponent(tmcc_id=11, flags=0b00000001),
            ConsistComponent(tmcc_id=22, flags=0b00000100),
        ]
        d = t.as_dict()
        assert d["scope"] == "train"
        assert isinstance(d["flags"], int)
        assert isinstance(d["components"], dict)
        # Keys are component tmcc_ids; values are info strings
        assert 11 in d["components"] and 22 in d["components"]
