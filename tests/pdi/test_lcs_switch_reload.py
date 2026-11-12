"""Exercise switch state recovery across a Base 3 roster reload."""

from threading import Event

# noinspection PyPackageRequirements
import pytest

from src.pytrain.comm.command_listener import SYNC_COMPLETE, SYNCING, CommandDispatcher
from src.pytrain.db.comp_data import SwitchData
from src.pytrain.db.component_state import ComponentState, SwitchState
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.pdi.asc2_req import Asc2Req
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import Asc2Action, PdiCommand
from src.pytrain.pdi.pdi_listener import PdiDispatcher
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum as Switch


def test_reload_restores_switch_updates_after_blank_base_record(monkeypatch: pytest.MonkeyPatch) -> None:
    # Isolate the singleton instances so the test can shut down its own dispatchers.
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    monkeypatch.setattr(CommandDispatcher, "_instance", None)
    monkeypatch.setattr(PdiDispatcher, "_instance", None)
    store = ComponentStateStore.build()
    dispatcher = PdiDispatcher.build()
    command_dispatcher = CommandDispatcher.get()
    scope = CommandScope.SWITCH
    base_id, port_id = 20, 21
    deleted = Event()
    monkeypatch.setattr(ComponentState, "request_config", lambda _state, _command: None)

    try:
        echo = CommandReq.from_bytes(CommandReq.build(Switch.THRU, port_id).as_bytes, from_tmcc_rx=True)
        store(echo)
        original = store.query(scope, port_id)
        assert isinstance(original, SwitchState)
        assert original.is_thru

        def mark_deleted(message: object) -> None:
            if message is original:
                deleted.set()

        dispatcher.subscribe_delete(mark_deleted)

        blank = BaseReq(
            port_id,
            PdiCommand.BASE_MEMORY,
            scope=scope,
            start=0,
            data_length=PdiReq.scope_record_length(scope),
            data_bytes=SwitchData(None, port_id).as_bytes(),
        )
        dispatcher.offer(blank.as_bytes)
        assert deleted.wait(1.5), "The blank Base 3 record did not clear the unlinked switch"
        assert store.query(scope, port_id) is None
        store(echo)
        assert store.query(scope, port_id) is None

        store(SYNCING)
        config = Asc2Req(base_id, PdiCommand.ASC2_RX, Asc2Action.CONFIG, mode=2)
        store(Asc2Req(config.as_bytes))
        store(SYNC_COMPLETE)
        restored = store.query(scope, port_id)
        assert restored is not original
        assert isinstance(restored, SwitchState)
        assert restored.parent_id == base_id
        assert restored.is_unknown

        store(echo)
        assert restored.is_thru
        feedback = Asc2Req(port_id, PdiCommand.ASC2_RX, Asc2Action.CONTROL4, values=1)
        store(Asc2Req(feedback.as_bytes))
        assert restored.is_out
    finally:
        dispatcher.shutdown()
        dispatcher.join(timeout=1.5)
        command_dispatcher.shutdown()
        command_dispatcher.join(timeout=1.5)
