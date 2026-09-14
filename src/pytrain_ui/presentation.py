"""Presentation-neutral view models derived from semantic cab metadata."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from pytrain_ui.actions import CabAction
from pytrain_ui.profiles import EngineControlProfile


@dataclass(frozen=True, slots=True)
class CabActionView:
    """Resolved action behavior ready for any presentation toolkit."""

    key: str
    label: str
    icon: str
    group: str
    hold: bool
    hold_threshold_ms: int
    hold_kind: str
    hold_target: str
    repeat: bool
    repeat_interval_ms: int


def resolve_action_view(action: CabAction, profile: EngineControlProfile) -> CabActionView:
    """Resolve capability-dependent behavior without imposing a visual layout."""
    hold_enabled = action.hold and not (action.hold_legacy_only and not profile.is_legacy)
    if hold_enabled and action.hold_kind == "analog":
        hold_enabled = action.hold_target in profile.analog_modes

    return CabActionView(
        key=action.key,
        label=action.label,
        icon=action.icon,
        group=action.group,
        hold=hold_enabled,
        hold_threshold_ms=action.hold_threshold_ms,
        hold_kind=action.hold_kind if hold_enabled else "",
        hold_target=action.hold_target if hold_enabled else "",
        repeat=action.repeat,
        repeat_interval_ms=action.repeat_interval_ms,
    )


def resolve_action_views(
    actions: Iterable[CabAction],
    profile: EngineControlProfile,
    supports: Callable[[CabAction], bool],
) -> tuple[CabActionView, ...]:
    """Filter semantic actions by capability, then resolve their interaction behavior."""
    return tuple(resolve_action_view(action, profile) for action in actions if supports(action))
