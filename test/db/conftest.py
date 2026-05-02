import pytest


@pytest.fixture(autouse=True, scope="package")
def mock_command_dispatcher_ip():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("src.pytrain.comm.command_listener.get_ip_address", lambda: ["127.0.0.1"])
    yield
    monkeypatch.undo()
