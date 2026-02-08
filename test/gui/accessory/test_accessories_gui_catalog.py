from __future__ import annotations

import sys
import types

import pytest

from src.pytrain.gui.accessories.accessory_gui_catalog import AccessoryGuiCatalog, GuiCatalogEntry
from src.pytrain.gui.accessories.accessory_type import AccessoryType


def test_register_duplicate_key_rejected() -> None:
    cat = AccessoryGuiCatalog()

    # We need to register a duplicate *normalized* key.
    e1 = GuiCatalogEntry(key="milk", module=".dummy_mod", attr="Dummy", accessory_type=AccessoryType.MILK_LOADER)
    e2 = GuiCatalogEntry(key="MILK", module=".dummy_mod2", attr="Dummy2", accessory_type=AccessoryType.MILK_LOADER)

    # wipe the defaults for this test (Catalog as written pre-registers entries)
    cat._entries.clear()  # ok for unit tests

    cat.register(e1)
    with pytest.raises(ValueError, match="Duplicate"):
        cat.register(e2)


def test_resolve_exact_match_and_normalization() -> None:
    cat = AccessoryGuiCatalog()

    # This assumes your catalog has "milk" registered like you showed.
    e = cat.resolve("milk")
    assert e.key.lower() == "milk"

    # normalization: underscores/hyphens/quotes removed
    e2 = cat.resolve("m-i_l'k")
    assert e2.key.lower() == "milk"


def test_resolve_substring_match_prefers_first_insert_order() -> None:
    cat = AccessoryGuiCatalog()

    # isolate test catalog
    cat._entries.clear()

    cat.register(
        GuiCatalogEntry(
            "smoke",
            ".dummy_smoke",
            "SmokeGui",
            accessory_type=AccessoryType.SMOKE_FLUID_LOADER,
        )
    )
    cat.register(
        GuiCatalogEntry(
            "smokestack",
            ".dummy_stack",
            "StackGui",
            accessory_type=AccessoryType.SMOKE_FLUID_LOADER,
        )
    )

    # substring "smok" matches both; catalog returns first inserted match
    e = cat.resolve("smok")
    assert e.key == "smoke"


def test_resolve_invalid_raises() -> None:
    cat = AccessoryGuiCatalog()
    with pytest.raises(ValueError, match="Invalid GUI key"):
        cat.resolve("not_a_real_accessory")


def test_load_class_lazy_import() -> None:
    """
    GuiCatalogEntry.load_class uses import_module(self.module, package=__package__).

    We simulate a module under the catalog's package and ensure load_class returns
    the class attribute.
    """
    # Create dummy module: pytrain.gui.accessories._dummy_for_test
    mod_name = "src.pytrain.gui.accessories._dummy_for_test"
    dummy_mod = types.ModuleType(mod_name)

    class DummyGui:
        pass

    dummy_mod.DummyGui = DummyGui  # type: ignore[attr-defined]
    sys.modules[mod_name] = dummy_mod

    # Use relative import string so import_module(..., package=__package__) works.
    entry = GuiCatalogEntry(
        key="dummy",
        module="._dummy_for_test",
        attr="DummyGui",
        accessory_type=AccessoryType.PLAYGROUND,
    )

    loaded = entry.load_class()
    assert loaded is DummyGui
