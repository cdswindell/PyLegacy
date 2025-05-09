from guizero import App, PushButton, Text, Box

from src.pytrain import find_file

app = App(title="Launch Pad", width=480, height=320)
center_box = Box(app, layout="grid")

launch_jpg = find_file("launch.jpg")
abort_jpg = find_file("abort.jpg")
button = PushButton(center_box, image=launch_jpg, height=128, width=128, grid=[0, 0])
pad = Text(center_box, text="Launch Pad", grid=[1, 0, 2, 1], size=30)
abort = PushButton(center_box, image=abort_jpg, height=128, width=128, grid=[4, 0])

app.display()
