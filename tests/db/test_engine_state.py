#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from threading import Thread
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

import pytest

from src.pytrain import CommandScope, TMCC2EffectsControl
from src.pytrain.comm.comm_buffer import CommBuffer
from src.pytrain.db.comp_data import CompData, CompDataMixin, encode_tmcc_speed
from src.pytrain.db.component_state import UpdateResult
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.components import ConsistComponent
from src.pytrain.db.engine_state import EngineState, TrainState
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import LEGACY_CONTROL_TYPE, TMCC_CONTROL_TYPE
from src.pytrain.protocol.multibyte.multibyte_constants import TMCC2EngineCommandEnumEx
from src.pytrain.protocol.sequence.speed_ramp import (
    DEFAULT_LABOR,
    MAX_RPM_BIAS,
    EchoFamily,
    RampRegistry,
    SpeedRamp,
)
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum as TMCC1, TMCC1HaltCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import (
    TMCC2EngineCommandEnum as TMCC2,
    tmcc2_speed_to_rpm,
)


@pytest.fixture(autouse=True)
def pin_process_globals(monkeypatch):
    """
    Keep an update from asking the Base 3 for a configuration record.

    `ComponentState._prepare_update` treats a component whose record is empty as one it
    has never heard from, and requests its configuration - which, for a state that is
    not yet marked as carrying a record, re-initializes `comp_data` and so blanks the
    speed and target speed a test has set. Both halves of that decision are process-wide
    singletons: whether state is synchronized, and whether this instance is the server.
    Another test module leaving either of them set therefore made these tests depend on
    what ran before them, and only under load, so both are pinned to what a bare state
    object actually is here: a client that has heard nothing from a Base 3.
    """
    monkeypatch.setattr(CommBuffer, "is_server", staticmethod(lambda: False))
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", classmethod(lambda _cls: False))


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
        # the Legacy ceiling, and the same value speed_max reports below for an unset limit
        assert e.decode_speed_info(255) == 199
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
    routes through it, and it records the aborts it is asked for and the commands it
    puts on the wire.
    """

    def __init__(self, state: EngineState, target: int = 80) -> None:
        # the sink is a bound method, so it has to exist before the base class stores it
        self.sent: list[tuple] = []
        super().__init__(state, target, sender=self._record, linger=0.0, delay_scale=0.0)
        self.aborts: list[str | None] = []
        self.abort_targets: list[int | None] = []
        self.abort_hard_stops: list[bool] = []
        self.abort_yields: list[int | None] = []

    def _record(self, command, _address: int, data: int, _scope) -> None:
        self.sent.append((command, data))

    @property
    def is_active(self) -> bool:
        return True

    def abort(
        self,
        reason: str = None,
        *,
        target_speed: int = None,
        hard_stop: bool = False,
        yield_speed: int = None,
    ) -> None:
        self.aborts.append(reason)
        self.abort_targets.append(target_speed)
        self.abort_hard_stops.append(hard_stop)
        self.abort_yields.append(yield_speed)
        super().abort(reason, target_speed=target_speed, hard_stop=hard_stop, yield_speed=yield_speed)


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
        # the registry is a process-wide singleton keyed by (scope, tmcc_id), and every
        # engine here is engine 7: a handle left behind by another test would be reachable
        # through abort_ramp, and one left behind here would outlive the test that made it
        RampRegistry.reset()
        yield
        RampRegistry.reset()

    @staticmethod
    def _ramping_engine(addr: int = 7, speed: int = 30, target: int = 80) -> tuple[EngineState, _LiveRamp]:
        state = EngineState(CommandScope.ENGINE)
        state.initialize(CommandScope.ENGINE, addr)
        state._address = addr
        state.comp_data._control_type = LEGACY_CONTROL_TYPE
        state.comp_data._speed = speed
        state._is_legacy = True
        # this engine's record has arrived, which is what having a speed and a control
        # type means. Left empty - which is how `initialize` leaves it - every command
        # would send `_prepare_update` down its never-heard-from path, and that path can
        # re-initialize comp_data underneath the test, blanking exactly the speed and
        # target set here
        state._empty = False
        ramp = _LiveRamp(state, target)
        state._ramp = ramp
        state.is_ramping = True
        # the façade's TARGET_SPEED announcement, as _update_state would have recorded it
        state.comp_data.target_speed = encode_tmcc_speed(target, True)
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

    def test_a_retarget_does_not_strand_the_step_in_flight(self):
        # the reported defect, through the real arbitration path: a step is still on its
        # way to the Base 3 when the slider retargets, so its echo arrives *after* the
        # TARGET_SPEED announcement, which is noop and comes back in process at once
        state, ramp = self._ramping_engine()
        ramp.echo_ledger.record(EchoFamily.SPEED, 34)
        ramp._commanded_speed = 36
        ramp.echo_ledger.record(EchoFamily.SPEED, 36)
        ramp.retarget(49)

        self._update(state, CommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, data=49))
        self._update(state, CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=34))

        # both are this ramp's own work, so it keeps driving the engine
        assert ramp.aborts == []
        assert state.ramp is ramp
        assert state.is_ramping is True
        assert ramp.requested_speed == 49

    def test_foreign_absolute_speed_cancels(self):
        state, ramp = self._ramping_engine()

        self._update(state, CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=150))

        # the reason names the takeover, so an abort on a real layout is diagnosable
        assert ramp.aborts == ["foreign ABSOLUTE_SPEED"]
        assert state.ramp is None
        assert state.is_ramping is False

    def test_the_reported_takeover_yields_the_road(self):
        # the reported sequence: the ramp had swept up through 30 and had 34 on the wire
        # when the other controller's ABSOLUTE_SPEED 30 came back to us
        state, ramp = self._ramping_engine(speed=32)
        for speed in (30, 32, 34):
            ramp.echo_ledger.record(EchoFamily.SPEED, speed)
        ramp._commanded_speed = 34
        ramp._last_speed = 34
        ramp._last_labor = 27
        for speed in (30, 32):
            assert ramp.echo_ledger.claim(EchoFamily.SPEED, speed) is True

        self._update(state, CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=30))

        assert ramp.aborts == ["foreign ABSOLUTE_SPEED"]
        assert ramp.abort_yields == [30]
        # step 34 was committed before their command could possibly be seen, so it
        # landed after theirs and the engine would have been left at 34. Detection
        # cannot recall it; the only way their command is honored is to re-assert it
        assert ramp.sent[0] == (TMCC2.ABSOLUTE_SPEED, 30)
        assert ramp.sent[-1] == (TMCC2.ENGINE_LABOR, ramp.init_labor)
        assert state.target_speed == 30
        assert state.is_ramping is False

    def test_a_takeover_nothing_overtook_is_not_re_asserted(self):
        state, ramp = self._ramping_engine(speed=32)
        ramp.echo_ledger.record(EchoFamily.SPEED, 34)
        ramp._commanded_speed = 34
        assert ramp.echo_ledger.claim(EchoFamily.SPEED, 34) is True

        self._update(state, CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=30))

        # every step is accounted for, so their command is already the last word on the
        # wire: the yield is offered and declined
        assert ramp.abort_yields == [30]
        assert [cmd for cmd, _ in ramp.sent if cmd == TMCC2.ABSOLUTE_SPEED] == []

    def test_foreign_target_speed_cancels(self):
        state, ramp = self._ramping_engine()

        self._update(state, CommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, data=150))

        assert ramp.aborts == ["foreign TARGET_SPEED"]
        assert state.ramp is None
        # is_ramping is then re-established from the foreign target itself, exactly as
        # it was before arbitration existed: another controller now owns this ramp

    #
    # duplicate suppression must not hide a takeover
    #
    def test_a_suppressed_duplicate_still_reaches_the_ramp(self):
        # another controller asks for exactly the speed the ramp is sitting at, which is
        # genuinely ambiguous, so the first copy is accepted. By the time their second
        # copy arrives the ramp has stepped on and it is provably not ours - but it is
        # also an exact repeat of the last command, which is what used to drop it unseen
        state, ramp = self._ramping_engine(speed=30)
        foreign = CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=30)

        state.update(foreign)
        assert ramp.aborts == []

        ramp._commanded_speed = 33
        ramp.echo_ledger.record(EchoFamily.SPEED, 33)
        state.update(foreign)

        assert ramp.aborts == ["foreign ABSOLUTE_SPEED"]
        assert state.ramp is None
        assert state.is_ramping is False
        assert state.target_speed == 30
        # and a takeover found this way is a takeover like any other: step 33 was
        # committed after their command, so their speed is re-asserted
        assert ramp.sent[0] == (TMCC2.ABSOLUTE_SPEED, 30)

    def test_our_own_echo_arriving_twice_does_not_cancel(self):
        state, ramp = self._ramping_engine(speed=30)
        ramp._commanded_speed = 34
        ramp.echo_ledger.record(EchoFamily.SPEED, 34)
        echo = CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=34)

        state.update(echo)  # matched from the head of the ledger
        state.update(echo)  # the Lionel double-send, still dropped by state

        # the ledger accepts an exact repeat of the value it just matched, and only that,
        # which is what makes offering a duplicate to the ramp safe
        assert ramp.aborts == []
        assert state.ramp is ramp
        assert state.is_ramping is True

    def test_a_duplicate_is_still_suppressed(self):
        state, ramp = self._ramping_engine(speed=30)
        ramp._commanded_speed = 34
        ramp.echo_ledger.record(EchoFamily.SPEED, 34)
        echo = CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=34)
        state.update(echo)

        # arbitrating a duplicate does not stop it being one: the values it carries were
        # recorded by the copy in front of it
        assert self._update(state, echo) is UpdateResult.IGNORED

    def test_a_duplicate_trim_is_not_absorbed_twice(self):
        state, ramp = self._ramping_engine(speed=30)
        trim = CommandReq.build(TMCC2.DIESEL_RPM, 7, data=5)

        state.update(trim)
        bias = ramp.rpm_bias
        ramp._commanded_speed = 60  # the ramp steps on, into the next band of the curve
        state.update(trim)

        # an RPM trim can never stop a ramp, so the duplicate is left where the guard
        # dropped it: absorbing it again would re-derive the offset against a speed the
        # ramp has since left
        assert bias == 5 - tmcc2_speed_to_rpm(30, ramp.rpm_max_speed)
        assert ramp.rpm_bias == bias

    def test_a_repeated_announcement_cannot_cancel_a_ramp_that_is_not_ours(self):
        # the RampedSpeedReq path: state knows it is ramping but owns no thread, so
        # nothing here can tell a takeover from a double-send. The repeat stays where the
        # guard dropped it rather than tearing the ramp down a second time
        state, _ = self._ramping_engine()
        state._ramp = None
        announcement = CommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, data=80)

        state.update(announcement)
        state.update(announcement)

        assert state.is_ramping is True
        # the record these updates wrote to must still be the one being read: a comp_data
        # blanked mid-test reports speed 0 and no control type, which is a different
        # failure from the target write going wrong, and worth telling apart
        assert state.speed == 30
        assert state.target_speed == 80

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

    #
    # a record's target speed is the only sighting of an instance that talks to the
    # Base 3 directly rather than through our command stream
    #
    def test_a_record_carrying_the_ramps_own_target_never_cancels(self):
        state, ramp = self._ramping_engine()

        self._update(state, _CompDataRecord(state.comp_data))

        assert ramp.aborts == []
        assert ramp.is_target_confirmed is True

    def test_a_record_that_predates_the_announcement_never_cancels(self):
        # the base answers a query with its memory as of that moment, so a record queried
        # just before the ramp's TARGET_SPEED reached it still carries the engine's
        # previous target. Aborting on one of those would kill a ramp at birth
        state, ramp = self._ramping_engine()
        state.comp_data.target_speed = encode_tmcc_speed(0, True)

        self._update(state, _CompDataRecord(state.comp_data))

        assert ramp.aborts == []
        assert state.ramp is ramp
        assert ramp.is_target_confirmed is False

    def test_a_record_carrying_a_foreign_target_cancels_the_ramp(self):
        # the reported takeover: another PyTrain instance commanded this engine directly,
        # writing the base's own target byte. Nothing reached our wire, so this record is
        # the only evidence of it, and without this check the ramp drove on to its target
        state, ramp = self._ramping_engine()
        self._update(state, _CompDataRecord(state.comp_data))
        state.comp_data.target_speed = encode_tmcc_speed(30, True)

        self._update(state, _CompDataRecord(state.comp_data))

        assert ramp.aborts == ["foreign target speed 30"]
        assert state.ramp is None
        assert state.is_ramping is False
        assert state.target_speed == 30

    def test_a_record_with_no_target_never_cancels(self):
        state, ramp = self._ramping_engine()
        self._update(state, _CompDataRecord(state.comp_data))
        state.comp_data.target_speed = 255  # Lionel's "never set"

        self._update(state, _CompDataRecord(state.comp_data))

        assert ramp.aborts == []
        assert state.ramp is ramp

    def test_a_record_never_cancels_without_a_ramp_of_our_own(self):
        state, ramp = self._ramping_engine()
        state._ramp = None
        state.comp_data.target_speed = encode_tmcc_speed(30, True)

        self._update(state, _CompDataRecord(state.comp_data))

        assert ramp.aborts == []
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
        # nothing was cancelled, so the target the ramp is chasing still stands
        assert state.target_speed == 80

    #
    # a cancelled ramp leaves an honest target speed behind
    #
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
    def test_hard_aborts_zero_the_target_speed(self, command, data):
        state, ramp = self._ramping_engine()
        state._direction = TMCC2.FORWARD_DIRECTION
        assert state.target_speed == 80

        self._update(state, CommandReq.build(command, 7, data=data))

        # the engine is going to a standstill, so the target it was ramping toward is
        # no longer where it is headed
        assert state.target_speed == 0
        assert ramp.abort_targets[0] == 0

    def test_foreign_absolute_speed_becomes_the_new_target(self):
        state, ramp = self._ramping_engine()

        self._update(state, CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=150))

        # another controller owns the throttle now: its speed is the new target
        assert state.target_speed == 150
        assert ramp.abort_targets == [150]

    def test_a_speed_alias_resolves_to_its_absolute_speed(self):
        # a railroad speed carries its speed in its alias rather than its data, so the
        # cancel target is read the same way _update_state reads it further down
        state, _ = self._ramping_engine()
        req = CommandReq.build(TMCC2.SPEED_RESTRICTED, 7)

        assert state._cancelled_target_speed(req) == int(TMCC2.SPEED_RESTRICTED.alias[1])

    def test_foreign_target_speed_becomes_the_new_target(self):
        state, ramp = self._ramping_engine()

        self._update(state, CommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, data=150))

        assert state.target_speed == 150
        assert ramp.abort_targets == [150]

    def test_abort_ramp_leaves_the_speed_the_ramp_reached(self):
        state, ramp = self._ramping_engine()

        state.abort_ramp("done")

        assert ramp.abort_targets == [None]
        assert state.target_speed == ramp.commanded_speed == 30

    def test_abort_ramp_records_a_target_without_a_ramp_of_our_own(self):
        state, _ = self._ramping_engine()
        state._ramp = None

        state.abort_ramp("halt", target_speed=0)

        assert state.target_speed == 0

    def test_sync_target_speed_leaves_the_ramping_flag_alone(self):
        state, _ = self._ramping_engine()

        state.sync_target_speed(40)

        assert state.target_speed == 40
        assert state.is_ramping is True

    #
    # a hard stop returns effort to neutral on the engine, not just in state
    #
    @pytest.mark.parametrize(
        "command, data",
        [
            (TMCC1HaltCommandEnum.HALT, None),
            (TMCC2.SYSTEM_HALT, None),
            (TMCC2.STOP_IMMEDIATE, None),
            (TMCC2.RESET, None),
            (TMCC2.NUMERIC, 0),
            (TMCC2.FORWARD_DIRECTION, None),
            (TMCC2.REVERSE_DIRECTION, None),
            (TMCC2.TOGGLE_DIRECTION, None),
            (TMCC2.SHUTDOWN_IMMEDIATE, None),
        ],
    )
    def test_hard_aborts_return_effort_to_neutral_on_the_wire(self, command, data):
        state, ramp = self._ramping_engine()
        # start from the opposite direction, so a direction command is a real change
        state._direction = TMCC2.REVERSE_DIRECTION if command is TMCC2.FORWARD_DIRECTION else TMCC2.FORWARD_DIRECTION
        # the ramp has effort dialed up, as an acceleration leaves it
        ramp._last_labor = 20
        state.comp_data.labor_tmcc = 20

        self._update(state, CommandReq.build(command, 7, data=data))

        # an engine returns to a standstill on its own, but never gives effort back:
        # without this command the locomotive keeps laboring, and the next Base 3
        # record reports that notch straight back into state
        assert ramp.abort_hard_stops[0] is True
        assert (TMCC2.ENGINE_LABOR, DEFAULT_LABOR) in ramp.sent

    def test_a_direction_change_during_a_ramp_returns_effort_to_neutral(self):
        # the reported defect, end to end: state and engine have to agree afterward
        state, ramp = self._ramping_engine()
        state._direction = TMCC2.FORWARD_DIRECTION
        ramp._last_labor = 20
        state.comp_data.labor_tmcc = 20

        self._update(state, CommandReq.build(TMCC2.REVERSE_DIRECTION, 7))

        assert ramp.aborts != []
        assert (TMCC2.ENGINE_LABOR, DEFAULT_LABOR) in ramp.sent
        assert state.labor == DEFAULT_LABOR
        assert state.is_ramping is False
        assert state.target_speed == 0

    def test_a_redundant_direction_command_leaves_effort_alone(self):
        state, ramp = self._ramping_engine()
        state._direction = TMCC2.FORWARD_DIRECTION
        ramp._last_labor = 20
        state.comp_data.labor_tmcc = 20

        self._update(state, CommandReq.build(TMCC2.FORWARD_DIRECTION, 7))

        # the engine never changed direction, so it is still ramping and still laboring
        assert ramp.sent == []
        assert state.labor == 20

    @pytest.mark.parametrize(
        "command, data", [(TMCC2.ABSOLUTE_SPEED, 150), (TMCC2EngineCommandEnumEx.TARGET_SPEED, 150)]
    )
    def test_a_foreign_throttle_command_hands_the_operators_effort_back(self, command, data):
        state, ramp = self._ramping_engine()
        ramp._last_labor = 20

        self._update(state, CommandReq.build(command, 7, data=data))

        # not a hard stop, so effort does not go to neutral - but it does go back. The
        # ramp raised it while there was a gap to close, and nobody else asked for that
        # notch: leaving it behind strands the locomotive laboring, and the next Base 3
        # record reports it straight back into the state this abort just cleaned
        assert ramp.abort_hard_stops == [False]
        assert ramp.sent == [(TMCC2.ENGINE_LABOR, ramp.init_labor)]

    def test_a_ramp_that_never_raised_effort_hands_nothing_back(self):
        state, ramp = self._ramping_engine()

        self._update(state, CommandReq.build(TMCC2.ABSOLUTE_SPEED, 7, data=150))

        # the engine is already sitting at the value the restore would carry
        assert ramp.init_labor == ramp._last_labor
        assert ramp.sent == []

    def test_a_tmcc1_hard_stop_sends_no_effort_command(self):
        state, ramp = self._ramping_engine()
        state.comp_data._control_type = TMCC_CONTROL_TYPE
        state._is_legacy = False
        state._direction = TMCC2.FORWARD_DIRECTION

        self._update(state, CommandReq.build(TMCC1.REVERSE_DIRECTION, 7))

        # ENGINE_LABOR is a Legacy command; a TMCC1 engine has no effort to restore
        assert ramp.abort_hard_stops[0] is True
        assert ramp.sent == []

    #
    # a hard stop re-asserts the standstill a step of ours overtook
    #
    def test_a_direction_change_re_asserts_the_standstill_a_step_overtook(self):
        # the reported defect: the direction change was already on the rails when we
        # issued our next step, so the step lands behind it and tells the engine to move
        state, ramp = self._ramping_engine()
        state._direction = TMCC2.FORWARD_DIRECTION
        ramp.echo_ledger.record(EchoFamily.SPEED, 34)
        ramp._commanded_speed = 34
        ramp._last_labor = 20

        self._update(state, CommandReq.build(TMCC2.REVERSE_DIRECTION, 7))

        assert ramp.aborts == ["REVERSE_DIRECTION"]
        assert ramp.abort_yields == [0]
        # the standstill, then the effort restore, and nothing whatever after them
        assert ramp.sent == [(TMCC2.ABSOLUTE_SPEED, 0), (TMCC2.ENGINE_LABOR, DEFAULT_LABOR)]
        assert state.target_speed == 0
        assert state.is_ramping is False

    @pytest.mark.parametrize(
        "command, data",
        [
            (TMCC1HaltCommandEnum.HALT, None),
            (TMCC2.SYSTEM_HALT, None),
            (TMCC2.STOP_IMMEDIATE, None),
            (TMCC2.RESET, None),
            (TMCC2.NUMERIC, 0),
            (TMCC2.FORWARD_DIRECTION, None),
            (TMCC2.REVERSE_DIRECTION, None),
            (TMCC2.TOGGLE_DIRECTION, None),
            (TMCC2.SHUTDOWN_IMMEDIATE, None),
        ],
    )
    def test_hard_aborts_re_assert_the_standstill(self, command, data):
        state, ramp = self._ramping_engine()
        state._direction = TMCC2.REVERSE_DIRECTION if command is TMCC2.FORWARD_DIRECTION else TMCC2.FORWARD_DIRECTION
        # a step still awaiting its echo: it was issued in the gap between the hard stop
        # reaching the rails and its echo reaching us
        ramp.echo_ledger.record(EchoFamily.SPEED, 34)
        ramp._commanded_speed = 34

        self._update(state, CommandReq.build(command, 7, data=data))

        assert ramp.abort_yields[0] == 0
        assert (TMCC2.ABSOLUTE_SPEED, 0) in ramp.sent

    def test_a_hard_stop_re_asserts_nothing_when_every_step_is_echoed(self):
        state, ramp = self._ramping_engine()
        state._direction = TMCC2.FORWARD_DIRECTION
        ramp.echo_ledger.record(EchoFamily.SPEED, 34)
        ramp._commanded_speed = 34
        assert ramp.echo_ledger.claim(EchoFamily.SPEED, 34) is True

        self._update(state, CommandReq.build(TMCC2.REVERSE_DIRECTION, 7))

        # nothing of ours is still in flight, so the direction change is already the last
        # word and commanding the engine again would be noise
        assert ramp.abort_yields == [0]
        assert [cmd for cmd, _ in ramp.sent if cmd == TMCC2.ABSOLUTE_SPEED] == []

    def test_a_foreign_target_speed_re_asserts_nothing(self):
        state, ramp = self._ramping_engine()
        ramp.echo_ledger.record(EchoFamily.SPEED, 34)
        ramp._commanded_speed = 34

        self._update(state, CommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, 7, data=150))

        # an announcement of intent rather than a position: whoever sent it is driving
        # the engine there themselves and does not need our help
        assert ramp.abort_yields == [None]
        assert [cmd for cmd, _ in ramp.sent if cmd == TMCC2.ABSOLUTE_SPEED] == []

    def test_a_settling_ramp_and_an_abort_do_not_deadlock(self):
        # the ramp thread takes its send gate and then, outside it, the engine's
        # condition; the dispatcher takes the condition and then the gate, through
        # abort(). Nesting those the other way round would hang a real layout, so the
        # order is exercised here rather than trusted
        state, ramp = self._ramping_engine()
        errors: list[BaseException] = []

        def settling() -> None:
            try:
                for _ in range(300):
                    ramp._is_running = True
                    ramp._settle()
            except BaseException as error:  # pragma: no cover
                errors.append(error)

        def dispatching() -> None:
            try:
                for _ in range(300):
                    ramp._is_running = True
                    with state._cv:  # exactly what ComponentState.update holds
                        ramp.abort("test", target_speed=0)
            except BaseException as error:  # pragma: no cover
                errors.append(error)

        threads = [Thread(target=settling, daemon=True), Thread(target=dispatching, daemon=True)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert [thread.is_alive() for thread in threads] == [False, False]
        assert errors == []

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
