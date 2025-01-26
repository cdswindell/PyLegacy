import time

# noinspection PyPackageRequirements
import pytest

# noinspection PyProtectedMember
from src.pytrain.comm.command_listener import CommandListener, CommandDispatcher
from src.pytrain.db.component_state import SwitchState
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum
from test.test_base import TestBase


@pytest.fixture(autouse=True)
def run_before_and_after_tests(tmpdir) -> None:
    """
    Fixture to execute asserts before and after a test is run
    """
    # Setup: fill with any logic you want

    yield  # this is where the testing happens

    # Teardown : fill with any logic you want
    if CommandListener.is_built():
        CommandListener().shutdown()
    assert CommandListener.is_built() is False

    if CommandDispatcher.is_built():
        CommandDispatcher().shutdown()
    assert CommandDispatcher.is_built() is False


# noinspection PyMethodMayBeStatic
class TestComponentStateStore(TestBase):
    def test_component_state_store_basic(self) -> None:
        # create a dispatcher to serve the store
        dispatcher = CommandDispatcher.build()
        assert dispatcher is not None
        assert dispatcher.is_running()

        # create a store
        store = ComponentStateStore(listeners=(dispatcher,))
        store.listen_for([CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.ACC, CommandScope.SWITCH])
        assert store is not None
        assert store.is_empty

        # add some state
        sw_out = CommandReq.build(TMCC1SwitchCommandEnum.OUT, 15)
        dispatcher.offer(sw_out)
        time.sleep(0.1)
        assert store.is_empty is False
        sw_15_state: SwitchState = store.query(CommandScope.SWITCH, 15)
        assert sw_15_state is not None
        assert sw_15_state.last_updated is not None
        assert sw_15_state.last_command == sw_out
        assert sw_15_state.is_known is True
        assert sw_15_state.state == TMCC1SwitchCommandEnum.OUT
        assert sw_15_state.is_out is True
        assert sw_15_state.is_through is False

        # throw to through
        sw_through = CommandReq.build(TMCC1SwitchCommandEnum.THRU, 15)
        dispatcher.offer(sw_through)
        time.sleep(0.1)
        assert sw_15_state is not None
        assert sw_15_state.last_updated is not None
        assert sw_15_state.last_command == sw_through
        assert sw_15_state.is_known is True
        assert sw_15_state.state == TMCC1SwitchCommandEnum.THRU
        assert sw_15_state.is_out is False
        assert sw_15_state.is_through is True

        # set the address of a different switch. should not cause state to be known
        sw_addr = CommandReq.build(TMCC1SwitchCommandEnum.SET_ADDRESS, 47)
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
        assert sw_47_state.state is TMCC1SwitchCommandEnum.OUT
        assert sw_47_state.is_out is True
        assert sw_47_state.is_through is False
