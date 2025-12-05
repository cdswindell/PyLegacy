#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
# noinspection PyPackageRequirements
# noinspection PyPackageRequirements
from PIL import ImageDraw, ImageFont, ImageTk


def center_text_on_image(
    photo: ImageTk.PhotoImage, text: str, font_size: int = 24, styled: bool = True
) -> ImageTk.PhotoImage:
    """
    Draw centered black text over a light-gray rounded rectangle.

    Styled=True → drop-cap effect:
        - first letter of each word = BIG (font_size)
        - remaining letters = SMALL (font_size - 6)

    Styled=False → all text uses big font_size
    """

    # Convert PhotoImage → PIL Image
    pil_img = ImageTk.getimage(photo).copy()
    draw = ImageDraw.Draw(pil_img)

    # Fonts
    font_big = ImageFont.truetype("DejaVuSans.ttf", font_size)
    font_small = ImageFont.truetype("DejaVuSans.ttf", max(font_size - 6, 1))

    # Uppercase in styled mode
    display_text = text.upper() if styled else text

    img_w, img_h = pil_img.size

    # ---- Vertical sizing ----
    ascent_big, descent_big = font_big.getmetrics()
    text_height_big = ascent_big + descent_big

    vpad = int(font_size * 0.25)
    bg_h = text_height_big + vpad * 2

    # ---- Measure total text width (style-aware) ----
    if not styled:
        bbox = draw.textbbox((0, 0), display_text, font=font_big)
        total_text_w = bbox[2] - bbox[0]
    else:
        total_text_w = 0
        new_word = True
        for ch in display_text:
            f = font_big if (ch != " " and new_word) else font_small
            bbox = draw.textbbox((0, 0), ch, font=f)
            total_text_w += bbox[2] - bbox[0]
            new_word = ch == " "

    # ---- Horizontal padding (NEW) ----
    hpad = int(font_size * 0.6)  # adjust if you want more/less
    bg_w = total_text_w + (2 * hpad)

    # ---- Box location ----
    bg_x = (img_w - bg_w) // 2
    bg_y = (img_h - bg_h) // 2
    bg_x2 = bg_x + bg_w
    bg_y2 = bg_y + bg_h

    draw.rounded_rectangle(
        [bg_x, bg_y, bg_x2, bg_y2],
        radius=int(font_size * 0.6),
        fill="#DDDDDD",
        outline=None,
    )

    # ---- Horizontal centering with padding ----
    text_x = bg_x + hpad

    # ---- Baseline calculation ----
    rect_center_y = (bg_y + bg_y2) // 2
    baseline_y = rect_center_y + (ascent_big - text_height_big // 2)

    # ---- Draw text ----
    if not styled:
        draw_y = baseline_y - ascent_big
        draw.text((text_x, draw_y), display_text, font=font_big, fill="black")

    else:
        ascent_small, descent_small = font_small.getmetrics()
        cursor_x = text_x
        new_word = True

        for ch in display_text:
            f = font_big if (ch != " " and new_word) else font_small
            ascent = ascent_big if f is font_big else ascent_small

            bbox = draw.textbbox((0, 0), ch, font=f)
            ch_w = bbox[2] - bbox[0]

            draw_y = baseline_y - ascent
            draw.text((cursor_x, draw_y), ch, font=f, fill="black")

            cursor_x += ch_w
            new_word = ch == " "

    return ImageTk.PhotoImage(pil_img)
