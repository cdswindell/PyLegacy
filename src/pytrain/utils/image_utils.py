#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
# noinspection PyPackageRequirements
from PIL import ImageDraw, ImageFont, ImageTk


def center_text_on_image(
    photo: ImageTk.PhotoImage, text: str, font_size: int = 22, styled: bool = True
) -> ImageTk.PhotoImage:
    """
    Draw centered black text over a light-gray rounded rectangle.

    If styled=True:
        - Text is upper-case
        - First letter of each word is drawn at font_size
        - Remaining letters are drawn at font_size - 2
    If styled=False:
        - Text is drawn as-is using one uniform font size

    Rectangle width = (text length + 1) characters of the BIG font.
    Returns a new PhotoImage.
    """

    # Convert PhotoImage → PIL Image
    pil_img = ImageTk.getimage(photo).copy()
    draw = ImageDraw.Draw(pil_img)

    # Load fonts
    font_big = ImageFont.truetype("DejaVuSans.ttf", font_size)
    font_small = ImageFont.truetype("DejaVuSans.ttf", max(font_size - 2, 1))

    img_w, img_h = pil_img.size

    # Determine actual displayed text
    if styled:
        display_text = text.upper()
    else:
        display_text = text  # do not alter case

    # Representative big character ("M") for box sizing
    bbox_m = draw.textbbox((0, 0), "M", font=font_big)
    char_w_big = bbox_m[2] - bbox_m[0]
    char_h_big = bbox_m[3] - bbox_m[1]

    # Background width = number_of_displayed_characters
    bg_chars = len(display_text)
    bg_w = char_w_big * bg_chars

    # Equal vertical padding
    padding = int(font_size * 0.5)
    bg_h = char_h_big + (padding * 2)

    # Rounded rect coordinates (centered)
    bg_x = (img_w - bg_w) // 2
    bg_y = (img_h - bg_h) // 2
    bg_x2 = bg_x + bg_w
    bg_y2 = bg_y + bg_h

    draw.rounded_rectangle([bg_x, bg_y, bg_x2, bg_y2], radius=int(font_size * 0.6), fill="#DDDDDD", outline=None)

    # ----------------------------------------------------
    # Measure total text width based on styling mode
    # ----------------------------------------------------
    total_text_w = 0

    if not styled:
        # Simple: measure full text at uniform font size
        bbox = draw.textbbox((0, 0), display_text, font=font_big)
        total_text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

    else:
        # Styled mode: per-character measurement
        new_word = True
        for ch in display_text:
            if ch == " ":
                bbox = draw.textbbox((0, 0), ch, font=font_small)
            else:
                font = font_big if new_word else font_small
                bbox = draw.textbbox((0, 0), ch, font=font)
                new_word = False if ch != " " else True
            total_text_w += bbox[2] - bbox[0]
        text_h = char_h_big  # good-enough height estimate

    # Center position for the whole text block
    text_x = bg_x + (bg_w - total_text_w) // 2
    text_y = bg_y + (bg_h - text_h) // 2

    # Visual upward shift to correct font baseline asymmetry
    vertical_adjust = int(font_size * 0.15)
    text_y -= vertical_adjust

    # ----------------------------------------------------
    # Render text
    # ----------------------------------------------------
    if not styled:
        # Draw the whole string at once
        draw.text((text_x, text_y), display_text, font=font_big, fill="black")

    else:
        # Draw character-by-character in styled mode
        cursor_x = text_x
        new_word = True
        for ch in display_text:
            if ch == " ":
                # Just advance cursor
                bbox = draw.textbbox((0, 0), ch, font=font_small)
                cursor_x += bbox[2] - bbox[0]
                new_word = True
                continue

            # Choose appropriate font
            font = font_big if new_word else font_small
            bbox = draw.textbbox((0, 0), ch, font=font)
            ch_w = bbox[2] - bbox[0]

            draw.text((cursor_x, text_y), ch, font=font, fill="black")

            cursor_x += ch_w
            new_word = False

    return ImageTk.PhotoImage(pil_img)
