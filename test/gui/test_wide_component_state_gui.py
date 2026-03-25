from __future__ import annotations

from typing import Any

import pytest

import src.pytrain.gui.accessories_gui as ac_mod
import src.pytrain.gui.guizero_base as base_mod
import src.pytrain.gui.motors_gui as mo_mod
import src.pytrain.gui.power_district_gui as pd_mod
import src.pytrain.gui.routes_gui as ro_mod
import src.pytrain.gui.switches_gui as sw_mod
import src.pytrain.gui.systems_gui as sy_mod
import src.pytrain.gui.wide_component_state_gui as wide_mod


class DummyGui:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class BuiltPane:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def pump_messages(self) -> None:
        return

    def destroy(self) -> None:
        return


@pytest.fixture(autouse=True)
def _patch_classes(monkeypatch):
    monkeypatch.setattr(ac_mod, "AccessoriesGui", DummyGui, raising=True)
    monkeypatch.setattr(mo_mod, "MotorsGui", DummyGui, raising=True)
    monkeypatch.setattr(pd_mod, "PowerDistrictsGui", DummyGui, raising=True)
    monkeypatch.setattr(ro_mod, "RoutesGui", DummyGui, raising=True)
    monkeypatch.setattr(sw_mod, "SwitchesGui", DummyGui, raising=True)
    monkeypatch.setattr(sy_mod, "SystemsGui", DummyGui, raising=True)
    monkeypatch.setattr(base_mod.CommandDispatcher, "get", staticmethod(lambda: object()), raising=True)
    monkeypatch.setattr(base_mod.ComponentStateStore, "get", staticmethod(lambda: object()), raising=True)


def test_direct_single_gui_per_pane_builds_without_combo(monkeypatch) -> None:
    created: list[BuiltPane] = []

    def fake_create_pane(self, app, root, pane_guis, pane_width, pane_height, column):
        pane = BuiltPane(
            app=app,
            root=root,
            pane_guis=pane_guis,
            pane_width=pane_width,
            pane_height=pane_height,
            column=column,
        )
        created.append(pane)
        return pane

    monkeypatch.setattr(wide_mod.WideComponentStateGui, "_create_pane", fake_create_pane, raising=True)

    gui = wide_mod.WideComponentStateGui(
        width=1920,
        height=480,
        screen_components=[["Routes"], ["Power Districts"]],
        auto_start=False,
    )
    gui._build_panes(app=None, root=None)  # type: ignore[arg-type]

    assert len(gui.panes) == 2
    assert len(created) == 2
    assert created[0].kwargs["pane_width"] == 960
    assert created[1].kwargs["pane_width"] == 960
    assert created[0].kwargs["column"] == 0
    assert created[1].kwargs["column"] == 1
    assert created[0].kwargs["pane_guis"] == ["Routes"]
    assert created[1].kwargs["pane_guis"] == ["Power Districts"]


def test_multi_gui_set_creates_expected_panes(monkeypatch) -> None:
    created: list[BuiltPane] = []

    def fake_create_pane(self, app, root, pane_guis, pane_width, pane_height, column):
        pane = BuiltPane(
            pane_guis=pane_guis,
            pane_width=pane_width,
            pane_height=pane_height,
            column=column,
        )
        created.append(pane)
        return pane

    monkeypatch.setattr(wide_mod.WideComponentStateGui, "_create_pane", fake_create_pane, raising=True)

    gui = wide_mod.WideComponentStateGui(
        width=1920,
        height=480,
        screen_components=[["Routes", "Power Districts"], ["Switches"]],
        auto_start=False,
    )
    gui._build_panes(app=None, root=None)  # type: ignore[arg-type]

    assert len(created) == 2
    assert created[0].kwargs["pane_guis"] == ["Routes", "Power Districts"]
    assert created[1].kwargs["pane_guis"] == ["Switches"]
    assert created[0].kwargs["pane_width"] == 960
    assert created[1].kwargs["pane_width"] == 960


def test_invalid_gui_name_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid GUI name"):
        _ = wide_mod.WideComponentStateGui(
            width=800,
            height=480,
            screen_components=[["Not A Real GUI"]],
            auto_start=False,
        )


def test_subprocess_options_are_accepted_and_ignored() -> None:
    gui = wide_mod.WideComponentStateGui(
        width=800,
        height=480,
        screen_components=[["Routes"]],
        use_subprocesses=True,
        process_start_method="fork",
        auto_start=False,
    )
    assert gui.width == 800
    assert gui.height == 480
