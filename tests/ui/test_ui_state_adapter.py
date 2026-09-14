from types import SimpleNamespace

from pytrain_ui.adapters.state import snapshot_from_state


def _state(*, is_legacy: bool, is_rpm: bool = True):
    return SimpleNamespace(
        is_legacy=is_legacy,
        is_rpm=is_rpm,
        scope=SimpleNamespace(name="ENGINE"),
        tmcc_id=12,
        road_name="Test Road",
        road_number="1200",
        speed=10,
        target_speed=12,
        speed_max=199 if is_legacy else 31,
        speed_limit=40 if is_legacy else 20,
        speeds=(0, 0, 40 if is_legacy else 20, 0),
        direction=SimpleNamespace(name="FORWARD"),
        momentum=4,
        momentum_text="Med 4",
        train_brake=0,
        smoke=2,
        smoke_text="Med",
        labor=12,
        rpm=3,
    )


def test_snapshot_contains_controller_view_status_readouts() -> None:
    snapshot = snapshot_from_state(_state(is_legacy=True))

    assert snapshot.info_items == (
        ("Mom", "Med 4"),
        ("Brake", "Off"),
        ("Smoke", "Med"),
        ("Speed Lim", "40"),
        ("Effort", "12"),
        ("RPM", "3"),
    )


def test_tmcc1_snapshot_marks_legacy_only_status_as_na() -> None:
    snapshot = snapshot_from_state(_state(is_legacy=False, is_rpm=False))

    assert snapshot.brake_text == "NA"
    assert snapshot.smoke_text == "NA"
    assert snapshot.rpm_text == "NA"
