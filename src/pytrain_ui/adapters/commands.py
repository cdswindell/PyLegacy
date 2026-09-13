"""PyTrain command adapter for cab presentation code."""

from __future__ import annotations

from pytrain.pdi.base_req import BaseReq
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from pytrain.protocol.sequence.labor_effect import LaborEffectDownReq, LaborEffectUpReq
from pytrain.protocol.sequence.ramp_speed_req import RampSpeedReq
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

from pytrain_ui.actions import CabAction, action_applies_to_type, cab_action

from .state import PyTrainCabStateAdapter


class PyTrainCabCommandAdapter:
    """Translate presentation-level cab actions into PyTrain commands.

    Engine-type visibility mirrors ControllerView.apply_engine_type() and the scope tags
    in ENGINE_OPS_LAYOUT; QML only renders the resulting action list.
    """

    def __init__(self, state_adapter: PyTrainCabStateAdapter) -> None:
        self._state_adapter = state_adapter

    @property
    def state(self):
        return self._state_adapter.state

    @property
    def _enum_type(self):
        return TMCC2EngineCommandEnum if self.state.is_legacy else TMCC1EngineCommandEnum

    @property
    def controller_type_key(self) -> str:
        """Return the same type key ControllerView.apply_engine_type() uses."""
        state = self.state
        if getattr(state, "is_diesel", False):
            return "d"
        if getattr(state, "is_steam", False):
            return "s"
        if getattr(state, "is_passenger", False):
            return "p"
        if getattr(state, "is_freight", False):
            return "f"
        if getattr(state, "is_acela", False):
            return "a"
        if getattr(state, "is_electric", False):
            return "l"
        if getattr(state, "is_crane", False):
            return "r"
        if getattr(state, "is_transformer", False):
            return "t"
        return "d"

    def set_speed(self, speed: int) -> None:
        maximum = 199 if self.state.is_legacy else 31
        speed = max(0, min(maximum, int(speed)))
        RampSpeedReq(self.state.tmcc_id, speed, self.state.scope).send()

    def change_speed(self, delta: int) -> None:
        self.set_speed(self._state_adapter.current().target_speed + int(delta))

    def set_momentum(self, value: int) -> None:
        """Set momentum using the same 0-7 behavior as ControllerView."""
        value = max(0, min(7, int(value)))
        if self.state.is_legacy:
            CommandReq.build(
                TMCC2EngineCommandEnum.MOMENTUM,
                self.state.tmcc_id,
                data=value,
                scope=self.state.scope,
            ).send()
            return
        # TMCC1 only exposes the three traditional presets. Match the current GUI's bands.
        name = "MOMENTUM_LOW" if value <= 1 else "MOMENTUM_MEDIUM" if value <= 4 else "MOMENTUM_HIGH"
        self.send_named(name)

    def set_train_brake(self, value: int) -> None:
        """Set Legacy train-brake level, 0-7."""
        if not bool(self.state.is_legacy):
            return
        value = max(0, min(7, int(value)))
        CommandReq.build(
            TMCC2EngineCommandEnum.TRAIN_BRAKE,
            self.state.tmcc_id,
            data=value,
            scope=self.state.scope,
        ).send()

    def set_quilling_horn(self, value: int) -> None:
        """Set quilling horn position, falling back to a normal horn on TMCC1."""
        value = max(0, min(15, int(value)))
        if value <= 0:
            return
        if self.state.is_legacy and self.supports_named("QUILLING_HORN"):
            CommandReq.build(
                TMCC2EngineCommandEnum.QUILLING_HORN,
                self.state.tmcc_id,
                data=value,
                scope=self.state.scope,
            ).send()
        else:
            self.horn(True)

    def set_speed_limit(self, value: int | None) -> None:
        # EngineGui uses the Base 3 roster field for speed limits rather than a
        # track command. 255 is the established clear/no-limit value.
        if value is None:
            speed_limit = 255
        else:
            maximum = 199 if self.state.is_legacy else 31
            speed_limit = max(1, min(maximum, int(value)))
        BaseReq.do_update_field("SPEED_LIMIT", speed_limit, self.state, True)

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

    def supports_effect(self, name: str) -> bool:
        if not bool(self.state.is_legacy):
            return False
        try:
            TMCC2EffectsControl.by_name(name, raise_exception=True)
        except (KeyError, ValueError):
            return False
        return True

    def supports_smoke(self) -> bool:
        if self.state.is_legacy:
            return self.supports_effect("SMOKE_OFF") and self.supports_effect("SMOKE_HIGH")
        return self.supports_named("SMOKE_OFF") and self.supports_named("SMOKE_ON")

    def supports_action(self, action: CabAction | str) -> bool:
        if isinstance(action, str):
            action = cab_action(action)
        if action is None:
            return False
        if not action_applies_to_type(action, self.controller_type_key):
            return False
        if action.legacy_only and not bool(self.state.is_legacy):
            return False
        if action.command_kind == "sequence":
            return action.command in {"LABOR_EFFECT_DOWN", "LABOR_EFFECT_UP"} and bool(self.state.is_legacy)
        if action.command_kind == "effects":
            return self.supports_effect(action.command)
        if action.command_kind == "smoke":
            return self.supports_smoke()
        return self.supports_named(action.command)

    def perform(self, action: CabAction | str) -> bool:
        if isinstance(action, str):
            action = cab_action(action)
        if action is None or not self.supports_action(action):
            return False
        if action.command_kind == "sequence":
            if action.command == "LABOR_EFFECT_UP":
                LaborEffectUpReq(self.state.tmcc_id, scope=self.state.scope).send()
                return True
            if action.command == "LABOR_EFFECT_DOWN":
                LaborEffectDownReq(self.state.tmcc_id, scope=self.state.scope).send()
                return True
            return False
        if action.command_kind == "effects":
            command = TMCC2EffectsControl.by_name(action.command, raise_exception=True)
            CommandReq.build(command, self.state.tmcc_id, scope=self.state.scope).send()
            return True
        if action.command_kind == "smoke":
            if self.state.is_legacy:
                effect_name = "SMOKE_OFF" if action.command == "SMOKE_OFF" else "SMOKE_HIGH"
                command = TMCC2EffectsControl.by_name(effect_name, raise_exception=True)
                CommandReq.build(command, self.state.tmcc_id, scope=self.state.scope).send()
                return True
            return self.send_named(action.command)
        return self.send_named(action.command)

    def send_named(self, name: str) -> bool:
        """Send a named engine/train command when the active control type supports it."""
        try:
            command = self._enum_type.by_name(name, raise_exception=True)
        except (KeyError, ValueError):
            return False
        # Use the factory rather than CommandReq(...) directly. The factory is the
        # canonical PyTrain dispatch path and correctly creates ordinary, multibyte,
        # and sequence request subclasses.
        CommandReq.build(command, self.state.tmcc_id, scope=self.state.scope).send()
        return True
