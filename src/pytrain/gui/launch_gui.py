from threading import Thread

from guizero import App, PushButton, Text, Box

from ..gpio.gpio_handler import GpioHandler
from ..utils.path_utils import find_file


class LaunchGui(Thread):
    def __init__(self, tmcc_id: int = 39):
        super().__init__(daemon=True, name=f"Pad {tmcc_id} GUI")
        self.tmcc_id = tmcc_id

        self.launch_jpg = find_file("launch.jpg")
        self.abort_jpg = find_file("abort.jpg")
        self.siren_on = find_file("red_light.jpg")
        self.siren_off = find_file("red_light_off.jpg")
        self.on_button = find_file("on_button.jpg")
        self.off_button = find_file("off_button.jpg")
        self.padding = 0

        self.counter = 30

        self.app = self.upper_box = self.lower_box = self.message = None
        self.launch_button = self.abort = self.pad = self.count = self.label = None
        self.power_button = self.lights_button = self.siren_button = self.klaxon_button = None
        self.gantry_left = self.gantry_right = None

        self.start()

    def run(self):
        GpioHandler.cache_handler(self)
        self.app = app = App(title="Launch Pad", width=480, height=320)
        app.full_screen = True
        self.upper_box = upper_box = Box(app, layout="grid", border=False)

        self.launch_button = PushButton(
            upper_box,
            image=self.launch_jpg,
            height=112,
            width=112,
            grid=[0, 0, 1, 2],
            align="left",
            padx=self.padding,
            pady=self.padding,
            command=self.do_launch,
        )

        self.abort = PushButton(
            upper_box,
            image=self.abort_jpg,
            height=112,
            width=112,
            grid=[4, 0, 1, 2],
            align="right",
            padx=self.padding,
            pady=self.padding,
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

        lights_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(lights_box, text="Lights", grid=[0, 0], size=16, underline=True)
        self.lights_button = PushButton(
            lights_box,
            image=self.on_button,
            grid=[0, 1],
            command=self.toggle_lights,
            height=72,
            width=72,
        )

        siren_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(siren_box, text="Siren", grid=[0, 0], size=16, underline=True)
        self.siren_button = PushButton(
            siren_box,
            image=self.siren_off,
            grid=[0, 1],
            height=72,
            width=72,
        )
        self.siren_button.when_left_button_pressed = lambda _: self.toggle_sound(self.siren_button)
        self.siren_button.when_left_button_released = lambda _: self.toggle_sound(self.siren_button)

        klaxon_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(klaxon_box, text="Klaxon", grid=[0, 0], size=16, underline=True)
        self.klaxon_button = PushButton(
            klaxon_box,
            image=self.siren_off,
            grid=[0, 1],
            height=72,
            width=72,
        )
        self.klaxon_button.when_left_button_pressed = lambda _: self.toggle_sound(self.klaxon_button)
        self.klaxon_button.when_left_button_released = lambda _: self.toggle_sound(self.klaxon_button)

        gantry_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(gantry_box, text="Gantry", grid=[0, 0, 2, 1], size=16, underline=True)
        self.gantry_left = PushButton(
            gantry_box,
            image=self.siren_off,
            grid=[0, 1],
            height=72,
            width=72,
        )
        self.gantry_right = PushButton(
            gantry_box,
            image=self.siren_off,
            grid=[1, 1],
            height=72,
            width=72,
        )

        # start upper box disabled
        self.upper_box.disable()

        # display GUI
        self.app.display()
        self.app.show()

    def reset(self):
        self.app.destroy()

    def update_counter(self, value: int = None):
        prefix = "-"
        if value is None:
            self.counter -= 1
        else:
            self.counter = value

        count = self.counter
        if count < 0:
            prefix = "+"
            count = abs(count)
            self.label.value = "Launch"
        else:
            self.label.value = "T-Minus"

        minute = count // 60
        second = count % 60
        self.count.value = f"{prefix}{minute:02d}:{second:02d}"

    def do_launch(self):
        self.abort.enable()
        self.message.clear()
        self.update_counter(value=30)
        self.count.repeat(1000, self.update_counter)

    def do_abort(self):
        self.count.cancel(self.update_counter)
        self.message.clear()
        if self.counter >= 0:
            self.message.value = "Launch Aborted"
        else:
            self.message.value = "Self Destruct"
        self.message.show()
        self.abort.disable()

    def toggle_power(self):
        self.update_counter(value=0)
        self.label.value = "T-Minus"
        self.message.clear()
        if self.power_button.image == self.on_button:
            self.power_button.image = self.off_button
            self.upper_box.enable()
        else:
            self.power_button.image = self.on_button
            self.upper_box.disable()
        self.power_button.height = self.power_button.width = 72

    def toggle_lights(self):
        if self.lights_button.image == self.on_button:
            self.lights_button.image = self.off_button
        else:
            self.lights_button.image = self.on_button
        self.lights_button.height = self.lights_button.width = 72

    def toggle_sound(self, button: PushButton):
        if button.image == self.siren_off:
            button.image = self.siren_on
        else:
            button.image = self.siren_off
        button.height = button.width = 72
