"""API hosts receive explicit PyTrain exit reasons without executing OS actions."""

from threading import Lock
from unittest.mock import Mock, patch

import pytest

from src.pytrain.cli.pytrain import PyTrain, PyTrainExitException, PyTrainExitStatus


@pytest.fixture
def api_train():
    train = object.__new__(PyTrain)
    train._api = True
    train._exit_status = None
    train._admin_state_lock = Lock()
    train._api_exit_notified = False
    train._admin_action = None
    train._log_admin_exit = Mock()
    train._flatpak_local_restart = False
    return train


@pytest.mark.parametrize(
    ("method", "kwargs", "expected"),
    [
        ("restart", {}, PyTrainExitStatus.RESTART),
        ("reboot", {}, PyTrainExitStatus.REBOOT),
        ("reboot", {"reboot": False}, PyTrainExitStatus.SHUTDOWN),
        ("update", {}, PyTrainExitStatus.UPDATE),
        ("upgrade", {}, PyTrainExitStatus.UPGRADE),
    ],
)
def test_api_operations_raise_correct_exit_reason(api_train, monkeypatch, method, kwargs, expected):
    # Prevent a regression from invoking an actual system command or relaunch.
    monkeypatch.setattr("src.pytrain.cli.pytrain.subprocess.run", Mock(side_effect=AssertionError("subprocess")))
    monkeypatch.setattr("src.pytrain.cli.pytrain.os.execv", Mock(side_effect=AssertionError("execv")))
    with patch.object(PyTrain, "is_server", property(lambda _: True)):
        with pytest.raises(PyTrainExitException) as exc:
            getattr(api_train, method)(**kwargs)
    assert exc.value.reason is expected
    assert api_train.exit_status is expected
    assert expected.value in (0, 11, 12, 13, 14, 15)


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (PyTrainExitStatus.QUIT, 0),
        (PyTrainExitStatus.REBOOT, 11),
        (PyTrainExitStatus.RESTART, 12),
        (PyTrainExitStatus.SHUTDOWN, 13),
        (PyTrainExitStatus.UPDATE, 14),
        (PyTrainExitStatus.UPGRADE, 15),
    ],
)
def test_api_exit_status_codes(status, code):
    assert status.value == code


@pytest.mark.parametrize("status", list(PyTrainExitStatus))
def test_api_host_notification_records_status_once(api_train, monkeypatch, status):
    kill = Mock()
    monkeypatch.setattr("src.pytrain.cli.pytrain.os.kill", kill)
    api_train._notify_api_exit(status)
    assert api_train.exit_status is status
    assert api_train._api_exit_notified is True
    assert kill.call_count == 1
    api_train._notify_api_exit(status)
    assert kill.call_count == 1
