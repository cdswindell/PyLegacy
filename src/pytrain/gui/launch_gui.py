#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
import atexit
import logging
from threading import Condition, RLock, Thread
from time import sleep, time
from tkinter import RAISED

from guizero import App, Box, PushButton, Text

from ..comm.command_listener import CommandDispatcher
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum, TMCC1EngineCommandEnum
from ..utils.path_utils import find_file

log = logging.getLogger(__name__)


class LaunchGui(Thread):
    def __init__(self, tmcc_id: int = 39, track_id: int = None, width: int = None, height: int = None):
        # initialize guizero thread
        super().__init__(daemon=True, name=f"Pad {tmcc_id} GUI")
        self.tmcc_id = tmcc_id
        self.track_id = track_id
        if width is None or height is None:
            try:
                from tkinter import Tk

                root = Tk()
                self.width = root.winfo_screenwidth()
                self.height = root.winfo_screenheight()
                root.destroy()
            except Exception as e:
                log.exception("Error determining window size", exc_info=e)
        else:
            self.width = width
            self.height = height
        self.s_72 = self.scale(72, 0.7)
        self.s_16 = self.scale(16, 0.7)
        self._cv = Condition(RLock())

        self.launch_jpg = find_file("launch.jpg")
        self.abort_jpg = find_file("abort.jpg")
        self.siren_on = find_file("red_light.jpg")
        self.siren_off = find_file("red_light_off.jpg")
        self.on_button = find_file("on_button.jpg")
        self.off_button = find_file("off_button.jpg")
        self.left_arrow = find_file("left_arrow.jpg")
        self.right_arrow = find_file("right_arrow.jpg")
        self.engr_comm = find_file("walkie_talkie.png")
        self.tower_comm = find_file("tower.png")

        self.counter = None

        self.app = self.upper_box = self.lower_box = self.message = None
        self.launch = self.abort = self.pad = self.count = self.label = None
        self.gantry_box = self.siren_box = self.klaxon_box = self.lights_box = None
        self.power_button = self.lights_button = self.siren_button = self.klaxon_button = None
        self.gantry_rev = self.gantry_fwd = None
        self.comms_box = self.tower_comms = self.engr_comms = None

        self.track_on_req = CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, track_id) if track_id else None
        self.power_on_req = CommandReq(TMCC1EngineCommandEnum.START_UP_IMMEDIATE, tmcc_id)
        self.power_off_req = CommandReq(TMCC1EngineCommandEnum.SHUTDOWN_IMMEDIATE, tmcc_id)
        self.reset_req = CommandReq(TMCC1EngineCommandEnum.NUMERIC, tmcc_id, 0)
        self.launch_now_req = CommandReq(TMCC1EngineCommandEnum.FRONT_COUPLER, tmcc_id)
        self.abort_now_req = CommandReq(TMCC1EngineCommandEnum.NUMERIC, tmcc_id, 5)
        self.gantry_rev_req = CommandReq(TMCC1EngineCommandEnum.NUMERIC, tmcc_id, 6)
        self.gantry_fwd_req = CommandReq(TMCC1EngineCommandEnum.NUMERIC, tmcc_id, 3)
        self.lights_on_req = CommandReq(TMCC1EngineCommandEnum.AUX2_ON, tmcc_id)
        self.lights_off_req = CommandReq(TMCC1EngineCommandEnum.AUX2_OFF, tmcc_id)
        self.siren_req = CommandReq(TMCC1EngineCommandEnum.BLOW_HORN_ONE, tmcc_id)
        self.klaxon_req = CommandReq(TMCC1EngineCommandEnum.RING_BELL, tmcc_id)
        self.engr_comm_req = CommandReq(TMCC1EngineCommandEnum.NUMERIC, tmcc_id, 2)
        self.tower_comm_req = CommandReq(TMCC1EngineCommandEnum.NUMERIC, tmcc_id, 7)
        self.launch_15_req = CommandReq(TMCC1EngineCommandEnum.REAR_COUPLER, tmcc_id)
        self.launch_seq_act = CommandReq(TMCC1EngineCommandEnum.AUX1_OPTION_ONE, tmcc_id).as_action(duration=3.5)

        # listen for state changes
        self._dispatcher = CommandDispatcher.get()
        self._state_store = ComponentStateStore.get()
        self._synchronized = False
        self._sync_state = self._state_store.get_state(CommandScope.SYNC, 99)
        self._monitored_state = None
        self._last_cmd = None
        self._last_cmd_at = 0
        self._launch_seq_time_trigger = None
        self._is_countdown = False
        self._is_flashing = False
        self.started_up = False
        if self._sync_state and self._sync_state.is_synchronized is True:
            self._sync_watcher = None
            self.on_sync()
        else:
            self._sync_watcher = StateWatcher(self._sync_state, self.on_sync)
        self._is_closed = False
        atexit.register(self.close)

    def scale(self, value: int, factor: float = None) -> int:
        orig_value = value
        value = max(orig_value, int(value * self.width / 480))
        if factor is not None and self.width > 480:
            value = max(orig_value, int(factor * value))
        return value

    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True
            self._monitored_state = self._state_store.get_state(CommandScope.ENGINE, self.tmcc_id, False)
            if self._monitored_state is None:
                raise ValueError(f"No state found for tmcc_id: {self.tmcc_id}")
            # watch for external state changes
            StateWatcher(self._monitored_state, self.sync_gui_state)
            # start GUI
            self.start()
            # listen for state updates
            self._dispatcher.subscribe(self, CommandScope.ENGINE, self.tmcc_id)

    def close(self) -> None:
        with self._cv:
            if not self._is_closed:
                self._is_closed = True
                self.app.after(10, self.app.destroy)
                self.join()

    def reset(self):
        self.close()

    def sync_gui_state(self) -> None:
        if self._monitored_state:
            with self._cv:
                # power on?
                if self._monitored_state.is_started is True:
                    self.do_power_on()
                    # Lights on?
                    self.sync_pad_lights()
                else:
                    self.do_power_off()
                    self.set_lights_on_icon()

    def sync_pad_lights(self):
        with self._cv:
            if self._monitored_state.is_aux2 is True:
                self.set_lights_off_icon()
            else:
                self.set_lights_on_icon()

    def __call__(self, cmd: CommandReq) -> None:
        with self._cv:
            # handle launch sequence differently
            if cmd.command == TMCC1EngineCommandEnum.AUX1_OPTION_ONE:
                if self._launch_seq_time_trigger is None:
                    if self._last_cmd != cmd or (time() - self._last_cmd_at) > 5:
                        self._launch_seq_time_trigger = time()
                else:
                    if self._last_cmd == cmd and (time() - self._launch_seq_time_trigger) > 3.1:
                        if not self._is_countdown:
                            self.do_launch(76, detected=True)
                        self._launch_seq_time_trigger = None
                self._last_cmd = cmd
                self._last_cmd_at = time()
                return
            else:
                self._launch_seq_time_trigger = None
            if cmd != self._last_cmd or (time() - self._last_cmd_at) >= 1.0:
                self._last_cmd_at = time()
                if cmd.command == TMCC1EngineCommandEnum.NUMERIC:
                    if cmd.data in (3, 6):
                        # mark launch pad as on and lights as on
                        self.do_power_on()
                        self.sync_pad_lights()
                    elif cmd.data == 5:
                        self.set_lights_on_icon()
                        self.do_power_off()
                    elif cmd.data == 0:  # reset
                        self.do_klaxon_off()
                        if self._is_countdown:
                            self.do_abort(detected=True)
                        else:
                            # reset causes engine to start up, check for that state change here
                            self.sync_gui_state()
                elif self.is_active():
                    if cmd.command == TMCC1EngineCommandEnum.REAR_COUPLER:
                        self.do_power_on()
                        self.do_launch(15, detected=True, hold=False)
                    elif cmd.command == TMCC1EngineCommandEnum.AUX2_OPTION_ONE:
                        self.sync_pad_lights()
                    elif cmd.command == TMCC1EngineCommandEnum.AUX2_ON:
                        self.set_lights_off_icon()
                    elif cmd.command == TMCC1EngineCommandEnum.AUX2_OFF:
                        self.set_lights_on_icon()
                    elif cmd.command == TMCC1EngineCommandEnum.BLOW_HORN_ONE:
                        self.siren_sounded()
                    elif cmd.command == TMCC1EngineCommandEnum.RING_BELL:
                        self.klaxon_sounded()
            # remember last command
            self._last_cmd = cmd

    def is_active(self) -> bool:
        return True if self._monitored_state and self._monitored_state.is_started is True else False

    def run(self):
        GpioHandler.cache_handler(self)
        self.app = app = App(title="Launch Pad", width=self.width, height=self.height)
        app.full_screen = True
        app.when_closed = self.close
        self.upper_box = upper_box = Box(app, layout="grid", border=False)

        s_128 = self.scale(128)
        self.launch = PushButton(
            upper_box,
            image=self.launch_jpg,
            height=s_128,
            width=s_128,
            grid=[0, 0, 1, 2],
            align="left",
            command=self.do_launch,
        )

        self.abort = PushButton(
            upper_box,
            image=self.abort_jpg,
            height=s_128,
            width=s_128,
            grid=[4, 0, 1, 2],
            align="right",
            command=self.do_abort,
        )

        if self.tmcc_id == 39:
            self.pad = Text(upper_box, text="Pad 39A", grid=[1, 0, 2, 1], size=self.scale(30), bold=True)
        else:
            self.pad = Text(upper_box, text=f"Pad {self.tmcc_id}", grid=[1, 0, 2, 1], size=self.scale(28))

        countdown_box = Box(upper_box, layout="auto", border=True, grid=[1, 1, 2, 1])
        self.label = Text(
            countdown_box,
            text="T-Minus",
            align="left",
            size=self.scale(16),
            height="fill",
            bg="black",
            color="white",
            italic=True,
        )
        self.count = Text(
            countdown_box,
            text="-00:00",
            align="right",
            size=self.scale(18),
            height=2,
            font="DigitalDream",
            bg="black",
            color="white",
            italic=True,
        )

        _ = Text(upper_box, text=" ", grid=[0, 2, 5, 1], size=self.scale(10))
        self.message = Text(
            upper_box,
            grid=[0, 3, 5, 1],
            size=self.scale(24),
            color="black",
            bold=True,
            align="top",
            height="fill",
        )

        self.lower_box = lower_box = Box(app, border=2, align="bottom")
        power_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(power_box, text="Power", grid=[0, 0], size=self.s_16, underline=True)
        self.power_button = PushButton(
            power_box,
            image=self.on_button,
            grid=[0, 1],
            command=self.toggle_power,
            height=self.s_72,
            width=self.s_72,
        )

        self.lights_box = lights_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(lights_box, text="Lights", grid=[0, 0], size=self.s_16, underline=True)
        self.lights_button = PushButton(
            lights_box,
            image=self.on_button,
            grid=[0, 1],
            command=self.toggle_lights,
            height=self.s_72,
            width=self.s_72,
        )

        self.siren_box = siren_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(siren_box, text="Siren", grid=[0, 0], size=self.s_16, underline=True)
        self.siren_button = PushButton(
            siren_box,
            image=self.siren_off,
            grid=[0, 1],
            height=self.s_72,
            width=self.s_72,
            command=self.siren_req.send,
        )

        self.klaxon_box = klaxon_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(klaxon_box, text="Klaxon", grid=[0, 0], size=self.s_16, underline=True)
        self.klaxon_button = PushButton(
            klaxon_box,
            image=self.siren_off,
            grid=[0, 1],
            height=self.s_72,
            width=self.s_72,
            command=self.klaxon_req.send,
        )

        if self.width > 480:
            self.comms_box = comms_box = Box(lower_box, layout="grid", border=2, align="left")
            _ = Text(comms_box, text="Comms", grid=[0, 0, 2, 1], size=self.s_16, underline=True)
            self.engr_comms = PushButton(
                comms_box,
                image=self.engr_comm,
                grid=[0, 1],
                height=self.s_72,
                width=self.s_72,
                command=self.engr_comm_req.send,
            )
            self.engr_comms.tk.config(relief=RAISED)
            self.engr_comms.bg = "white"

            self.tower_comms = PushButton(
                comms_box,
                image=self.tower_comm,
                grid=[1, 1],
                height=self.s_72,
                width=self.s_72,
                command=self.tower_comm_req.send,
            )
            self.tower_comms.tk.config(relief=RAISED)
            self.tower_comms.bg = "white"

        self.gantry_box = gantry_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(gantry_box, text="Gantry", grid=[0, 0, 2, 1], size=self.s_16, underline=True)
        self.gantry_rev = PushButton(
            gantry_box,
            image=self.left_arrow,
            grid=[0, 1],
            height=self.s_72,
            width=self.s_72,
        )
        self.gantry_rev.when_clicked = lambda: self.gantry_rev_req.send(repeat=2)

        self.gantry_fwd = PushButton(
            gantry_box,
            image=self.right_arrow,
            grid=[1, 1],
            height=self.s_72,
            width=self.s_72,
        )
        self.gantry_fwd.when_clicked = lambda x: self.gantry_fwd_req.send(repeat=2)

        # start upper box disabled
        self.upper_box.disable()
        self.lights_box.disable()
        self.siren_box.disable()
        self.klaxon_box.disable()
        self.gantry_box.disable()
        if self.comms_box:
            self.comms_box.disable()

        # sync GUI with current state
        self.sync_gui_state()

        # display GUI and start event loop; call blocks
        self.app.display()

    def siren_sounded(self) -> None:
        self.toggle_sound(self.siren_button)
        self.siren_button.after(13000, self.toggle_sound, [self.siren_button])

    def klaxon_sounded(self) -> None:
        self.toggle_sound(self.klaxon_button)

    def update_counter(self, value: int = None):
        with self._cv:
            prefix = "-"
            if value is None:
                self.counter -= 1
            else:
                self.counter = value

            count = self.counter if self.counter is not None else 0
            if -30 <= count < 0:
                prefix = "+"
                count = abs(count)
                self.label.value = "Launch"
            else:
                self.label.value = "T-Minus"
                if count <= -30:
                    count = 0
                    if self._is_countdown:
                        self.count.cancel(self.update_counter)
                        self._is_countdown = False
                        self.launch.enable()
            minute = count // 60
            second = count % 60
            self.count.value = f"{prefix}{minute:02d}:{second:02d}"

    def do_launch(self, t_minus: int = 80, detected: bool = False, hold=False):
        with self._cv:
            print(f"Launching: T Minus: {t_minus}")
            if self._is_countdown:
                self.count.cancel(self.update_counter)
            self._is_countdown = True
            if detected:
                self.gantry_rev_req.send()
                self.siren_req.send()
            else:
                self.launch_seq_act()
            self.abort.enable()
            self.launch.disable()
            self.message.clear()
            self.cancel_flashing()
            self.message.value = "All Systems Nominal"
            self.message.text_color = "black"
            self.update_counter(value=t_minus)
            # start the clock
            if not hold:
                self.count.repeat(1090, self.update_counter)

    def do_abort(self, detected: bool = False):
        """
        Abort launch sequence if counting down, initiate self-destruct if bird
        is in the air.
        """
        with self._cv:
            if not detected:
                self.reset_req.send()
            self.message.clear()
            self.cancel_flashing()
            if self._is_countdown:
                self.count.cancel(self.update_counter)
                self._is_countdown = False
                self.message.text_color = "red"
                if self.counter >= 0:
                    self.message.value = "** Launch Aborted **"
                else:
                    self.message.value = "** Self Destruct **"
                self.message.visible = True
                self.message.repeat(500, self.flash_message)
            else:
                self.reset_req.send()
                self.update_counter(value=0)
            self.launch.enable()
            self.message.show()

    def flash_message(self):
        with self._cv:
            if self.message.text_color == "red":
                self.message.text_color = self.app.bg
            else:
                self.message.text_color = "red"
            self._is_flashing = True

    def cancel_flashing(self):
        with self._cv:
            if self._is_flashing:
                self.message.cancel(self.flash_message)
                self._is_flashing = False

    def toggle_power(self):
        self.update_counter(value=0)
        self.label.value = "T-Minus"
        self.message.clear()
        self.cancel_flashing()
        if self.power_button.image == self.on_button:
            self.do_power_on()
            if self.track_on_req:
                self.track_on_req.send()
                sleep(0.5)
            self.power_on_req.send()
        else:
            self.do_power_off()
            self.power_off_req.send()
            self.lights_off_req.send(delay=0.5)
        self.power_button.height = self.power_button.width = self.s_72

    def do_power_off(self):
        with self._cv:
            self.cancel_flashing()
            if self._is_countdown:
                self.count.cancel(self.update_counter)
                self._is_countdown = False
            if self.power_button.image != self.on_button:
                self.power_button.image = self.on_button
                self.power_button.height = self.power_button.width = self.s_72
            self.upper_box.disable()
            self.lights_box.disable()
            self.siren_box.disable()
            self.klaxon_box.disable()
            self.gantry_box.disable()
            if self.comms_box:
                self.comms_box.disable()

    def do_power_on(self):
        with self._cv:
            if self.power_button.image != self.off_button:
                self.power_button.image = self.off_button
                self.power_button.height = self.power_button.width = self.s_72
            self.upper_box.enable()
            self.lights_box.enable()
            self.siren_box.enable()
            self.klaxon_box.enable()
            self.gantry_box.enable()
            if self.comms_box:
                self.comms_box.enable()
            self.sync_pad_lights()
            if self._is_countdown:
                self.launch.disable()

    def set_lights_off_icon(self):
        with self._cv:
            if self.lights_button.image != self.off_button:
                self.lights_button.image = self.off_button
                self.lights_button.height = self.lights_button.width = self.s_72

    def set_lights_on_icon(self):
        with self._cv:
            if self.lights_button.image != self.on_button:
                self.lights_button.image = self.on_button
                self.lights_button.height = self.lights_button.width = self.s_72

    def toggle_lights(self):
        with self._cv:
            if self._monitored_state.is_aux2:
                self.lights_off_req.send(repeat=2)
            else:
                self.lights_on_req.send(repeat=2)

    def do_klaxon_off(self):
        self.klaxon_button.image = self.siren_off
        self.klaxon_button.height = self.klaxon_button.width = self.s_72

    def toggle_sound(self, button: PushButton):
        if button.enabled is True:
            if button.image == self.siren_off:
                button.image = self.siren_on
            else:
                button.image = self.siren_off
            button.height = button.width = self.s_72
