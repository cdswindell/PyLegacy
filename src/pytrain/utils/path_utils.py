#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import os
from typing import Tuple


def find_dir(target: str, places: Tuple = (".", "../")) -> str | None:
    for d in places:
        if os.path.isdir(d):
            for root, dirs, _ in os.walk(d):
                if root.startswith("./.") or root.startswith("./venv/"):
                    continue
                for cd in dirs:
                    if cd.startswith(".") or cd in ["__pycache__", ".tox", ".github"]:
                        continue
                    if cd == target:
                        return f"{root}/{cd}"
    return None


def find_file(target: str, places: Tuple = (".", "../")) -> str | None:
    for d in places:
        if os.path.isdir(d):
            for root, dirs, files in os.walk(d):
                if root.startswith("./.") or root.startswith("./venv/"):
                    continue
                for file in files:
                    if file.startswith(".") or file in ["__pycache__"]:
                        continue
                    if file == target:
                        return f"{root}/{file}"
    return None
