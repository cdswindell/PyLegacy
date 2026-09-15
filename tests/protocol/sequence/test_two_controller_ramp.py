#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
"""
Two controllers, one engine.

PyTrain allows several controllers, and a ramp is owned by the instance that asked for
it, so each controller runs its own thread against its own copy of the engine's state.
What is exercised here is the collision: both controllers point a ramp at the same
engine, the second controller's distinguishable speed wins, and the first is left clean - no ramp of its
own, and a state that settles on what the winner actually did, which is what its GUI
draws from.

The layout below stands in for CommandDispatcher -> ComponentStateStore ->
state.update(): whatever one controller sends is delivered to the state every controller
keeps. The ramps are driven synchronously, so the whole handoff is deterministic.
"""

from typing import Callable

import pytest

from src.pytrain.comm.comm_buffer import CommBuffer
from src.pytrain.db.engine_state import EngineState
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import LEGACY_CONTROL_TYPE, CommandScope
from src.pytrain.protocol.multibyte.multibyte_constants import TMCC2EngineCommandEnumEx
from src.pytrain.protocol.sequence import speed_ramp
from src.pytrain.protocol.sequence.speed_ramp import DEFAULT_LABOR, ECHO_TTL, RampRegistry, RampStep, SpeedRamp
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

from ...test_base import TestBase

ENGINE_ID = 7


def legacy_engine(tmcc_id: int = ENGINE_ID, speed: int = 0) -> EngineState:
    """One controller's copy of a Legacy engine's state."""
    state = EngineState(CommandScope.ENGINE)
    state.initialize(CommandScope.ENGINE, tmcc_id)
    state._address = tmcc_id
    state.comp_data._control_type = LEGACY_CONTROL_TYPE
    state.comp_data._speed = speed
    state._is_legacy = True
    # The supplied record is populated, so updates must not request configuration.
    state._empty = False
    return state


class Layout:
    """
    The one command bus every controller listens to. A command sent by any controller
    reaches the state each of them keeps, in the order it was sent, and a hook can act
    on the stream to stage a second controller's move mid-ramp.
    """

    def __init__(self, hook: Callable[["Layout"], None] = None) -> None:
        self.controllers: list["Controller"] = []
        self.sent: list[tuple] = []
        self.hook = hook

    def join(self, controller: "Controller") -> None:
        self.controllers.append(controller)

    def publish(self, command, address: int, data: int, scope: CommandScope) -> None:
        self.sent.append((command, data))
        req = CommandReq.build(command, address, data=data, scope=scope)
        for controller in self.controllers:
            # noinspection PyProtectedMember
            # what ComponentStateStore.__call__ does, minus the synchronizer and the
            # duplicate suppression, so the handoff is deterministic
            controller.state._update_state(req)
        if self.hook is not None:
            self.hook(self)

    def of(self, command) -> list[int]:
        return [data for cmd, data in self.sent if cmd == command]


class Controller:
    """
    One PyTrain instance: its own engine state, its own ramp registry, its own thread.
    `ramp_to` starts or retargets a local ramp without announcing its destination.
    """

    def __init__(self, layout: Layout, name: str, speed: int = 0) -> None:
        self.name = name
        self.layout = layout
        self.registry = RampRegistry()
        self.state = legacy_engine(speed=speed)
        self.sent: list[tuple] = []
        layout.join(self)

    def send(self, command, address: int, data: int, scope: CommandScope) -> None:
        self.sent.append((command, data))
        self.layout.publish(command, address, data, scope)

    def ramp_to(self, speed: int) -> SpeedRamp:
        ramp = self.registry.ramp_to(self.state, speed, sender=self.send, linger=0.0, delay_scale=0.0)
        self.state._ramp = ramp
        return ramp

    def of(self, command) -> list[int]:
        return [data for cmd, data in self.sent if cmd == command]

    @property
    def speeds(self) -> list[int]:
        return [data for cmd, data in self.sent if cmd == TMCC2EngineCommandEnum.ABSOLUTE_SPEED]


# noinspection PyMethodMayBeStatic
class TestTwoControllerRamp(TestBase):
    """A second controller's ramp takes the engine, and the first one lets go of it."""

    @staticmethod
    @pytest.fixture(autouse=True)
    def one_process(monkeypatch):
        # cancel_ramps() reaches CommBuffer for the legacy RampedSpeedReq path
        monkeypatch.setattr(CommBuffer, "cancel_delayed_requests", staticmethod(lambda *_args, **_kw: None))
        # both controllers live in this process, so their ramps are driven by hand
        # rather than started; is_active then has to answer without a live thread
        monkeypatch.setattr(SpeedRamp, "start", lambda _ramp: None)
        monkeypatch.setattr(SpeedRamp, "is_active", property(lambda ramp: ramp._is_running is True))

    @pytest.mark.parametrize("speed", [0, 25])
    def test_legacy_engine_has_a_populated_record_before_updates(self, monkeypatch, speed):
        state = legacy_engine(speed=speed)
        record = state.comp_data
        assert state.is_comp_data_record is True
        assert state.is_comp_data_empty is False
        assert state.speed == speed

        def unexpected_config_request(_command):
            pytest.fail("A populated test engine must not request configuration")

        monkeypatch.setattr(state, "request_config", unexpected_config_request)
        for received_speed in (20, 20, 40, 40):
            state.update(CommandReq.build(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, ENGINE_ID, received_speed))
            assert state.comp_data is record
            assert state.control_type == LEGACY_CONTROL_TYPE
            assert state.speed == state.target_speed == received_speed

    @staticmethod
    def _handed_off(first_target: int = 120, second_target: int = 60, takeover_step: int = 3):
        """
        The first controller ramps up; partway through, the second asks for a ramp of
        its own. Returns both controllers and both ramps, with the first controller's
        ramp already run to wherever the takeover left it.
        """
        layout = Layout()
        first = Controller(layout, "deck")
        second = Controller(layout, "cab")
        taken_over = False
        second_ramp: SpeedRamp | None = None

        def hook(_bus: Layout) -> None:
            # A distinguishable speed from the second owner, not its local request,
            # signals takeover. Set the flag before its send re-enters this hook.
            nonlocal taken_over, second_ramp
            if taken_over is True or len(first.speeds) != takeover_step:
                return
            taken_over = True
            second_ramp = second.ramp_to(second_target)
            assert first_ramp.is_active is True
            second_ramp._send_step(RampStep(second.state.speed + 3, None, None, 0.2))

        layout.hook = hook
        first_ramp = first.ramp_to(first_target)
        first_ramp.run()
        assert second_ramp is not None
        return first, second, first_ramp, second_ramp

    def test_the_second_ramp_wins(self):
        first, second, first_ramp, second_ramp = self._handed_off()

        # the loser stopped where it was, and can say why it stopped
        assert first_ramp.is_active is False
        assert first_ramp.abort_reason == "foreign ABSOLUTE_SPEED"
        assert first.state.ramp is None
        # the winner never noticed, and still owns the engine
        assert second_ramp.abort_reason is None
        assert second_ramp.is_active is True
        assert second.state.ramp is second_ramp
        assert second_ramp.requested_speed == 60
        assert first.layout.of(TMCC2EngineCommandEnumEx.TARGET_SPEED) == []

    def test_other_nodes_observe_speed_without_owning_the_ramp(self):
        layout = Layout()
        owner = Controller(layout, "deck")
        observers = [Controller(layout, "pi"), Controller(layout, "base-server")]
        ramp = owner.ramp_to(70)
        assert layout.sent == []
        assert all(node.state.target_speed != 70 for node in layout.controllers)

        def observe(_bus):
            assert owner.state.ramp is ramp
            assert ramp.requested_speed == 70
            for node in observers:
                assert node.state.ramp is None
                assert node.state.is_ramping is False
                assert node.state.speed == node.state.target_speed == owner.state.speed
                assert node.sent == []

        layout.hook = observe
        ramp.run()
        assert owner.speeds[-1] == 70
        assert ramp.is_active is False
        assert layout.of(TMCC2EngineCommandEnumEx.TARGET_SPEED) == []

    @pytest.mark.parametrize("takeover_speed", [30, 37])
    def test_delayed_echoes_keep_ramping_until_a_backward_or_unsent_speed(self, monkeypatch, takeover_speed):
        clock = [100.0]
        monkeypatch.setattr(speed_ramp, "time", lambda: clock[0])
        state = legacy_engine()
        sent = []
        ramp = SpeedRamp(state, 120, sender=lambda *args: sent.append(args))
        state._ramp = ramp
        state.is_ramping = True
        for speed in (10, 20, 30, 40, 50):
            ramp._send_step(RampStep(speed, None, None, 0.2))
            clock[0] += ECHO_TTL / 20
        clock[0] = 100.0 + ECHO_TTL * 0.8
        for speed in (20, 20, 40, 40):
            state.update(CommandReq.build(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, ENGINE_ID, speed))
            assert state.ramp is ramp
            assert ramp.is_active is True
            assert ramp.commanded_speed == 50
            assert state.target_speed == state.speed == speed
            assert ramp.requested_speed == 120
        assert [args[2] for args in sent] == [10, 20, 30, 40, 50]

        state.update(CommandReq.build(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, ENGINE_ID, takeover_speed))
        assert state.ramp is None
        assert ramp.is_active is False
        assert ramp.abort_reason == "foreign ABSOLUTE_SPEED"
        assert state.speed == takeover_speed
        assert state.target_speed == takeover_speed
        assert sent[-1][2] == takeover_speed

    def test_server_ramp_survives_a_base_echo_overtaken_by_local_feedback(self, monkeypatch):
        clock = [100.0]
        monkeypatch.setattr(speed_ramp, "time", lambda: clock[0])
        state = legacy_engine(tmcc_id=60)
        sent = []

        def send(command, address, data, scope):
            request = CommandReq.build(command, address, data, scope)
            sent.append(request)
            state.update(request)

        ramp = SpeedRamp(state, 41, sender=send)
        state._ramp = ramp
        state.is_ramping = True
        for speed in (3, 6, 9, 12):
            ramp._send_step(RampStep(speed, None, None, 0.2))
            clock[0] += ECHO_TTL / 20
            state.update(CommandReq.from_bytes(sent[-1].as_bytes, from_tmcc_rx=True))

        ramp._send_step(RampStep(15, None, None, 0.2))
        delayed = sent[-1]
        clock[0] += ECHO_TTL / 8
        ramp._send_step(RampStep(18, None, None, 0.2))
        latest = sent[-1]

        state.update(CommandReq.from_bytes(delayed.as_bytes, from_tmcc_rx=True))
        assert state.ramp is ramp
        assert ramp.is_active is True
        assert ramp.abort_reason is None
        assert ramp.requested_speed == 41
        assert ramp.commanded_speed == 18
        assert state.speed == state.target_speed == 15

        state.update(CommandReq.from_bytes(latest.as_bytes, from_tmcc_rx=True))
        for speed in (21, 24, 27, 30, 33, 36, 39, 41):
            clock[0] += ECHO_TTL / 20
            ramp._send_step(RampStep(speed, None, None, 0.2))
            state.update(CommandReq.from_bytes(sent[-1].as_bytes, from_tmcc_rx=True))
            assert state.ramp is ramp
            assert ramp.requested_speed == 41
            assert ramp.abort_reason is None
        assert ramp.commanded_speed == state.speed == state.target_speed == 41
        assert [request.data for request in sent] == [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 41]

    @pytest.mark.parametrize("is_rx", [False, True])
    @pytest.mark.parametrize("pending_step", [False, True])
    def test_takeover_yields_only_steps_unacknowledged_by_either_stream(self, is_rx, pending_step):
        state = legacy_engine()
        sent = []
        ramp = SpeedRamp(state, 41, sender=lambda *args: sent.append(args))
        state._ramp = ramp
        state.is_ramping = True
        ramp._send_step(RampStep(10, None, None, 0.2))
        request = CommandReq.build(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, ENGINE_ID, 10)
        state.update(CommandReq.from_bytes(request.as_bytes, from_tmcc_rx=is_rx))
        if pending_step:
            ramp._send_step(RampStep(20, None, None, 0.2))

        request = CommandReq.build(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, ENGINE_ID, 17)
        state.update(CommandReq.from_bytes(request.as_bytes, from_tmcc_rx=is_rx))

        assert state.ramp is None
        assert ramp.is_active is False
        assert ramp.abort_reason == "foreign ABSOLUTE_SPEED"
        assert state.speed == state.target_speed == 17
        assert [args[2] for args in sent] == ([10, 20, 17] if pending_step else [10])

    def test_the_loser_drives_the_engine_no_further(self):
        first, _second, _first_ramp, _second_ramp = self._handed_off()

        assert len(first.speeds) == 3
        # no settle at the target it will never reach, and no trailing trim either
        assert 120 not in first.speeds
        # Every step was echoed before takeover, so nothing needs to be re-asserted.
        assert first.of(TMCC2EngineCommandEnum.ABSOLUTE_SPEED) == first.speeds
        # the effort it borrowed is the only thing still owed, and the only thing sent
        assert first.sent[-1] == (TMCC2EngineCommandEnum.ENGINE_LABOR, _first_ramp.init_labor)

    def test_the_loser_hands_back_the_effort_it_borrowed(self):
        first, _second, first_ramp, _second_ramp = self._handed_off()
        labors = first.of(TMCC2EngineCommandEnum.ENGINE_LABOR)

        # another controller taking the throttle is not a hard stop, so effort does not
        # go to neutral - but it does go back. The loser raised it while it had a gap to
        # close, and leaving that notch behind would strand the engine laboring for a
        # ramp that no longer exists, with the winner's own steps trimming from there
        assert labors[:-1] != []
        assert max(labors[:-1]) > first_ramp.init_labor
        assert labors[-1] == first_ramp.init_labor

    def test_the_first_controller_is_left_clean(self):
        first, second, _first_ramp, second_ramp = self._handed_off()

        # the winner finishes its ramp; every step reaches both controllers
        second_ramp.run()

        assert second.speeds[-1] == 60
        # neither controller is left holding a live ramp: the loser dropped its handle
        # when it was cancelled, and the winner's thread has run its course
        assert first.state.ramp is None
        assert second_ramp.is_active is False
        for controller in (first, second):
            state = controller.state
            # nothing left showing a ramp in flight on either controller
            assert state.is_ramping is False, controller.name
            assert state.speed == 60, controller.name
            assert state.target_speed == 60, controller.name
        # and the two controllers agree on everything the throttle pane draws
        assert first.state.labor == second.state.labor
        assert first.state.rpm == second.state.rpm

    def test_the_loser_observes_steps_not_the_winners_local_destination(self):
        first, second, _first_ramp, second_ramp = self._handed_off()

        assert first.state.speed == first.state.target_speed == second.speeds[-1]
        assert first.state.target_speed != second_ramp.requested_speed
        assert second_ramp.requested_speed == 60

    def test_only_one_ramp_is_left_on_the_layout(self):
        first, second, _first_ramp, _second_ramp = self._handed_off()

        assert first.registry.active_ramps == []
        assert len(second.registry.active_ramps) == 1

    def test_a_hard_stop_after_the_handoff_cleans_up_both_controllers(self):
        first, second, _first_ramp, second_ramp = self._handed_off()
        for controller in (first, second):
            controller.state._direction = TMCC2EngineCommandEnum.FORWARD_DIRECTION
            controller.state.comp_data.labor_tmcc = 20
        # the winner has effort dialed up, as an acceleration leaves it, so neutral is
        # genuinely owed rather than already in effect
        second_ramp._last_labor = 20

        # the engine is thrown into reverse while the winner is still ramping it
        second.layout.publish(TMCC2EngineCommandEnum.REVERSE_DIRECTION, ENGINE_ID, None, CommandScope.ENGINE)

        # the ramp that owns the engine is the one that hands effort back
        assert second_ramp.abort_reason == "REVERSE_DIRECTION"
        assert (TMCC2EngineCommandEnum.ENGINE_LABOR, DEFAULT_LABOR) in second.sent
        for controller in (first, second):
            state = controller.state
            assert state.ramp is None, controller.name
            assert state.is_ramping is False, controller.name
            assert state.target_speed == 0, controller.name
            assert state.labor == DEFAULT_LABOR, controller.name
