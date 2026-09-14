"""Toolkit-neutral contracts shared by PyTrain presentation implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class EngineViewState:
    """Presentation-friendly snapshot of an engine or train cab."""

    scope: str
    tmcc_id: int
    road_name: str = ""
    road_number: str = ""
    speed: int = 0
    target_speed: int = 0
    speed_max: int = 199
    direction: str = ""
    momentum: int = 0
    train_brake: int = 0
    smoke: int = 0
    labor: int = 0
    rpm: int = 0
    momentum_text: str = ""
    brake_text: str = "NA"
    smoke_text: str = "NA"
    speed_limit_text: str = ""
    effort_text: str = ""
    rpm_text: str = "NA"

    @property
    def info_items(self) -> tuple[tuple[str, str], ...]:
        """ControllerView-compatible six-field status summary."""
        return (
            ("Mom", self.momentum_text),
            ("Brake", self.brake_text),
            ("Smoke", self.smoke_text),
            ("Speed Lim", self.speed_limit_text),
            ("Effort", self.effort_text),
            ("RPM", self.rpm_text),
        )


StateListener = Callable[[EngineViewState], None]
Unsubscribe = Callable[[], None]


@runtime_checkable
class CabStatePort(Protocol):
    """Read/subscribe interface exposed to a cab presentation."""

    def current(self) -> EngineViewState: ...

    def subscribe(self, listener: StateListener) -> Unsubscribe: ...


@runtime_checkable
class CabCommandPort(Protocol):
    """Semantic commands emitted by touch, mouse, keyboard, or controller input."""

    def set_speed(self, speed: int) -> None: ...

    def change_speed(self, delta: int) -> None: ...

    def set_momentum(self, value: int) -> None: ...

    def set_train_brake(self, value: int) -> None: ...

    def set_quilling_horn(self, value: int) -> None: ...

    def set_speed_limit(self, value: int | None) -> None: ...

    def set_direction(self, direction: str) -> None: ...

    def bell(self) -> None: ...

    def horn(self, active: bool) -> None: ...

    def boost(self, active: bool) -> None: ...

    def brake(self, active: bool) -> None: ...

    def stop(self) -> None: ...

    def reset(self) -> None: ...
