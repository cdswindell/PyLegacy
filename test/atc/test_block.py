from unittest import mock

from src.pytrain.atc.block import Block
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.protocol.constants import Direction
from test.test_base import TestBase


class TestBlock(TestBase):
    def test_create_block(self) -> None:
        with mock.patch.object(ComponentStateStore, "get_state") as mk_get_state:
            mk_get_state.return_value = None
            with mock.patch.object(Block, "broadcast_state") as mk_broadcast_state:
                b = Block(1, "test block")
                assert mk_get_state.call_count == 2
                mk_broadcast_state.assert_called_once()
                assert b is not None
                assert b.block_id == 1
                assert b.name == "test block"
                assert b.direction == Direction.L2R
                assert b.is_occupied is False
                assert b.occupied_by is None
                assert b.occupied_direction is None
                assert b.sensor_track is None
                assert b.switch is None
                assert b.next_block is None
                assert b.prev_block is None
