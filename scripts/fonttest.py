import os
import sys
import tkinter as tk
import tkinter.font as font
import _tkinter


def tk_value(root, *args):
    try:
        return root.tk.call(*args)
    except tk.TclError as exc:
        return f"unavailable ({exc})"


def loaded_tcl_tk_libraries():
    maps = "/proc/self/maps"
    if not os.path.exists(maps):
        return []
    with open(maps, encoding="utf-8") as file:
        paths = {line.rsplit(maxsplit=1)[-1] for line in file if "/" in line}
    return sorted(path for path in paths if "libtcl" in path.lower() or "libtk" in path.lower())


root = tk.Tk()
default = font.nametofont("TkDefaultFont", root=root).actual()
families = sorted(set(font.families(root=root)), key=str.casefold)
print("Python executable:", sys.executable)
print("Python version:", sys.version.replace("\n", " "))
print("tkinter module:", tk.__file__)
print("_tkinter extension:", _tkinter.__file__)
print("Tk patchlevel:", root.tk.call("info", "patchlevel"))
print("Tcl patchlevel:", tk_value(root, "set", "tcl_patchLevel"))
print("Windowing system:", root.tk.call("tk", "windowingsystem"))
print("Display:", os.environ.get("DISPLAY", "<not set>"))
print("Wayland display:", os.environ.get("WAYLAND_DISPLAY", "<not set>"))
print("X server:", root.winfo_server())
print("Tcl library:", tk_value(root, "set", "tcl_library"))
print("Tk library:", tk_value(root, "set", "tk_library"))
print("TCL_LIBRARY environment:", os.environ.get("TCL_LIBRARY", "<not set>"))
print("TK_LIBRARY environment:", os.environ.get("TK_LIBRARY", "<not set>"))
libraries = loaded_tcl_tk_libraries()
print("Loaded Tcl/Tk libraries:", libraries if libraries else "not available on this platform")
print("Tk scaling:", root.tk.call("tk", "scaling"))
print("DPI:", root.winfo_fpixels("1i"))
print("Default:", default)
print("Default bold test:", font.Font(root=root, family=default["family"], size=16, weight="bold").actual())
for family in ("DejaVu Sans", "Noto Sans", "Liberation Sans"):
    print(f"{family} bold test:", font.Font(root=root, family=family, size=16, weight="bold").actual())
print(f"Tk-visible font families ({len(families)}):")
print(", ".join(families) if families else "<none>")
root.destroy()
