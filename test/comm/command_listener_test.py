import pytest

from src.comm.command_listener import CommandListener
from src.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT
from test.test_base import TestBase


@pytest.fixture(autouse=True)
def run_before_and_after_tests(tmpdir) -> None:
    """
        Fixture to execute asserts before and after a test is run
    """
    # Setup: fill with any logic you want

    yield  # this is where the testing happens

    # Teardown : fill with any logic you want
    if CommandListener.is_built:
        CommandListener().shutdown()
    assert CommandListener.is_built is False


class TestCommandListener(TestBase):
    def test_singleton(self) -> None:
        assert CommandListener.is_built is False
        listener = CommandListener()
        assert listener.is_built is True
        assert listener.is_running is True
        assert isinstance(listener, CommandListener)
        assert listener is CommandListener()
        assert listener.baudrate == DEFAULT_BAUDRATE
        assert listener.port == DEFAULT_PORT

        # shutdown should clear singleton, forcing a new one to be created
        listener.shutdown()
        assert listener.is_built is False
        assert listener.is_running is False
        assert CommandListener.is_built is False
        assert listener != CommandListener()

    def test_build(self) -> None:
        listener = CommandListener.build()
        assert listener
        assert listener.is_built is True
        assert listener.is_running is True
        assert CommandListener.is_built is True
        assert CommandListener.is_running is True
