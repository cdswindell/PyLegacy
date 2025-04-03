from threading import Thread

from .. import ComponentStateStore
from ..db.component_state import EngineState
from ..protocol.constants import DEFAULT_ADDRESS, PROGRAM_NAME, CommandScope
from .i2c.oled import Oled, OledDevice


class EngineStatus(Thread):
    def __init__(
        self,
        tmcc_id: int | EngineState = DEFAULT_ADDRESS,
        scope: CommandScope = CommandScope.ENGINE,
        rows: int = 4,
        cols: int = 20,
        address: int = 0x3C,
        oled_device: OledDevice | str = OledDevice.ssd1309,
    ) -> None:
        super().__init__(daemon=False, name=f"{PROGRAM_NAME} Engine Status Oled")
        self._oled = Oled(rows, cols, address, oled_device, auto_update=False)
        if isinstance(tmcc_id, EngineState):
            self._monitored_state = tmcc_id
            self._tmcc_id = tmcc_id.address
            self._scope = tmcc_id.scope
        elif isinstance(tmcc_id, int) and 1 <= tmcc_id <= 9999 and scope in [CommandScope.ENGINE, CommandScope.TRAIN]:
            self._tmcc_id = tmcc_id
            self._scope = scope
            if tmcc_id != 99:
                self._monitored_state = ComponentStateStore.get_state(scope, tmcc_id)
            else:
                self._monitored_state = None
        else:
            raise ValueError(f"Invalid tmcc_id: {tmcc_id} or scope: {scope}")

    @property
    def oled(self) -> Oled:
        return self._oled

    @property
    def tmcc_id(self) -> int:
        return self._tmcc_id

    @property
    def scope(self) -> CommandScope:
        return self._scope
