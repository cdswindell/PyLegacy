from __future__ import annotations

from .constants import PdiCommand, PDI_SOP, PDI_EOP
from .pdi_req import PdiReq
from ..atc.block import Block
from ..db.block_state import BlockState
from ..protocol.constants import CommandScope, Direction


class BlockReq(PdiReq):
    def __init__(
        self,
        data: bytes | Block | BlockState,
        pdi_command: PdiCommand = PdiCommand.BLOCK_RX,
    ) -> None:
        super().__init__(data, pdi_command)
        self._scope = CommandScope.BLOCK
        if isinstance(data, bytes):
            data_len = len(self._data)
            self._block_id = self._tmcc_id = self._data[1] if data_len > 0 else None
            self._prev_block_id = self._data[2] if data_len > 2 else None
            self._next_block_id = self._data[3] if data_len > 3 else None
            self._flags = self._data[4] if data_len > 4 else None
            self._sensor_track_id = self._data[5] if data_len > 5 else None
            self._switch_id = self._data[6] if data_len > 6 else None
            self._motive_id = int.from_bytes(self._data[7:9], byteorder="little") if data_len > 7 else None
            self._motive_scope = CommandScope.by_value(self._data[9]) if data_len > 9 else None
            self._motive_direction = Direction.by_value(self._data[10]) if data_len > 10 else None
            self._name = self.decode_text(self._data[11:44]) if data_len > 11 else None
            self._direction = Direction.L2R if (self.flags & 0x10 > 0) else Direction.R2L
        elif isinstance(data, Block):
            self._block_id = self._tmcc_id = data.block_id
            self._prev_block_id = data.prev_block.block_id if data.prev_block else None
            self._next_block_id = data.next_block.block_id if data.next_block else None
            self._sensor_track_id = data.sensor_track.address if data.sensor_track else None
            self._switch_id = data.switch.address if data.switch else None
            self._name = data.name
            self._direction = data.direction
            if data.occupied_by:
                self._motive_id = data.occupied_by.address
                self._motive_scope = data.occupied_by.scope
                self._motive_direction = data.occupied_direction
            else:
                self._motive_id = None
                self._motive_scope = None
                self._motive_direction = None
            flags = 0
            for i, flag in enumerate(
                [data.is_occupied, data.is_entered, data.is_slowed, data.is_stopped, data.is_left_to_right]
            ):
                flags |= (1 << i) if flag is True else 0
            self._flags = flags
        elif isinstance(data, BlockState):
            self._block_id = self._tmcc_id = data.block_id
            self._prev_block_id = data.prev_block.block_id if data.prev_block else None
            self._next_block_id = data.next_block.block_id if data.next_block else None
            self._sensor_track_id = data.sensor_track.address if data.sensor_track else None
            self._switch_id = data.switch.address if data.switch else None
            self._name = data.name
            self._direction = data.direction
            if data.occupied_by:
                self._motive_id = data.occupied_by.address
                self._motive_scope = data.occupied_by.scope
                self._motive_direction = data.occupied_direction
            else:
                self._motive_id = None
                self._motive_scope = None
                self._motive_direction = None
            self._flags = data.flags
        else:
            raise AttributeError(f"Unsupported argument: {data}")

    @property
    def payload(self) -> str | None:
        oc = f" Occupied: {self.is_occupied}"
        nm = f"  {self.name}" if self.name else ""
        return f"Block Id: {self.block_id}{nm}{oc} {self.packet}"

    @property
    def as_bytes(self) -> bytes:
        if self._original:
            return self._original
        byte_str = self.pdi_command.as_bytes
        byte_str += self.block_id.to_bytes(1, byteorder="big")
        byte_str += (self._prev_block_id if self._prev_block_id else 0).to_bytes(1, byteorder="big")
        byte_str += (self._next_block_id if self._next_block_id else 0).to_bytes(1, byteorder="big")
        byte_str += (self._flags if self._flags else 0).to_bytes(1, byteorder="big")
        byte_str += (self._sensor_track_id if self._sensor_track_id else 0).to_bytes(1, byteorder="big")
        byte_str += (self._switch_id if self._switch_id else 0).to_bytes(1, byteorder="big")
        byte_str += (self._motive_id if self._motive_id else 0).to_bytes(2, byteorder="little")
        byte_str += (self._motive_scope.value if self._motive_scope else 0).to_bytes(1, byteorder="big")
        byte_str += (self._motive_direction.value if self._motive_direction else 0).to_bytes(1, byteorder="big")
        byte_str += self.encode_text(self._name, 33)
        byte_str, checksum = self._calculate_checksum(byte_str)
        byte_str = PDI_SOP.to_bytes(1, byteorder="big") + byte_str
        byte_str += checksum
        byte_str += PDI_EOP.to_bytes(1, byteorder="big")
        return byte_str

    @property
    def block_id(self) -> int:
        return self._block_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def direction(self) -> Direction:
        return self._direction

    @property
    def prev_block_id(self) -> int:
        return self._prev_block_id

    @property
    def next_block_id(self) -> int:
        return self._next_block_id

    @property
    def sensor_track_id(self) -> int:
        return self._sensor_track_id

    @property
    def switch_id(self) -> int:
        return self._switch_id

    @property
    def motive_id(self) -> int:
        return self._motive_id

    @property
    def motive_scope(self) -> CommandScope:
        return self._motive_scope

    @property
    def motive_direction(self) -> Direction:
        return self._motive_direction

    @property
    def flags(self) -> int:
        return self._flags

    @property
    def is_occupied(self) -> bool:
        return self._flags & (1 << 0) != 0
