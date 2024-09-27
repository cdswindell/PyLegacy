from collections import defaultdict

import pytest

from src.db.component_state import SwitchState, AccessoryState, EngineState, TrainState
from src.db.component_state import ComponentState, SystemStateDict, ComponentStateDict
from src.protocol.command_req import CommandReq
from src.protocol.constants import CommandScope
from src.protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandDef
from src.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandDef as Acc
from src.protocol.tmcc1.tmcc1_constants import TMCC1SwitchState as Switch
from src.protocol.tmcc2.tmcc2_constants import TMCC2RouteCommandDef
from ..test_base import TestBase


# noinspection PyMethodMayBeStatic
class TestComponentState(TestBase):
    def test_component_state(self) -> None:
        with pytest.raises(TypeError):
            # noinspection PyTypeCher
            ComponentState(None)

    def test_switch_state(self) -> None:
        """
            Test that switch state is correctly initialized and that behavior
            implemented in the parent ComponentState class is as expected
        """
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
        set_req = CommandReq(Switch.SET_ADDRESS, 1)
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
        out_req = CommandReq(Switch.OUT, 1)
        ss.update(out_req)
        assert ss.last_command == out_req
        assert ss.last_updated is not None
        assert ss.last_updated >= last_updated
        last_updated = ss.last_updated
        assert ss.address == 1
        assert ss.state == Switch.OUT
        assert ss.is_known is True
        assert ss.is_out is True
        assert ss.is_through is False

        # create a "switch thrown to through" request
        thru_req = CommandReq(Switch.THROUGH, 1)
        ss.update(thru_req)
        assert ss.last_command == thru_req
        assert ss.last_updated is not None
        assert ss.last_updated >= last_updated
        last_updated = ss.last_updated
        assert ss.address == 1
        assert ss.state == Switch.THROUGH
        assert ss.is_known is True
        assert ss.is_out is False
        assert ss.is_through is True

        # update with another "set address" request, state should be unchanged
        ss.update(set_req)
        assert ss.last_command == set_req
        assert ss.last_updated is not None
        assert ss.last_updated >= last_updated
        last_updated = ss.last_updated
        assert ss.address == 1
        assert ss.state == Switch.THROUGH
        assert ss.is_known is True
        assert ss.is_out is False
        assert ss.is_through is True

        # throw switch out and check state is as expected
        ss.update(out_req)
        assert ss.last_command == out_req
        assert ss.last_updated is not None
        assert ss.last_updated >= last_updated
        assert ss.address == 1
        assert ss.state == Switch.OUT
        assert ss.is_known is True
        assert ss.is_out is True
        assert ss.is_through is False

        # verify address can not be modified once set
        thru_req = CommandReq(Switch.THROUGH, 2)
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
        assert ss.state == Switch.OUT
        assert ss.is_known is True
        assert ss.is_out is True
        assert ss.is_through is False

    def test_accessory_state(self) -> None:
        """
            Test that AccessoryState is correctly initialized and that behavior specific
            to it is handled correctly.
        """
        acc_state = AccessoryState()
        assert acc_state is not None
        assert acc_state.scope == CommandScope.ACC
        assert acc_state.address is None
        assert acc_state.last_command is None
        assert acc_state.last_updated is None
        assert acc_state.aux_state is None
        assert acc_state.aux1_state is None
        assert acc_state.aux2_state is None
        assert acc_state.is_known is False
        assert acc_state.value is None

        # assert construction with scope Acc succeeds
        acc_state = AccessoryState(CommandScope.ACC)
        assert acc_state is not None
        assert acc_state.scope == CommandScope.ACC

        # assert construction with any other scope fails
        for scope in CommandScope:
            if scope == CommandScope.ACC:
                continue
            with pytest.raises(ValueError):
                # noinspection PyTypeChecker
                AccessoryState(scope)

        # assert calling update with a valid request succeeds
        set_req = CommandReq(Acc.SET_ADDRESS, 5)
        assert set_req is not None
        assert set_req.scope == CommandScope.ACC
        assert set_req.address == 5

        # now call update
        acc_state.update(set_req)
        assert acc_state.last_command == set_req
        assert acc_state.last_updated is not None
        last_updated = acc_state.last_updated
        assert acc_state.address == 5

        # states should still be unknown
        assert acc_state.aux_state is None
        assert acc_state.aux1_state is None
        assert acc_state.aux2_state is None
        assert acc_state.is_known is False

        # Send Aux1 Opt1 (Aux 1 btn) this should set state
        aux1_opt1_req = CommandReq(Acc.AUX1_OPTION_ONE, 5)
        acc_state.update(aux1_opt1_req)
        assert acc_state.aux_state == Acc.AUX1_OPTION_ONE
        assert acc_state.is_aux_on is True
        assert acc_state.is_aux_off is False
        assert acc_state.aux1_state == Acc.AUX1_OPTION_ONE
        assert acc_state.aux2_state is None
        assert acc_state.value is None
        assert acc_state.is_known is True
        assert acc_state.last_updated >= last_updated
        last_updated = acc_state.last_updated

        # send a numeric command
        aux1_num_req = CommandReq(Acc.NUMERIC, 5, 6)
        acc_state.update(aux1_num_req)
        assert acc_state.aux_state == Acc.AUX1_OPTION_ONE
        assert acc_state.is_aux_on is True
        assert acc_state.is_aux_off is False
        assert acc_state.aux1_state == Acc.AUX1_OPTION_ONE
        assert acc_state.aux2_state is None
        assert acc_state.value == 6
        assert acc_state.is_known is True
        assert acc_state.last_updated >= last_updated
        last_updated = acc_state.last_updated

        # send a halt command, it should turn Aux off
        halt_req = CommandReq(TMCC1HaltCommandDef.HALT, 1)
        acc_state.update(halt_req)
        assert acc_state.aux_state == Acc.AUX2_OPTION_ONE
        assert acc_state.is_aux_on is False
        assert acc_state.is_aux_off is True
        assert acc_state.aux1_state == Acc.AUX1_OFF
        assert acc_state.aux2_state == Acc.AUX2_OFF
        assert acc_state.value is None
        assert acc_state.is_known is True
        assert acc_state.last_updated >= last_updated

        # turn Aux back on, then off
        acc_state.update(aux1_opt1_req)
        assert acc_state.aux_state == Acc.AUX1_OPTION_ONE
        assert acc_state.is_aux_on is True
        assert acc_state.is_aux_off is False
        assert acc_state.aux1_state == Acc.AUX1_OPTION_ONE
        assert acc_state.aux2_state is Acc.AUX2_OFF
        assert acc_state.value is None
        assert acc_state.is_known is True

        aux2_opt1_req = CommandReq(Acc.AUX2_OPTION_ONE, 5)
        acc_state.update(aux2_opt1_req)
        assert acc_state.aux_state == Acc.AUX2_OPTION_ONE
        assert acc_state.is_aux_on is False
        assert acc_state.is_aux_off is True
        assert acc_state.aux1_state == Acc.AUX1_OPTION_ONE
        assert acc_state.aux2_state is Acc.AUX2_OPTION_ONE
        assert acc_state.value is None
        assert acc_state.is_known is True

    def test_engine_state(self) -> None:
        """
            Test that EngineState is correctly initialized and that behavior specific
            to it is handled correctly.
        """
        eng_state = EngineState()
        assert eng_state is not None
        assert eng_state.scope == CommandScope.ENGINE
        assert eng_state.address is None
        assert eng_state.last_command is None
        assert eng_state.last_updated is None

        # assert construction with scope Acc succeeds
        eng_state = EngineState(CommandScope.ENGINE)
        assert eng_state is not None
        assert eng_state.scope == CommandScope.ENGINE

        # assert construction with any other scope fails
        for scope in CommandScope:
            if scope in [CommandScope.ENGINE, CommandScope.TRAIN]:
                continue
            with pytest.raises(ValueError):
                # noinspection PyTypeChecker
                EngineState(scope)

        # TODO: add tests once Engine State is defined

    def test_train_state(self) -> None:
        """
            Test that TrainState is correctly initialized and that behavior specific
            to it is handled correctly.
        """
        train_state = TrainState()
        assert train_state is not None
        assert train_state.scope == CommandScope.TRAIN
        assert train_state.address is None
        assert train_state.last_command is None
        assert train_state.last_updated is None

        # assert construction with scope Acc succeeds
        train_state = EngineState(CommandScope.TRAIN)
        assert train_state is not None
        assert train_state.scope == CommandScope.TRAIN

        train_state = TrainState(CommandScope.TRAIN)
        assert train_state is not None
        assert train_state.scope == CommandScope.TRAIN

        # assert construction with any other scope fails
        for scope in CommandScope:
            if scope == CommandScope.TRAIN:
                continue
            with pytest.raises(ValueError):
                # noinspection PyTypeChecker
                TrainState(scope)

        # TODO: add tests once Engine State is defined

    def test_system_state_dict(self) -> None:
        """
            SystemStateDict is used by the PyTrain cli to maintain a cache of engine, train,
            switch, and accessory state, as determined by the TMCC command stream it receives
            via publish/subscribe in the CommandListener class.
        """
        ss_dict = SystemStateDict()
        assert ss_dict is not None
        assert isinstance(ss_dict, defaultdict)
        assert isinstance(ss_dict, dict)
        assert len(ss_dict) == 0
        assert len(ss_dict.keys()) == 0
        assert len(ss_dict.values()) == 0

        # keys are instances of a subset of CommandScope
        for key in [CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.SWITCH, CommandScope.ACC]:
            assert key not in ss_dict
            value = ss_dict[key]
            assert key in ss_dict
            assert value.scope == key
            assert value is not None
            assert ss_dict[key] == value  # identical keys should return same values
            assert isinstance(value, ComponentStateDict)

        # we should have an entry for each of the 4 scopes and that the entry is an empty
        # ComponentStateDict with the correct scope
        for key in [CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.SWITCH, CommandScope.ACC]:
            assert key in ss_dict
            assert isinstance(ss_dict[key], ComponentStateDict)
            assert len(ss_dict[key]) == 0
            assert ss_dict[key] is not None
            assert ss_dict[key].scope == key

        # should not be able to add other keys
        with pytest.raises(KeyError, match="Invalid scope key: 123"):
            _ = ss_dict[123]

        # including CommandScopes other than the 4 above
        for key in CommandScope:
            if key in [CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.SWITCH, CommandScope.ACC]:
                continue
            with pytest.raises(KeyError, match=f"Invalid scope key: {key}"):
                _ = ss_dict[key]

    def test_component_state_dict(self) -> None:
        """
            ComponentStateDict saves system state for engines, trains, switches, and accessories
            as determined by the TMCC command stream. CommandScope-appropriate dicts are
            constructed by SystemStateDict as needed, using the defailtdict mechanism.

            ComponentStateDict keys themselves are ints between 1 and 99 inclusive.
        """
        # test that all four types of ComponentStateDicts are built
        for scope in [CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.SWITCH, CommandScope.ACC]:
            cs_dict = ComponentStateDict(scope)
            assert isinstance(cs_dict, ComponentStateDict)
            assert cs_dict.scope == scope
            value = cs_dict[1]
            assert value is not None
            assert isinstance(value, ComponentState)
            assert value.scope == scope

        # verify we cannot construct a dict from an invalid scope
        for key in CommandScope:
            if key in [CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.SWITCH, CommandScope.ACC]:
                continue
            with pytest.raises(ValueError, match=f"Invalid scope: {key}"):
                ComponentStateDict(key)

        # verify dicts allow keys to be inserted
        for scope in [CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.SWITCH, CommandScope.ACC]:
            cs_dict = ComponentStateDict(scope)
            for key in range(1, 99 + 1):
                assert key not in cs_dict
                value = cs_dict[key]
                assert key in cs_dict
                assert value.scope == scope
                assert isinstance(value, ComponentState)
                assert value.address == key
                assert value.last_command is None
                assert value.last_updated is None

        # verify invalid keys not allowed
        for scope in [CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.SWITCH, CommandScope.ACC]:
            cs_dict = ComponentStateDict(scope)
            for key in [-4, 0, "abc", 100, CommandScope.TRAIN]:
                assert key not in cs_dict
                with pytest.raises(KeyError, match=f"Invalid ID: {key}"):
                    _ = cs_dict[key]
