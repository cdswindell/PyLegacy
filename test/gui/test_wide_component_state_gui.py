from __future__ import annotations

from typing import Any

import pytest

import src.pytrain.gui.accessories_gui as ac_mod
import src.pytrain.gui.component_state_gui as comp_mod
import src.pytrain.gui.motors_gui as mo_mod
import src.pytrain.gui.power_district_gui as pd_mod
import src.pytrain.gui.routes_gui as ro_mod
import src.pytrain.gui.switches_gui as sw_mod
import src.pytrain.gui.systems_gui as sy_mod
import src.pytrain.gui.wide_component_state_gui as wide_mod


class DummyPane:
    instances: list["DummyPane"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        DummyPane.instances.append(self)

    def reset(self) -> None:
        return


class DummyAggregator:
    instances: list["DummyAggregator"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        DummyAggregator.instances.append(self)

    def reset(self) -> None:
        return


@pytest.fixture(autouse=True)
def _patch_classes(monkeypatch):
    DummyPane.instances.clear()
    DummyAggregator.instances.clear()

    monkeypatch.setattr(ac_mod, "AccessoriesGui", DummyPane, raising=True)
    monkeypatch.setattr(mo_mod, "MotorsGui", DummyPane, raising=True)
    monkeypatch.setattr(pd_mod, "PowerDistrictsGui", DummyPane, raising=True)
    monkeypatch.setattr(ro_mod, "RoutesGui", DummyPane, raising=True)
    monkeypatch.setattr(sw_mod, "SwitchesGui", DummyPane, raising=True)
    monkeypatch.setattr(sy_mod, "SystemsGui", DummyPane, raising=True)
    monkeypatch.setattr(wide_mod, "ComponentStateGui", DummyAggregator, raising=True)
    monkeypatch.setattr(comp_mod, "ComponentStateGui", DummyAggregator, raising=False)
    yield
    DummyPane.instances.clear()
    DummyAggregator.instances.clear()


def test_direct_single_gui_per_pane_builds_without_combo() -> None:
    gui = wide_mod.WideComponentStateGui(
        width=1920,
        height=480,
        screen_components=[["Routes"], ["Power Districts"]],
    )

    assert len(gui.panes) == 2
    assert len(DummyPane.instances) == 2
    assert len(DummyAggregator.instances) == 0

    first, second = DummyPane.instances
    assert first.kwargs["width"] == 960
    assert second.kwargs["width"] == 960
    assert first.kwargs["x_offset"] == 0
    assert second.kwargs["x_offset"] == 960
    assert first.kwargs["full_screen"] is False
    assert second.kwargs["full_screen"] is False


def test_multi_gui_set_builds_combo_limited_aggregator() -> None:
    _ = wide_mod.WideComponentStateGui(
        width=1920,
        height=480,
        screen_components=[["Routes", "Power Districts"], ["Switches"]],
    )

    assert len(DummyAggregator.instances) == 1
    assert len(DummyPane.instances) == 1

    combo_pane = DummyAggregator.instances[0]
    assert combo_pane.kwargs["initial"] == "Routes"
    assert set(combo_pane.kwargs["guis"].keys()) == {"Routes", "Power Districts"}
    assert combo_pane.kwargs["screens"] == 1
    assert combo_pane.kwargs["x_offset"] == 0
    assert combo_pane.kwargs["width"] == 960

    direct_pane = DummyPane.instances[0]
    assert direct_pane.kwargs["x_offset"] == 960
    assert direct_pane.kwargs["width"] == 960


def test_invalid_gui_name_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid GUI name"):
        _ = wide_mod.WideComponentStateGui(
            width=800,
            height=480,
            screen_components=[["Not A Real GUI"]],
        )
