#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
from PIL import ImageDraw, ImageFont, ImageTk


def center_text_on_image(photo: ImageTk.PhotoImage, text: str, font_size: int = 48) -> ImageTk.PhotoImage:
    """
    Draw centered black text over a light-gray background rectangle that is 20 characters wide.
    Returns a new PhotoImage.
    """

    # Convert PhotoImage → PIL Image
    pil_img = ImageTk.getimage(photo).copy()
    draw = ImageDraw.Draw(pil_img)

    # Load Pillow's default scalable font
    font = ImageFont.truetype("DejaVuSans.ttf", font_size)

    img_w, img_h = pil_img.size

    # Determine character width and height using "M" (typically widest)
    bbox_m = draw.textbbox((0, 0), "M", font=font)
    char_w = bbox_m[2] - bbox_m[0]
    char_h = bbox_m[3] - bbox_m[1]

    # Background width = 20 characters
    bg_w = char_w * 20
    bg_h = char_h + int(font_size * 0.4)  # small padding above/below text

    # Center background rectangle
    bg_x = (img_w - bg_w) // 2
    bg_y = (img_h - bg_h) // 2

    # Draw light-grey background box
    draw.rectangle(
        [bg_x, bg_y, bg_x + bg_w, bg_y + bg_h],
        fill="#DDDDDD",  # light gray
    )

    # Measure text
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Center text inside the rectangle
    text_x = bg_x + (bg_w - text_w) // 2
    text_y = bg_y + (bg_h - text_h) // 2

    # Draw black text
    draw.text((text_x, text_y), text, font=font, fill="black")

    return ImageTk.PhotoImage(pil_img)
