#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
# noinspection PyPackageRequirements
from PIL import ImageDraw, ImageFont, ImageTk


def center_text_on_image(photo: ImageTk.PhotoImage, text: str, font_size: int = 22) -> ImageTk.PhotoImage:
    """
    Draw centered black text over a light-gray rounded rectangle whose width
    equals (text length + 1) characters.
    Text is visually centered by shifting it slightly upward.
    Returns a new PhotoImage.
    """

    # Convert PhotoImage → PIL Image
    pil_img = ImageTk.getimage(photo).copy()
    draw = ImageDraw.Draw(pil_img)

    # Load scalable default font
    font = ImageFont.truetype("DejaVuSans.ttf", font_size)

    img_w, img_h = pil_img.size

    # Character dimensions (measure "M")
    bbox_m = draw.textbbox((0, 0), "M", font=font)
    char_w = bbox_m[2] - bbox_m[0]
    char_h = bbox_m[3] - bbox_m[1]

    # Background width = len(text)+1 characters
    bg_w = char_w * (len(text) + 1)

    # Even padding above/below only for the rectangle
    padding = int(font_size * 0.5)
    bg_h = char_h + (padding * 2)

    # Rectangle position
    bg_x = (img_w - bg_w) // 2
    bg_y = (img_h - bg_h) // 2
    bg_x2 = bg_x + bg_w
    bg_y2 = bg_y + bg_h

    # Draw rounded rectangle
    draw.rounded_rectangle([bg_x, bg_y, bg_x2, bg_y2], radius=int(font_size * 0.6), fill="#DDDDDD", outline=None)

    # Measure actual text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Base centered position
    text_x = bg_x + (bg_w - text_w) // 2
    text_y = bg_y + (bg_h - text_h) // 2

    # 🔥 Apply upward visual-centering adjustment
    # This value has been calibrated for DejaVuSans and looks visually centered.
    vertical_adjust = int(font_size * 0.15)  # shift upward 15% of font size
    text_y -= vertical_adjust

    # Draw black text
    draw.text((text_x, text_y), text, font=font, fill="black")

    return ImageTk.PhotoImage(pil_img)
