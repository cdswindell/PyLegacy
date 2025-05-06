from __future__ import annotations

from threading import RLock, Thread
from time import sleep
from typing import List

from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.i2c.lcd import LCD_PCF8574_ADDRESS, Lcd
from ..protocol.constants import PROGRAM_NAME, CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from .engine_controller import EngineController
from .engine_status import EngineStatus
from .gpio_device import GpioDevice, P
from .keypad import KEYPAD_PCF8574_ADDRESS, Keypad, KeyPadI2C
from ..utils.unique_deque import UniqueDeque

COMMANDS_OF_INTEREST = {
    TMCC1EngineCommandEnum.ABSOLUTE_SPEED,
    TMCC1EngineCommandEnum.FORWARD_DIRECTION,
    TMCC1EngineCommandEnum.REVERSE_DIRECTION,
    TMCC1EngineCommandEnum.NUMERIC,
    TMCC2EngineCommandEnum.ABSOLUTE_SPEED,
    TMCC2EngineCommandEnum.FORWARD_DIRECTION,
    TMCC2EngineCommandEnum.REVERSE_DIRECTION,
    TMCC2EngineCommandEnum.DIESEL_RPM,
    TMCC2EngineCommandEnum.NUMERIC,
    TMCC2EngineCommandEnum.MOMENTUM,
    TMCC2EngineCommandEnum.MOMENTUM_LOW,
    TMCC2EngineCommandEnum.MOMENTUM_MEDIUM,
    TMCC2EngineCommandEnum.MOMENTUM_HIGH,
    TMCC2EngineCommandEnum.TRAIN_BRAKE,
}


class Controller(Thread, GpioDevice):
    @classmethod
    def build(
        cls,
        lcd_address: int = 0x27,
        lcd_rows: int = 4,
        lcd_cols: int = 20,
        is_lcd: bool = False,
        oled_address: int = 0,
        oled_device="ssd1362",
        is_oled: bool = True,
        keypad_address: int | None = KEYPAD_PCF8574_ADDRESS,
        row_pins: List[int | str] = None,
        column_pins: List[int | str] = None,
        base_online_pin: P = None,
        base_offline_pin: P = None,
        base_cathode: bool = True,
        base_ping_freq: int = 5,
        speed_pins: List[int | str] = None,
        halt_pin: P = None,
        reset_pin: P = None,
        fwd_pin: P = None,
        rev_pin: P = None,
        front_coupler_pin: P = None,
        rear_coupler_pin: P = None,
        start_up_pin: P = None,
        shutdown_pin: P = None,
        boost_pin: P = None,
        brake_pin: P = None,
        bell_pin: P = None,
        horn_pin: P = None,
        rpm_up_pin: P = None,
        rpm_down_pin: P = None,
        labor_up_pin: P = None,
        labor_down_pin: P = None,
        vol_up_pin: P = None,
        vol_down_pin: P = None,
        smoke_on_pin: P = None,
        smoke_off_pin: P = None,
        tower_dialog_pin: P = None,
        engr_dialog_pin: P = None,
        aux1_pin: P = None,
        aux2_pin: P = None,
        aux3_pin: P = None,
        stop_immediate_pin: P = None,
        i2c_adc_address: int = 0x48,
        train_brake_chn: int = None,
        quilling_horn_chn: int = None,
        num_lasts: int = 4,
    ) -> Controller:
        if row_pins and column_pins:
            c = Controller(
                lcd_address=lcd_address,
                lcd_rows=lcd_rows,
                lcd_cols=lcd_cols,
                is_lcd=is_lcd,
                oled_address=oled_address,
                oled_device=oled_device,
                is_oled=is_oled,
                row_pins=row_pins,
                column_pins=column_pins,
                base_online_pin=base_online_pin,
                base_offline_pin=base_offline_pin,
                base_cathode=base_cathode,
                base_ping_freq=base_ping_freq,
                speed_pins=speed_pins,
                halt_pin=halt_pin,
                reset_pin=reset_pin,
                fwd_pin=fwd_pin,
                rev_pin=rev_pin,
                front_coupler_pin=front_coupler_pin,
                rear_coupler_pin=rear_coupler_pin,
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
                aux1_pin=aux1_pin,
                aux2_pin=aux2_pin,
                aux3_pin=aux3_pin,
                stop_immediate_pin=stop_immediate_pin,
                i2c_adc_address=i2c_adc_address,
                train_brake_chn=train_brake_chn,
                quilling_horn_chn=quilling_horn_chn,
                num_lasts=num_lasts,
            )
        else:
            c = ControllerI2C(
                lcd_address=lcd_address,
                lcd_rows=lcd_rows,
                lcd_cols=lcd_cols,
                is_lcd=is_lcd,
                oled_address=oled_address,
                oled_device=oled_device,
                is_oled=is_oled,
                keypad_address=keypad_address,
                base_online_pin=base_online_pin,
                base_offline_pin=base_offline_pin,
                base_cathode=base_cathode,
                base_ping_freq=base_ping_freq,
                speed_pins=speed_pins,
                halt_pin=halt_pin,
                reset_pin=reset_pin,
                fwd_pin=fwd_pin,
                rev_pin=rev_pin,
                front_coupler_pin=front_coupler_pin,
                rear_coupler_pin=rear_coupler_pin,
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
                aux1_pin=aux1_pin,
                aux2_pin=aux2_pin,
                aux3_pin=aux3_pin,
                stop_immediate_pin=stop_immediate_pin,
                i2c_adc_address=i2c_adc_address,
                train_brake_chn=train_brake_chn,
                quilling_horn_chn=quilling_horn_chn,
                num_lasts=num_lasts,
            )
        return c

    def __init__(
        self,
        row_pins: List[P] = None,
        column_pins: List[P] = None,
        speed_pins: List[P] = None,
        halt_pin: P = None,
        reset_pin: P = None,
        fwd_pin: P = None,
        rev_pin: P = None,
        front_coupler_pin: P = None,
        rear_coupler_pin: P = None,
        start_up_pin: P = None,
        shutdown_pin: P = None,
        boost_pin: P = None,
        brake_pin: P = None,
        bell_pin: P = None,
        horn_pin: P = None,
        rpm_up_pin: P = None,
        rpm_down_pin: P = None,
        labor_up_pin: P = None,
        labor_down_pin: P = None,
        vol_up_pin: P = None,
        vol_down_pin: P = None,
        smoke_on_pin: P = None,
        smoke_off_pin: P = None,
        tower_dialog_pin: P = None,
        engr_dialog_pin: P = None,
        aux1_pin: P = None,
        aux2_pin: P = None,
        aux3_pin: P = None,
        stop_immediate_pin: P = None,
        i2c_adc_address: int = 0x48,
        train_brake_chn: P = None,
        quilling_horn_chn: P = None,
        base_online_pin: P = None,
        base_offline_pin: P = None,
        base_cathode: bool = True,
        base_ping_freq: int = 5,
        lcd_address: int = LCD_PCF8574_ADDRESS,
        lcd_rows: int = 4,
        lcd_cols: int = 20,
        is_lcd: bool = False,
        oled_address: int = 0,
        oled_device="ssd1362",
        is_oled: bool = True,
        keypad: Keypad | KeyPadI2C = None,
        num_lasts: int = 3,
    ):
        self._lock = RLock()
        if is_lcd is True and is_oled is True:
            raise AttributeError("Must specify is_oled=True or is_lcd=True, not both")

        if is_lcd is True and lcd_address:
            self._lcd = Lcd(address=lcd_address, rows=lcd_rows, cols=lcd_cols)
        else:
            self._lcd = None
        if is_oled is True and oled_address is not None:
            self._status = EngineStatus(address=oled_address, device=oled_device)
        else:
            self._status = None

        if row_pins and column_pins:
            self._keypad = Keypad(row_pins, column_pins)
        else:
            self._keypad = keypad
        self._key_queue = self._keypad.key_queue
        self._last_listener = None
        self._state_store = ComponentStateStore.get()
        self._state = None
        self._scope = CommandScope.ENGINE
        self._tmcc_id = None
        self._railroad = None
        self._last_known_speed = None
        self._state_watcher = None
        self._last_motive = UniqueDeque[tuple[int, CommandScope]](maxlen=num_lasts)
        if speed_pins or fwd_pin or rev_pin or reset_pin:
            self._engine_controller = EngineController(
                speed_pin_1=speed_pins[0] if speed_pins and len(speed_pins) > 0 else None,
                speed_pin_2=speed_pins[1] if speed_pins and len(speed_pins) > 1 else None,
                reset_pin=reset_pin,
                halt_pin=halt_pin,
                fwd_pin=fwd_pin,
                rev_pin=rev_pin,
                front_coupler_pin=front_coupler_pin,
                rear_coupler_pin=rear_coupler_pin,
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
                aux1_pin=aux1_pin,
                aux2_pin=aux2_pin,
                aux3_pin=aux3_pin,
                stop_immediate_pin=stop_immediate_pin,
                i2c_adc_address=i2c_adc_address,
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
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Controller")
        if self._sync_state and self._sync_state.is_synchronized:
            self._sync_watcher = None
            self.on_sync()
        else:
            self.update_display()
            self._sync_watcher = StateWatcher(self._sync_state, self.on_sync)

    @property
    def engine_controller(self) -> EngineController:
        return self._engine_controller

    @property
    def is_synchronized(self) -> bool:
        return self._synchronized

    def run(self) -> None:
        while self._is_running:
            key = self._key_queue.wait_for_keypress(60)
            if self._key_queue.is_clear:
                self.process_clear_key()
            elif self._key_queue.is_eol:
                if self._key_queue.key_presses:
                    self.update_engine(self._key_queue.key_presses)
                else:
                    self._key_queue.reset()
            elif key == "A":
                self.change_scope(CommandScope.ENGINE)
            elif key == "B":
                self.change_scope(CommandScope.TRAIN)
            elif key == "*":
                self.last_engine()
            elif key is not None:
                if self._key_queue.is_digit:
                    if self._engine_controller:
                        self._engine_controller.on_numeric(key)
                    self._key_queue.reset()
                else:
                    if self._status:
                        self._status.display.write(str(key))
                        if len(self._key_queue) >= 4:
                            self.update_engine(self._key_queue.key_presses)
                        else:
                            self._status.display.refresh_display()
                    if self._lcd:
                        self._lcd.print(key)
            sleep(0.1)

    def monitor_state_updates(self):
        if self._state_watcher:
            self._state_watcher.shutdown()
            self._state_watcher = None
        if self._state:
            self._state_watcher = StateWatcher(self._state, self.on_state_update)

    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
            self._synchronized = True
            self.update_display()
            self.start()
            self.cache_handler(self)

    def on_state_update(self) -> None:
        cur_speed = self._state.speed if self._state else None
        if cur_speed is not None and self._last_known_speed != cur_speed:
            self._last_known_speed = cur_speed
            if self._engine_controller:
                self._engine_controller.on_speed_changed(cur_speed)
        self.update_display(clear_display=False)

    def cache_engine(self) -> None:
        # don't cache an empty id
        if self._tmcc_id is None or self._state is None or self._tmcc_id != self._state.address:
            return
        # make sure there's a scope
        self._scope = self._scope if self._scope else CommandScope.ENGINE
        # push the most recent engine to the head of the queue (element 0)
        self._last_motive.push((self._tmcc_id, self._scope))

    def last_engine(self):
        if len(self._last_motive):
            # get the item at the head of the list
            if self._tmcc_id is None or self._state is None:
                self._tmcc_id = self._last_motive[0][0]
                self._scope = self._last_motive[0][1]
                self._last_motive.rotate(-1)
            else:
                if self._tmcc_id == self._last_motive[0][0] and self._scope == self._last_motive[0][1]:
                    # if the top of the stack is this engine, try the next one
                    self._last_motive.rotate(-1)
                # else:
                #     # otherwise, save the current engine as the second one in the queue
                #     last_motive = self._last_motive.popleft()
                #     self._last_motive.push((self._tmcc_id, self._scope))
                #     self._last_motive.push(last_motive)
                self._tmcc_id = self._last_motive[0][0]
                self._scope = self._last_motive[0][1]
            self.update_engine(self._tmcc_id)

    def change_scope(self, scope: CommandScope) -> None:
        self.cache_engine()
        self._scope = scope
        self._tmcc_id = self._state = None
        self._key_queue.reset()
        if self._status:
            self._status.update_engine(self._tmcc_id, self._scope)
        self.update_display()

    def process_clear_key(self) -> None:
        self._key_queue.reset()
        if self._tmcc_id and self._state is None:
            # clear not found engine/train
            self._tmcc_id = None
        self.update_engine(self._tmcc_id)
        if self._status:
            self._status.update_engine(self._tmcc_id, self._scope)
        self.update_display()

    def update_engine(self, engine_id: str | int | None):
        if engine_id:
            tmcc_id = int(engine_id)
            # allow use of road numbers; unless an engine supports 4-digit addressing,
            # road numbers are >= 100
            if tmcc_id > 99:
                state = ComponentStateStore.get_state(self._scope, tmcc_id, False)
                if state:
                    tmcc_id = state.address
            # is this engine defined?
            prev_state = self._state
            self._state = self._state_store.get_state(self._scope, tmcc_id, False)
            if self._state:
                if prev_state and self._tmcc_id is not None and tmcc_id != self._tmcc_id:
                    self.cache_engine()
                self._tmcc_id = tmcc_id
                if self._status:
                    self._status.update_engine(self._tmcc_id, self._scope)
                self._last_known_speed = self._state.speed if self._state else None
                if self._engine_controller:
                    self._engine_controller.update(tmcc_id, self._scope, self._state)
            else:
                self._tmcc_id = tmcc_id
            if self._status:
                self._status.update_engine(self._tmcc_id, self._scope)
            self.monitor_state_updates()
            self._key_queue.reset()
            self.cache_engine()
            self.update_display()

    def update_display(self, clear_display: bool = True) -> None:
        if self._lcd is None:
            return
        with self._lock:
            self._lcd.clear_frame_buffer()
            if self._state is not None:
                rname = self._state.road_name if self._state.road_name else "No Information"
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
                        if self._state.is_rpm:
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
        if self._lcd:
            self._lcd.close(True)
        if self._status:
            self._status.close()
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
        halt_pin: P = None,
        reset_pin: P = None,
        fwd_pin: P = None,
        rev_pin: P = None,
        front_coupler_pin: P = None,
        rear_coupler_pin: P = None,
        start_up_pin: P = None,
        shutdown_pin: P = None,
        boost_pin: P = None,
        brake_pin: P = None,
        bell_pin: P = None,
        horn_pin: P = None,
        rpm_up_pin: P = None,
        rpm_down_pin: P = None,
        labor_up_pin: P = None,
        labor_down_pin: P = None,
        vol_up_pin: P = None,
        vol_down_pin: P = None,
        smoke_on_pin: P = None,
        smoke_off_pin: P = None,
        tower_dialog_pin: P = None,
        engr_dialog_pin: P = None,
        aux1_pin: P = None,
        aux2_pin: P = None,
        aux3_pin: P = None,
        stop_immediate_pin: P = None,
        i2c_adc_address: int = 0x48,
        train_brake_chn: P = None,
        quilling_horn_chn: P = None,
        base_online_pin: P = None,
        base_offline_pin: P = None,
        base_cathode: bool = True,
        base_ping_freq: int = 5,
        lcd_address: int = 0x27,
        lcd_rows: int = 4,
        lcd_cols: int = 20,
        is_lcd: bool = False,
        oled_address: int = 0,
        oled_device="ssd1362",
        is_oled: bool = True,
        num_lasts: int = 3,
    ):
        keypad = KeyPadI2C(keypad_address)
        super().__init__(
            speed_pins=speed_pins,
            halt_pin=halt_pin,
            reset_pin=reset_pin,
            fwd_pin=fwd_pin,
            rev_pin=rev_pin,
            front_coupler_pin=front_coupler_pin,
            rear_coupler_pin=rear_coupler_pin,
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
            aux1_pin=aux1_pin,
            aux2_pin=aux2_pin,
            aux3_pin=aux3_pin,
            stop_immediate_pin=stop_immediate_pin,
            i2c_adc_address=i2c_adc_address,
            train_brake_chn=train_brake_chn,
            quilling_horn_chn=quilling_horn_chn,
            base_online_pin=base_online_pin,
            base_offline_pin=base_offline_pin,
            base_cathode=base_cathode,
            base_ping_freq=base_ping_freq,
            lcd_address=lcd_address,
            lcd_rows=lcd_rows,
            lcd_cols=lcd_cols,
            is_lcd=is_lcd,
            oled_address=oled_address,
            oled_device=oled_device,
            is_oled=is_oled,
            keypad=keypad,
            num_lasts=num_lasts,
        )
