from __future__ import annotations

from src.pytrain.gui.controller.catalog_panel import CatalogPanel
from src.pytrain.protocol.constants import CommandScope


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
