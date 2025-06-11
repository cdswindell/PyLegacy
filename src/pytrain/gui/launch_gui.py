import atexit
from threading import Thread, Condition, RLock
from time import time

from guizero import App, PushButton, Text, Box

from ..comm.command_listener import CommandDispatcher
from ..db.state_watcher import StateWatcher
from ..protocol.constants import CommandScope
from ..db.component_state_store import ComponentStateStore
from ..protocol.command_req import CommandReq
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum

from ..gpio.gpio_handler import GpioHandler
from ..utils.path_utils import find_file


class LaunchGui(Thread):
    def __init__(self, tmcc_id: int = 39):
        # initialize guizero thread
        super().__init__(daemon=True, name=f"Pad {tmcc_id} GUI")
        self.tmcc_id = tmcc_id
        self._cv = Condition(RLock())

        self.launch_jpg = find_file("launch.jpg")
        self.abort_jpg = find_file("abort.jpg")
        self.siren_on = find_file("red_light.jpg")
        self.siren_off = find_file("red_light_off.jpg")
        self.on_button = find_file("on_button.jpg")
        self.off_button = find_file("off_button.jpg")
        self.left_arrow = find_file("left_arrow.jpg")
        self.right_arrow = find_file("right_arrow.jpg")

        self.counter = None

        self.app = self.upper_box = self.lower_box = self.message = None
        self.launch = self.abort = self.pad = self.count = self.label = None
        self.gantry_box = self.siren_box = self.klaxon_box = self.lights_box = None
        self.power_button = self.lights_button = self.siren_button = self.klaxon_button = None
        self.gantry_rev = self.gantry_fwd = None

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
        self.started_up = False
        if self._sync_state and self._sync_state.is_synchronized is True:
            self._sync_watcher = None
            self.on_sync()
        else:
            self._sync_watcher = StateWatcher(self._sync_state, self.on_sync)
        atexit.register(self.close)

    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True
            self._monitored_state = self._state_store.get_state(CommandScope.ENGINE, self.tmcc_id, False)
            if self._monitored_state is None:
                raise ValueError(f"No state found for tmcc_id: {self.tmcc_id}")
            # start GUI
            self.start()
            # listen for state updates
            self._dispatcher.subscribe(self, CommandScope.ENGINE, self.tmcc_id)

    def close(self) -> None:
        pass

    def sync_gui_state(self) -> None:
        if self._monitored_state:
            # power on?
            if self._monitored_state.is_started is True:
                self.do_power_on()
                self.lights_on_req.send()
            else:
                self.do_power_off()
                self.lights_off_req.send()
            # lights on?
            if self._monitored_state.is_aux2 is True:
                self.do_lights_on()
            else:
                self.do_lights_off()

    def __call__(self, cmd: CommandReq) -> None:
        with self._cv:
            # handle launch sequence differently
            if cmd.command == TMCC1EngineCommandEnum.AUX1_OPTION_ONE:
                if self._launch_seq_time_trigger is None:
                    if self._last_cmd != cmd or (time() - self._last_cmd_at) > 5:
                        self._launch_seq_time_trigger = time()
                else:
                    if self._last_cmd == cmd and (time() - self._launch_seq_time_trigger) > 3.1:
                        if self._is_countdown is False:
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
                        self.do_lights_on()
                    elif cmd.data == 5:
                        self.do_lights_off()
                        self.do_power_off()
                    elif cmd.data == 0:  # reset
                        self.do_klaxon_off()
                        if self._is_countdown is True:
                            self.do_abort(detected=True)
                elif self.is_active is True:
                    if cmd.command == TMCC1EngineCommandEnum.REAR_COUPLER:
                        self.do_power_on()
                        self.do_launch(15, detected=True, hold=False)
                    elif cmd.command == TMCC1EngineCommandEnum.AUX2_OPTION_ONE:
                        if self._monitored_state.is_aux2 is True:
                            self.do_lights_on()
                        else:
                            self.do_lights_off()
                    elif cmd.command == TMCC1EngineCommandEnum.AUX2_ON:
                        self.do_lights_on()
                    elif cmd.command == TMCC1EngineCommandEnum.AUX2_OFF:
                        self.do_lights_off()

            # remember last command
            self._last_cmd = cmd

    @property
    def is_active(self) -> bool:
        return True if self._monitored_state and self._monitored_state.is_started is True else False

    def run(self):
        GpioHandler.cache_handler(self)
        self.app = app = App(title="Launch Pad", width=480, height=320)
        app.full_screen = True
        self.upper_box = upper_box = Box(app, layout="grid", border=False)

        self.launch = PushButton(
            upper_box,
            image=self.launch_jpg,
            height=128,
            width=128,
            grid=[0, 0, 1, 2],
            align="left",
            command=self.do_launch,
        )

        self.abort = PushButton(
            upper_box,
            image=self.abort_jpg,
            height=128,
            width=128,
            grid=[4, 0, 1, 2],
            align="right",
            command=self.do_abort,
        )

        if self.tmcc_id == 39:
            self.pad = Text(upper_box, text="Pad 39A", grid=[1, 0, 2, 1], size=30, bold=True)
        else:
            self.pad = Text(upper_box, text=f"Pad {self.tmcc_id}", grid=[1, 0, 2, 1], size=28)

        countdown_box = Box(upper_box, layout="auto", border=True, grid=[1, 1, 2, 1])
        self.label = Text(
            countdown_box,
            text="T-Minus",
            align="left",
            size=16,
            height=2,
            bg="black",
            color="white",
            italic=True,
        )
        self.count = Text(
            countdown_box,
            text="-00:00",
            align="right",
            size=18,
            height=2,
            font="DigitalDream",
            bg="black",
            color="white",
            italic=True,
        )

        _ = Text(upper_box, text=" ", grid=[0, 2, 5, 1], size=10)
        self.message = Text(upper_box, text="", grid=[0, 3, 5, 1], size=24, color="red", bold=True, align="top")

        self.lower_box = lower_box = Box(app, border=2, align="bottom")
        power_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(power_box, text="Power", grid=[0, 0], size=16, underline=True)
        self.power_button = PushButton(
            power_box,
            image=self.on_button,
            grid=[0, 1],
            command=self.toggle_power,
            height=72,
            width=72,
        )

        self.lights_box = lights_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(lights_box, text="Lights", grid=[0, 0], size=16, underline=True)
        self.lights_button = PushButton(
            lights_box,
            image=self.on_button,
            grid=[0, 1],
            command=self.toggle_lights,
            height=72,
            width=72,
        )

        self.siren_box = siren_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(siren_box, text="Siren", grid=[0, 0], size=16, underline=True)
        self.siren_button = PushButton(
            siren_box,
            image=self.siren_off,
            grid=[0, 1],
            height=72,
            width=72,
        )
        self.siren_button.when_clicked = lambda x: self.siren_req.send()
        self.siren_button.when_left_button_pressed = lambda _: self.toggle_sound(self.siren_button)
        self.siren_button.when_left_button_released = lambda _: self.toggle_sound(self.siren_button)

        self.klaxon_box = klaxon_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(klaxon_box, text="Klaxon", grid=[0, 0], size=16, underline=True)
        self.klaxon_button = PushButton(
            klaxon_box,
            image=self.siren_off,
            grid=[0, 1],
            height=72,
            width=72,
        )
        self.klaxon_button.when_clicked = self.toggle_klaxon

        self.gantry_box = gantry_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(gantry_box, text="Gantry", grid=[0, 0, 2, 1], size=16, underline=True)
        self.gantry_rev = PushButton(
            gantry_box,
            image=self.left_arrow,
            grid=[0, 1],
            height=70,
            width=70,
        )
        self.gantry_rev.when_clicked = lambda x: self.gantry_rev_req.send(repeat=2)

        self.gantry_fwd = PushButton(
            gantry_box,
            image=self.right_arrow,
            grid=[1, 1],
            height=70,
            width=70,
        )
        self.gantry_fwd.when_clicked = lambda x: self.gantry_fwd_req.send(repeat=2)

        # start upper box disabled
        self.upper_box.disable()
        self.lights_box.disable()
        self.siren_box.disable()
        self.klaxon_box.disable()
        self.gantry_box.disable()

        # sync GUI with current state
        self.sync_gui_state()

        # display GUI and start event loop; call blocks
        self.app.display()

    def reset(self):
        self.app.destroy()

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
                    if self._is_countdown is True:
                        self.count.cancel(self.update_counter)
                        self._is_countdown = False
                        self.launch.enable()
            minute = count // 60
            second = count % 60
            self.count.value = f"{prefix}{minute:02d}:{second:02d}"

    def do_launch(self, t_minus: int = 80, detected: bool = False, hold=False):
        with self._cv:
            print(f"Launching: T Minus: {t_minus}")
            if self._is_countdown is True:
                self.count.cancel(self.update_counter)
            self._is_countdown = True
            if detected is True:
                self.gantry_rev_req.send()
                self.siren_req.send()
            else:
                self.launch_seq_act()
            self.abort.enable()
            self.launch.disable()
            self.message.clear()
            self.update_counter(value=t_minus)
            # start the clock
            if hold is False:
                self.count.repeat(1090, self.update_counter)

    def do_abort(self, detected: bool = False):
        with self._cv:
            if detected is False:
                self.reset_req.send()
            self.message.clear()
            if self._is_countdown is True:
                self.count.cancel(self.update_counter)
                self._is_countdown = False
                if self.counter >= 0:
                    self.message.value = "Launch Aborted"
                else:
                    self.message.value = "Self Destruct"
            self.launch.enable()
            self.message.show()

    def toggle_power(self):
        self.update_counter(value=0)
        self.label.value = "T-Minus"
        self.message.clear()
        if self.power_button.image == self.on_button:
            self.do_power_on()
            self.power_on_req.send()
        else:
            self.do_power_off()
            self.power_off_req.send()
        self.power_button.height = self.power_button.width = 72

    def do_power_off(self):
        with self._cv:
            if self._is_countdown is True:
                self.count.cancel(self.update_counter)
                self._is_countdown = False
            if self.power_button.image != self.on_button:
                self.power_button.image = self.on_button
                self.power_button.height = self.power_button.width = 72
            self.upper_box.disable()
            self.lights_box.disable()
            self.siren_box.disable()
            self.klaxon_box.disable()
            self.gantry_box.disable()

    def do_power_on(self):
        with self._cv:
            if self.power_button.image != self.off_button:
                self.power_button.image = self.off_button
                self.power_button.height = self.power_button.width = 72
            self.upper_box.enable()
            self.lights_box.enable()
            self.siren_box.enable()
            self.klaxon_box.enable()
            self.gantry_box.enable()
            if self._is_countdown is True:
                self.launch.disable()

    def do_lights_on(self):
        if self.lights_button.image != self.off_button:
            self.lights_button.image = self.off_button
            self.lights_button.height = self.lights_button.width = 72

    def do_lights_off(self):
        if self.lights_button.image != self.on_button:
            self.lights_button.image = self.on_button
            self.lights_button.height = self.lights_button.width = 72

    def toggle_klaxon(self) -> None:
        self.klaxon_req.send()
        self.toggle_sound(self.klaxon_button)

    def do_klaxon_off(self):
        if self.klaxon_button.image != self.siren_off:
            self.klaxon_button.image = self.siren_off
            self.klaxon_button.height = self.klaxon_button.width = 72

    def toggle_lights(self):
        if self.lights_button.image == self.on_button:
            self.do_lights_on()
            self.lights_on_req.send(repeat=2)
        else:
            self.do_lights_off()
            self.lights_off_req.send(repeat=2)

    def toggle_sound(self, button: PushButton):
        if button.enabled is True:
            if button.image == self.siren_off:
                button.image = self.siren_on
            else:
                button.image = self.siren_off
            button.height = button.width = 72
