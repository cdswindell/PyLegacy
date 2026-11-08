import logging
from unittest.mock import MagicMock, Mock, call

import pytest

from src.pytrain.cli import pytrain as module
from src.pytrain.pdi.pdi_device import PdiDevice


@pytest.fixture
def state_train(bare_pytrain):
    bare_pytrain._state_store = MagicMock(spec=module.ComponentStateStore)
    bare_pytrain._pdi_state_store = MagicMock(spec=module.PdiStateStore)
    return bare_pytrain


@pytest.mark.parametrize("value", [None, False, True])
def test_synchronized(state_train, value):
    state = Mock(spec=module.SyncState) if value is not None else None
    if state:
        state.is_synchronized.return_value = value
    state_train._state_store.get_state.return_value = state
    assert state_train.is_synchronized() is bool(value)
    state_train._state_store.get_state.assert_called_once_with(module.CommandScope.SYNC, 99, False)


@pytest.mark.parametrize(
    "no_wait,headless,known_server", [(False, False, True), (False, True, False), (True, False, True)]
)
@pytest.mark.parametrize("sync", [None, [True], [False, False, True]])
def test_load_client_state(state_train, monkeypatch, capsys, no_wait, headless, known_server, sync):
    state_train._server_ips = ["192.0.2.1"] if known_server else []
    state_train._server = "192.0.2.1"
    state_train._no_wait = no_wait
    state_train._headless = headless
    state = Mock(spec=module.SyncState) if sync else None
    if state:
        state.is_synchronized.side_effect = sync
    state_train._state_store.get_state.return_value = state
    delay = Mock()
    monkeypatch.setattr(module, "sleep", delay)
    state_train._load_client_state()
    assert delay.call_args_list == [call(0.1)] * (len(sync) - 1 if sync and not no_wait else 0)
    assert ("Done" in capsys.readouterr().out) is bool(sync and not no_wait)
    if no_wait:
        state_train._state_store.get_state.assert_not_called()


@pytest.mark.parametrize("startup,no_wait", [(False, False), (False, True), (True, False), (True, True)])
@pytest.mark.parametrize("sync", [None, [True], [False, True]])
def test_roster_requests(state_train, monkeypatch, capsys, startup, no_wait, sync):
    state_train._pdi_buffer = Mock(spec=module.PdiListener)
    state_train._dispatcher = Mock()
    state_train._force_sync = True
    state_train._no_d4 = False
    state_train._no_wait = no_wait
    state_train._base_addr = "192.0.2.2"
    state = Mock(spec=module.SyncState) if sync else None
    if state:
        state.is_synchronized.side_effect = sync
    state_train._state_store.get_state.return_value = state
    startup_factory = Mock()
    monkeypatch.setattr(module, "StartupState", startup_factory)
    delay = Mock()
    monkeypatch.setattr(module, "sleep", delay)
    state_train._get_system_state(is_startup=startup)
    startup_factory.assert_called_once_with(
        state_train._pdi_buffer, state_train._dispatcher, state_train._pdi_state_store, force_sync=True, no_d4=False
    )
    assert state_train._startup_state is startup_factory.return_value
    waiting = not (startup and no_wait)
    assert delay.call_count == (len(sync) - 1 if waiting and sync else 0)
    assert ("Done" in capsys.readouterr().out) is bool(waiting and sync)


@pytest.mark.parametrize("query", [None, "freight", "diesel", "legacy", "railsounds", "bt", "abcd", "missing"])
def test_db_filters(state_train, capsys, query):
    state = MagicMock(spec=module.EngineState)
    state.name = "Freight"
    state.engine_type_label = "Diesel"
    state.control_type_label = "Legacy"
    state.sound_type_label = "RailSounds"
    state.bt_id = "ABCD"
    state.__str__.return_value = "matching engine"
    state_train._state_store.__contains__.return_value = True
    state_train._state_store.get_all.return_value = [state]
    state_train._do_db(["engine"] + ([query] if query else []))
    assert capsys.readouterr().out.strip() == ("No data" if query == "missing" else "matching engine")


@pytest.mark.parametrize("found", [True, False])
def test_db_address(state_train, capsys, found):
    state_train._state_store.query.return_value = "engine seven" if found else None
    state_train._do_db(["engine", "7"])
    state_train._state_store.query.assert_called_once_with(module.CommandScope.ENGINE, 7)
    assert capsys.readouterr().out.strip() == ("engine seven" if found else "No data available for this Engine.")


@pytest.mark.parametrize("params", [[], ["unknown"], ["engine"], ["lcs"], ["lcs", "unknown"], ["lcs", "asc2"]])
def test_empty_database(state_train, capsys, params):
    state_train._state_store.keys.return_value = []
    state_train._pdi_state_store.keys.return_value = []
    state_train._state_store.__contains__.return_value = False
    state_train._pdi_state_store.__contains__.return_value = False
    state_train._do_db(params)
    assert capsys.readouterr().out == "No data\n"


def test_database_counts_and_lcs(state_train, capsys):
    state_train._state_store.keys.side_effect = lambda scope=None: (
        [1, 2]
        if scope
        else [module.CommandScope.BASE, module.CommandScope.SYNC, module.CommandScope.IRDA, module.CommandScope.ENGINE]
    )
    state_train._do_db([])
    assert capsys.readouterr().out == "Engines: 2\n"
    state_train._pdi_state_store.keys.side_effect = lambda device=None: [7] if device else [PdiDevice.ASC2]
    state_train._do_db(["lcs"])
    assert "1" in capsys.readouterr().out
    state_train._pdi_state_store.__contains__.return_value = True
    state_train._pdi_state_store.get_all.return_value = ["ASC2 configuration"]
    state_train._do_db(["lcs", "asc2"])
    state_train._pdi_state_store.get_all.assert_called_once_with(PdiDevice.ASC2)
    assert capsys.readouterr().out == "ASC2 configuration\n"


@pytest.mark.parametrize(
    "state_kind,available", [("engine", True), ("engine", False), ("no_btid", False), ("missing", False)]
)
def test_product_lookup(state_train, monkeypatch, caplog, state_kind, available):
    state = Mock(spec=module.EngineState) if state_kind != "missing" else None
    if state:
        state.bt_id = "ABCD" if state_kind == "engine" else None
    state_train._state_store.get_state.return_value = state
    info = Mock()
    info.as_dict.return_value = {"Name": "Freight", "Year": 2024}
    lookup = Mock(return_value=info if available else None)
    monkeypatch.setattr(module.ProdInfo, "by_btid", lookup)
    with caplog.at_level(logging.INFO):
        state_train._get_engine_info(["7"])
    if available:
        assert "Name: Freight" in caplog.text
        assert "Year: 2024" in caplog.text
    else:
        assert "No product information" in caplog.text
    if state_kind == "engine":
        lookup.assert_called_once_with("ABCD")
    else:
        lookup.assert_not_called()


def test_query_errors_and_empty_info(state_train, caplog):
    state_train._get_engine_info([])
    state_train._state_store.get_state.assert_not_called()
    state_train._get_engine_info(["invalid"])
    assert "invalid" in caplog.text
    state_train._state_store.query.side_effect = RuntimeError("database unavailable")
    state_train._do_db(["engine", "7"])
    assert "database unavailable" in caplog.text
