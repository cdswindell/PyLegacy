from threading import Thread
from time import sleep
from typing import List

from .engine_controller import EngineController
from .keypad import Keypad
from .lcd import Lcd
from ..comm.command_listener import CommandDispatcher
from ..pdi.pdi_req import PdiReq
from ..protocol.command_req import CommandReq
from ..protocol.constants import PROGRAM_NAME, CommandScope
from ..db.component_state_store import ComponentStateStore
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef
from ..utils.expiring_set import ExpiringSet

COMMANDS_OF_INTEREST = {
    TMCC2EngineCommandDef.ABSOLUTE_SPEED,
    TMCC2EngineCommandDef.FORWARD_DIRECTION,
    TMCC2EngineCommandDef.REVERSE_DIRECTION,
}


class Controller(Thread):
    def __init__(
        self,
        row_pins: List[int | str],
        column_pins: List[int | str],
        speed_pins: List[int | str] = None,
        halt_pin: int | str = None,
        reset_pin: int | str = None,
        fwd_pin: int | str = None,
        rev_pin: int | str = None,
        toggle_pin: int | str = None,
        start_up_pin: int | str = None,
        shutdown_pin: int | str = None,
        boost_pin: int | str = None,
        brake_pin: int | str = None,
        bell_pin: int | str = None,
        horn_pin: int | str = None,
        rpm_up_pin: int | str = None,
        rpm_down_pin: int | str = None,
        momentum_up_pin: int | str = None,
        momentum_down_pin: int | str = None,
        vol_up_pin: int | str = None,
        vol_down_pin: int | str = None,
        smoke_up_pin: int | str = None,
        smoke_down_pin: int | str = None,
        train_brake_chn: int | str = None,
        lcd_address: int = 0x27,
        lcd_rows: int = 4,
        lcd_cols: int = 20,
    ):
        super().__init__(name=f"{PROGRAM_NAME} Controller", daemon=True)
        self._lcd = Lcd(address=lcd_address, rows=lcd_rows, cols=lcd_cols)
        self._keypad = Keypad(row_pins, column_pins)
        self._key_queue = self._keypad.key_queue
        self._last_listener = None
        self._state = ComponentStateStore.build()
        self._tmcc_dispatcher = CommandDispatcher.get()
        self._scope = CommandScope.ENGINE
        self._tmcc_id = None
        self._last_scope = None
        self._last_tmcc_id = None
        self._filter = ExpiringSet(max_age_seconds=0.5)
        if speed_pins or fwd_pin or rev_pin or reset_pin:
            self._engine_controller = EngineController(
                speed_pin_1=speed_pins[0] if speed_pins and len(speed_pins) > 0 else None,
                speed_pin_2=speed_pins[1] if speed_pins and len(speed_pins) > 1 else None,
                reset_pin=reset_pin,
                halt_pin=halt_pin,
                fwd_pin=fwd_pin,
                rev_pin=rev_pin,
                toggle_pin=toggle_pin,
                start_up_pin=start_up_pin,
                shutdown_pin=shutdown_pin,
                boost_pin=boost_pin,
                brake_pin=brake_pin,
                bell_pin=bell_pin,
                horn_pin=horn_pin,
                rpm_up_pin=rpm_up_pin,
                rpm_down_pin=rpm_down_pin,
                momentum_up_pin=momentum_up_pin,
                momentum_down_pin=momentum_down_pin,
                vol_up_pin=vol_up_pin,
                vol_down_pin=vol_down_pin,
                smoke_up_pin=smoke_up_pin,
                smoke_down_pin=smoke_down_pin,
                train_brake_chn=train_brake_chn,
            )
        else:
            self._engine_controller = None
        self._is_running = True
        self.start()

    def __call__(self, cmd: CommandReq | PdiReq) -> None:
        """
        Callback specified in the Subscriber protocol used to send events to listeners
        """
        if isinstance(cmd, CommandReq):
            if cmd.command in COMMANDS_OF_INTEREST and cmd.address == self._tmcc_id:
                cmd_bytes = cmd.as_bytes
                if cmd_bytes not in self._filter:
                    print(cmd, cmd_bytes in self._filter, len(self._filter), self._filter)
                    self._filter.add(cmd_bytes)
                    self.update_display()

    @property
    def engine_controller(self) -> EngineController:
        return self._engine_controller

    def run(self) -> None:
        self.update_display()
        while self._is_running:
            key = self._key_queue.wait_for_keypress(60)
            if self._key_queue.is_clear:
                self.change_scope(self._scope)
            elif self._key_queue.is_eol:
                if self._key_queue.keypresses:
                    self.update_engine(self._key_queue.keypresses)
            elif key == "A":
                self.change_scope(CommandScope.ENGINE)
            elif key == "B":
                self.change_scope(CommandScope.TRAIN)
            elif key == "*":
                self.last_engine()
            elif key is not None:
                self._lcd.print(key)
            sleep(0.1)

    def cache_engine(self):
        if self._tmcc_id and self._scope:
            self._last_scope = self._scope
            self._last_tmcc_id = self._tmcc_id

    def last_engine(self):
        if self._last_scope and self._last_tmcc_id:
            tmp_scope = self._last_scope
            tmp_tmcc_id = self._last_tmcc_id
            self._last_scope = self._scope
            self._last_tmcc_id = self._tmcc_id
            self._scope = tmp_scope
            self._tmcc_id = tmp_tmcc_id
            self.update_engine(tmp_tmcc_id)

    def change_scope(self, scope: CommandScope) -> None:
        self.cache_engine()
        self._scope = scope
        self._tmcc_id = None
        self.update_display()
        self._key_queue.reset()

    def update_engine(self, engine_id: str | int):
        self.cache_engine()
        self._tmcc_id = tmcc_id = int(engine_id)
        if self._engine_controller:
            self._engine_controller.update(tmcc_id, self._scope)
        self.listen_for_updates(self._scope, tmcc_id)

        self.update_display()
        self._key_queue.reset()

    def update_display(self):
        self._lcd.clear()
        row = f"{self._scope.friendly}: "
        tmcc_id_pos = len(row)
        if self._tmcc_id is not None:
            row += f"{self._tmcc_id:04}"
            state = self._state.get_state(self._scope, self._tmcc_id)
            if state:
                if state.control_type is not None and self._lcd.cols > 16:
                    row += f" {state.control_type_label[0]}"
                if state.road_number:
                    rn = f"#{state.road_number}"
                    row += rn.rjust(self._lcd.cols - len(row), " ")
        else:
            state = None
        self._lcd.add(row)

        if state is not None:
            row = state.road_name if state.road_name else "No Information"
            self._lcd.add(row)
            if self._lcd.rows > 2:
                row = f"Speed: {state.speed:03} "
                row += state.direction_label
                self._lcd.add(row)
        self._lcd.write_frame_buffer()
        if self._tmcc_id is None:
            self._lcd.cursor_pos = (0, tmcc_id_pos)

    def reset(self) -> None:
        self._is_running = False
        self._key_queue.reset()
        self._lcd.close(True)
        self._keypad.close()

    def close(self) -> None:
        self.reset()

    def listen_for_updates(self, scope, tmcc_id):
        if self._last_listener == (scope, tmcc_id):
            return
        if self._last_listener:
            self._tmcc_dispatcher.unsubscribe(self, *self._last_listener)
        self._tmcc_dispatcher.listen_for(self, scope, tmcc_id)
        self._last_listener = (scope, tmcc_id)
