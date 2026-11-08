"""Regression tests for state-store initialization before PyTrain binds listeners."""

from unittest.mock import Mock

from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.protocol.constants import CommandScope


def test_early_state_store_initialization_accepts_later_listeners(monkeypatch):
    # Isolate the singleton from other tests without constructing network listeners.
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    early_store = ComponentStateStore()
    assert early_store._listeners == ()

    listener = Mock()
    configured_store = ComponentStateStore(listeners=(listener,))
    assert configured_store is early_store

    # This raised TypeError: 'NoneType' object is not iterable on client startup.
    configured_store.listen_for(CommandScope.BASE)
    listener.listen_for.assert_called_once_with(configured_store, CommandScope.BASE)


def test_early_state_store_rebind_preserves_existing_state(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    store = ComponentStateStore()
    original_state = store._state

    first_listener = Mock()
    assert ComponentStateStore(listeners=(first_listener,)) is store
    assert store._listeners == (first_listener,)
    assert store._state is original_state

    # A subsequent lookup without listeners must not discard the bound listeners.
    assert ComponentStateStore() is store
    store.listen_for(CommandScope.ENGINE)
    first_listener.listen_for.assert_called_once_with(store, CommandScope.ENGINE)
