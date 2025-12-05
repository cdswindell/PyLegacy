#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
from PIL import ImageDraw, ImageFont, ImageTk


def center_text_on_image(photo: ImageTk.PhotoImage, text: str, font_size: int = 96) -> ImageTk.PhotoImage:
    """
    Draw centered text over a tkinter PhotoImage and return a new PhotoImage.
    """

    # Convert PhotoImage → PIL.Image
    pil_img = ImageTk.getimage(photo).copy()
    draw = ImageDraw.Draw(pil_img)

    # Load font
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()

    wo, ho = pil_img.size

    # Measure text (Pillow 10+ safe)
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Center text
    x = (wo - w) // 2
    y = (ho - h) // 2

    draw.text(
        (x, y),
        text,
        font=font,
        fill="white",
        stroke_width=2,
        stroke_fill="black",
    )

    # Convert PIL.Image → PhotoImage
    return ImageTk.PhotoImage(pil_img)
