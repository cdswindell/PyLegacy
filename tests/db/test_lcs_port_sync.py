"""Verify that LCS port associations converge across sync packet orders."""

import logging

import pytest

from pytrain.comm.command_listener import SYNC_COMPLETE, SYNCING
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.pdi.asc2_req import Asc2Req
from pytrain.pdi.bpc2_req import Bpc2Req
from pytrain.pdi.constants import Asc2Action, Bpc2Action, PdiCommand
from pytrain.protocol.constants import CommandScope


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    monkeypatch.setattr("pytrain.comm.comm_buffer.CommBuffer.is_server", lambda: False)
    return ComponentStateStore.build()


# Pytest's built-in log capture fixture is named caplog.
# noinspection SpellCheckingInspection
@pytest.mark.parametrize("config_after_sync", [False, True])
@pytest.mark.parametrize(
    "request_type, command, mode, scope, port_count",
    [
        (Bpc2Req, PdiCommand.BPC2_RX, 2, CommandScope.ACC, 8),
        (Asc2Req, PdiCommand.ASC2_RX, 0, CommandScope.ACC, 8),
        (Asc2Req, PdiCommand.ASC2_RX, 1, CommandScope.ACC, 1),
        (Asc2Req, PdiCommand.ASC2_RX, 2, CommandScope.SWITCH, 4),
    ],
)
def test_config_links_ports_on_either_side_of_sync(
    store, config_after_sync, request_type, command, mode, scope, port_count, caplog
):
    caplog.set_level(logging.INFO)
    store(SYNCING)
    if config_after_sync:
        store(SYNC_COMPLETE)

    config = request_type(request_type(20, command, mode=mode).as_bytes)
    store(config)
    base = store.get_state(scope, 20, False)
    children = [store.get_state(scope, address, False) for address in range(21, 20 + port_count)]
    assert all(
        child is not None and child.parent is base and child.port == port for port, child in enumerate(children, 2)
    )

    store(config)
    if not config_after_sync:
        store(SYNC_COMPLETE)
    assert store.addresses(scope) == set(range(20, 20 + port_count))
    assert children == [store.get_state(scope, address, False) for address in range(21, 20 + port_count)]
    assert caplog.text.count("LCS port links repaired on CONFIG") == int(config_after_sync and port_count > 1)
    assert "LCS post-sync validation repaired port links" not in caplog.text


# Pytest's built-in log capture fixture is named caplog.
# noinspection SpellCheckingInspection
def test_post_sync_restores_missing_port_and_keeps_existing_feedback(store, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    scope = CommandScope.ACC
    store(SYNCING)
    store(Bpc2Req(1, PdiCommand["BPC2_RX"], Bpc2Action.CONFIG, mode=2))
    store(Bpc2Req(4, PdiCommand["BPC2_RX"], Bpc2Action.CONTROL3, state=1))
    child = store.get_state(scope, 4, False)
    child.comp_data.road_name = "Conveyor Belt"
    # Simulate a missing link while preserving the child and its recorded feedback.
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(child, "_parent", None)
    store.delete_state(store.get_state(scope, 5, False))

    store(SYNC_COMPLETE)

    base = store.get_state(scope, 1, False)
    assert store.get_state(scope, 4, False) is child
    assert child.parent is base and child.port == 4 and child.is_aux_on
    assert child.comp_data.road_name == "Conveyor Belt"
    assert store.get_state(scope, 5, False).parent is base
    assert "LCS post-sync validation repaired port links: BPC2_RX ACC 1, ports at [4, 5]" in caplog.text


# Pytest's built-in log capture fixture is named caplog.
# noinspection SpellCheckingInspection
def test_asc2_latching_config_warns_and_sync_continues(store, caplog):
    store(SYNCING)
    latching = Asc2Req(bytes.fromhex("d1 3e 14 03 14 00 00 00 03 19 7b df"))
    assert latching.mode == 3
    store(latching)
    store(Asc2Req(30, PdiCommand["ASC2_RX"], Asc2Action.CONFIG, mode=0))
    store(SYNC_COMPLETE)

    assert store.is_state_synchronized()
    assert "ASC2 20 reported Mode 3 (latching switch); skipping port association" in caplog.text
    assert store.get_state(CommandScope.ACC, 21, False) is None
    assert store.get_state(CommandScope.ACC, 31, False).parent_id == 30
