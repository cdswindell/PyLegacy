#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

"""Generate the black-and-white button icons used by the generic-accessory return control.

Three flat, high-contrast icons drawn in the same black-silhouette-on-white style as the
existing op-*.jpg artwork:

* op-bpc2.jpg  -- an LCS BPC2 power-district controller (a terminal block).
* op-asc2.jpg  -- an LCS ASC2 accessory switch controller (a terminal block).
* op-screen.jpg -- a generic operating-accessory control screen (sliders and buttons).

The BPC2/ASC2 icons mark the "go back to this device's own panel" direction of the shared
ac_op_btn; the screen icon marks the "open the operating-accessory control screen"
direction. Re-run this script to regenerate the assets; it is deterministic and overwrites in
place.

Usage::

    ../bin/python scripts/generate_lcs_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# The images live beside every other button asset.
IMAGES_DIR = Path(__file__).resolve().parent.parent / "src" / "pytrain" / "gui" / "images"

SIZE = 600
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """A bold-ish font at the requested size, falling back to the bitmap default."""
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Arial.ttf", "Helvetica.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow < 10 has no size argument
        return ImageFont.load_default()


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (SIZE, SIZE), WHITE)
    return img, ImageDraw.Draw(img)


def _centered_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font, fill) -> None:
    left, top, right, bottom = box
    tl, tt, tr, tb = draw.textbbox((0, 0), text, font=font)
    tx = left + (right - left - (tr - tl)) // 2 - tl
    ty = top + (bottom - top - (tb - tt)) // 2 - tt
    draw.text((tx, ty), text, font=font, fill=fill)


def _terminal_block(label: str) -> Image.Image:
    """A black LCS controller silhouette carrying its model name in reversed-out text."""
    img, draw = _canvas()

    # Device body: a rounded black rectangle centered on the canvas.
    body = (70, 120, SIZE - 70, SIZE - 120)
    draw.rounded_rectangle(body, radius=36, fill=BLACK)

    # A reversed-out name plate across the top third so the device is identifiable at a glance.
    plate = (110, 160, SIZE - 110, 300)
    draw.rounded_rectangle(plate, radius=18, fill=WHITE)
    _centered_text(draw, plate, label, _font(120), BLACK)

    # A row of screw terminals along the bottom, the give-away of an LCS terminal block.
    n = 6
    margin = 130
    span = SIZE - 2 * margin
    gap = span / (n - 1)
    cy = SIZE - 195
    r = 30
    for i in range(n):
        cx = int(margin + i * gap)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=WHITE)
        # A slot in each screw head.
        draw.line((cx - r + 8, cy, cx + r - 8, cy), fill=BLACK, width=8)

    return img


def _operating_screen() -> Image.Image:
    """A generic operating-accessory control panel: a screen with sliders and buttons."""
    img, draw = _canvas()

    # The screen bezel.
    bezel = (70, 90, SIZE - 70, SIZE - 90)
    draw.rounded_rectangle(bezel, radius=40, fill=BLACK)

    # The inner display, reversed out so the controls read as black on white.
    inner = (110, 130, SIZE - 110, SIZE - 130)
    draw.rounded_rectangle(inner, radius=24, fill=WHITE)

    # Two vertical slider tracks with knobs -- the throttle-style controls.
    for i, cx in enumerate((200, 300)):
        top, bottom = 190, SIZE - 250
        draw.line((cx, top, cx, bottom), fill=BLACK, width=14)
        knob_y = top + (bottom - top) * (0.30 if i == 0 else 0.62)
        draw.rounded_rectangle((cx - 42, knob_y - 26, cx + 42, knob_y + 26), radius=12, fill=BLACK)

    # A stack of round action buttons on the right.
    for cy in (215, 330, 445):
        draw.ellipse((380, cy - 40, 460, cy + 40), outline=BLACK, width=14)

    # A status bar along the bottom of the display.
    draw.rounded_rectangle((150, SIZE - 210, SIZE - 150, SIZE - 175), radius=14, fill=BLACK)

    return img


def _save(img: Image.Image, name: str) -> None:
    path = IMAGES_DIR / name
    img.save(path, format="JPEG", quality=90, optimize=True)
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    _save(_terminal_block("BPC2"), "op-bpc2.jpg")
    _save(_terminal_block("ASC2"), "op-asc2.jpg")
    _save(_operating_screen(), "op-screen.jpg")


if __name__ == "__main__":
    main()
