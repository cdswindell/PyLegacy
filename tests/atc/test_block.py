from types import SimpleNamespace
from unittest import mock

import src.pytrain.protocol.sequence.ramp_speed_req as ramp_speed_req
from src.pytrain.atc.block import Block
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.protocol.constants import CommandScope, Direction
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2_RESTRICTED_SPEED
from tests.test_base import TestBase


class RampRecorder:
    """Stands in for RampSpeedReq, recording the ramp a block asked for."""

    def __init__(self) -> None:
        self.built: list[tuple[int, int | str, CommandScope]] = []
        self.sent: list[tuple[int, int | str, CommandScope]] = []

    def __call__(self, tmcc_id: int, speed: int | str, scope: CommandScope):
        call = (tmcc_id, speed, scope)
        self.built.append(call)
        return SimpleNamespace(send=lambda: self.sent.append(call))


def block_holding_motive(speed: int, occupied_ahead: bool = True) -> Block:
    """A block with just the state slow_down and resume_speed read, and no dialogs."""
    block = Block.__new__(Block)
    block._dialog = False
    block._next_block = SimpleNamespace(is_occupied=occupied_ahead)
    block._current_motive = SimpleNamespace(is_legacy=True, speed=speed, scope=CommandScope.ENGINE, tmcc_id=12)
    block._original_speed = None
    return block


class TestBlock(TestBase):
    def test_create_block(self) -> None:
        with mock.patch.object(ComponentStateStore, "get_state") as mk_get_state:
            mk_get_state.return_value = None
            with mock.patch.object(Block, "broadcast_state") as mk_broadcast_state:
                b = Block(1, "tests block")
                assert mk_get_state.call_count == 2
                mk_broadcast_state.assert_called_once()
                assert b is not None
                assert b.block_id == 1
                assert b.name == "tests block"
                assert b.direction == Direction.L2R
                assert b.is_occupied is False
                assert b.occupied_by is None
                assert b.occupied_direction is None
                assert b.sensor_track is None
                assert b.switch is None
                assert b.next_block is None
                assert b.prev_block is None

    def test_slow_down_hands_the_restriction_to_the_threaded_ramp(self, monkeypatch) -> None:
        # The block slows a train through the threaded ramper, not the queued sequence,
        # so a stick move or a stop of its own can still take the throttle back.
        recorder = RampRecorder()
        monkeypatch.setattr(ramp_speed_req, "RampSpeedReq", recorder)
        block = block_holding_motive(TMCC2_RESTRICTED_SPEED + 20)

        block.slow_down()

        assert recorder.built == [(12, "restricted", CommandScope.ENGINE)]
        assert recorder.sent == recorder.built
        assert block._original_speed == TMCC2_RESTRICTED_SPEED + 20

    def test_slow_down_is_silent_at_or_below_the_restriction(self, monkeypatch) -> None:
        recorder = RampRecorder()
        monkeypatch.setattr(ramp_speed_req, "RampSpeedReq", recorder)
        block = block_holding_motive(TMCC2_RESTRICTED_SPEED)

        block.slow_down()

        assert recorder.built == []

    def test_resume_speed_hands_the_original_speed_to_the_threaded_ramp(self, monkeypatch) -> None:
        recorder = RampRecorder()
        monkeypatch.setattr(ramp_speed_req, "RampSpeedReq", recorder)
        block = block_holding_motive(TMCC2_RESTRICTED_SPEED + 20)
        block._original_speed = 90

        block.resume_speed()

        assert recorder.built == [(12, 90, CommandScope.ENGINE)]
        assert recorder.sent == recorder.built
