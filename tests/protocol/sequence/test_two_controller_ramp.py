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
engine, the second request wins, and the first controller is left clean - no ramp of its
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
from src.pytrain.protocol.sequence.speed_ramp import DEFAULT_LABOR, RampRegistry, SpeedRamp
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
    `ramp_to` is what RampSpeedReq does - hand the ramp off, then announce the target.
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
        self.layout.publish(TMCC2EngineCommandEnumEx.TARGET_SPEED, self.state.tmcc_id, speed, self.state.scope)
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
            # the flag is set before the takeover, because asking for a ramp publishes
            # a TARGET_SPEED of its own and so re-enters this hook
            nonlocal taken_over, second_ramp
            if taken_over is True or len(first.speeds) != takeover_step:
                return
            taken_over = True
            second_ramp = second.ramp_to(second_target)

        layout.hook = hook
        first_ramp = first.ramp_to(first_target)
        first_ramp.run()
        assert second_ramp is not None
        return first, second, first_ramp, second_ramp

    def test_the_second_ramp_wins(self):
        first, second, first_ramp, second_ramp = self._handed_off()

        # the loser stopped where it was, and can say why it stopped
        assert first_ramp.is_active is False
        assert first_ramp.abort_reason == "foreign TARGET_SPEED"
        assert first.state.ramp is None
        # the winner never noticed, and still owns the engine
        assert second_ramp.abort_reason is None
        assert second_ramp.is_active is True
        assert second.state.ramp is second_ramp
        assert second_ramp.requested_speed == 60
        # both intentions were announced layout-wide, in the order they were asked for
        assert first.layout.of(TMCC2EngineCommandEnumEx.TARGET_SPEED) == [120, 60]

    def test_the_loser_drives_the_engine_no_further(self):
        first, _second, _first_ramp, _second_ramp = self._handed_off()

        assert len(first.speeds) == 3
        # no settle at the target it will never reach, and no trailing trim either
        assert 120 not in first.speeds
        # a foreign TARGET_SPEED is an announcement, not a position: the winner is
        # driving the engine there itself, so the loser has no speed to yield to it
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

    def test_the_first_controller_adopts_the_winners_target_at_once(self):
        first, _second, _first_ramp, _second_ramp = self._handed_off()

        # not left advertising the 120 it was chasing: the GUI follows the winner from
        # the moment the handoff lands, without waiting for the ramp to finish
        assert first.state.target_speed == 60

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
