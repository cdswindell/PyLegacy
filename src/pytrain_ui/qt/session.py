"""Persistent Qt cab session preferences."""

from __future__ import annotations

from PySide6.QtCore import QSettings

from pytrain.db.component_state_store import ComponentStateStore
from pytrain.protocol.constants import CommandScope

_LAST_ENGINE_ID = "cab/last_engine_id"
_LAST_ENGINE_BT = "cab/last_engine_bt"


def restore_engine() -> int | None:
    """Resolve the last controlled physical engine against the current roster."""
    settings = QSettings()
    bt_id = int(settings.value(_LAST_ENGINE_BT, 0) or 0)
    tmcc_id = int(settings.value(_LAST_ENGINE_ID, 0) or 0)
    store = ComponentStateStore.get()

    if bt_id:
        for state in store.get_all(CommandScope.ENGINE):
            if int(getattr(state, "bt_int", 0) or 0) == bt_id:
                if int(state.tmcc_id) == tmcc_id:
                    return tmcc_id
        for state in store.get_all(CommandScope.ENGINE):
            if int(getattr(state, "bt_int", 0) or 0) == bt_id:
                return int(state.tmcc_id)

    if tmcc_id and ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False) is not None:
        return tmcc_id
    return None


def save_engine(tmcc_id: int) -> None:
    """Remember the current engine and its physical Bluetooth identity, when known."""
    state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False)
    if state is None:
        return
    settings = QSettings()
    settings.setValue(_LAST_ENGINE_ID, tmcc_id)
    settings.setValue(_LAST_ENGINE_BT, int(getattr(state, "bt_int", 0) or 0))
