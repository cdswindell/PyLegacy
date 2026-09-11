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

import shutil

ROOT = Path("../src/pytrain/gui/images/engines")

restored = 0

for bak in ROOT.rglob("*.bak"):
    original = bak.with_suffix("")

    print(f"Restoring {original.name}")

    if original.exists():
        original.unlink()

    shutil.move(str(bak), str(original))

    restored += 1

print()

print(f"Restored {restored} files")
