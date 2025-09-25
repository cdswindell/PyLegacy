#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import os
from pathlib import Path
from typing import Tuple

EXCLUDE = {
    "__pycache__",
    ".tox",
    ".github",
    ".idea",
    ".git",
    "venv",
}


def find_dir(target: str, places: Tuple = (".", "../")) -> str | None:
    for d in places:
        if os.path.isdir(d):
            for root, dirs, _ in os.walk(d):
                if root.startswith("./.") or root.startswith("./venv/"):
                    continue
                root_path = Path(os.path.abspath(root))
                parts = root_path.parts
                if len(parts) == 0:
                    continue
                do_continue = False
                if len(parts) > 1:
                    for comp_dir in parts[1:]:
                        if comp_dir.startswith(".") or comp_dir in EXCLUDE:
                            do_continue = True
                            break
                if do_continue:
                    continue
                for cd in dirs:
                    if cd.startswith(".") or cd in EXCLUDE:
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
                root_path = Path(os.path.abspath(root))
                parts = root_path.parts
                if len(parts) == 0:
                    continue
                do_continue = False
                if len(parts) > 1:
                    for comp_dir in parts[1:]:
                        if comp_dir.startswith(".") or comp_dir in EXCLUDE:
                            do_continue = True
                            break
                if do_continue:
                    continue
                for file in files:
                    if file.startswith(".") or file in EXCLUDE:
                        continue
                    if file == target:
                        return f"{root}/{file}"
    return None
