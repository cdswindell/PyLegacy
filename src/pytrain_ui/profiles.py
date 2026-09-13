"""Resolved, toolkit-neutral control profiles for PyTrain cab targets.

A profile describes what controls the presentation layer should expose for one
specific engine or train. Protocol-level analog controls are determined by the
TMCC generation, not by engine family or product metadata.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EngineControlProfile:
    engine_type: str
    control_type: str
    type_key: str
    is_legacy: bool
    has_throttle: bool
    supports_momentum: bool
    supports_train_brake: bool
    supports_quilling_horn: bool
    supports_speed_limit: bool
    analog_modes: tuple[str, ...]


def resolve_engine_control_profile(
    state,
    *,
    type_key: str,
    momentum_supported: bool = False,
    train_brake_supported: bool = False,
    quilling_horn_supported: bool = False,
) -> EngineControlProfile:
    """Resolve presentation capabilities from explicit per-target state.

    Train-brake and quilling-horn sliders are TMCC-generation capabilities:
    expose both for TMCC2/Legacy targets and neither for TMCC1 targets. Engine
    family, throttle presence, and the semantic meaning a particular product
    assigns to quill levels do not affect their visibility.

    The *_supported arguments remain accepted while the command adapter is being
    simplified, but train-brake and quilling-horn visibility intentionally does
    not depend on them.
    """

    if state is None:
        return EngineControlProfile(
            engine_type="UNKNOWN",
            control_type="NA",
            type_key=type_key,
            is_legacy=False,
            has_throttle=False,
            supports_momentum=False,
            supports_train_brake=False,
            supports_quilling_horn=False,
            supports_speed_limit=False,
            analog_modes=(),
        )

    engine_type_enum = getattr(state, "engine_type_enum", None)
    engine_type = str(getattr(engine_type_enum, "name", "UNKNOWN") or "UNKNOWN")
    control_type = str(getattr(state, "control_type_label", "NA") or "NA")
    is_legacy = bool(getattr(state, "is_legacy", False))
    state_has_throttle = bool(getattr(state, "has_throttle", False))

    supports_momentum = state_has_throttle and momentum_supported
    supports_train_brake = is_legacy
    supports_quilling_horn = is_legacy
    supports_speed_limit = state_has_throttle

    analog_modes: list[str] = []
    if supports_train_brake:
        analog_modes.append("Brake")
    if supports_momentum:
        analog_modes.append("Momentum")
    if supports_quilling_horn:
        analog_modes.append("Horn")

    # CabView historically uses hasThrottle as the visibility gate for its
    # shared analog-control column. Legacy non-motive equipment can still use
    # Train Brake and Quilling Horn, so keep that column visible whenever the
    # resolved profile contains analog controls. Throttle-dependent capabilities
    # above continue to use the actual state flag.
    has_throttle = state_has_throttle or bool(analog_modes)

    return EngineControlProfile(
        engine_type=engine_type,
        control_type=control_type,
        type_key=type_key,
        is_legacy=is_legacy,
        has_throttle=has_throttle,
        supports_momentum=supports_momentum,
        supports_train_brake=supports_train_brake,
        supports_quilling_horn=supports_quilling_horn,
        supports_speed_limit=supports_speed_limit,
        analog_modes=tuple(analog_modes),
    )
