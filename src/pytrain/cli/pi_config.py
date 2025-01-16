import os
import subprocess
import sys
from argparse import ArgumentParser
from typing import List

SETTINGS = {
    "net_names": 0,
    "i2c": 0,
    "ssh": 0,
    "pi4video": 1,
    "boot_splash": 1,
    "rpi_connect": 1,
    "spi": 1,
    "serial_hw": 1,
    "serial_cons": 1,
    "onewire": 1,
    "rgpio": 1,
}

SERVICES = [
    "hciuart",
    "bluealsa",
    "bluetooth",
    "rpi-connect",
    "rpi-connect-wayvnc",
    "rpi-connect-wayvnc-watcher",
]

# Disable Bluetooth
# dtoverlay=disable-bt

# Enable audio (loads snd_bcm2835)
# dtparam=audio=on   OR
# dtparam=audio=off

# Automatically load overlays for detected cameras
# camera_auto_detect=1

# Automatically load overlays for detected DSI displays
# display_auto_detect=1


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
        if self.option == "check":
            self.do_check()
        else:
            if self.option in {"all", "configuration"}:
                self.optimize_config()
            if self.option in {"all", "services"}:
                self.optimize_services()

    def do_check(self) -> None:
        for setting, value in SETTINGS.items():
            if self.verbose:
                print(f"Checking {setting}...", end="")
            cmd = f"sudo raspi-config nonint get_{setting}"
            result = subprocess.run(cmd.split(), capture_output=True)
            if result.returncode == 0:
                status = result.stdout.decode("utf-8").strip()
                if status == str(value):
                    if self.verbose:
                        print("...OK")
                else:
                    if self.verbose:
                        print(f"...FAILED: {status} != {value}")
                    else:
                        good = "ENABLED" if value == 0 else "DISABLED"
                        bad = "DISABLED" if value == 1 else "ENABLED"
                        print(f"!!! {setting} is {bad} ({status}), should be {good} ({value}!!!")
            else:
                if self.verbose:
                    print("...ERROR")
                print(f"*** Check {setting} Error: {result.stderr.decode('utf-8').strip()} ***")

    def optimize_config(self) -> None:
        for setting, value in SETTINGS.items():
            cmd = f"sudo raspi-config nonint do_{setting} {value}"
            if self.verbose:
                print(f"Executing: {cmd}...", end="")
            try:
                status = os.system(cmd)
                if status == 0:
                    if self.verbose:
                        print("...Done")
                else:
                    print(f"...Failed with status {status}")
            except Exception as e:
                print(e)

    def optimize_services(self) -> None:
        for service in SERVICES:
            for sub_cmd in ["stop", "disable"]:
                cmd = f"sudo systemctl {sub_cmd} {service}.service"
                if self.verbose:
                    print(f"Executing: {cmd}...", end="")
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
            "-check",
            action="store_const",
            const="check",
            dest="option",
            help="Check Raspberry Pi configuration (no changes made)",
        )
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
        parser.set_defaults(option="check")
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
