from guizero import App, PushButton, Text, Box

from src.pytrain import find_file

app = App(title="Launch Pad", width=480, height=320)
app.full_screen = True
upper_box = Box(app, layout="grid", border=False)
lower_box = Box(app, border=2, align="bottom")

counter = 30


def update_text():
    global counter
    counter -= 1
    count.value = f"-00:{counter:02d}"


def do_launch():
    global counter
    message.clear()
    counter = 30
    count.value = f"-00:{counter:02d}"
    count.repeat(1000, update_text)


def do_abort():
    count.cancel(update_text)
    message.clear()
    message.value = "Launch Abort"
    message.show()


def toggle_power():
    if power_button.image == on_button:
        power_button.image = off_button
        upper_box.enable()
    else:
        power_button.image = on_button
        upper_box.disable()
    power_button.height = power_button.width = 64


def toggle_lights():
    if lights_button.image == on_button:
        lights_button.image = off_button
    else:
        lights_button.image = on_button

    lights_button.height = lights_button.width = 64


def toggle_siren():
    if siren_button.image == siren_on:
        siren_button.image = siren_off
    else:
        siren_button.image = siren_off

    siren_button.height = siren_button.width = 64


siren_on = find_file("red_light_pressed.jpg")
siren_off = find_file("red_light.jpg")
on_button = find_file("on_button.jpg")
off_button = find_file("off_button.jpg")
launch_jpg = find_file("launch.jpg")
abort_jpg = find_file("abort.jpg")
button = PushButton(
    upper_box,
    image=launch_jpg,
    height=128,
    width=128,
    grid=[0, 0, 1, 2],
    padx=0,
    pady=0,
    command=do_launch,
)
pad = Text(upper_box, text="Pad 39A", grid=[1, 0, 2, 1], size=28)
label = Text(upper_box, text="T-Minus", grid=[1, 1], size=24)
count = Text(upper_box, text="-00:00", grid=[2, 1], size=24, font="Digital Display")
abort = PushButton(
    upper_box,
    image=abort_jpg,
    height=128,
    width=128,
    grid=[4, 0, 1, 2],
    padx=0,
    pady=0,
    command=do_abort,
)

message = Text(upper_box, text="", grid=[1, 2, 2, 1], size=24, color="red")

power_box = Box(lower_box, layout="grid", border=2, align="left")
power_label = Text(power_box, text="Power", grid=[0, 0], size=16, underline=True)
power_button = PushButton(
    power_box,
    image=find_file("on_button.jpg"),
    grid=[0, 1],
    command=toggle_power,
    height=64,
    width=64,
)

lights_box = Box(lower_box, layout="grid", border=2, align="left")
lights_label = Text(lights_box, text="Lights", grid=[0, 0], size=16, underline=True)
lights_button = PushButton(
    lights_box,
    image=find_file("on_button.jpg"),
    grid=[0, 1],
    command=toggle_lights,
    height=64,
    width=64,
)

siren_box = Box(lower_box, layout="grid", border=2, align="left")
siren_label = Text(siren_box, text="Siren", grid=[0, 0], size=16, underline=True)
siren_button = PushButton(
    siren_box,
    image=find_file("red_light.jpg"),
    grid=[0, 1],
    height=64,
    width=64,
)
siren_button.when_left_button_pressed = toggle_siren
siren_button.when_left_button_released = toggle_siren
upper_box.disable()

app.display()
