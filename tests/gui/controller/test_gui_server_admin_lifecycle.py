"""GUI server admin actions are deferred until the Tk host closes."""

from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.pytrain.cli.pytrain import PyTrain
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum as Sync


@pytest.mark.parametrize("broadcast", [False, True])
def test_gui_server_action_claims_and_optionally_broadcasts(broadcast):
    train = object.__new__(PyTrain)
    train._admin_state_lock = Lock()
    train._exit_requested = False
    train._shutdown_started = False
    train._admin_action = None
    train._received_admin_cmds = set()
    train._admin_exit_previous = (None, False)
    train._dispatcher = SimpleNamespace(signal_clients=MagicMock())
    train._log_admin_exit = MagicMock()
    train._tmcc_buffer = MagicMock()
    # Avoid initializing the communication singleton: use a server property override.
    from unittest.mock import patch

    with patch.object(PyTrain, "is_server", new_callable=lambda: property(lambda _: True)):
        train.request_gui_server_action(Sync.RESTART, broadcast=broadcast)
    assert train._admin_action == Sync.RESTART
    assert train._exit_requested
    assert train._dispatcher.signal_clients.call_count == int(broadcast)


def test_deferred_restart_preserves_flatpak_exit_code():
    train = object.__new__(PyTrain)
    train._admin_action = Sync.RESTART
    train._flatpak_local_restart = True
    train._admin_state_lock = Lock()
    train._log_admin_exit = MagicMock()
    with pytest.raises(SystemExit) as exc:
        train.perform_deferred_admin_action()
    assert exc.value.code == 42


def test_pycab_gui_server_restart_reexecs_python(monkeypatch):
    import sys
    from unittest.mock import Mock

    from src.pytrain.cli.pycab import PyCabGuiCmd

    cmd = object.__new__(PyCabGuiCmd)
    cmd._pytrain = SimpleNamespace(_admin_action=Sync.RESTART)
    execv = Mock(side_effect=RuntimeError("exec intercepted"))
    monkeypatch.setattr("src.pytrain.cli.pycab.os.execv", execv)
    with pytest.raises(RuntimeError, match="exec intercepted"):
        cmd._perform_server_admin_action()
    execv.assert_called_once_with(sys.executable, [sys.executable, *sys.argv])


def test_pycab_gui_server_nonrestart_runs_deferred_action():
    from src.pytrain.cli.pycab import PyCabGuiCmd

    cmd = object.__new__(PyCabGuiCmd)
    train = SimpleNamespace(_admin_action=Sync.UPDATE, _api=True, perform_deferred_admin_action=MagicMock())
    cmd._pytrain = train
    cmd._perform_server_admin_action()
    assert train._api is False
    train.perform_deferred_admin_action.assert_called_once_with()
