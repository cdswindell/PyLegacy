#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#
#

from pathlib import Path
from PIL import Image

ROOT = Path(".")

MIN_SIZE_BYTES = 40_000
JPEG_QUALITY = 65
SCALE = 0.5
BACKUP = False

for path in ROOT.rglob("*"):
    if path.suffix.lower() not in {".jpg", ".jpeg"}:
        continue

    if path.stat().st_size < MIN_SIZE_BYTES:
        continue

    print(f"Processing {path.name}")

    if BACKUP:
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            backup.write_bytes(path.read_bytes())

    with Image.open(path) as img:
        img = img.convert("RGB")

        #
        # Create 3:1 canvas using the original image height
        #
        canvas_height = img.height
        canvas_width = canvas_height * 3

        #
        # If image is wider than 3:1 already,
        # use its width and expand height instead.
        #
        if img.width > canvas_width:
            canvas_width = img.width
            canvas_height = int(round(canvas_width / 3))

        canvas = Image.new(
            "RGB",
            (canvas_width, canvas_height),
            (255, 255, 255),
        )

        x = (canvas_width - img.width) // 2
        y = (canvas_height - img.height) // 2

        canvas.paste(img, (x, y))

        #
        # Reduce final size by 50%
        #
        final_size = (
            max(1, canvas.width // 2),
            max(1, canvas.height // 2),
        )

        canvas = canvas.resize(final_size, Image.LANCZOS)

        canvas.save(
            path,
            format="JPEG",
            quality=JPEG_QUALITY,
            optimize=True,
        )
