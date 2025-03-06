#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

import os
import subprocess
import sys
import tempfile
import textwrap
from argparse import ArgumentParser
from typing import List, Set, Tuple

from .pytrain import PROGRAM_NAME
from .. import is_package, is_linux, get_version

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
    "libgl1",
    "libegl1",
    "mesa-libgallium",
    "bluez",
    "colord",
    "cups",
    "cups-browsed",
    "dbus-org.freedesktop.ModemManager1",
    "firefox",
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


class PiConfig:
    def __init__(self, cmd_line: List[str] = None) -> None:
        if cmd_line:
            args = self.command_line_parser().parse_args(cmd_line)
        else:
            args = self.command_line_parser().parse_args()
        self._args = args
        self.option = args.option
        self.verbose = args.quiet is False
        if is_linux() is False:
            print("This command can only run on Raspberry Pi systems! Exiting...")
            sys.exit(1)
        # do the work
        if self.option == "check":
            self.do_check()
        elif self.option == "version":
            print(f"{self.__class__.__name__} {get_version()}")
        elif self.option == "expand_file_system":
            self.expand_file_system()
        else:
            do_reboot_msg = True
            if self.option == "all":
                cfg, svcs, pkgs = self.do_check("all")
            else:
                cfg = svcs = pkgs = None
            if self.option in {"all", "configuration"}:
                self.optimize_config(cfg)
                do_reboot_msg = False
            if self.option in {"all", "services"}:
                self.optimize_services(svcs)
                do_reboot_msg = False
            if self.option in {"all", "packages"}:
                self.optimize_packages(pkgs)
                do_reboot_msg = False
            if do_reboot_msg:
                print(f"Unknown optimization option: {self.option}")
            else:
                print("Your Pi must now be rebooted (sudo reboot)...")

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
            if do_output:
                print("Checking /boot/firmware/config.txt...", end="")
            lines = self._read_config("/boot/firmware/config.txt")
            if lines:
                bluetooth_disabled = audio_disabled = camera_disabled = display_disabled = False
                for line in lines:
                    if line.startswith("dtoverlay=disable-bt"):
                        bluetooth_disabled = True
                    elif self._contains(line, "dtparam=audio=off", "#dtparam=audio=on", "# dtparam=audio=on"):
                        audio_disabled = True
                    elif self._contains(line, "dtparam=audio=on"):
                        audio_disabled = False
                    elif self._contains(line, "#camera_auto_detect=1", "# camera_auto_detect=1"):
                        camera_disabled = True
                    elif self._contains(line, "camera_auto_detect=1"):
                        camera_disabled = False
                    elif self._contains(line, "#display_auto_detect=1", "# display_auto_detect=1"):
                        display_disabled = True
                    elif self._contains(line, "display_auto_detect=1"):
                        display_disabled = False
                if bluetooth_disabled and audio_disabled and camera_disabled and display_disabled:
                    if do_output:
                        print("...OK")
                elif do_output:
                    cfg.add("config.txt")
                    if self.verbose:
                        print("...FAILED")
                    if bluetooth_disabled is False:
                        print("*** Bluetooth should be disabled ***")
                    if audio_disabled is False:
                        print("*** Audio should be disabled ***")
                    if camera_disabled is False:
                        print("*** Camera Autodetect should be disabled ***")
                    if display_disabled is False:
                        print("*** Display Autodetect should be disabled ***")
                else:
                    cfg.add("config.txt")
            else:
                if do_output:
                    if self.verbose:
                        print("...FAILED")
                    print("*** /boot/firmware/config.txt is empty ***")
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

    def optimize_config(self, cfg: Set[str] = None) -> None:
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
        if (cfg and "config.txt" in cfg) or cfg is None:
            reboot_required = False
            print("Updating /boot/firmware/config.txt...")
            lines = self._read_config("/boot/firmware/config.txt", make_copy=True)
            if lines:
                bluetooth_disabled = False
                newlines = {}
                for i, line in enumerate(lines):
                    if line.startswith("dtoverlay=disable-bt"):
                        bluetooth_disabled = True
                    elif self._contains(line, "dtparam=audio=on"):
                        newlines[i] = "dtparam=audio=off"
                    elif self._contains(line, "camera_auto_detect=1"):
                        newlines[i] = "#camera_auto_detect=1"
                    elif self._contains(line, "display_auto_detect=1"):
                        newlines[i] = "#display_auto_detect=1"
                # replace modified lines
                for k, v in newlines.items():
                    reboot_required = True
                    lines[k] = v

                # disable bluetooth, if needed
                if bluetooth_disabled is False:
                    reboot_required = True
                    lines.append("")
                    lines.append("# Disable Bluetooth")
                    lines.append("dtoverlay=disable-bt")

                if reboot_required:
                    # rewrite the file
                    tmp = tempfile.NamedTemporaryFile()
                    with open(tmp.name, "w") as f:
                        for line in lines:
                            f.write(f"{line}\n")
                    subprocess.run(f"sudo cp -f {tmp.name} /boot/firmware/config.txt".split())
                    print("*** Reboot required to apply changes...")

    def optimize_services(self, svsc: Set[str] = None) -> None:
        if svsc is None or len(svsc) > 0:
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
        else:
            if self.verbose:
                print("No unneeded services found!")

    def optimize_packages(self, pkgs: Set[str] = None):
        if pkgs is None:
            _, _, pkgs = self.do_check("packages")
        if len(pkgs) == 0:
            if self.verbose:
                print("No extraneous packages remain!")
            return

        # hack to deal with squeekboard/labwc issue
        if os.path.isfile("/usr/share/labwc/autostart"):
            pass
        else:
            subprocess.run("sudo mkdir -p /usr/share/labwc".split())
            subprocess.run("sudo touch /usr/share/labwc/autostart".split())

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
    def expand_file_system():
        print("Expanding file system; your Pi will reboot...")
        cmd = "sudo sudo raspi-config --expand-rootfs"
        result = subprocess.run(cmd.split(), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error expanding file system: {result.stderr.strip()}")
        else:
            print("File system expansion complete! Rebooting...")
            subprocess.run("sudo reboot".split(), capture_output=True, text=True)

    def _read_config(self, filename: str = "/boot/firmware/config.txt", make_copy: bool = False) -> List[str]:
        config = list()
        if os.path.exists(filename):
            if make_copy:
                if self.verbose:
                    print(f"Making a backup copy of {filename}: {filename}.bak...")
                subprocess.run(f"sudo cp -f {filename} {filename}.bak".split())
            with open(filename, "r") as f:
                for line in f:
                    config.append(line.strip())
        return config

    def command_line_parser(self) -> ArgumentParser:
        prog = "piconfig" if is_package() else "piconfig.py"
        parser = ArgumentParser(
            prog=prog,
            description=f"Optimize Raspberry Pi for use with {PROGRAM_NAME}",
        )
        config_group = parser.add_mutually_exclusive_group()
        config_group.add_argument(
            "-check",
            action="store_const",
            const="check",
            dest="option",
            help="Check Raspberry Pi configuration (no changes made; default option)",
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
            help="Optimize Raspberry Pi configuration options",
        )

        config_group.add_argument(
            "-packages",
            action="store_const",
            const="packages",
            dest="option",
            help="Optimize packages",
        )
        config_group.add_argument(
            "-services",
            action="store_const",
            const="services",
            dest="option",
            help="Optimize services",
        )
        parser.set_defaults(option="check")

        misc_opts = parser.add_argument_group("Miscellaneous options")
        misc_opts.add_argument(
            "-expand_file_system",
            action="store_const",
            const="expand_file_system",
            dest="option",
            help="Expand file system and reboot",
        )
        misc_opts.add_argument(
            "-quiet",
            action="store_true",
            help="Operate quietly and don't provide feedback",
        )
        misc_opts.add_argument(
            "-version",
            action="version",
            version=f"{self.__class__.__name__} {get_version()}",
            help="Show version and exit",
        )
        return parser

    @staticmethod
    def _contains(line: str, *args: str) -> bool:
        for p in args:
            if line.startswith(p):
                return True
        return False


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        PiConfig(args)
        return 0
    except Exception as e:
        # Output anything else nicely formatted on stderr and exit code 1
        sys.exit(f"{__file__}: error: {e}\n")
