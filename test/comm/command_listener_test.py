import pytest

from src.comm.command_listener import CommandListener
from test.test_base import TestBase


@pytest.fixture(autouse=True)
def run_before_and_after_tests(tmpdir):
    """
        Fixture to execute asserts before and after a test is run
    """
    # Setup: fill with any logic you want

    yield  # this is where the testing happens

    # Teardown : fill with any logic you want
    if CommandListener.is_built():
        CommandListener().shutdown()
    assert CommandListener.is_built() is False


class TestCommandListener(TestBase):
    def test_singleton(self):
        assert CommandListener.is_built() is False
        listener = CommandListener()
        assert isinstance(listener, CommandListener)
        assert listener is CommandListener()

        # shutdown should clear singleton, forcing a new one to be created
        listener.shutdown()
        assert CommandListener.is_built() is False
        assert listener != CommandListener()
