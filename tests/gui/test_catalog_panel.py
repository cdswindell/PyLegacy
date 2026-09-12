from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.pytrain.db.component_state import RouteState, SwitchState
from src.pytrain.gui.controller.catalog_panel import CatalogPanel
from src.pytrain.gui.controller.engine_gui import EngineGui
from src.pytrain.gui.guizero_base import ACTIVE_STATE_BG
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum


class _Button:
    def __init__(self, value: int = 1) -> None:
        self.value = value
        self.text = ""


class _Catalog:
    def __init__(self) -> None:
        self.items: list[str] = []
        self.styles: dict[int, dict] = {}

    def clear(self) -> None:
        self.items.clear()
        self.styles.clear()

    def append(self, item: str) -> None:
        self.items.append(item)

    def set_item_style(self, **kwargs) -> None:
        self.styles[len(self.items) - 1] = kwargs


class _Accessory:
    def __init__(self, label: str) -> None:
        self.label = label


class _Accessories:
    def __init__(self, *labels: str) -> None:
        self._labels = labels

    def has_any(self) -> bool:
        return bool(self._labels)

    def configured_by_label_map(self) -> dict[str, list[_Accessory]]:
        return {label.lower(): [_Accessory(label)] for label in self._labels}


class _Provider:
    def get(self, acc: _Accessory) -> str:
        return f"adapter:{acc.label}"


class _Store:
    def get_all(self, _scope: CommandScope) -> list:
        return []


def test_controller_scroll_uses_visible_catalog_without_selecting() -> None:
    calls = []
    panel = CatalogPanel.__new__(CatalogPanel)
    panel._overlay = SimpleNamespace(visible=True)
    panel._catalog = SimpleNamespace(scroll_by_pixels=calls.append)
    gui = SimpleNamespace(_route_builder_panel=None, _catalog_panel=panel)
    assert EngineGui.list_scroll_panel.fget(gui) is panel
    assert panel.scroll_view is panel._catalog
    panel.scroll_by_pixels(37)
    panel.scroll_by_pixels(-12)
    assert calls == [37, -12]
    panel._overlay.visible = False
    assert EngineGui.list_scroll_panel.fget(gui) is None
    panel._catalog = None
    panel.scroll_by_pixels(10)
    assert panel.scroll_view is None
    assert calls == [37, -12]


def test_select_highlighted_delegates_to_catalog_list_box() -> None:
    panel = CatalogPanel.__new__(CatalogPanel)
    panel._catalog = type("Lb", (), {"activate_highlighted": lambda self: True})()

    assert panel.select_highlighted() is True


def test_select_highlighted_returns_false_without_catalog() -> None:
    panel = CatalogPanel.__new__(CatalogPanel)
    panel._catalog = None

    assert panel.select_highlighted() is False


def test_move_highlight_delegates_to_catalog_list_box() -> None:
    panel = CatalogPanel.__new__(CatalogPanel)
    calls: list[int] = []
    panel._catalog = type("Lb", (), {"move_highlight": lambda self, delta: calls.append(delta) or True})()

    assert panel.move_highlight(-1) is True
    assert calls == [-1]


def test_move_highlight_returns_false_without_catalog() -> None:
    panel = CatalogPanel.__new__(CatalogPanel)
    panel._catalog = None

    assert panel.move_highlight(1) is False


def test_reset_configured_accessory_cache_clears_and_rebuilds_active_accessory_catalog() -> None:
    panel = CatalogPanel.__new__(CatalogPanel)
    panel._configured_acc_labels = ["Old"]
    panel._configured_acc_dict = {"Old": object()}
    panel._scope = CommandScope.ACC
    panel._catalog = object()
    calls: list[tuple[CommandScope, bool]] = []
    panel.configure = lambda scope, force=False: calls.append((scope, force))

    panel.reset_configured_accessory_cache()

    assert panel._configured_acc_labels is None
    assert panel._configured_acc_dict is None
    assert calls == [(CommandScope.ACC, True)]


def test_reset_configured_accessory_cache_does_not_build_missing_catalog() -> None:
    panel = CatalogPanel.__new__(CatalogPanel)
    panel._configured_acc_labels = ["Old"]
    panel._configured_acc_dict = {"Old": object()}
    panel._scope = CommandScope.ACC
    panel._catalog = None
    calls: list[tuple[CommandScope, bool]] = []
    panel.configure = lambda scope, force=False: calls.append((scope, force))

    panel.reset_configured_accessory_cache()

    assert panel._configured_acc_labels is None
    assert panel._configured_acc_dict is None
    assert calls == []


def test_reset_configured_accessory_cache_rebuilds_from_current_scope() -> None:
    panel = CatalogPanel.__new__(CatalogPanel)
    catalog = _Catalog()
    panel._overlay = object()
    panel._gui = type(
        "Gui",
        (),
        {
            "accessories": _Accessories("New Crane", "New Loader"),
            "accessory_provider": _Provider(),
            "scope": CommandScope.ACC,
        },
    )()
    panel._state_store = _Store()
    panel._catalog = catalog
    panel._scope = CommandScope.ENGINE
    panel._configured_acc_labels = ["Old Crane"]
    panel._configured_acc_dict = {"Old Crane": object()}
    panel._scoped_sort_order = {}
    panel._scoped_selection = {}
    panel._sort_btns = type("Sort", (), {"value": "0"})()
    panel._sel_1_btn = _Button()
    panel._sel_2_btn = _Button()
    panel._sel_3_btn = _Button()
    panel._entry_state_map = {}
    panel._skip_update = False

    panel.reset_configured_accessory_cache(scope=CommandScope.ACC)

    assert catalog.items == ["New Crane", "New Loader"]
    assert panel._entry_state_map == {
        "New Crane": "adapter:New Crane",
        "New Loader": "adapter:New Loader",
    }


@pytest.mark.parametrize("scope", [CommandScope.SWITCH, CommandScope.ROUTE])
@pytest.mark.parametrize("sort_order", [0, 1, 2])
def test_active_catalog_rows_use_lighter_green_and_reset_when_inactive(scope, sort_order) -> None:
    state = SwitchState() if scope == CommandScope.SWITCH else RouteState()
    state._address = 7
    state.initialize(scope, 7)
    state._road_name = "Main siding"
    state._road_number = "0007"
    panel = CatalogPanel.__new__(CatalogPanel)
    panel._overlay = object()
    panel._state_store = SimpleNamespace(get_all=lambda _scope: [state])
    panel._catalog = _Catalog()
    panel._scope = None
    panel._scoped_sort_order = {scope: sort_order}
    panel._scoped_selection = {}
    panel._sort_btns = SimpleNamespace(value="0")
    panel._sel_1_btn = _Button()
    panel._sel_2_btn = _Button()
    panel._sel_3_btn = _Button()
    panel._entry_state_map = {}

    for active in (True, False, None, True):
        if scope == CommandScope.SWITCH:
            state._state = {True: TMCC1SwitchCommandEnum.THRU, False: TMCC1SwitchCommandEnum.OUT, None: None}[active]
        else:
            state._signature = {"S7": True}
            state._current_state = {"S7": active}
        panel.configure(scope)
        assert len(panel._catalog.items) == 1
        assert panel._catalog.styles == ({0: {"background": "#4c9a4c"}} if active else {})


def test_active_background_has_high_contrast_with_black_text() -> None:
    channels = [int(ACTIVE_STATE_BG[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    luminance = sum(weight * channel for weight, channel in zip((0.2126, 0.7152, 0.0722), linear))
    assert (luminance + 0.05) / 0.05 >= 6
