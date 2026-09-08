import pytest

from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_state import EngineState
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import DEFAULT_ADDRESS, CommandScope
from src.pytrain.protocol.multibyte.multibyte_constants import (
    TMCC2EngineCommandEnumEx,
    TMCC2RailSoundsDialogControl,
)
from src.pytrain.protocol.sequence.ramp_speed_req import RampSpeedDialogReq, RampSpeedReq, RampSpeedReqBase
from src.pytrain.protocol.sequence.sequence_constants import SequenceCommandEnum
from src.pytrain.protocol.sequence.sequence_req import SequenceReq
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, tmcc2_speed_to_rpm

from ...test_base import TestBase


class StubEngineState(EngineState):
    """
    A real EngineState subclass, so the facade's isinstance check holds, with only the
    handful of values it reads supplied and ramp_to recorded rather than performed.
    """

    # noinspection PyMissingConstructor
    def __init__(
        self,
        *,
        speed: int | None = 0,
        is_legacy: bool = True,
        tmcc_id: int = 12,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        self._stub_speed = speed
        self._stub_legacy = is_legacy
        self._scope = scope
        self._address = tmcc_id
        self.ramp_calls: list[tuple[int, bool]] = []

    @property
    def speed(self) -> int:
        # mirrors EngineState.speed, which is annotated -> int and returns None when
        # comp_data has not arrived
        # noinspection PyTypeChecker
        return self._stub_speed

    @property
    def is_legacy(self) -> bool:
        return self._stub_legacy

    @property
    def speed_max(self) -> int:
        return 199 if self._stub_legacy else 31

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def address(self) -> int:
        return self._address

    def ramp_to(self, speed: int, *, dialog: bool = False):
        self.ramp_calls.append((speed, dialog))
        return None


def install_state(monkeypatch, state) -> None:
    monkeypatch.setattr(ComponentStateStore, "get_state", staticmethod(lambda *_a, **_kw: state))


def enums(req: SequenceReq) -> list:
    return [sr.request.command for sr in req.requests]


# PyArgumentList / PyNoneFunctionAssignment: imported through the src.pytrain.* path,
# RampSpeedReq and RampSpeedDialogReq resolve as functions returning None, so every
# construction below is flagged twice over. They are ordinary classes, and
# gui/controller/engine_gui.py builds both with the same arguments and lints clean.
# noinspection PyMethodMayBeStatic,PyArgumentList,PyNoneFunctionAssignment
class TestRampSpeedReq(TestBase):
    #
    # registration and dispatch
    #
    def test_new_sequence_enums_exist(self):
        assert SequenceCommandEnum.by_name("RAMP_SPEED_SEQ") is SequenceCommandEnum.RAMP_SPEED_SEQ
        assert SequenceCommandEnum.by_name("RAMP_SPEED_DIALOG_SEQ") is SequenceCommandEnum.RAMP_SPEED_DIALOG_SEQ
        assert SequenceCommandEnum.RAMP_SPEED_SEQ.value.data_max == 199
        assert SequenceCommandEnum.RAMP_SPEED_DIALOG_SEQ.value.data_max == 199

    def test_new_sequence_enums_do_not_collide(self):
        bits = [e.value.bits for e in SequenceCommandEnum]
        assert len(bits) == len(set(bits))
        assert SequenceCommandEnum.RAMP_SPEED_SEQ.value.bits == 12
        assert SequenceCommandEnum.RAMP_SPEED_DIALOG_SEQ.value.bits == 13

    def test_command_classes_are_registered(self):
        assert SequenceCommandEnum.RAMP_SPEED_SEQ.value.cmd_class is RampSpeedReq
        assert SequenceCommandEnum.RAMP_SPEED_DIALOG_SEQ.value.cmd_class is RampSpeedDialogReq

    @pytest.mark.parametrize(
        "command, cls",
        [
            (SequenceCommandEnum.RAMP_SPEED_SEQ, RampSpeedReq),
            (SequenceCommandEnum.RAMP_SPEED_DIALOG_SEQ, RampSpeedDialogReq),
        ],
    )
    def test_sequence_req_build_dispatches_to_the_facade(self, monkeypatch, command, cls):
        install_state(monkeypatch, StubEngineState())
        req = SequenceReq.build(command, 12, 60, CommandScope.ENGINE)
        assert isinstance(req, cls)
        assert req.target_speed == 60

    #
    # emitted command list
    #
    def test_legacy_emits_only_a_target_speed(self, monkeypatch):
        install_state(monkeypatch, StubEngineState(is_legacy=True))
        req = RampSpeedReq(12, 60)
        assert enums(req) == [TMCC2EngineCommandEnumEx.TARGET_SPEED]
        assert req.requests[0].request.data == 60
        assert req.requests[0].request.address == 12
        assert req.is_ramp is True

    def test_tmcc1_emits_only_a_tmcc1_target_speed(self, monkeypatch):
        install_state(monkeypatch, StubEngineState(is_legacy=False))
        req = RampSpeedReq(12, 20, CommandScope.ENGINE)
        assert enums(req) == [TMCC1EngineCommandEnum.TARGET_SPEED]
        assert req.requests[0].request.data == 20

    def test_tmcc1_target_speed_is_sanitized_to_31(self, monkeypatch):
        install_state(monkeypatch, StubEngineState(is_legacy=False))
        req = RampSpeedReq(12, 199)
        assert req.target_speed == 31

    def test_train_scope_is_carried_through(self, monkeypatch):
        install_state(monkeypatch, StubEngineState(scope=CommandScope.TRAIN, tmcc_id=7))
        req = RampSpeedReq(7, 60, CommandScope.TRAIN)
        assert req.requests[0].request.scope == CommandScope.TRAIN

    def test_no_step_expansion(self, monkeypatch):
        """The whole point of the new facade: one announcement, no ramp steps, nothing scheduled."""
        install_state(monkeypatch, StubEngineState())
        req = RampSpeedReq(12, 199)
        assert len(req) == 1
        assert all(sr.delay in (None, 0) for sr in req.requests)
        assert TMCC2EngineCommandEnum.ABSOLUTE_SPEED not in enums(req)
        assert TMCC2EngineCommandEnum.DIESEL_RPM not in enums(req)
        assert TMCC2EngineCommandEnum.ENGINE_LABOR not in enums(req)

    #
    # dialog variant
    #
    def test_dialog_variant_adds_tower_and_engineer(self, monkeypatch):
        install_state(monkeypatch, StubEngineState())
        req = RampSpeedDialogReq(12, "limited")
        assert enums(req) == [
            TMCC2EngineCommandEnumEx.TARGET_SPEED,
            TMCC2RailSoundsDialogControl.TOWER_SPEED_LIMITED,
            TMCC2RailSoundsDialogControl.ENGINEER_SPEED_LIMITED,
        ]
        assert req.requests[-1].delay > 0

    def test_dialog_variant_on_tmcc1(self, monkeypatch):
        install_state(monkeypatch, StubEngineState(is_legacy=False))
        req = RampSpeedDialogReq(12, "restricted")
        assert enums(req)[0] == TMCC1EngineCommandEnum.TARGET_SPEED
        assert TMCC2RailSoundsDialogControl.TOWER_SPEED_RESTRICTED in enums(req)
        assert TMCC2RailSoundsDialogControl.ENGINEER_SPEED_RESTRICTED in enums(req)

    def test_rr_speed_string_resolves_to_a_speed(self, monkeypatch):
        install_state(monkeypatch, StubEngineState())
        req = RampSpeedReq(12, "restricted")
        assert isinstance(req.target_speed, int)
        assert 0 < req.target_speed < 199

    #
    # the _on_before_send handoff
    #
    def test_on_before_send_hands_the_target_to_the_state(self, monkeypatch):
        state = StubEngineState()
        install_state(monkeypatch, state)
        req = RampSpeedReq(12, 60)
        assert state.ramp_calls == []
        req._on_before_send()
        assert state.ramp_calls == [(60, False)]

    def test_dialog_variant_passes_the_dialog_flag(self, monkeypatch):
        state = StubEngineState()
        install_state(monkeypatch, state)
        RampSpeedDialogReq(12, "limited")._on_before_send()
        assert state.ramp_calls[0][1] is True

    def test_ramp_starts_before_any_bytes_go_out(self, monkeypatch):
        state = StubEngineState()
        install_state(monkeypatch, state)
        order: list[str] = []

        def ramp_to(speed: int, *, dialog: bool = False):
            order.append(f"ramp_to:{speed}:{dialog}")

        monkeypatch.setattr(state, "ramp_to", ramp_to)
        monkeypatch.setattr(CommandReq, "send", lambda req, *_a, **_kw: order.append(f"send:{req.command.name}"))

        RampSpeedReq(12, 60).send()
        assert order == ["ramp_to:60:False", "send:TARGET_SPEED"]

    #
    # no-state / DEFAULT_ADDRESS fallback
    #
    def test_no_state_falls_back_to_absolute_speed(self, monkeypatch):
        install_state(monkeypatch, None)
        req = RampSpeedReq(12, 20)
        assert enums(req) == [TMCC1EngineCommandEnum.ABSOLUTE_SPEED]
        assert req.is_ramp is False

    def test_state_without_a_speed_falls_back(self, monkeypatch):
        state = StubEngineState(speed=None)
        install_state(monkeypatch, state)
        req = RampSpeedReq(12, 20)
        assert TMCC2EngineCommandEnum.ABSOLUTE_SPEED in enums(req)
        assert req.is_ramp is False
        req._on_before_send()
        assert state.ramp_calls == []

    def test_default_address_emits_both_generations_plus_rpm(self, monkeypatch):
        install_state(monkeypatch, None)
        req = RampSpeedReq(DEFAULT_ADDRESS, 60)
        assert enums(req) == [
            TMCC1EngineCommandEnum.ABSOLUTE_SPEED,
            TMCC2EngineCommandEnum.ABSOLUTE_SPEED,
            TMCC2EngineCommandEnum.DIESEL_RPM,
        ]
        assert req.requests[-1].request.data == tmcc2_speed_to_rpm(req.target_speed)
        assert req.is_ramp is False

    def test_fallback_sends_without_starting_a_ramp(self, monkeypatch):
        install_state(monkeypatch, None)
        sent: list[str] = []
        monkeypatch.setattr(CommandReq, "send", lambda req, *_a, **_kw: sent.append(req.command.name))
        RampSpeedReq(12, 20).send()
        assert sent == ["ABSOLUTE_SPEED"]

    #
    # the base class stays abstract-ish and untouched callers keep working
    #
    def test_base_is_not_registered(self):
        assert SequenceCommandEnum.RAMP_SPEED_SEQ.value.cmd_class is not RampSpeedReqBase

    def test_ramped_speed_req_is_still_registered(self):
        from src.pytrain.protocol.sequence.ramped_speed_req import RampedSpeedDialogReq, RampedSpeedReq

        assert SequenceCommandEnum.RAMPED_SPEED_SEQ.value.cmd_class is RampedSpeedReq
        assert SequenceCommandEnum.RAMPED_SPEED_DIALOG_SEQ.value.cmd_class is RampedSpeedDialogReq
