#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import os
import sys


class Install:
    def __init__(self, args: list[str] = None) -> None:
        tmpl = self.template_dir
        print(f"Install: {tmpl} {os.path.isfile(tmpl+'/pytrain_client.bash.template')}")

    @property
    def template_dir(self) -> str:
        for d in [".", "../", "src"]:
            if os.path.isdir(d):
                for root, dirs, _ in os.walk(d):
                    if root.startswith("./.") or root.startswith("./venv/"):
                        continue
                    print(f"Root: {root} Looking in {dirs} for install template...")
                    for cd in dirs:
                        if cd.startswith(".") or cd in ["__pycache__"]:
                            continue
                        if cd == "installation":
                            return f"{root}/{cd}"

        return os.getcwd() + "/lib/python3.12/site-packages/install"


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        Install(args)
        return 0
    except Exception as e:
        # Output anything else nicely formatted on stderr and exit code 1
        sys.exit(f"{__file__}: error: {e}\n")
