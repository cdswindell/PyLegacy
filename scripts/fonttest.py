import tkinter as tk
import tkinter.font as font


root = tk.Tk()
print("Tk patchlevel:", root.tk.call("info", "patchlevel"))
print("Tk scaling:", root.tk.call("tk", "scaling"))
print("DPI:", root.winfo_fpixels("1i"))
print("Default:", font.nametofont("TkDefaultFont").actual())
print("Bold test:", font.Font(family="TkDefaultFont", size=16, weight="bold").actual())
root.destroy()
