"""Connect the Qt management panel to the PyTrain runtime."""

from ipaddress import ip_address
from socket import AF_INET
from threading import Thread

import psutil
from PySide6.QtCore import QObject, Property, Signal, Slot

from pytrain import get_version
from pytrain.cli.pytrain import PyTrain
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum as Sync
from pytrain.utils.flatpak_updates import check_flatpak_update, installed_flatpak_tag, request_flatpak_update
from pytrain.utils.host_info import HostInfo, is_linux, is_steam_deck
from pytrain.utils.update_policy import self_update_disabled


class AdminController(QObject):
    changed = Signal()
    finished = Signal(str)
    exitRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._runtime = PyTrain.current(raise_exception=False)
        self._flatpak_tag = installed_flatpak_tag()
        self._deck = is_steam_deck()
        self._pi = is_linux() and HostInfo().is_pi
        self._updates_disabled = self_update_disabled()
        self._busy = False
        self._status = ""
        self.finished.connect(self._finish)

    @Property(str, constant=True)
    def version(self) -> str:
        role = "Server" if self._runtime and self._runtime.is_server else "Client"
        version = self._flatpak_tag or f"v{get_version()}"
        return f"PyTrain {role} {version}"

    @Property(str, notify=changed)
    def layoutName(self) -> str:
        state = ComponentStateStore.get_state(CommandScope.BASE, 0, create=False)
        return getattr(state, "base_name", None) or ""

    @Property(str, notify=changed)
    def addresses(self) -> str:
        try:
            interfaces = psutil.net_if_addrs()
        except OSError:
            return "Unavailable"
        addresses = [
            address.address
            for entries in interfaces.values()
            for address in entries
            if address.family == AF_INET and not ip_address(address.address).is_loopback
        ]
        return ", ".join(dict.fromkeys(addresses)) or "Unavailable"

    @Property(bool, notify=changed)
    def synchronized(self) -> bool:
        return bool(self._runtime and self._runtime.is_synchronized())

    @Property(str, notify=changed)
    def databaseStatus(self) -> str:
        if self.synchronized:
            return "Loaded"
        state = ComponentStateStore.get_state(CommandScope.SYNC, 99, create=False)
        return "Reloading…" if state is not None and state.is_synchronizing() else "Unavailable"

    @Property(bool, notify=changed)
    def logging(self) -> bool:
        return bool(self._runtime and self._runtime.echo)

    @Property(bool, notify=changed)
    def debugging(self) -> bool:
        return bool(self._runtime and self._runtime.debug)

    @Property(str, notify=changed)
    def status(self) -> str:
        return self._status

    @Slot()
    def refresh(self) -> None:
        self.changed.emit()

    @Slot(bool)
    def setLogging(self, enabled: bool) -> None:
        if self._runtime is not None:
            self._runtime.echo = enabled
            if not enabled:
                self._runtime.debug = False
            self.changed.emit()

    @Slot(bool)
    def setDebugging(self, enabled: bool) -> None:
        if self._runtime is not None and self.logging:
            self._runtime.debug = enabled
            self.changed.emit()

    @Slot(str, bool, result=bool)
    def canRun(self, name: str, all_nodes: bool) -> bool:
        if self._runtime is None or self._busy:
            return False
        if name == "RESYNC":
            return self.synchronized
        if name in {"REBOOT", "SHUTDOWN"} and self._flatpak_tag and not all_nodes:
            return False
        if name == "UPGRADE":
            return not self._deck and not self._updates_disabled and (self._pi or all_nodes)
        if name == "UPDATE":
            return bool(self._flatpak_tag) or not self._updates_disabled
        return name in {"RESTART", "REBOOT", "SHUTDOWN", "QUIT"}

    @Slot(str, bool)
    def run(self, name: str, all_nodes: bool) -> None:
        if not self.canRun(name, all_nodes):
            return
        self._busy = True
        self._status = ""
        self.changed.emit()
        Thread(target=self._dispatch, args=(Sync[name], all_nodes), daemon=True).start()

    def _dispatch(self, command: Sync, all_nodes: bool) -> None:
        runtime = self._runtime
        message = ""
        try:
            if command == Sync.RESYNC:
                CommandReq.build(command).send()
            elif self._flatpak_tag and command == Sync.UPDATE:
                if all_nodes:
                    runtime.broadcast_update_to_other_nodes()
                if check_flatpak_update(self._flatpak_tag).available:
                    marker = request_flatpak_update()
                    try:
                        runtime.request_local_restart()
                    except Exception:
                        marker.unlink(missing_ok=True)
                        raise
                elif all_nodes and runtime.is_client:
                    runtime.request_local_restart()
                else:
                    message = "PyCab is up to date"
            elif self._flatpak_tag and command == Sync.RESTART and not all_nodes:
                runtime.request_local_restart()
            elif runtime.is_server and (not self._flatpak_tag or command == Sync.QUIT):
                runtime.request_gui_server_action(command, broadcast=True)
                self.exitRequested.emit()
            elif all_nodes:
                CommandReq.build(command).send()
            else:
                runtime.do_admin_cmd(command, ["me"])
        except KeyboardInterrupt:
            self.exitRequested.emit()
        except Exception as exc:
            message = str(exc) or "Unable to complete the request"
        self.finished.emit(message)

    @Slot(str)
    def _finish(self, message: str) -> None:
        self._status = message
        self._busy = False
        self.changed.emit()
