from types import SimpleNamespace

from pytrain.protocol.constants import EngineType

from pytrain_ui.profiles import resolve_engine_control_profile


def _state(
    *,
    engine_type: EngineType,
    control_type: str,
    is_legacy: bool,
    has_throttle: bool = True,
):
    return SimpleNamespace(
        engine_type_enum=engine_type,
        control_type_label=control_type,
        is_legacy=is_legacy,
        has_throttle=has_throttle,
    )


def test_profile_preserves_exact_engine_and_control_types() -> None:
    profile = resolve_engine_control_profile(
        _state(
            engine_type=EngineType.DIESEL_SWITCHER,
            control_type="Legacy",
            is_legacy=True,
        ),
        type_key="d",
        momentum_supported=True,
    )

    assert profile.engine_type == "DIESEL_SWITCHER"
    assert profile.control_type == "Legacy"
    assert profile.type_key == "d"
    assert profile.is_legacy is True


def test_tmcc2_target_exposes_train_brake_and_quilling_horn() -> None:
    profile = resolve_engine_control_profile(
        _state(engine_type=EngineType.DIESEL, control_type="Legacy", is_legacy=True),
        type_key="d",
        momentum_supported=True,
    )

    assert profile.supports_train_brake is True
    assert profile.supports_momentum is True
    assert profile.supports_quilling_horn is True
    assert profile.analog_modes == ("Brake", "Momentum", "Horn")


def test_tmcc1_target_hides_train_brake_and_quilling_horn() -> None:
    profile = resolve_engine_control_profile(
        _state(engine_type=EngineType.STEAM, control_type="TMCC", is_legacy=False),
        type_key="s",
        momentum_supported=True,
    )

    assert profile.supports_train_brake is False
    assert profile.supports_momentum is True
    assert profile.supports_quilling_horn is False
    assert profile.analog_modes == ("Momentum",)


def test_engine_family_does_not_limit_tmcc2_analog_controls() -> None:
    profile = resolve_engine_control_profile(
        _state(engine_type=EngineType.ACELA, control_type="Legacy", is_legacy=True),
        type_key="a",
        momentum_supported=True,
    )

    assert profile.supports_train_brake is True
    assert profile.supports_quilling_horn is True
    assert profile.analog_modes == ("Brake", "Momentum", "Horn")


def test_non_throttle_tmcc2_target_still_exposes_protocol_analog_controls() -> None:
    profile = resolve_engine_control_profile(
        _state(
            engine_type=EngineType.FREIGHT_SOUNDS,
            control_type="Legacy",
            is_legacy=True,
            has_throttle=False,
        ),
        type_key="f",
        momentum_supported=True,
    )

    assert profile.has_throttle is False
    assert profile.supports_momentum is False
    assert profile.supports_train_brake is True
    assert profile.supports_quilling_horn is True
    assert profile.supports_speed_limit is False
    assert profile.analog_modes == ("Brake", "Horn")
