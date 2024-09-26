import pytest

from src.db.component_state import ComponentState, SwitchState
from src.protocol.command_req import CommandReq
from src.protocol.constants import CommandScope
from src.protocol.tmcc1.tmcc1_constants import TMCC1SwitchState, TMCC1HaltCommandDef
from src.protocol.tmcc2.tmcc2_constants import TMCC2RouteCommandDef
from ..test_base import TestBase


# noinspection PyMethodMayBeStatic
class TestComponentState(TestBase):
    def test_component_state(self) -> None:
        with pytest.raises(TypeError):
            # noinspection PyTypeCher
            ComponentState(None)

    def test_switch_state(self) -> None:
        ss = SwitchState()
        assert ss is not None
        assert ss.scope == CommandScope.SWITCH
        assert ss.address is None
        assert ss.last_command is None
        assert ss.last_updated is None
        assert ss.state is None
        assert ss.is_known is False
        assert ss.is_through is False
        assert ss.is_out is False

        # assert construction with scope Switch succeeds
        ss = SwitchState(CommandScope.SWITCH)
        assert ss is not None
        assert ss.scope == CommandScope.SWITCH

        # assert construction with any other scope fails
        for scope in CommandScope:
            if scope == CommandScope.SWITCH:
                continue
            with pytest.raises(ValueError):
                # noinspection PyTypeChecker
                SwitchState(scope)

        # assert calling update with a valid request succeeds
        set_req = CommandReq(TMCC1SwitchState.SET_ADDRESS, 1)
        assert set_req is not None
        assert set_req.scope == CommandScope.SWITCH
        assert set_req.address == 1

        # now call update
        ss.update(set_req)
        assert ss.last_command == set_req
        assert ss.last_updated is not None
        last_updated = ss.last_updated
        assert ss.address == 1
        # state should still be unknown
        assert ss.state is None
        assert ss.is_known is False
        assert ss.is_through is False
        assert ss.is_out is False

        # create a "switch thrown to out" request
        out_req = CommandReq(TMCC1SwitchState.OUT, 1)
        ss.update(out_req)
        assert ss.last_command == out_req
        assert ss.last_updated is not None
        assert ss.last_updated > last_updated
        last_updated = ss.last_updated
        assert ss.address == 1
        assert ss.state == TMCC1SwitchState.OUT
        assert ss.is_known is True
        assert ss.is_out is True
        assert ss.is_through is False

        # create a "switch thrown to through" request
        thru_req = CommandReq(TMCC1SwitchState.THROUGH, 1)
        ss.update(thru_req)
        assert ss.last_command == thru_req
        assert ss.last_updated is not None
        assert ss.last_updated > last_updated
        last_updated = ss.last_updated
        assert ss.address == 1
        assert ss.state == TMCC1SwitchState.THROUGH
        assert ss.is_known is True
        assert ss.is_out is False
        assert ss.is_through is True

        # update with another "set address" request, state should be unchanged
        ss.update(set_req)
        assert ss.last_command == set_req
        assert ss.last_updated is not None
        assert ss.last_updated > last_updated
        last_updated = ss.last_updated
        assert ss.address == 1
        assert ss.state == TMCC1SwitchState.THROUGH
        assert ss.is_known is True
        assert ss.is_out is False
        assert ss.is_through is True

        # throw switch out and check state is as expected
        ss.update(out_req)
        assert ss.last_command == out_req
        assert ss.last_updated is not None
        assert ss.last_updated > last_updated
        assert ss.address == 1
        assert ss.state == TMCC1SwitchState.OUT
        assert ss.is_known is True
        assert ss.is_out is True
        assert ss.is_through is False

        # verify address can not be modified once set
        thru_req = CommandReq(TMCC1SwitchState.THROUGH, 2)
        with pytest.raises(ValueError, match="Switch #1 received update for Switch #2, ignoring"):
            ss.update(thru_req)

        # verify we can't send update for some other object
        route_req = CommandReq(TMCC2RouteCommandDef.FIRE, 1)
        with pytest.raises(ValueError, match="Switch 1 received update for Route, ignoring"):
            ss.update(route_req)

        # verify we can receive a Halt command
        halt_req = CommandReq(TMCC1HaltCommandDef.HALT, 1)
        ss.update(halt_req)
        # but that it didn't affect state
        assert ss.last_command == out_req
        assert ss.address == 1
        assert ss.state == TMCC1SwitchState.OUT
        assert ss.is_known is True
        assert ss.is_out is True
        assert ss.is_through is False

    def test_accessory_state(self) -> None:
        assert False

    def test_engine_state(self) -> None:
        assert False

    def test_train_state(self) -> None:
        assert False

    def test_system_state_dict(self) -> None:
        assert False

    def test_component_state_dict(self) -> None:
        assert False
