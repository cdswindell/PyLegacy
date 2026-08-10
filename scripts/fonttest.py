import tkinter as tk
import tkinter.font as font


root = tk.Tk()
default = font.nametofont("TkDefaultFont", root=root).actual()
print("Tk patchlevel:", root.tk.call("info", "patchlevel"))
print("Tk scaling:", root.tk.call("tk", "scaling"))
print("DPI:", root.winfo_fpixels("1i"))
print("Default:", default)
print("Default bold test:", font.Font(root=root, family=default["family"], size=16, weight="bold").actual())
for family in ("DejaVu Sans", "Noto Sans", "Liberation Sans"):
    print(f"{family} bold test:", font.Font(root=root, family=family, size=16, weight="bold").actual())
root.destroy()
