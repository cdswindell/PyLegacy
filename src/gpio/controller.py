from threading import Thread, Lock
from time import sleep
from typing import List

from .engine_controller import EngineController
from .keypad import Keypad, KeyPadI2C, KEYPAD_PCF8574_ADDRESS
from .lcd import Lcd, LCD_PCF8574_ADDRESS
from ..db.state_watcher import StateWatcher
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
        row_pins: List[int | str] = None,
        column_pins: List[int | str] = None,
        speed_pins: List[int | str] = None,
        halt_pin: int | str = None,
        reset_pin: int | str = None,
        fwd_pin: int | str = None,
        rev_pin: int | str = None,
        start_up_pin: int | str = None,
        shutdown_pin: int | str = None,
        boost_pin: int | str = None,
        brake_pin: int | str = None,
        bell_pin: int | str = None,
        horn_pin: int | str = None,
        rpm_up_pin: int | str = None,
        rpm_down_pin: int | str = None,
        labor_up_pin: int | str = None,
        labor_down_pin: int | str = None,
        vol_up_pin: int | str = None,
        vol_down_pin: int | str = None,
        smoke_on_pin: int | str = None,
        smoke_off_pin: int | str = None,
        tower_dialog_pin: int | str = None,
        engr_dialog_pin: int | str = None,
        train_brake_chn: int | str = None,
        quilling_horn_chn: int | str = None,
        base_online_pin: int | str = None,
        base_offline_pin: int | str = None,
        base_cathode: bool = True,
        base_ping_freq: int = 5,
        lcd_address: int = LCD_PCF8574_ADDRESS,
        lcd_rows: int = 4,
        lcd_cols: int = 20,
        keypad: Keypad | KeyPadI2C = None,
    ):
        super().__init__(name=f"{PROGRAM_NAME} Controller", daemon=True)
        self._lock = Lock()
        self._lcd = Lcd(address=lcd_address, rows=lcd_rows, cols=lcd_cols)
        if row_pins and column_pins:
            self._keypad = Keypad(row_pins, column_pins)
        else:
            self._keypad = keypad
        self._key_queue = self._keypad.key_queue
        self._last_listener = None
        self._state_store = ComponentStateStore.build()
        self._state = None
        self._scope = CommandScope.ENGINE
        self._tmcc_id = None
        self._last_scope = None
        self._last_tmcc_id = None
        self._railroad = None
        self._last_known_speed = None
        self._state_watcher = None
        if speed_pins or fwd_pin or rev_pin or reset_pin:
            self._engine_controller = EngineController(
                speed_pin_1=speed_pins[0] if speed_pins and len(speed_pins) > 0 else None,
                speed_pin_2=speed_pins[1] if speed_pins and len(speed_pins) > 1 else None,
                reset_pin=reset_pin,
                halt_pin=halt_pin,
                fwd_pin=fwd_pin,
                rev_pin=rev_pin,
                start_up_pin=start_up_pin,
                shutdown_pin=shutdown_pin,
                boost_pin=boost_pin,
                brake_pin=brake_pin,
                bell_pin=bell_pin,
                horn_pin=horn_pin,
                rpm_up_pin=rpm_up_pin,
                rpm_down_pin=rpm_down_pin,
                labor_up_pin=labor_up_pin,
                labor_down_pin=labor_down_pin,
                vol_up_pin=vol_up_pin,
                vol_down_pin=vol_down_pin,
                smoke_on_pin=smoke_on_pin,
                smoke_off_pin=smoke_off_pin,
                tower_dialog_pin=tower_dialog_pin,
                engr_dialog_pin=engr_dialog_pin,
                train_brake_chn=train_brake_chn,
                quilling_horn_chn=quilling_horn_chn,
                base_online_pin=base_online_pin,
                base_offline_pin=base_offline_pin,
                base_cathode=base_cathode,
                base_ping_freq=base_ping_freq,
            )
        else:
            self._engine_controller = None
        self._is_running = True
        # check for state synchronization
        self._synchronized = False
        self._sync_state = self._state_store.get_state(CommandScope.SYNC, 99)
        if self._sync_state and self._sync_state.is_synchronized:
            self._sync_watcher = None
            self.on_sync()
        else:
            self._sync_watcher = StateWatcher(self._sync_state, self.on_sync)
            self.update_display()

    @property
    def engine_controller(self) -> EngineController:
        return self._engine_controller

    @property
    def is_synchronized(self) -> bool:
        return self._synchronized

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
        self._state_watcher = StateWatcher(self._state, self.on_state_update)

    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            self._synchronized = True
            self._lcd.clear()
            if self._sync_watcher:
                self._sync_watcher.shutdown()
            self.start()

    def on_state_update(self) -> None:
        cur_speed = self._state.speed if self._state else None
        if cur_speed is not None and self._last_known_speed != cur_speed:
            self._last_known_speed = cur_speed
            if self._engine_controller:
                self._engine_controller.on_speed_changed(cur_speed)
        self.refresh_display()

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
        # allow use of road numbers; unless an engine supports 4 digit addressing,
        # road numbers are >= 100
        if tmcc_id > 99:
            state = ComponentStateStore.get_state(self._scope, tmcc_id, False)
            if state:
                tmcc_id = state.address
        if self._tmcc_id is not None and tmcc_id != self._tmcc_id:
            self.cache_engine()
        self._tmcc_id = tmcc_id
        self._state = self._state_store.get_state(self._scope, tmcc_id)
        self._last_known_speed = self._state.speed if self._state else None
        if self._engine_controller:
            self._engine_controller.update(tmcc_id, self._scope, self._state)
        self.monitor_state_updates()
        self._key_queue.reset()
        self.update_display()

    def refresh_display(self) -> None:
        self.update_display(clear_display=False)

    def update_display(self, clear_display: bool = True) -> None:
        with self._lock:
            self._lcd.clear_frame_buffer()
            if self._state is not None:
                rname = self._state.road_name.title() if self._state.road_name else "No Information"
                rnum = f"#{self._state.road_number} " if self._state.road_number else ""
                row = f"{rnum}{rname}"
            else:
                row = self.railroad
            self._lcd.add(row)
            if self.is_synchronized:
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
                        row = f"Speed: {self._state.speed if self._state.speed is not None else 'N/A':03} "
                        row += self._state.direction_label
                        row += f" Ef: {self._state.labor_label:.2} "
                        # row += f"  {self._state.year if self._state.year else ''}"
                        self._lcd.add(row)
                    if self._lcd.rows > 3:
                        row = f"Mom: {self._state.momentum_label:.1} "
                        row += f"TB: {self._state.train_brake_label:.1} "
                        row += f"RPM: {self._state.rpm_label:.1}"
                        self._lcd.add(row)
            else:
                tmcc_id_pos = 0

            self._lcd.write_frame_buffer(clear_display)
            if self.is_synchronized and self._tmcc_id is None:
                self._lcd.cursor_pos = (1, tmcc_id_pos)

    @property
    def railroad(self) -> str:
        if self._railroad is None:
            base_state = self._state_store.get_state(CommandScope.BASE, 0, False)
            if base_state and base_state.base_name:
                self._railroad = base_state.base_name.title()
        return self._railroad if self._railroad is not None else "Loading Engine Roster..."

    def reset(self) -> None:
        self._is_running = False
        self._key_queue.reset()
        self._lcd.close(True)
        self._keypad.close()
        if self._state_watcher:
            self._state_watcher.shutdown()

    def close(self) -> None:
        self.reset()


class ControllerI2C(Controller):
    def __init__(
        self,
        keypad_address: int = KEYPAD_PCF8574_ADDRESS,
        speed_pins: List[int | str] = None,
        halt_pin: int | str = None,
        reset_pin: int | str = None,
        fwd_pin: int | str = None,
        rev_pin: int | str = None,
        start_up_pin: int | str = None,
        shutdown_pin: int | str = None,
        boost_pin: int | str = None,
        brake_pin: int | str = None,
        bell_pin: int | str = None,
        horn_pin: int | str = None,
        rpm_up_pin: int | str = None,
        rpm_down_pin: int | str = None,
        labor_up_pin: int | str = None,
        labor_down_pin: int | str = None,
        vol_up_pin: int | str = None,
        vol_down_pin: int | str = None,
        smoke_on_pin: int | str = None,
        smoke_off_pin: int | str = None,
        tower_dialog_pin: int | str = None,
        engr_dialog_pin: int | str = None,
        train_brake_chn: int | str = None,
        quilling_horn_chn: int | str = None,
        base_online_pin: int | str = None,
        base_offline_pin: int | str = None,
        base_cathode: bool = True,
        base_ping_freq: int = 5,
        lcd_address: int = 0x27,
        lcd_rows: int = 4,
        lcd_cols: int = 20,
    ):
        keypad = KeyPadI2C(keypad_address)
        super().__init__(
            speed_pins=speed_pins,
            halt_pin=halt_pin,
            reset_pin=reset_pin,
            fwd_pin=fwd_pin,
            rev_pin=rev_pin,
            start_up_pin=start_up_pin,
            shutdown_pin=shutdown_pin,
            boost_pin=boost_pin,
            brake_pin=brake_pin,
            bell_pin=bell_pin,
            horn_pin=horn_pin,
            rpm_up_pin=rpm_up_pin,
            rpm_down_pin=rpm_down_pin,
            labor_up_pin=labor_up_pin,
            labor_down_pin=labor_down_pin,
            vol_up_pin=vol_up_pin,
            vol_down_pin=vol_down_pin,
            smoke_on_pin=smoke_on_pin,
            smoke_off_pin=smoke_off_pin,
            tower_dialog_pin=tower_dialog_pin,
            engr_dialog_pin=engr_dialog_pin,
            train_brake_chn=train_brake_chn,
            quilling_horn_chn=quilling_horn_chn,
            base_online_pin=base_online_pin,
            base_offline_pin=base_offline_pin,
            base_cathode=base_cathode,
            base_ping_freq=base_ping_freq,
            lcd_address=lcd_address,
            lcd_rows=lcd_rows,
            lcd_cols=lcd_cols,
            keypad=keypad,
        )
