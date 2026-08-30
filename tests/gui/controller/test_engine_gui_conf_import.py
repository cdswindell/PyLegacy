from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

import src.pytrain.gui.controller.engine_gui_conf as conf
from src.pytrain.protocol.constants import EngineType

MODULE_NAME = "src.pytrain.gui.controller.engine_gui_conf"
FIND_FILE_TARGET = "src.pytrain.utils.path_utils.find_file"


def test_importing_engine_gui_conf_does_not_call_find_file():
    """Importing the module must not resolve any image paths eagerly.

    Path resolution was moved off the import critical path; the module now stores plain
    filenames and only calls find_file on first access.
    """
    sys.modules.pop(MODULE_NAME, None)
    try:
        with patch(FIND_FILE_TARGET) as spy:
            importlib.import_module(MODULE_NAME)
            assert spy.call_count == 0, f"find_file was called {spy.call_count} time(s) during import"
    finally:
        # restore a real, un-patched module for the rest of the suite
        sys.modules.pop(MODULE_NAME, None)
        importlib.import_module(MODULE_NAME)


def test_engine_type_to_image_mapping_api_is_preserved():
    """The lazy mapping must behave like the old plain dict for readers."""
    fresh = importlib.import_module(MODULE_NAME)
    mapping = fresh.ENGINE_TYPE_TO_IMAGE

    # keys/iteration/len/contains mirror the underlying filename table
    assert set(mapping) == set(fresh.ENGINE_TYPE_TO_IMAGE_FILE)
    assert len(mapping) == len(fresh.ENGINE_TYPE_TO_IMAGE_FILE)
    assert EngineType.DIESEL in mapping

    # __getitem__ resolves to a real path (asset is bundled) and .get honors defaults
    diesel = mapping[EngineType.DIESEL]
    assert isinstance(diesel, str) and diesel.endswith("generic_diesel.jpg")
    assert mapping.get(EngineType.DIESEL) == diesel

    # a key not present in the table falls back to the supplied default
    class _NotAnEngineType:
        pass

    sentinel = object()
    assert mapping.get(_NotAnEngineType(), sentinel) is sentinel


def test_image_for_engine_type_matches_mapping():
    diesel_a = conf.image_for_engine_type(EngineType.DIESEL)
    diesel_b = conf.ENGINE_TYPE_TO_IMAGE[EngineType.DIESEL]
    assert diesel_a == diesel_b
    assert diesel_a is not None and diesel_a.endswith("generic_diesel.jpg")
