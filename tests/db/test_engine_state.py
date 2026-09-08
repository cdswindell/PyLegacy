#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

import pytest

from src.pytrain import CommandScope, TMCC2EffectsControl
from src.pytrain.comm.comm_buffer import CommBuffer
from src.pytrain.db.comp_data import CompData, CompDataMixin
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.components import ConsistComponent
from src.pytrain.db.engine_state import EngineState, TrainState
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import LEGACY_CONTROL_TYPE, TMCC_CONTROL_TYPE
from src.pytrain.protocol.multibyte.multibyte_constants import TMCC2EngineCommandEnumEx
from src.pytrain.protocol.sequence.speed_ramp import MAX_RPM_BIAS, SpeedRamp
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum as TMCC1, TMCC1HaltCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import (
    TMCC2EngineCommandEnum as TMCC2,
    tmcc2_speed_to_rpm,
)


class TestEngineStateBehavior:
    @staticmethod
    def _new_engine(addr: int = 7) -> EngineState:
        st = EngineState(CommandScope.ENGINE)
        # Simulate that component data is known/allocated
        st.initialize(CommandScope.ENGINE, addr)
        # Set address so properties relying on it work predictably
        st._address = addr  # type: ignore[attr-defined]
        return st

    @staticmethod
    def _new_train(addr: int = 101) -> TrainState:
        st = TrainState(CommandScope.TRAIN)
        st.initialize(CommandScope.TRAIN, addr)
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
        assert e.speed_max == 16

        # Both limits present -> pick min; still capped for TMCC
        e.comp_data._max_speed = 160  # type: ignore[attr-defined]
        e.comp_data._speed_limit = 175  # type: ignore[attr-defined]
        assert e.speed_max == 25

        # set max_speed to not set; should default to speed limit
        e.comp_data._max_speed = 255
        assert e.speed_max == 27

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

    def test_duplicate_command_is_ignored_for_last_command_and_notification(self):
        e = self._new_engine()
        req = CommandReq.build(TMCC1.FORWARD_DIRECTION, e.address)

        e.update(req)
        assert e.last_command == req
        assert e.changed.is_set() is True
        last_updated = e.last_updated

        e.changed.clear()
        e.update(req)

        assert e.last_command == req
        assert e.last_updated == last_updated
        assert e.changed.is_set() is False

    def test_no_change_command_records_without_notification(self):
        e = self._new_engine()
        e._direction = TMCC1.FORWARD_DIRECTION  # type: ignore[attr-defined]
        req = CommandReq.build(TMCC1.FORWARD_DIRECTION, e.address)

        e.update(req)

        assert e.last_command == req
        assert e.last_updated is not None
        assert e.changed.is_set() is False

    def test_as_bytes_yields_packets_list(self):
        e = self._new_engine(addr=12)  # <=99 so BaseReq BASE_MEMORY should be first
        # Provide some extra state that can be serialized if present
        e._start_stop = TMCC1.START_UP_IMMEDIATE  # type: ignore[attr-defined]
        # Use a smoke value the mapping will understand
        e.comp_data.smoke_tmcc = TMCC2EffectsControl.SMOKE_LOW

        packets = e.as_bytes()
        # EngineState.as_bytes returns list[bytes]
        assert isinstance(packets, list)
        assert len(packets) == 4
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

    def test_train_moniker(self):
        t = TrainState(CommandScope.TRAIN)
        assert t.moniker == "Train"

    def test_train_as_bpc2_moniker(self):
        with patch.object(TrainState, "is_bpc2", new_callable=PropertyMock) as mock_prop:
            mock_prop.return_value = True
            t = TrainState(CommandScope.TRAIN)
            assert t.moniker == "Power District"

    def test_engine_moniker(self):
        t = EngineState(CommandScope.ENGINE)
        assert t.moniker == "Engine"

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

    def test_train_state_as_dict_includes_core_engine(self):
        t = TrainState(CommandScope.TRAIN)
        t.initialize(CommandScope.TRAIN, tmcc_id=105)
        t._address = 105  # type: ignore[attr-defined]
        t.comp_data._speed = 25
        t.comp_data._control_type = LEGACY_CONTROL_TYPE
        t.comp_data._road_name = t._road_name = "abc road"
        t.comp_data._road_number = t._road_number = "123"
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
        assert d["speed"] == 25
        assert d["road_name"] == "abc road"
        assert d["road_number"] == "123"

    def test_train_state_rejects_non_train_scope(self):
        with pytest.raises(ValueError, match="expected TRAIN"):
            TrainState(CommandScope.ENGINE)

    def test_train_state_consist_component_helpers_classify_components(self):
        t = self._new_train()
        head = ConsistComponent(tmcc_id=11, flags=0b00000001)
        link = ConsistComponent(tmcc_id=22, flags=0b00001010)
        accessory = ConsistComponent(tmcc_id=33, flags=0b10000011)
        t.comp_data._consist_comps = [head, link, accessory]  # type: ignore[attr-defined]

        assert t.consist_components == [head, link, accessory]
        assert t.head_tmcc_id == 11
        assert t.link_tmcc_id == 22
        assert t.engine_ids == [11]
        assert t.link_tmcc_ids == [22]
        assert t.accessory_ids == [33]
        assert t.num_engines == 1
        assert t.num_train_linked == 1
        assert t.num_accessories == 1
        assert t.get_consist_component(22) is link
        assert t.get_consist_component(99) is None

    def test_train_state_consist_helpers_return_empty_values_without_components(self):
        t = self._new_train()

        assert t.head_tmcc_id is None
        assert t.link_tmcc_id is None
        assert t.engine_ids is None
        assert t.link_tmcc_ids is None
        assert t.accessory_ids is None
        assert t.num_engines == 0
        assert t.num_train_linked == 0
        assert t.num_accessories == 0
        assert t.get_consist_component(11) is None

    def test_train_state_contains_engine_by_consist_tmcc_id(self):
        t = self._new_train()
        t.comp_data._consist_comps = [ConsistComponent(tmcc_id=11, flags=0b00000001)]  # type: ignore[attr-defined]
        included_engine = self._new_engine(11)
        excluded_engine = self._new_engine(12)

        assert included_engine in t
        assert excluded_engine not in t
        assert t not in t

    def test_train_state_head_fetches_engine_state_from_store(self, monkeypatch):
        t = self._new_train()
        t.comp_data._consist_comps = [ConsistComponent(tmcc_id=77, flags=0b00000001)]  # type: ignore[attr-defined]
        head = self._new_engine(77)
        calls = []

        def get_state(scope, address, create):
            calls.append((scope, address, create))
            return head

        monkeypatch.setattr(ComponentStateStore, "get_state", staticmethod(get_state))

        assert t.head is head
        assert calls == [(CommandScope.ENGINE, 77, False)]

    def test_train_state_delegates_capabilities_to_head(self, monkeypatch):
        t = self._new_train()
        t.comp_data._consist_comps = [ConsistComponent(tmcc_id=77, flags=0b00000001)]  # type: ignore[attr-defined]
        head = SimpleNamespace(
            is_rpm=True,
            is_steam=True,
            is_electric=False,
            is_diesel=True,
            is_crane=False,
            is_passenger=True,
            is_freight=False,
            is_acela=True,
            has_throttle=True,
            has_lights=False,
        )

        monkeypatch.setattr(ComponentStateStore, "get_state", staticmethod(lambda *_args: head))

        assert t.is_rpm is True
        assert t.is_steam is True
        assert t.is_electric is False
        assert t.is_diesel is True
        assert t.is_crane is False
        assert t.is_passenger is True
        assert t.is_freight is False
        assert t.is_acela is True
        assert t.has_throttle is True
        assert t.has_lights is False


class _CompDataRecord(CompDataMixin):
    """A stand-in for the BaseReq / D4Req comp_data record the Base 3 pushes back."""

    def __init__(self, comp_data) -> None:
        super().__init__()
        self._comp_data = comp_data
        self._comp_data_record = True


class _LiveRamp(SpeedRamp):
    """
    A SpeedRamp that is never started: it reports itself active so that arbitration
    routes through it, and it records the aborts it is asked for.
    """

    def __init__(self, state: EngineState, target: int = 80) -> None:
        super().__init__(state, target, sender=lambda *_args: None, linger=0.0, delay_scale=0.0)
        self.aborts: list[str | None] = []

    @property
    def is_active(self) -> bool:
        return True

    def abort(self, reason: str = None) -> None:
        self.aborts.append(reason)
        super().abort(reason)


class TestEngineStateRampArbitration:
    """
    A live ramp arbitrates the commands that reach engine state: its own echoes and
    every RPM or effort trim leave it running, a foreign throttle command stops it,
    and the hard-abort commands stop it unconditionally.
    """

    @staticmethod
    @pytest.fixture(autouse=True)
    def no_comm_buffer(monkeypatch):
        # cancel_ramps() reaches CommBuffer for the legacy RampedSpeedReq path
        monkeypatch.setattr(CommBuffer, "cancel_delayed_requests", staticmethod(lambda *_args, **_kw: None))

    @staticmethod
    def _ramping_engine(addr: int = 7, speed: int = 30) -> tuple[EngineState, _LiveRamp]:
        state = EngineState(CommandScope.ENGINE)
        state.initialize(CommandScope.ENGINE, addr)
        state._address = addr
        state.comp_data._control_type = LEGACY_CONTROL_TYPE
        state.comp_data._speed = speed
        state._is_legacy = True
        ramp = _LiveRamp(state)
        state._ramp = ramp
        state.is_ramping = True
        return state, ramp

    @staticmethod
    def _update(state: EngineState, command: CommandReq):
        return state._update_state(command)

    def test_ramp_hooks_present_on_engine_state(self):
        state, ramp = self._ramping_engine()
        assert state.ramp is ramp
        state.abort_ramp("done")
        assert state.ramp is None
        assert ramp.aborts == ["done"]

    def test_notify_ramp_without_ramp_preserves_legacy_answer(self):
        state, _ = self._ramping_engine()
        state._ramp = None
        assert state.notify_ramp(CommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, data=50)) is False
        assert state.notify_ramp(CommandReq.build(TMCC2.DIESEL_RPM, 7, data=5)) is True
        assert state.notify_ramp(CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=50)) is True

    def test_self_echo_does_not_cancel(self):
        state, ramp = self._ramping_engine()
        echo = CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=ramp.commanded_speed)

        self._update(state, echo)

        assert ramp.aborts == []
        assert state.ramp is ramp
        assert state.is_ramping is True

    def test_own_target_echo_does_not_cancel(self):
        state, ramp = self._ramping_engine()
        echo = CommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, data=ramp.requested_speed)

        self._update(state, echo)

        assert ramp.aborts == []
        assert state.is_ramping is True

    def test_foreign_absolute_speed_cancels(self):
        state, ramp = self._ramping_engine()

        self._update(state, CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=150))

        assert ramp.aborts == [None]
        assert state.ramp is None
        assert state.is_ramping is False

    def test_foreign_target_speed_cancels(self):
        state, ramp = self._ramping_engine()

        self._update(state, CommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, data=150))

        assert ramp.aborts == [None]
        assert state.ramp is None
        # is_ramping is then re-established from the foreign target itself, exactly as
        # it was before arbitration existed: another controller now owns this ramp

    def test_foreign_rpm_absorbs_without_cancelling(self):
        state, ramp = self._ramping_engine()
        expected = 5 - tmcc2_speed_to_rpm(ramp.commanded_speed, ramp.rpm_max_speed)

        self._update(state, CommandReq.build(TMCC2.DIESEL_RPM, 7, data=5))

        assert ramp.aborts == []
        assert state.ramp is ramp
        assert state.is_ramping is True
        assert ramp.rpm_bias == max(-MAX_RPM_BIAS, min(MAX_RPM_BIAS, expected))

    def test_foreign_labor_re_baselines_without_cancelling(self):
        state, ramp = self._ramping_engine()

        self._update(state, CommandReq.build(TMCC2.ENGINE_LABOR, 7, data=20))

        assert ramp.aborts == []
        assert state.ramp is ramp
        assert state.is_ramping is True
        assert ramp.init_labor == 20

    def test_pdi_speed_limit_record_never_cancels(self):
        state, ramp = self._ramping_engine()
        state.comp_data.speed_limit = 40

        self._update(state, _CompDataRecord(state.comp_data))

        assert ramp.aborts == []
        assert state.ramp is ramp
        assert state.is_ramping is True

    @pytest.mark.parametrize(
        "command, data",
        [
            (TMCC1HaltCommandEnum.HALT, None),
            (TMCC2.SYSTEM_HALT, None),
            (TMCC2.STOP_IMMEDIATE, None),
            (TMCC2.RESET, None),
            (TMCC2.NUMERIC, 0),
            (TMCC2.REVERSE_DIRECTION, None),
            (TMCC2.SHUTDOWN_IMMEDIATE, None),
        ],
    )
    def test_hard_aborts_stop_the_ramp_and_clear_is_ramping(self, command, data):
        state, ramp = self._ramping_engine()
        state._direction = TMCC2.FORWARD_DIRECTION

        self._update(state, CommandReq.build(command, 7, data=data))

        assert ramp.aborts != []
        assert state.ramp is None
        assert state.is_ramping is False

    def test_redundant_same_direction_command_does_not_abort(self):
        state, ramp = self._ramping_engine()
        state._direction = TMCC2.FORWARD_DIRECTION

        self._update(state, CommandReq.build(TMCC2.FORWARD_DIRECTION, 7))

        assert ramp.aborts == []
        assert state.ramp is ramp
        assert state.is_ramping is True

    def test_ramp_to_starts_one_thread_and_then_retargets(self, monkeypatch):
        state, _ = self._ramping_engine()
        state._ramp = None
        started: list[SpeedRamp] = []
        monkeypatch.setattr(SpeedRamp, "start", lambda ramp: started.append(ramp))
        monkeypatch.setattr(SpeedRamp, "is_active", property(lambda ramp: True))

        first = state.ramp_to(60)
        second = state.ramp_to(90)

        assert first is second
        assert started == [first]
        assert first.requested_speed == 90
