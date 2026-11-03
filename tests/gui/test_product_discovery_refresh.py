"""A Bluetooth ID discovered after selection must replace provisional product/image results."""

from concurrent.futures import Future
from threading import Condition
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest

from src.pytrain.db.component_state import ComponentStateDict
import src.pytrain.gui.controller.image_presenter as image_mod
from src.pytrain.gui.controller.engine_gui import EngineGui
from src.pytrain.gui.controller.image_presenter import ImagePresenter
from src.pytrain.protocol.constants import CommandScope


class ProductHost(EngineGui):
    """Run the real state callback and product scheduler without Tk, sockets, or workers."""

    # Initialize only the services under test; the superclass starts GUI/runtime workers.
    # noinspection PyProtectedMember,PyMissingConstructor
    def __init__(self, state):
        self._cv = Condition()
        self.scope = CommandScope.ENGINE
        self._scope_tmcc_ids = {CommandScope.ENGINE: state.tmcc_id}
        self._state_store = SimpleNamespace(get_state=lambda *_args, **_kwargs: state)
        self._image_cache = {}
        self._prod_info_cache = {}
        self._pending_prod_infos = set()
        self._image_bt_ids = {}
        self._provisional = set()
        self._executor = Mock()
        self._executor.submit.return_value = Future()
        self._active_train_state = None
        self._state_info = None
        self._is_train_linked_cars = False
        self._scope_buttons = {CommandScope.TRAIN: SimpleNamespace(bg="white")}
        self._controller_view = Mock()
        self.name_text = SimpleNamespace(value="")
        self.get_scaled_image = Mock(return_value=object())
        self.get_image = Mock(return_value=object())


@pytest.fixture
def product_flow(monkeypatch, tmp_path):
    state = ComponentStateDict(CommandScope.ENGINE)[31]
    host = ProductHost(state)
    # Patch imported bindings in the consumer module. PyCharm cannot resolve these
    # string-based monkeypatch targets even though the bindings exist at runtime.
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(image_mod, "ENGINE_IMAGES_CACHE_DIR", str(tmp_path))
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(image_mod, "find_file", lambda *_args, **_kwargs: None)
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(image_mod, "center_text_on_image", lambda image, *_args, **_kwargs: image)
    presenter = ImagePresenter(host)
    # Replace only rendering and geometry; cache selection and product scheduling remain real.
    # noinspection PyProtectedMember
    presenter._update_image = Mock()
    presenter.refresh_box_size = lambda: (96, 192)
    # Custom file lookup is covered separately; these cases start after a confirmed miss.
    # noinspection PyProtectedMember
    presenter._checked_for_custom_images.add(31)
    # Connect the real helper to the inherited EngineGui state callback.
    # noinspection PyProtectedMember
    host._image_presenter = presenter
    try:
        yield state, host, presenter
    finally:
        # The presenter's file-lookup executor is not needed by these synchronous cases.
        # noinspection PyProtectedMember
        presenter._executor.shutdown(wait=True, cancel_futures=True)


def discover(state):
    state.initialize(CommandScope.ENGINE, state.tmcc_id)
    state.comp_data.bt_id = 0x6483
    state.comp_data.control_type = 1
    state.comp_data.engine_type = 1
    state.comp_data.sound_type = 2
    # Preserve the exact manufacturer-supplied road name from the hardware trace.
    # noinspection SpellCheckingInspection
    state.comp_data.road_name = "STRASBURG 0-6-0T"
    state.comp_data.road_number = "0301"


# Cache assertions verify the provisional sentinel is not mistaken for an attempted lookup.
# noinspection PyProtectedMember
def test_missing_bluetooth_id_does_not_cache_an_unavailable_product(product_flow):
    _state, host, _presenter = product_flow
    result = host.get_prod_info(None, Mock(), 31, available_width=192, available_height=96)
    assert result == "N/A"
    assert 31 not in host._prod_info_cache
    cast(Mock, host._executor).submit.assert_not_called()


# Exercise the real EngineGui callback, presenter invalidation, and base lookup scheduler together.
# noinspection PyProtectedMember
def test_tmcc_discovery_replaces_cached_fallback_and_schedules_product_lookup_once(product_flow):
    state, host, presenter = product_flow
    host.on_new_engine(state)
    presenter.update(tmcc_id=31)
    fallback = host._image_cache[(CommandScope.ENGINE, 31)]
    cast(Mock, host._executor).submit.assert_not_called()
    discover(state)
    host.on_new_engine(state)
    assert not state.is_legacy
    assert state.bt_id == "6483"
    assert (CommandScope.ENGINE, 31) not in host._image_cache
    cast(Mock, host._executor).submit.assert_called_once()
    assert cast(Mock, host._executor).submit.call_args.args[:2] == (host._fetch_prod_info, "6483")
    assert isinstance(host._prod_info_cache[31], Future)
    assert cast(Mock, presenter._update_image).call_args.args[0] is not fallback
    host.on_new_engine(state)
    cast(Mock, host._executor).submit.assert_called_once()


# The custom-image callback owns this private cache, so run it directly with a headless image.
# noinspection PyProtectedMember
def test_late_bluetooth_id_preserves_custom_image(product_flow):
    state, host, presenter = product_flow
    custom = object()
    # This sentinel stands in for an already prepared Tk image.
    # noinspection PyTypeChecker
    presenter._finish_custom_image_lookup(31, None, custom)
    discover(state)
    host.on_new_engine(state)
    assert host._image_cache[(CommandScope.ENGINE, 31)] is custom
    cast(Mock, host._executor).submit.assert_not_called()


# A failed lookup for an actual Bluetooth ID must not retry on every state update.
# noinspection PyProtectedMember
def test_failed_known_product_lookup_is_not_retried_for_unchanged_bluetooth_id(product_flow):
    state, host, presenter = product_flow
    discover(state)
    host._prod_info_cache[31] = "N/A"
    host.on_new_engine(state)
    presenter.update(tmcc_id=31)
    host.on_new_engine(state)
    cast(Mock, host._executor).submit.assert_not_called()
    assert host._prod_info_cache[31] == "N/A"


# A fetched image may replace a fallback between state notifications; retain that actual image.
# noinspection PyProtectedMember
def test_late_bluetooth_id_does_not_discard_an_already_replaced_image(product_flow):
    state, host, presenter = product_flow
    presenter.update(tmcc_id=31)
    product_image = object()
    host._image_cache[(CommandScope.ENGINE, 31)] = product_image
    discover(state)
    host.on_new_engine(state)
    assert host._image_cache[(CommandScope.ENGINE, 31)] is product_image
    cast(Mock, host._executor).submit.assert_not_called()
