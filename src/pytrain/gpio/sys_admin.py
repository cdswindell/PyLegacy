#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from gpiozero import Button

from ..protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum
from .gpio_device import GpioDevice, P


class SystemAdmin(GpioDevice):
    def __init__(self):
        super().__init__()

    def shutdown(
        self,
        shutdown_pin: P,
        hold_time: float = 5,
    ) -> Button:
        """
        Send the system shutdown command to all nodes
        """
        cmd, shutdown_btn, led = self.make_button(shutdown_pin, TMCC1SyncCommandEnum.SHUTDOWN, hold_time=hold_time)
        shutdown_btn.when_held = cmd.as_action()
        return shutdown_btn

    def reboot(
        self,
        reboot_pin: P,
        hold_time: float = 5,
    ) -> Button:
        """
        Send the system restart command to all nodes
        """
        cmd, reboot_btn, led = self.make_button(reboot_pin, TMCC1SyncCommandEnum.REBOOT, hold_time=hold_time)
        reboot_btn.when_held = cmd.as_action()
        return reboot_btn

    def restart(
        self,
        restart_pin: P,
        hold_time: float = 5,
    ) -> Button:
        """
        Send the system restart command to all nodes
        """
        cmd, restart_btn, led = self.make_button(restart_pin, TMCC1SyncCommandEnum.RESTART, hold_time=hold_time)
        restart_btn.when_held = cmd.as_action()
        return restart_btn

    def update(
        self,
        update_pin: P,
        hold_time: float = 5,
    ) -> Button:
        """
        Send the system update command to all nodes
        """
        cmd, update_btn, led = self.make_button(update_pin, TMCC1SyncCommandEnum.UPDATE, hold_time=hold_time)
        update_btn.when_held = cmd.as_action()
        return update_btn

    def upgrade(
        self,
        upgrade_pin: P,
        hold_time: float = 5,
    ) -> Button:
        """
        Send the system upgrade command to all nodes
        """
        cmd, upgrade_btn, led = self.make_button(upgrade_pin, TMCC1SyncCommandEnum.UPGRADE, hold_time=hold_time)
        upgrade_btn.when_held = cmd.as_action()
        return upgrade_btn

    def resync(
        self,
        resync_pin: P,
        hold_time: float = None,
    ) -> Button:
        """
        Send the resync state command to server
        """
        cmd, resync_btn, led = self.make_button(resync_pin, TMCC1SyncCommandEnum.RESYNC, hold_time=hold_time)
        if hold_time:
            resync_btn.when_held = cmd.as_action()
        else:
            resync_btn.when_pressed = cmd.as_action()
        return resync_btn
