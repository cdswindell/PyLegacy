"""PyTrain command adapter for cab presentation code."""

from __future__ import annotations

from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.sequence.ramp_speed_req import RampSpeedReq
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

from .state import PyTrainCabStateAdapter


class PyTrainCabCommandAdapter:
    def __init__(self, state_adapter: PyTrainCabStateAdapter) -> None:
        self._state_adapter = state_adapter

    @property
    def state(self):
        return self._state_adapter.state

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
        self._send_named(f"{normalized}_DIRECTION")

    def bell(self) -> None:
        self._send_named("RING_BELL")

    def horn(self, active: bool) -> None:
        if active:
            self._send_named("BLOW_HORN_ONE")

    def boost(self, active: bool) -> None:
        if active:
            self._send_named("BOOST_SPEED")

    def brake(self, active: bool) -> None:
        if active:
            self._send_named("BRAKE_SPEED")

    def stop(self) -> None:
        self._send_named("STOP_IMMEDIATE")

    def reset(self) -> None:
        self._send_named("RESET")

    def _send_named(self, name: str) -> None:
        enum_type = TMCC2EngineCommandEnum if self.state.is_legacy else TMCC1EngineCommandEnum
        command = enum_type.by_name(name, raise_exception=True)
        CommandReq(command, self.state.tmcc_id, scope=self.state.scope).send()
