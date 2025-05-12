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

        self.counter = 30

        self.app = self.upper_box = self.lower_box = self.message = None
        self.launch_button = self.abort = self.pad = self.count = self.label = None
        self.power_button = self.lights_button = self.siren_button = self.klaxon_button = None

        self.start()

    def run(self):
        GpioHandler.cache_handler(self)
        self.app = app = App(title="Launch Pad", width=480, height=320)
        app.full_screen = True
        self.upper_box = upper_box = Box(app, layout="grid", border=False)

        self.launch_button = PushButton(
            upper_box,
            image=self.launch_jpg,
            height=128,
            width=128,
            grid=[0, 0, 1, 2],
            padx=0,
            pady=0,
            command=self.do_launch,
        )

        self.abort = PushButton(
            upper_box,
            image=self.abort_jpg,
            height=128,
            width=128,
            grid=[4, 0, 1, 2],
            padx=0,
            pady=0,
            command=self.do_abort,
        )

        if self.tmcc_id == 39:
            self.pad = Text(upper_box, text="Pad 39A", grid=[1, 0, 2, 1], size=28)
        else:
            self.pad = Text(upper_box, text=f"Pad {self.tmcc_id}", grid=[1, 0, 2, 1], size=28)
        self.label = Text(upper_box, text="T-Minus", grid=[1, 1], size=24)
        self.count = Text(upper_box, text="-00:00", grid=[2, 1], size=24, font="Digital Display")

        self.lower_box = lower_box = Box(app, border=2, align="bottom")
        self.message = Text(upper_box, text="", grid=[1, 2, 2, 1], size=24, color="red")

        power_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(power_box, text="Power", grid=[0, 0], size=16, underline=True)
        self.power_button = PushButton(
            power_box,
            image=self.on_button,
            grid=[0, 1],
            command=self.toggle_power,
            height=80,
            width=80,
        )

        lights_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(lights_box, text="Lights", grid=[0, 0], size=16, underline=True)
        self.lights_button = PushButton(
            lights_box,
            image=find_file("on_button.jpg"),
            grid=[0, 1],
            command=self.toggle_lights,
            height=80,
            width=80,
        )

        siren_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(siren_box, text="Siren", grid=[0, 0], size=16, underline=True)
        self.siren_button = PushButton(
            siren_box,
            image=self.siren_off,
            grid=[0, 1],
            height=80,
            width=80,
        )
        self.siren_button.when_left_button_pressed = self.toggle_siren
        self.siren_button.when_right_button_pressed = self.toggle_siren
        self.siren_button.when_left_button_released = self.toggle_siren
        self.siren_button.when_right_button_released = self.toggle_siren

        klaxon_box = Box(lower_box, layout="grid", border=2, align="left")
        _ = Text(klaxon_box, text="Klaxon", grid=[0, 0], size=16, underline=True)
        self.klaxon_button = PushButton(
            klaxon_box,
            image=self.siren_off,
            grid=[0, 1],
            height=80,
            width=80,
        )
        self.klaxon_button.when_left_button_pressed = lambda _: self.toggle_sound(self.klaxon_button)
        self.klaxon_button.when_left_button_released = lambda _: self.toggle_sound(self.klaxon_button)

        # start upper box disabled
        self.upper_box.disable()

        # display GUI
        self.app.display()

    def reset(self):
        self.app.destroy()

    def update_text(self):
        self.counter -= 1
        self.count.value = f"-00:{self.counter:02d}"

    def do_launch(self):
        self.message.clear()
        self.counter = 30
        self.count.value = f"-00:{self.counter:02d}"
        self.count.repeat(1000, self.update_text)

    def do_abort(self):
        self.count.cancel(self.update_text)
        self.message.clear()
        self.message.value = "Launch Abort"
        self.message.show()

    def toggle_power(self):
        if self.power_button.image == self.on_button:
            self.power_button.image = self.off_button
            self.upper_box.enable()
        else:
            self.power_button.image = self.on_button
            self.upper_box.disable()
        self.power_button.height = self.power_button.width = 80

    def toggle_lights(self):
        if self.lights_button.image == self.on_button:
            self.lights_button.image = self.off_button
        else:
            self.lights_button.image = self.on_button

        self.lights_button.height = self.lights_button.width = 80

    def toggle_siren(self):
        if self.siren_button.image == self.siren_off:
            self.siren_button.image = self.siren_on
        else:
            self.siren_button.image = self.siren_off
        print("toggle siren")

        self.siren_button.height = self.siren_button.width = 80

    def toggle_sound(self, button: PushButton):
        if button.image == self.siren_off:
            button.image = self.siren_on
        else:
            button.image = self.siren_off
        print("toggle button")

        button.height = button.width = 80
