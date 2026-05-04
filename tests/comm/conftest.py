import pytest


@pytest.fixture(autouse=True, scope="package")
def mock_comm_external_io():
    class DummySerialReader:
        def __init__(self, baudrate=None, port=None, consumer=None) -> None:
            self.baudrate = baudrate
            self.port = port
            self.consumer = consumer
            self.is_running = False

        def start(self) -> None:
            self.is_running = True

        def shutdown(self) -> None:
            self.is_running = False

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("src.pytrain.comm.command_listener.get_ip_address", lambda: ["127.0.0.1"])
    monkeypatch.setattr("src.pytrain.comm.serial_reader.SerialReader", DummySerialReader)
    yield
    monkeypatch.undo()
