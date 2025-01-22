#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

import re

U33C_PATTERN = re.compile(r"[A-Z]\d{2}[A-Z]")


def title(text: str):
    if text:
        parts = text.strip().split(" ")
        for i, part in enumerate(parts):
            part = part.strip().upper()
            if len(part) > 3:
                if part.startswith("SD") and (part.endswith("ACE") or part.endswith("AC")):
                    if part.endswith("ACE"):
                        part = part.replace("ACE", "ACe")
                    else:
                        part = part.replace("AC", "ACe")
                elif part.startswith("SD"):
                    if i + 1 < len(parts) and parts[i + 1].upper() == "ACE":
                        part = part + "ACe"
                        part = part.replace("SD-", "SD")
                        parts[i + 1] = ""
                elif part.startswith("FA-") or part.startswith("RS-") or part.startswith("GP"):
                    pass
                elif U33C_PATTERN.match(part):
                    pass
                else:
                    part = part.capitalize()
            elif part in {"NEW", "OLD", "CAR", "RIO", "PAD", "BEE"}:
                part = part.capitalize()
            parts[i] = part
        text = " ".join([p for p in parts if p])
    return text
