"""PyTrain command adapter for cab presentation code."""

from __future__ import annotations

from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.sequence.ramp_speed_req import RampSpeedReq
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

from pytrain_ui.actions import CabAction, cab_action

from .state import PyTrainCabStateAdapter


class PyTrainCabCommandAdapter:
    """Translate presentation-level cab actions into PyTrain commands.

    Keep command names here rather than in QML so the presentation layer does not
    need to know which TMCC enum implements an operation.
    """

    def __init__(self, state_adapter: PyTrainCabStateAdapter) -> None:
        self._state_adapter = state_adapter

    @property
    def state(self):
        return self._state_adapter.state

    @property
    def _enum_type(self):
        return TMCC2EngineCommandEnum if self.state.is_legacy else TMCC1EngineCommandEnum

    def set_speed(self, speed: int) -> None:
        maximum = 199 if self.state.is_legacy else 31
        speed = max(0, min(maximum, int(speed)))
        RampSpeedReq(self.state.tmcc_id, speed, self.state.scope).send()

    def change_speed(self, delta: int) -> None:
        self.set_speed(self._state_adapter.current().target_speed + int(delta))

    def set_direction(self, direction: str) -> None:
        normalized = direction.strip().upper()
        if normalized not in {"FORWARD", "REVERSE"}:
            raise ValueError("direction must be FORWARD or REVERSE")
        self.send_named(f"{normalized}_DIRECTION")

    def bell(self) -> None:
        self.send_named("RING_BELL")

    def horn(self, active: bool) -> None:
        if active:
            self.send_named("BLOW_HORN_ONE")

    def boost(self, active: bool) -> None:
        if active:
            self.send_named("BOOST_SPEED")

    def brake(self, active: bool) -> None:
        if active:
            self.send_named("BRAKE_SPEED")

    def stop(self) -> None:
        self.send_named("STOP_IMMEDIATE")

    def reset(self) -> None:
        self.send_named("RESET")

    def startup(self) -> None:
        self.perform("startup")

    def shutdown(self) -> None:
        self.perform("shutdown")

    def front_coupler(self) -> None:
        self.perform("front_coupler")

    def rear_coupler(self) -> None:
        self.perform("rear_coupler")

    def smoke_up(self) -> None:
        self.perform("smoke_up")

    def smoke_down(self) -> None:
        self.perform("smoke_down")

    def volume_up(self) -> None:
        self.perform("volume_up")

    def volume_down(self) -> None:
        self.perform("volume_down")

    def rpm_up(self) -> None:
        self.perform("rpm_up")

    def rpm_down(self) -> None:
        self.perform("rpm_down")

    def engineer_chatter(self) -> None:
        self.perform("engineer_chatter")

    def tower_chatter(self) -> None:
        self.perform("tower_chatter")

    def supports_named(self, name: str) -> bool:
        try:
            self._enum_type.by_name(name, raise_exception=True)
        except (KeyError, ValueError):
            return False
        return True

    def supports_action(self, action: CabAction | str) -> bool:
        if isinstance(action, str):
            action = cab_action(action)
        return action is not None and self.supports_named(action.command)

    def perform(self, action: CabAction | str) -> bool:
        if isinstance(action, str):
            action = cab_action(action)
        if action is None:
            return False
        return self.send_named(action.command)

    def send_named(self, name: str) -> bool:
        """Send a named engine/train command when the active control type supports it.

        A few EngineGui operations are generation-specific. Returning False lets the
        Qt layer remain usable with older TMCC equipment without turning an unsupported
        convenience button into a UI exception.
        """
        try:
            command = self._enum_type.by_name(name, raise_exception=True)
        except (KeyError, ValueError):
            return False
        CommandReq(command, self.state.tmcc_id, scope=self.state.scope).send()
        return True
