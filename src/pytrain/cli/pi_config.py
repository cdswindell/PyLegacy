import os
import subprocess
import sys
import textwrap
from argparse import ArgumentParser
from typing import List, Set, Tuple

from src.pytrain import PROGRAM_NAME

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
    "ModemManager",
    "bluealsa",
    "bluetooth",
    "colord",
    "cups",
    "cupsd",
    "dbus-org.bluez",
    "dbus-org.freedesktop.ModemManager1",
    "hciuart",
    "lightdm",
    "packagekit",
    "pipewire",
    "pulseaudio",
    "rpi-connect",
    "rpi-connect",
    "rpi-connect-wayvnc",
    "rpi-connect-wayvnc-watcher",
    "rpicam-apps",
]

PACKAGES = [
    "squeekboard",  # must be removed before labwc...
    "bluez",
    "colord",
    "cups",
    "cups-browsed",
    "dbus-org.freedesktop.ModemManager1",
    "labwc",
    "mailcap",
    "mailutils",
    "modemmanager",
    "packagekit",
    "pipewire",
    "pulseaudio",
    "rpi-connect",
    "rpicam-apps",
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
        # do the work
        if self.option == "check":
            self.do_check()
        else:
            if self.option in {"all", "configuration"}:
                self.optimize_config()
            if self.option in {"all", "services"}:
                self.optimize_services()
            if self.option in {"all", "packages"}:
                self.optimize_packages()

    def do_check(self, option: str = "all") -> Tuple[Set[str], Set[str], Set[str]]:
        do_output = self.verbose is True and option == "all"
        cfg: Set[str] = set()
        if option in {"all", "configuration"}:
            if do_output:
                print("Checking Raspberry Pi Configuration...")
            for setting, value in SETTINGS.items():
                if do_output:
                    print(f"Checking {setting}...", end="")
                cmd = f"sudo raspi-config nonint get_{setting}"
                result = subprocess.run(cmd.split(), capture_output=True, text=True)
                if result.returncode == 0:
                    status = result.stdout.strip()
                    if status == str(value):
                        if do_output:
                            print("...OK")
                    else:
                        cfg.add(setting)
                        if do_output:
                            if self.verbose:
                                good = "ENABLED" if int(status) == 0 else "DISABLED"
                                print(f"...FAILED: {good}")
                            else:
                                good = "ENABLED" if value == 0 else "DISABLED"
                                bad = "DISABLED" if good == "ENABLED" else "ENABLED"
                                print(f"!!! {setting} is {bad} ({status}), should be {good} ({value})!!!")
                elif do_output:
                    if self.verbose:
                        print("...ERROR")
                    print(f"*** Check {setting} Error: {result.stderr.strip()} ***")
        # check services
        svsc: Set[str] = set()
        if option in {"all", "services"}:
            if do_output:
                print("\nChecking installed services...")
            for service in SERVICES:
                if do_output:
                    print(f"Checking {service}...", end="")
                cmd = f"sudo systemctl status {service}.service"
                result = subprocess.run(cmd.split(), capture_output=True)
                if result.returncode == 4 or os.path.exists(f"/etc/systemd/system/{service}.service") is False:
                    if do_output:
                        print("...OK")
                else:
                    svsc.add(service)
                    if do_output:
                        if self.verbose:
                            print("...FOUND; can be removed")
                        else:
                            print(
                                f"*** {service} is installed; for {PROGRAM_NAME}, it can be deactivated and removed ***"
                            )
        # check packages
        pkgs: Set[str] = set()
        if option in {"all", "packages"}:
            if do_output:
                print("\nChecking packages...")
            for package in PACKAGES:
                if do_output:
                    print(f"Checking {package}...", end="")
                cmd = f"sudo apt policy {package}"
                result = subprocess.run(cmd.split(), capture_output=True, text=True)
                success = (
                    result.returncode != 0 or len(result.stdout.strip()) == 0 or "Installed: (none)" in result.stdout
                )
                if success:
                    if do_output:
                        print("...OK")
                else:
                    pkgs.add(package)
                    if do_output:
                        if self.verbose:
                            print("...CAN BE REMOVED")
                        else:
                            print(f"*** {package} installed; {PROGRAM_NAME} doesn't require it ***")
        return cfg, svsc, pkgs

    def optimize_config(self) -> None:
        for setting, value in SETTINGS.items():
            cmd = f"sudo raspi-config nonint do_{setting} {value}"
            if self.verbose:
                print(f"Executing: {cmd}...", end="")
            try:
                result = subprocess.run(cmd.split(), capture_output=True)
                if result.returncode == 0:
                    if self.verbose:
                        print("...Done")
                else:
                    print(f"...Failed with code {result.returncode}: {result.stderr.decode('utf-8').strip()}")
            except Exception as e:
                print(e)

    def optimize_services(self) -> None:
        if self.verbose:
            print("Disabling/removing unneeded services...")
        for service in SERVICES:
            results = list()
            if self.verbose:
                print(f"Disabling: {service} service...", end="")
            for sub_cmd in ["stop", "disable"]:
                cmd = f"sudo systemctl {sub_cmd} {service}.service"
                try:
                    results.append(subprocess.run(cmd.split(), capture_output=True))
                except Exception as e:
                    print(f"Error disabling {service}: {e}")
            # delete service file, if it exists
            if os.path.exists(f"/etc/systemd/system/{service}.service"):
                subprocess.run(f"sudo rm -f /etc/systemd/system/{service}.service".split())
            if self.verbose:
                print("...Done")
        # do a daemon reload
        if self.verbose:
            print("Reloading daemon services...")
        subprocess.run("sudo systemctl daemon-reload".split())

    def optimize_packages(self):
        _, _, pkgs = self.do_check("packages")
        if len(pkgs) == 0:
            if self.verbose:
                print("No extraneous packages remain!")
            return
        if self.verbose:
            text = ", ".join(pkgs)
            text = (
                f"The following packages aren't needed to run {PROGRAM_NAME} and will be removed: {text}; "
                f"This may take awhile..."
            )
            print(textwrap.fill(text, width=70))

        cmd = f"sudo apt purge -y {' '.join(pkgs)}"
        try:
            subprocess.run(cmd.split())
        except Exception as e:
            print(f"Error removing packages: {e}")

        if self.verbose:
            print("Removing unused files... This may take a while...")
        r = subprocess.run("sudo apt autoremove --purge -y".split(), capture_output=True, text=True)
        if self.verbose:
            print(r.stdout.strip())
        # cups (printing damon) is particularly pernicious...
        cmd = "sudo find . -name 'cups*' -print | sudo xargs rm -fr"
        r = subprocess.run(cmd.split(), capture_output=True, text=True)
        if self.verbose:
            print(r.stdout.strip())

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
