from threading import Thread, Lock
from time import sleep
from typing import List, Callable

from .engine_controller import EngineController
from .keypad import Keypad
from .lcd import Lcd
from ..db.component_state import ComponentState
from ..protocol.constants import PROGRAM_NAME, CommandScope
from ..db.component_state_store import ComponentStateStore
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandDef
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef

COMMANDS_OF_INTEREST = {
    TMCC1EngineCommandDef.ABSOLUTE_SPEED,
    TMCC1EngineCommandDef.FORWARD_DIRECTION,
    TMCC1EngineCommandDef.REVERSE_DIRECTION,
    TMCC1EngineCommandDef.NUMERIC,
    TMCC2EngineCommandDef.ABSOLUTE_SPEED,
    TMCC2EngineCommandDef.FORWARD_DIRECTION,
    TMCC2EngineCommandDef.REVERSE_DIRECTION,
    TMCC2EngineCommandDef.DIESEL_RPM,
    TMCC2EngineCommandDef.NUMERIC,
    TMCC2EngineCommandDef.MOMENTUM,
    TMCC2EngineCommandDef.MOMENTUM_LOW,
    TMCC2EngineCommandDef.MOMENTUM_MEDIUM,
    TMCC2EngineCommandDef.MOMENTUM_HIGH,
    TMCC2EngineCommandDef.TRAIN_BRAKE,
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
        self._lock = Lock()
        self._lcd = Lcd(address=lcd_address, rows=lcd_rows, cols=lcd_cols)
        self._keypad = Keypad(row_pins, column_pins)
        self._key_queue = self._keypad.key_queue
        self._last_listener = None
        self._state_store = ComponentStateStore.build()
        self._state = None
        self._state_watcher = None
        self._scope = CommandScope.ENGINE
        self._tmcc_id = None
        self._last_scope = None
        self._last_tmcc_id = None
        self._railroad = None
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

    def monitor_state_updates(self):
        if self._state_watcher:
            self._state_watcher.shutdown()
        self._state_watcher = StateWatcher(self._state, self.refresh_display)

    def cache_engine(self):
        if self._tmcc_id != self._last_tmcc_id:
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
        self._tmcc_id = self._state = None
        self._key_queue.reset()
        self.update_display()

    def update_engine(self, engine_id: str | int):
        tmcc_id = int(engine_id)
        if self._tmcc_id is not None and tmcc_id != self._tmcc_id:
            self.cache_engine()
        self._tmcc_id = tmcc_id
        self._state = self._state_store.get_state(self._scope, tmcc_id)
        if self._engine_controller:
            self._engine_controller.update(tmcc_id, self._scope)
        self.monitor_state_updates()
        self._key_queue.reset()
        self.update_display()

    def refresh_display(self) -> None:
        self.update_display(clear_display=False)

    def update_display(self, clear_display: bool = True) -> None:
        with self._lock:
            self._lcd.clear_frame_buffer()
            if self._state is not None:
                row = self._state.road_name if self._state.road_name else "No Information"
                if self._state.road_number:
                    row += f" #{self._state.road_number}".rjust(self._lcd.cols - len(row), " ")
            else:
                row = self.railroad
            self._lcd.add(row)

            row = f"{self._scope.label}: "
            tmcc_id_pos = len(row)
            if self._tmcc_id is not None:
                row += f"{self._tmcc_id:04}"
                if self._state:
                    if self._state.control_type is not None:
                        row += f" {self._state.control_type_label}"

            self._lcd.add(row)
            if self._state is not None:
                if self._lcd.rows > 2:
                    row = f"Speed: {self._state.speed:03} "
                    row += self._state.direction_label
                    self._lcd.add(row)
                if self._lcd.rows > 3:
                    row = f"RPM: {self._state.rpm_label} "
                    row += f"Mom: {self._state.momentum_label} "
                    row += f"TB: {self._state.train_brake_label} "
                    self._lcd.add(row)
            self._lcd.write_frame_buffer(clear_display)
            if self._tmcc_id is None:
                self._lcd.cursor_pos = (1, tmcc_id_pos)

    @property
    def railroad(self) -> str:
        if self._railroad is None:
            base_state = self._state_store.get_state(CommandScope.BASE, 0, False)
            if base_state and base_state.name:
                self._railroad = base_state.base_name.capitalize()
        return self._railroad if self._railroad is not None else "Lionel Lines"

    def reset(self) -> None:
        self._is_running = False
        self._key_queue.reset()
        self._lcd.close(True)
        self._keypad.close()
        if self._state_watcher:
            self._state_watcher.shutdown()

    def close(self) -> None:
        self.reset()


class StateWatcher(Thread):
    def __init__(self, state: ComponentState, action: Callable) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} State Watcher {state.scope.label} {state.address}")
        self._state = state
        self._action = action
        self._is_running = True
        self.start()

    def shutdown(self) -> None:
        self._is_running = False
        with self._state.synchronizer:
            self._state.synchronizer.notify_all()

    def run(self) -> None:
        while self._state is not None and self._is_running:
            with self._state.synchronizer:
                self._state.synchronizer.wait()
                if self._is_running:
                    self._action()
