from __future__ import annotations

from src.pytrain.gui.controller.catalog_panel import CatalogPanel
from src.pytrain.protocol.constants import CommandScope


class _Button:
    def __init__(self, value: int = 1) -> None:
        self.value = value
        self.text = ""


class _Catalog:
    def __init__(self) -> None:
        self.items: list[str] = []

    def clear(self) -> None:
        self.items.clear()

    def append(self, item: str) -> None:
        self.items.append(item)


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
