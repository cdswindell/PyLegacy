from guizero import App, PushButton, Text, Box

from src.pytrain import find_file

app = App(title="Launch Pad", width=480, height=320)
app.full_screen = True
center_box = Box(app, layout="grid", border=False)

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


launch_jpg = find_file("launch.jpg")
abort_jpg = find_file("abort.jpg")
button = PushButton(
    center_box,
    image=launch_jpg,
    height=128,
    width=128,
    grid=[0, 0, 1, 2],
    padx=0,
    pady=0,
    command=do_launch,
)
pad = Text(center_box, text="Pad 39A", grid=[1, 0, 2, 1], size=28)
label = Text(center_box, text="T-Minus", grid=[1, 1], size=24)
count = Text(center_box, text="-00:00", grid=[2, 1], size=24, font="Digital Display")
abort = PushButton(
    center_box,
    image=abort_jpg,
    height=128,
    width=128,
    grid=[4, 0, 1, 2],
    padx=0,
    pady=0,
    command=do_abort,
)

message = Text(center_box, text="", grid=[1, 2, 2, 1], size=24, color="red")
app.display()
