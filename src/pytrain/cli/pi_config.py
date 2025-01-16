import os
import sys
from argparse import ArgumentParser
from typing import List

SETTINGS = {
    "do_net_names 0",
    "do_i2c 0",
    "do_ssh 0",
    "do_pi4video V3",
    "do_boot_splash 1",
    "do_rpi_connect 1",
    "do_spi 1",
    "do_serial_hw 1",
    "do_serial_cons 1",
    "do_onewire 1",
    "do_rgpio 1",
}


class PiConfig:
    def __init__(self, cmd_line: List[str] = None) -> None:
        if cmd_line:
            args = self.command_line_parser().parse_args(cmd_line)
        else:
            args = self.command_line_parser().parse_args()
        self._args = args
        self.option = args.option
        self.verbose = args.quiet is False
        self.do_services = self.option in {"all", "services"}
        self.do_packages = self.option in {"all", "packages"}
        # do the work
        if self.option in {"all", "configuration"}:
            self.optimize_config()

    def optimize_config(self) -> None:
        for setting in SETTINGS:
            cmd = f"sudo raspi-config nonint {setting}"
            if self.verbose:
                print(f"Executing: {cmd}...", end="\r")
            try:
                status = os.system(cmd)
                if status == 0:
                    if self.verbose:
                        print("...Done")
                else:
                    print(f"...Failed with status {status}")
            except Exception as e:
                print(e)

    @staticmethod
    def command_line_parser() -> ArgumentParser:
        parser = ArgumentParser()
        parser.add_argument(
            "-quiet",
            action="store_true",
            help="Operate quietly and don't provide feedback",
        )
        config_group = parser.add_mutually_exclusive_group()
        config_group.add_argument(
            "-all",
            action="store_const",
            const="all",
            dest="option",
            help="Perform all optimizations",
        )
        config_group.add_argument(
            "-configuration",
            action="store_const",
            const="configuration",
            dest="option",
            help="Enable/disable Raspberry Pi configuration options",
        )
        config_group.add_argument(
            "-services",
            action="store_const",
            const="services",
            dest="option",
            help="Only disable unneeded services",
        )
        config_group.add_argument(
            "-packages",
            action="store_const",
            const="packages",
            dest="option",
            help="Only remove unneeded packages",
        )
        parser.set_defaults(option="all")
        return parser


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        PiConfig(args)
        return 0
    except Exception as e:
        # Output anything else nicely formatted on stderr and exit code 1
        sys.exit(f"{__file__}: error: {e}\n")
