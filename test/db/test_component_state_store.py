import time

# noinspection PyPackageRequirements
import pytest

# noinspection PyProtectedMember
from src.comm.command_listener import CommandListener, _CommandDispatcher
from src.db.component_state import SwitchState
from src.db.component_state_store import ComponentStateStore
from src.protocol.command_req import CommandReq
from src.protocol.constants import CommandScope
from src.protocol.tmcc1.tmcc1_constants import TMCC1SwitchState
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

    if _CommandDispatcher.is_built:
        _CommandDispatcher().shutdown()
    assert _CommandDispatcher.is_built is False


# noinspection PyMethodMayBeStatic
class TestComponentStateStore(TestBase):
    def test_component_state_store_basic(self) -> None:
        # create a store
        store = ComponentStateStore()
        store.listen_for([CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.ACC, CommandScope.SWITCH])
        assert store is not None
        assert store.is_empty

        dispatcher = store._listener._dispatcher
        assert dispatcher is not None
        assert dispatcher.is_running is True

        # add some state
        sw_out = CommandReq.build(TMCC1SwitchState.OUT, 15)
        dispatcher.offer(sw_out)
        time.sleep(0.1)
        assert store.is_empty is False
        sw_15_state: SwitchState = store.query(CommandScope.SWITCH, 15)
        assert sw_15_state is not None
        assert sw_15_state.last_updated is not None
        assert sw_15_state.last_command == sw_out
        assert sw_15_state.is_known is True
        assert sw_15_state.state == TMCC1SwitchState.OUT
        assert sw_15_state.is_out is True
        assert sw_15_state.is_through is False

        # throw to through
        sw_through = CommandReq.build(TMCC1SwitchState.THROUGH, 15)
        dispatcher.offer(sw_through)
        time.sleep(0.1)
        assert sw_15_state is not None
        assert sw_15_state.last_updated is not None
        assert sw_15_state.last_command == sw_through
        assert sw_15_state.is_known is True
        assert sw_15_state.state == TMCC1SwitchState.THROUGH
        assert sw_15_state.is_out is False
        assert sw_15_state.is_through is True

        # set the address of a different switch. should not cause state to be known
        sw_addr = CommandReq.build(TMCC1SwitchState.SET_ADDRESS, 47)
        dispatcher.offer(sw_addr)
        time.sleep(0.1)
        sw_47_state: SwitchState = store.query(CommandScope.SWITCH, 47)
        assert sw_47_state is not None
        assert sw_47_state.last_updated is not None
        assert sw_47_state.last_command == sw_addr
        assert sw_47_state.is_known is False
        assert sw_47_state.state is None
        assert sw_47_state.is_out is False
        assert sw_47_state.is_through is False

        # throw the switch to out, state should now be set
        sw_out.address = 47
        assert sw_out.address == 47
        dispatcher.offer(sw_out)
        time.sleep(0.1)
        sw_47_state: SwitchState = store.query(CommandScope.SWITCH, 47)
        assert sw_47_state is not None
        assert sw_47_state.last_updated is not None
        assert sw_47_state.last_command == sw_out
        assert sw_47_state.is_known is True
        assert sw_47_state.state is TMCC1SwitchState.OUT
        assert sw_47_state.is_out is True
        assert sw_47_state.is_through is False
