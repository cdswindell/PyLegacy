from guizero import App, PushButton, Text, Box

from src.pytrain import find_file

app = App(title="Launch Pad", width=480, height=320)
app.full_screen = True
upper_box = Box(app, layout="grid", border=False)
lower_box = Box(app, layout="grid", border=2, align="bottom", width="fill")

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

power_label = Text(lower_box, text="Power", grid=[0, 0], size=18, underline=True)
power_button = PushButton(
    lower_box,
    image=find_file("on_button.jpg"),
    grid=[0, 1],
    command=toggle_power,
    height=64,
    width=64,
)

lights_label = Text(lower_box, text="Lights", grid=[1, 0], size=18, underline=True)
lights_button = PushButton(
    lower_box,
    image=find_file("on_button.jpg"),
    grid=[1, 1],
    command=toggle_lights,
    height=64,
    width=64,
)
upper_box.disable()

app.display()
