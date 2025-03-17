#!/usr/bin/env python3

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import logging.config
import os
import readline
import signal
import socket
import subprocess
import sys
import threading
from argparse import ArgumentParser, ArgumentError, SUPPRESS
from datetime import datetime, timedelta
from queue import Queue, Empty
from time import sleep
from timeit import default_timer as timer
from typing import List, Tuple, Dict, Any

from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser, ServiceStateChange

from .acc import AccCli
from .asc2 import Asc2Cli
from .bpc2 import Bpc2Cli
from .dialogs import DialogsCli
from .effects import EffectsCli
from .engine import EngineCli
from .halt import HaltCli
from .lighting import LightingCli
from .route import RouteCli
from .sounds import SoundEffectsCli
from .switch import SwitchCli
from ..comm.comm_buffer import CommBuffer, CommBufferSingleton
from ..comm.command_listener import CommandListener, CommandDispatcher
from ..comm.enqueue_proxy_requests import EnqueueProxyRequests
from ..db.client_state_listener import ClientStateListener
from ..db.component_state import ComponentState
from ..db.component_state_store import ComponentStateStore
from ..db.startup_state import StartupState
from ..gpio.gpio_handler import GpioHandler
from ..pdi.base_req import BaseReq
from ..pdi.constants import PdiCommand, PDI_SOP
from ..pdi.pdi_listener import PdiListener
from ..pdi.pdi_req import PdiReq, AllReq
from ..pdi.pdi_state_store import PdiStateStore
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import (
    BROADCAST_TOPIC,
    CommandScope,
    DEFAULT_BASE_PORT,
    PROGRAM_NAME,
    SERVICE_TYPE,
    SERVICE_NAME,
    DEFAULT_SERVER_PORT,
    DEFAULT_VALID_BAUDRATES,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_QUEUE_SIZE,
    Mixins,
)
from ..protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum
from ..utils.argument_parser import StripPrefixesHelpFormatter, PyTrainArgumentParser
from ..utils.dual_logging import set_up_logging
from ..utils.ip_tools import get_ip_address, find_base_address

DEFAULT_BUTTONS_FILE: str = "buttons.py"
DEFAULT_REPLAY_FILE: str = "replay.txt"
DEFAULT_HISTORY_FILE: str = f".{PROGRAM_NAME.lower()}.history"

ADMIN_COMMAND_TO_ACTION_MAP: Dict[str, CommandDefEnum] = {
    "quit": TMCC1SyncCommandEnum.QUIT,
    "update": TMCC1SyncCommandEnum.UPDATE,
    "upgrade": TMCC1SyncCommandEnum.UPGRADE,
    "restart": TMCC1SyncCommandEnum.RESTART,
    "reboot": TMCC1SyncCommandEnum.REBOOT,
    "shutdown": TMCC1SyncCommandEnum.SHUTDOWN,
}
ACTION_TO_ADMIN_COMMAND_MAP: Dict[CommandDefEnum, str] = {v: k for k, v in ADMIN_COMMAND_TO_ACTION_MAP.items()}


class PyTrain:
    def __init__(self, cmd_line: List[str] = None) -> None:
        from .. import get_version

        if cmd_line:
            args = self.command_line_parser().parse_args(cmd_line)
        else:
            args = self.command_line_parser().parse_args()
        log.debug(f"{PROGRAM_NAME} args: {args}")
        self._args = args
        self._buttons_file = args.buttons_file
        self._replay_file = args.replay_file
        self._baudrate = args.baudrate
        self._port = args.port
        self._listener: CommandListener | ClientStateListener
        self._receiver = None
        self._state_store = None
        self._pdi_store = None
        self._echo = args.echo
        self._headless = args.headless
        self._ser2 = args.ser2
        self._no_wait = args.no_wait
        self._service_info = None
        self._api = False
        self._api_thread = None
        self._command_queue = None
        self._zeroconf = None
        self._pytrain_servers: List[ServiceInfo] = []
        self._server_discovered = threading.Event()
        self._server, self._port = CommBuffer.parse_server(args.server, args.port, args.server_port)
        self._client = args.client
        self._received_admin_cmds = set()
        self._buttons_loader: ButtonsFileLoader | None = None
        self._client_ip = None
        self._server_ips = None
        self._admin_action: CommandDefEnum | None = None
        self._base_addr = self._base_port = None
        self._dispatcher = None
        self._started_at = timer()
        self._exit_status = None
        self._version = get_version()

        #
        # PyTrain servers need to communicate with either a Base 3 or an LCS Ser 2 (or both).
        # Unless we are running as a client, make sure one of those 2 devices is specified
        if args.base is not None:
            if isinstance(args.base, list) and len(args.base):
                base = args.base[0]
            else:
                print("Looking for Lionel Base on local network...")
                base = find_base_address()
                if base is None:
                    raise AttributeError(f"{PROGRAM_NAME} could not find a Lionel Base on the local network")
            base_pieces = base.split(":")
            self._base_addr = args.base = base_pieces[0]
            self._base_port = base_pieces[1] if len(base_pieces) > 1 else DEFAULT_BASE_PORT
            self._client = False  # disable client mode
        elif self._server is None and args.client is True:
            # use avahi/zeroconf to locate a PyTrain server on the local network
            # raise exception and exit if none found
            info = self.get_service_info()
            if info is None:
                raise RuntimeError(f"No {PROGRAM_NAME} servers found on the local network, exiting")
            self._server, self._port = info
            self._server_ips = {self._server}
        elif self._server is not None:
            pass
        else:
            if args.ser2 is False:
                raise AttributeError(f"{PROGRAM_NAME} requires either an LCS SER2 and/or Base 2/3 connection")
            else:
                self._client = False
            self._base_addr = self._base_port = None

        # Based on the arguments, we are either connecting to an LCS Ser 2 or a named PyTrain server
        self._tmcc_buffer = CommBuffer.build(
            baudrate=self._baudrate, port=self._port, server=self._server, ser2=self._ser2 is True
        )

        listeners = []
        self._pdi_buffer = None
        if isinstance(self.tmcc_buffer, CommBufferSingleton):
            # listen for client connections; must be built before CommandListener
            print(f"Listening for client requests on port {self._args.server_port}...")
            self._receiver = EnqueueProxyRequests(self.tmcc_buffer, self._args.server_port)

            # Remember Base 3 address on the comm buffer; it is an object that both
            # clients and servers both have
            self._tmcc_buffer.base3_address = self._base_addr
            self._tmcc_listener = CommandListener.build(
                baudrate=self._baudrate,
                port=self._port,
                ser2_receiver=self._ser2,
                base3_receiver=self._base_addr is not None,
            )
            listeners.append(self._tmcc_listener)

            if self._base_addr is not None:
                print(f"Listening for Lionel Base broadcasts on {self._base_addr}:{self._base_port}...")
                self._pdi_buffer = PdiListener.build(self._base_addr, self._base_port)
                listeners.append(self._pdi_buffer)
                self.tmcc_buffer.is_use_base3 = True

                if self._receiver:
                    self._receiver.base3_dispatcher = self._pdi_buffer

            if self._ser2 is True:
                print("Listening for Lionel LCS Ser2 broadcasts...")

            if self._pdi_buffer or self._ser2 is False:
                print(f"Sending commands directly to Lionel Base at {self._base_addr}:{self._base_port}...")
            else:
                print(f"Sending commands directly to Lionel LCS Ser2 on {self._port} {self._baudrate} baud...")
        else:
            print(f"Sending commands to {PROGRAM_NAME} server at {self._server}:{self._port}...")
            self._tmcc_listener = ClientStateListener.build()
            listeners.append(self._tmcc_listener)
            print(f"Listening for state updates on port {self._tmcc_listener.port}...")
            self._client_ip: str = self._tmcc_buffer.server_ip()
        # register listeners
        self._is_ser2 = args.ser2 is True
        self._is_base = self._base_addr is not None
        self._state_store: ComponentStateStore = ComponentStateStore(
            listeners=tuple(listeners),
            is_base=self._is_base,
            is_ser2=self._is_ser2,
        )
        if self._args.echo:
            self._enable_echo()

        # register server signal handle
        # signal.signal(signal.SIGINT, self._handle_signals)

        print("Registering listeners...")
        self._state_store.listen_for(CommandScope.ENGINE)
        self._state_store.listen_for(CommandScope.TRAIN)
        self._state_store.listen_for(CommandScope.SWITCH)
        self._state_store.listen_for(CommandScope.ROUTE)
        self._state_store.listen_for(CommandScope.ACC)
        self._state_store.listen_for(CommandScope.IRDA)
        self._state_store.listen_for(CommandScope.BASE)
        self._state_store.listen_for(CommandScope.SYNC)
        self._state_store.listen_for(CommandScope.BLOCK)

        # Subscribe this instance of PyTrain to sync updates so we can receive
        # Update and Reboot command directives from clients
        self._tmcc_listener.subscribe(self, CommandScope.SYNC)

        # Command dispatcher should be built by now, get call will throw exception
        # if it is not
        self._dispatcher = CommandDispatcher.get()

        # load roster
        if self._pdi_buffer is not None:
            self._pdi_state_store = PdiStateStore()
            self._get_system_state()
            if self._no_wait is False:  # wait for roster download
                cycle = 0
                cursor = {0: "|", 1: "/", 2: "-", 3: "\\"}
                print(f"Loading roster from Lionel Base at {self._base_addr}... {cursor[cycle]}", end="\r")
                sync_state = self._state_store.get_state(CommandScope.SYNC, 99)
                if sync_state is not None:
                    while not sync_state.is_synchronized:
                        cycle += 1
                        print(f"Loading roster from Lionel Base at {self._base_addr}... {cursor[cycle % 4]}", end="\r")
                        sleep(0.10)
                    print(f"Loading roster from Lionel Base at {self._base_addr} ...Done")
                else:
                    print("")
            else:
                print(f"Loading roster from Lionel Base at {self._base_addr}...")
        elif self.is_client:
            server = f" at: {self._server}" if self._server_ips else ""
            if self._no_wait is False:  # wait for roster download
                cycle = 0
                cursor = {0: "|", 1: "/", 2: "-", 3: "\\"}
                print(f"Loading layout state from {PROGRAM_NAME} server{server}... {cursor[cycle]}", end="\r")
                sync_state = self._state_store.get_state(CommandScope.SYNC, 99)
                if sync_state is not None:
                    while not sync_state.is_synchronized:
                        cycle += 1
                        print(
                            f"Loading layout state from {PROGRAM_NAME} server{server}... {cursor[cycle % 4]}", end="\r"
                        )
                        sleep(0.10)
                    print(f"Loading layout state from {PROGRAM_NAME} server{server}......Done")
                else:
                    print("")
            else:
                print(f"Loading layout state {PROGRAM_NAME} from server{server}...")

        # Start the command line processor; run as thread if we're serving the REST api
        self._command_processor_ev = threading.Event()
        if args.api is True:
            self._api = True
            self._command_queue = Queue(DEFAULT_QUEUE_SIZE)
            self._api_thread: threading.Thread | None = threading.Thread(target=self.run)
            self._api_thread.daemon = True
            self._api_thread.start()
        else:
            self.run()

    def run(self) -> None:
        # print opening line
        log.info(f"{PROGRAM_NAME}, {self._version}")
        # process startup script
        if self._buttons_file:
            self._buttons_loader = ButtonsFileLoader(self._buttons_file)
            self._buttons_loader.join()

        # register as server so clients can connect without IP addr
        if self.is_server:
            self._zeroconf = Zeroconf()
            self._service_info = self.register_service(
                self._ser2 is True,
                self._base_addr is not None,
                self._args.server_port,
            )

        processed_replay = False
        if self._headless:
            log.info("Not accepting keyboard input; background mode")
        try:
            if self._headless is False:
                # provide limited command line recall and editing
                readline.set_auto_history(True)
            while True:
                try:
                    if processed_replay is False and self._replay_file:
                        processed_replay = True
                        if os.path.isfile(self._replay_file):
                            log.info(f"Replaying commands from {self._replay_file}...")
                            with open(self._replay_file, "r") as f:
                                for line in f:
                                    try:
                                        self._handle_command(line)
                                    except SystemExit:
                                        pass
                                    except ArgumentError:
                                        pass
                        else:
                            log.warning(f'Replay file "{self._replay_file}" not found, continuing...')
                    elif self._api:
                        cmd = None
                        try:
                            cmd = self._command_queue.get(block=True)
                            self._handle_command(cmd)
                        except Empty:
                            pass
                        finally:
                            if cmd and self._command_queue:
                                self._command_queue.task_done()
                    elif self._headless:
                        signal.pause()  # essentially puts the job into the background
                    else:
                        ui: str = input(">> ")
                        self._handle_command(ui)
                except SystemExit:
                    pass
                except ArgumentError:
                    pass
                except KeyboardInterrupt:
                    self.shutdown()
                    break
        finally:
            if self._headless is False and self._api is False:
                readline.write_history_file(DEFAULT_HISTORY_FILE)
            self.shutdown_service()
            if self._admin_action in ACTION_TO_ADMIN_COMMAND_MAP:
                if self._admin_action == TMCC1SyncCommandEnum.UPGRADE:
                    self.upgrade()
                elif self._admin_action == TMCC1SyncCommandEnum.UPDATE:
                    self.update()
                elif self._admin_action == TMCC1SyncCommandEnum.RESTART:
                    self.restart()
                elif self._admin_action == TMCC1SyncCommandEnum.REBOOT:
                    self.reboot()
                elif self._admin_action == TMCC1SyncCommandEnum.SHUTDOWN:
                    self.reboot(reboot=False)

    def queue_command(self, cmd: str) -> None:
        if cmd:
            if self._api:
                self._command_queue.put(cmd)
            else:
                self._handle_command(cmd)

    @property
    def exit_status(self) -> PyTrainExitStatus:
        return self._exit_status

    @property
    def tid(self) -> int:
        return threading.get_native_id()

    @property
    def store(self) -> ComponentStateStore:
        return self._state_store

    @property
    def command_dispatcher(self) -> CommandDispatcher:
        return self._dispatcher

    @property
    def tmcc_buffer(self) -> CommBuffer:
        return self._tmcc_buffer

    @classmethod
    def command_line_parser(cls) -> ArgumentParser:
        from .. import is_package, get_version

        prog = "pytrain" if is_package() else "pytrain.py"
        parser = PyTrainArgumentParser(
            prog=prog,
            description="Send TMCC and Legacy-formatted commands to a Lionel Base 3 and/or LCS Ser2",
        )
        mode_group = parser.add_mutually_exclusive_group()
        mode_group.add_argument(
            "-base",
            nargs="*",
            type=str,
            help="Connect to Lionel Base 2/3 or LCS Wi-Fi at IP address (Server mode)",
        )
        mode_group.add_argument(
            "-client",
            action="store_true",
            help=f"Connect to an available {PROGRAM_NAME} server (Client mode)",
        )
        mode_group.add_argument(
            "-server",
            action="store",
            help=f"Connect to {PROGRAM_NAME} server at IP address (Client mode)",
        )
        parser.set_defaults(client=True)
        server_opts = parser.add_argument_group("Client/Server options")
        server_opts.add_argument(
            "-server_port",
            type=int,
            default=DEFAULT_SERVER_PORT,
            help=f"Server port that remote clients connect to (default: {DEFAULT_SERVER_PORT})",
        )
        ser2_opts = parser.add_argument_group("LCS Ser2 options")
        ser2_opts.add_argument(
            "-baudrate",
            action="store",
            type=int,
            choices=DEFAULT_VALID_BAUDRATES,
            default=DEFAULT_BAUDRATE,
            help=f"Baud Rate ({DEFAULT_BAUDRATE})",
        )
        ser2_opts.add_argument(
            "-port",
            action="store",
            default=DEFAULT_PORT,
            help=f"Serial port for LCS Ser2 connection ({DEFAULT_PORT})",
        )
        ser2_opts.add_argument("-ser2", action="store_true", help="Send or receive TMCC commands from an LCS Ser2")
        misc_opts = parser.add_argument_group("Miscellaneous options")
        misc_opts.add_argument("-api", action="store_true", help=SUPPRESS)
        misc_opts.add_argument(
            "-buttons_file",
            type=str,
            nargs="?",
            const=DEFAULT_BUTTONS_FILE,
            help=f"Load button definitions at start up (default file: {DEFAULT_BUTTONS_FILE})",
        )
        misc_opts.add_argument("-echo", action="store_true", help="Echo received TMCC/PDI commands to console")
        misc_opts.add_argument(
            "-headless", action="store_true", help="Do not prompt for user input (run in background),"
        )
        misc_opts.add_argument("-no_wait", action="store_true", help="Do not wait for roster download")
        misc_opts.add_argument(
            "-replay_file",
            type=str,
            nargs="?",
            const=DEFAULT_REPLAY_FILE,
            help=f"Replay {PROGRAM_NAME} commands at start up (default file: {DEFAULT_REPLAY_FILE})",
        )
        misc_opts.add_argument(
            "-version",
            action="version",
            version=f"{cls.__qualname__} {get_version()}",
            help="Show version and exit",
        )
        return parser

    def __call__(self, cmd: CommandReq | PdiReq) -> None:
        """
        Callback specified in the Subscriber protocol used to send events to listeners
        """
        if self._echo:
            log.info(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {cmd}")

        if cmd.command in ACTION_TO_ADMIN_COMMAND_MAP:
            if cmd.command not in self._received_admin_cmds:
                self._received_admin_cmds.add(cmd.command)
                if self.is_client and cmd.command == TMCC1SyncCommandEnum.QUIT:
                    log.info("Client exiting...")
                # record the admin command and send the interrupt signal
                # this will interrupt the comment prompt loop and call
                # the appropriate handler
                self._admin_action = cmd.command
                if self._api_thread:
                    self.shutdown()
                if self.is_api:
                    self._exit_status = PyTrainExitStatus.by_name(self._admin_action.name, raise_exception=False)
                os.kill(os.getpid(), signal.SIGINT)

    def __repr__(self) -> str:
        sc = "Server" if self.is_server else "Client"
        return f"<{PROGRAM_NAME} {sc} {timedelta(seconds=timer() - self._started_at)}>"

    @property
    def is_server(self) -> bool:
        return isinstance(self._tmcc_buffer, CommBufferSingleton)

    @property
    def is_client(self) -> bool:
        return not self.is_server

    @property
    def is_api(self) -> bool:
        return self._api

    @property
    def is_api_active(self) -> bool:
        return self._api is True and self._command_queue is not None and self._api_thread is not None

    def shutdown(self):
        try:
            self.shutdown_service()
        except Exception as e:
            log.warning(f"Error closing zeroconf, continuing shutdown: {e}")
        try:
            if self._api is True and self._command_queue is not None:
                with self._command_queue.mutex:
                    self._command_queue.queue.clear()
                    self._command_queue.all_tasks_done.notify_all()
                    self._command_queue.unfinished_tasks = 0
                    self._command_queue = None
        except Exception as e:
            log.warning(f"Error disconnecting API, continuing shutdown: {e}")
        try:
            if self.is_client:
                self._tmcc_buffer.disconnect(self._tmcc_listener.port)
        except Exception as e:
            log.warning(f"Error disconnecting client, continuing shutdown: {e}")
        try:
            CommBuffer.stop()
        except Exception as e:
            log.warning(f"Error closing command buffer, continuing shutdown: {e}")
        try:
            CommandListener.stop()
        except Exception as e:
            log.warning(f"Error closing TMCC listener, continuing shutdown: {e}")
        try:
            PdiListener.stop()
        except Exception as e:
            log.warning(f"Error closing PDI listener, continuing shutdown: {e}")
        try:
            ComponentStateStore.reset()
        except Exception as e:
            log.warning(f"Error closing state store, continuing shutdown: {e}")
        try:
            GpioHandler.reset_all()
        except Exception as e:
            log.warning(f"Error closing GPIO, continuing shutdown: {e}")

    def do_admin_cmd(self, command: CommandDefEnum, args: List[str] = None):
        cmd = CommandReq(command)
        # special case to see if we want to operate on a different client node
        if args and args[0] not in self._server_ips and args[0] != "me":
            # point to point; command will execute on the specified node
            arg_parts = args[0].split(":")
            addr = arg_parts[0] if len(arg_parts) > 0 else None
            port = int(arg_parts[1]) if len(arg_parts) > 0 else self._port
            print(f"Sending {command.name} request to {addr}:{port}...")
            self._dispatcher.signal_clients(cmd, client=addr, port=port)
            return

        # exit pytrain, signalling the exit behavior by setting
        # self._admin_action to the requested operation
        self._admin_action = command

        # if we're a client, send command to all instances on the client host
        if args and args[0] == "me" and self.is_client:
            # If the client is on the server node, send command to the server
            if self._client_ip in self._server_ips:
                print(f"Sending {command.name} to {PROGRAM_NAME} server...")
                self._tmcc_buffer.enqueue_command(cmd.as_bytes)
            else:
                print(f"Sending {command.name} to all clients on this system ({self._client_ip})...")
                self._tmcc_buffer.enqueue_command(cmd.as_bytes + self._client_ip.encode())
                self._admin_action = None
            return
        elif self.is_server:
            # if server, signal all clients as well as the server
            self._dispatcher.signal_clients(cmd)
        else:
            # send command to server, it will send it to all clients
            # then will execute it on the server itself
            self._tmcc_buffer.enqueue_command(cmd.as_bytes)
        raise KeyboardInterrupt()

    @staticmethod
    def decode_command(param: List[str]) -> None:
        try:
            param = "".join(param).lower().strip()
            if param.startswith("0x"):
                param = param[2:]
            param = param.replace(":", "")
            byte_str = bytes.fromhex(param)
            if byte_str and byte_str[0] == PDI_SOP:
                cmd = PdiReq.from_bytes(byte_str)
            else:
                cmd = CommandReq.from_bytes(byte_str)
            print(f"0x{byte_str.hex()} --> {cmd}")
        except Exception as e:
            log.info(e)

    def reboot(self, reboot: bool = True) -> None:
        if reboot is True:
            msg = "rebooting"
        else:
            msg = "shutting down"
        log.info(f"{'Server' if self.is_server else 'Client'} {msg}...")
        # are we running in API mode? if so, send signal
        if self.is_api:
            self._exit_status = PyTrainExitStatus.REBOOT if reboot is True else PyTrainExitStatus.SHUTDOWN
            raise PyTrainExitException(PyTrainExitStatus.REBOOT if reboot is True else PyTrainExitStatus.SHUTDOWN)
        if reboot is True:
            opt = " -r"
        else:
            opt = ""
        os.system(f"sudo shutdown{opt} now")

    def restart(self) -> None:
        try:
            log.info(f"{'Server' if self.is_server else 'Client'} restarting...")
        except KeyboardInterrupt:
            pass
        self.relaunch(PyTrainExitStatus.RESTART)

    def update(self, do_inform: bool = True) -> None:
        from .. import is_package, PROGRAM_PACKAGE

        if do_inform:
            log.info(f"{'Server' if self.is_server else 'Client'} updating...")
        # always update pip
        os.system(f"cd {os.getcwd()}; pip install -U pip")
        if self.is_api:
            self._exit_status = PyTrainExitStatus.UPDATE
            raise PyTrainExitException(PyTrainExitStatus.UPDATE)

        if is_package():
            # upgrade from Pypi
            os.system(f"cd {os.getcwd()}; pip install -U {PROGRAM_PACKAGE}")
        else:
            # upgrade from github
            os.system(f"cd {os.getcwd()}; git pull")
            os.system(f"cd {os.getcwd()}; pip install -r requirements.txt")
        self.relaunch(PyTrainExitStatus.UPDATE)

    def upgrade(self) -> None:
        log.info(f"{'Server' if self.is_server else 'Client'} upgrading...")
        if sys.platform == "linux":
            os.system("sudo apt update")
            sleep(1)
            os.system("sudo apt upgrade -y")
        if self.is_api:
            self._exit_status = PyTrainExitStatus.UPDATE
            raise PyTrainExitException(PyTrainExitStatus.UPDATE)
        self.update(do_inform=False)

    def relaunch(self, exit_status: PyTrainExitStatus, delay: bool = True) -> None:
        # if we're a client, we need to give the server time to respond, otherwise, we
        # will connect to it as it is shutting down
        if self.is_client is True and delay is True:
            sleep(10)
        # are we running in API mode? if so, send signal
        if self.is_api:
            self._exit_status = exit_status
            raise PyTrainExitException(exit_status)
        # are we a service or run from the commandline?
        if self.is_service is True:
            # restart service
            os.system(f"sudo systemctl restart pytrain_{'server' if self.is_server else 'client'}.service")
        else:
            # rerun commandline pgm
            if self._echo is True and "-echo" not in sys.argv:
                sys.argv.append("-echo")
            elif self._echo is False and "-echo" in sys.argv:
                sys.argv.remove("-echo")
            os.execv(sys.argv[0], sys.argv)

    @property
    def is_service(self) -> bool:
        from .. import is_linux

        if is_linux() is False:
            return False
        service = f"pytrain_{'server' if self.is_server else 'client'}.service"
        stat = subprocess.call(f"systemctl is-active --quiet {service}".split())
        return stat == 0

    def register_service(self, ser2, base3, server_port) -> ServiceInfo:
        port = server_port
        properties = {
            "version": "1.0",
            "Ser2": "1" if ser2 is True else "0",
            "Base3": "1" if base3 is True else "0",
        }
        self._server_ips = server_ips = get_ip_address()
        hostname = socket.gethostname()
        hostname = hostname if hostname.endswith(".local") else hostname + ".local"

        # Create the ServiceInfo object
        info = ServiceInfo(
            SERVICE_TYPE,
            SERVICE_NAME,
            addresses=[socket.inet_aton(x) for x in server_ips],
            port=port,
            properties=properties,
            server=hostname,
        )
        # register this machine as serving PyTrain, allowing clients to connect for state updates
        self._zeroconf.register_service(info, allow_name_change=True)
        log.info(f"{PROGRAM_NAME} Service registered successfully!")
        return info

    def update_service(self, update: Dict[str, Any]) -> None:
        self._zeroconf.unregister_service(self._service_info)
        for prop, value in update.items():
            self._service_info.properties[prop.encode("utf-8")] = str(value).encode("utf-8")
        self._zeroconf.register_service(self._service_info)

    def get_service_info(self) -> Tuple[str, int] | None:
        z = Zeroconf()
        an_info = None
        base3_info = None
        try:
            # listens for services on a background thread
            ServiceBrowser(z, [SERVICE_TYPE], handlers=[self.on_service_state_change])
            found_at = -1
            waiting = 240
            cursor = {0: "|", 1: "\\", 2: "-", 3: "/"}
            while waiting > 0:
                print(f"Looking for {PROGRAM_NAME} servers {cursor[waiting % 4]}", end="\r")
                waiting -= 1
                if self._server_discovered.wait(0.5) is True:
                    for info in self._pytrain_servers:
                        is_ser2 = False
                        is_base3 = False
                        an_info = info
                        for prop, value in info.properties.items():
                            decoded_prop = prop.decode("utf-8")
                            decoded_value = value.decode("utf-8") if value is not None else None
                            if decoded_prop == "Ser2":
                                is_ser2 = decoded_value == "1"
                            elif decoded_prop == "Base3":
                                is_base3 = decoded_value == "1"
                        if is_base3 is True:
                            base3_info = info
                        if is_ser2 is True and is_base3 is True:
                            waiting = 0
                            break
                if found_at < 0:
                    found_at = waiting
                if base3_info and (found_at - waiting) / 2 > 15:
                    # if we found a server with a base 3, and more than
                    # 15 seconds have passed, return it
                    an_info = base3_info
                    break
                self._server_discovered.clear()
        except Exception as e:
            log.warning(e)
        finally:
            z.close()
            print()
        if an_info:
            return an_info.parsed_addresses()[0], an_info.port
        else:
            return None

    def on_service_state_change(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ):
        log.debug(f"Service {name} of type {service_type} state changed: {state_change}")
        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                self._pytrain_servers.append(info)
                self._server_discovered.set()

    def shutdown_service(self):
        if self._service_info and self._zeroconf:
            self._zeroconf.unregister_service(self._service_info)
            self._zeroconf.close()
            self._service_info = self._zeroconf = None

    def parse_cli(self, command_line: str) -> str | None:
        """
        Parse a command line to determine ig it's a valid command, if so,
        return the command. If not, return an informative error message
        """
        # get the first token and check it for pytrain-specific command
        token = command_line.split()[0] if command_line else None
        if token is None:
            return "No command specified."
        # is token an admin command?
        if token.lower() in ADMIN_COMMAND_TO_ACTION_MAP:
            return f"Unrecognized command: {token}"

        # call _handle_command to do the command parsing
        return self._handle_command(command_line, parse_only=True)

    def _handle_command(self, ui: str, parse_only: bool = False) -> str | CommandReq | None:
        """
        Parse the user's input, reusing the individual CLI command parsers.
        If a valid command is specified, send it to the Lionel LCS SER2.
        """
        if ui is None:
            return "No command specified."
        ui = ui.lower().strip()
        if ui:
            # show help, if user enters '?'
            if ui == "?":
                ui = "h"
            # the argparse library requires the argument string to be presented as a list
            ui_parts = ui.split()
            if ui_parts[0]:
                # parse the first token
                ui_parser = None
                try:
                    # if the keyboard input starts with a valid command, args.command
                    # is set to the corresponding CLI command class, or the verb 'quit'
                    args = self._command_parser().parse_args(["-" + ui_parts[0]])
                    if parse_only is False and args.command == "quit":
                        # if server, signal clients to disconnect
                        if self.is_server:
                            self._dispatcher.signal_clients()
                        elif self.is_client and len(ui_parts) > 1 and ui_parts[1] == "server":
                            # signal server to quit
                            print(f"Sending Quit request to {PROGRAM_NAME} server...")
                            cmd = CommandReq(ADMIN_COMMAND_TO_ACTION_MAP.get("quit"))
                            self._tmcc_buffer.enqueue_command(cmd.as_bytes)
                            return None
                        # if client quits, remaining nodes continue to run
                        raise KeyboardInterrupt()
                    elif parse_only is False and args.command in ADMIN_COMMAND_TO_ACTION_MAP:
                        self.do_admin_cmd(ADMIN_COMMAND_TO_ACTION_MAP.get(args.command), ui_parts[1:])
                        return None
                    elif parse_only is False and args.command == "help":
                        self._command_parser().parse_args(["-help"])
                    if parse_only is False and args.command == "db":
                        self._do_db(ui_parts[1:])
                        return None
                    if parse_only is False and args.command == "decode":
                        self.decode_command(ui_parts[1:])
                        return None
                    if parse_only is False and args.command == "pdi":
                        try:
                            self._do_pdi(ui_parts[1:])
                        except Exception as e:
                            log.warning(e)
                        return None
                    if parse_only is False and args.command == "echo":
                        self._handle_echo(ui_parts)
                        return None
                    if parse_only is False and args.command == "uptime":
                        print(timedelta(seconds=timer() - self._started_at))
                        return None
                    if parse_only is False and args.command == "version":
                        print(f"{PROGRAM_NAME} {self._version}")
                        return None
                    #
                    # we're done with the admin/special commands, now do train stuff
                    #
                    ui_parser = args.command.command_parser()
                    ui_parser.remove_args(["baudrate", "port", "server"])
                    # very hacky; should turn into a method to reduce complexity of this section
                    # if the user entered "tr....", treat this as a train command
                    # normally, this is done by adding the "-train" token after the tmcc_id but
                    # before any subparsers
                    if "train".startswith(ui_parts[0].strip().lower()) and len(ui_parts) > 2:
                        has_train_arg = False
                        for token in ui_parts[2:]:
                            if token.startswith("-"):
                                if "-train".startswith(token.lower()):
                                    has_train_arg = True
                                    break
                            else:
                                break  # we're into a subparser
                        if has_train_arg is False:
                            ui_parts.insert(2, "-train")
                    if parse_only is True and isinstance(ui_parser, PyTrainArgumentParser):
                        # TODO: provide tool to get usage text
                        ui_parser.clear_exit_on_error()
                    cli_cmd = args.command(ui_parser, ui_parts[1:], False)
                    if cli_cmd.command is None:
                        raise ArgumentError(None, f"'{ui}' is not a valid command")
                    if parse_only is True and isinstance(ui_parser, PyTrainArgumentParser):
                        return cli_cmd.command.command_req
                    cli_cmd.send()
                except ArgumentError as e:
                    if parse_only is True:
                        return e.message
                    log.warning(e)
                finally:
                    if ui_parser and parse_only is True:
                        ui_parser.reset_exit_on_error()

    def _get_system_state(self):
        self._startup_state = StartupState(self._pdi_buffer, self._pdi_state_store)

    def _do_db(self, param) -> None:
        try:
            if len(param) >= 1:
                scope = CommandScope.by_prefix(param[0])
                if scope is not None:
                    if len(param) > 1:
                        address = int(param[1])
                        state: ComponentState = self._state_store.query(scope, address)
                        if state is not None:
                            print(state)
                            return
                    elif scope in self._state_store:
                        for state in self._state_store.get_all(scope):
                            print(state)
                        return
            else:
                keys = self._state_store.keys()
                if keys:
                    for key in keys:
                        if key in {CommandScope.BASE, CommandScope.SYNC, CommandScope.IRDA}:
                            continue
                        num = len(self._state_store.keys(key))
                        print(f"{key.label}s: {num}")
                    return
            print("No data")
        except Exception as e:
            log.exception(e)

    def _handle_echo(self, ui_parts: List[str] = None):
        if ui_parts is None:
            ui_parts = ["echo"]
        if len(ui_parts) == 1 or (len(ui_parts) > 1 and ui_parts[1].lower() == "on"):
            if self._echo is False:
                self._enable_echo()
        else:
            if self._echo is True:
                self._disable_echo()

    def _disable_echo(self):
        self._tmcc_listener.unsubscribe(self, BROADCAST_TOPIC)
        print("TMCC command echoing DISABLED...")
        if self._pdi_buffer:
            self._pdi_buffer.unsubscribe(self, BROADCAST_TOPIC)
        print("PDI command echoing DISABLED")
        self._echo = False

    def _enable_echo(self):
        self._tmcc_listener.listen_for(self, BROADCAST_TOPIC)
        print("TMCC command echoing ENABLED..")
        if self._pdi_buffer:
            self._pdi_buffer.listen_for(self, BROADCAST_TOPIC)
        print("PDI command echoing ENABLED")
        self._echo = True

    def _do_pdi(self, param: List[str]) -> None:
        # if self._pdi_buffer is None:
        #     raise AttributeError("Not connected to a Lionel Base 3, PDI commands not enabled...")
        param_len = len(param)
        agr = None
        if param_len == 1:
            if param[0].lower().startswith("re"):
                self._get_system_state()
            elif param[0].lower().startswith("ba"):
                agr = BaseReq(0, PdiCommand.BASE)
        elif param_len == 2:
            if param[0].lower().startswith("e"):
                agr = BaseReq(int(param[1]), PdiCommand.BASE_ENGINE)
            elif param[0].lower().startswith("t"):
                agr = BaseReq(int(param[1]), PdiCommand.BASE_TRAIN)
            elif param[0].lower().startswith("a"):
                agr = BaseReq(int(param[1]), PdiCommand.BASE_ACC)
            elif param[0].lower().startswith("s"):
                agr = BaseReq(int(param[1]), PdiCommand.BASE_SWITCH)
            elif param[0].lower().startswith("r"):
                agr = BaseReq(int(param[1]), PdiCommand.BASE_ROUTE)
        elif param_len >= 3:
            from ..pdi.pdi_device import PdiDevice
            from ..pdi.constants import CommonAction, IrdaAction
            from ..pdi.irda_req import IrdaReq, IrdaSequence

            dev = PdiDevice.by_prefix(param[0])
            if dev is None:
                raise AttributeError(f"Device '{param[0]}' not defined")
            tmcc_id = int(param[1])
            ca = CommonAction.by_prefix(param[2])
            if ca is None:
                ca = dev.value.enums.by_prefix(param[2])
                if ca is None:
                    raise AttributeError(f"Action '{param[2]}' not valid")
            if ca == CommonAction.FIRMWARE:
                agr = dev.firmware(tmcc_id)
            elif ca == CommonAction.STATUS:
                agr = dev.status(tmcc_id)
            elif ca == CommonAction.INFO:
                agr = dev.info(tmcc_id)
            elif ca == CommonAction.CONFIG:
                agr = dev.config(tmcc_id)
            elif ca == CommonAction.IDENTIFY:
                ident = 1
                if tmcc_id < 0:
                    ident = 0
                    tmcc_id = -tmcc_id
                agr = dev.identify(tmcc_id, ident=ident)
            elif ca == CommonAction.CLEAR_ERRORS:
                agr = dev.clear_errors(tmcc_id)
            elif ca == CommonAction.RESET:
                agr = dev.reset(tmcc_id)
            elif ca == IrdaAction.SEQUENCE:
                if param_len > 3:
                    seq = IrdaSequence.by_prefix(param[3])
                    if seq is None and param[3].isnumeric():
                        seq = IrdaSequence.by_value(int(param[3]))
                    if seq is None:
                        raise AttributeError(f"Sequence '{param[3]}' is invalid")
                    agr = IrdaReq(tmcc_id, PdiCommand.IRDA_SET, ca, sequence=seq)
            elif ca is not None:
                agr = dev.build_req(tmcc_id, ca)
        else:
            agr = AllReq()
        if agr is not None:
            if self.is_server:
                self._pdi_buffer.enqueue_command(agr)
            else:
                self._tmcc_buffer.enqueue_command(agr.as_bytes)

    @staticmethod
    def _command_parser() -> ArgumentParser:
        """
        Parse the first token of the user's input
        """
        command_parser = PyTrainArgumentParser(
            prog="",
            description="Valid commands:",
            epilog="Commands can be abbreviated, so long as they are unique; e.g., 'en', "
            "or 'eng' are the same as typing 'engine'. Help on a specific command "
            "is also available by typing the command name (or abbreviation), "
            "followed by '-h', e.g., 'sw -h'",
            formatter_class=StripPrefixesHelpFormatter,
            exit_on_error=False,
        )
        group = command_parser.add_mutually_exclusive_group()
        group.add_argument(
            "-accessory", action="store_const", const=AccCli, dest="command", help="Issue accessory commands"
        )
        group.add_argument("-asc2", action="store_const", const=Asc2Cli, dest="command", help="Issue Asc2 commands")
        group.add_argument("-bpc2", action="store_const", const=Bpc2Cli, dest="command", help="Issue Bpc2 commands")
        group.add_argument(
            "-db", action="store_const", const="db", dest="command", help="Query engine/train/switch/accessory state"
        )
        group.add_argument(
            "-decode", action="store_const", const="decode", dest="command", help="Decode TMCC command bytes"
        )
        group.add_argument(
            "-dialogs", action="store_const", const=DialogsCli, dest="command", help="Trigger RailSounds dialogs"
        )
        group.add_argument(
            "-echo", action="store_const", const="echo", dest="command", help="Enable/disable TMCC command echoing"
        )
        group.add_argument(
            "-effects",
            action="store_const",
            const=EffectsCli,
            dest="command",
            help="Issue engine/train effects commands",
        )
        group.add_argument(
            "-engine", action="store_const", const=EngineCli, dest="command", help="Issue engine commands"
        )
        group.add_argument("-train", action="store_const", const=EngineCli, dest="command", help="Issue train commands")
        group.add_argument("-halt", action="store_const", const=HaltCli, dest="command", help="Emergency stop")
        group.add_argument(
            "-lighting",
            action="store_const",
            const=LightingCli,
            dest="command",
            help="Issue engine/train lighting effects commands",
        )
        group.add_argument("-pdi", action="store_const", const="pdi", dest="command", help="Sent PDI commands")
        group.add_argument("-quit", action="store_const", const="quit", dest="command", help=f"Quit {PROGRAM_NAME}")
        group.add_argument(
            "-reboot",
            action="store_const",
            const="reboot",
            dest="command",
            help=f"Quit {PROGRAM_NAME} and reboot all nodes,",
        )
        group.add_argument(
            "-restart",
            action="store_const",
            const="restart",
            dest="command",
            help=f"Quit {PROGRAM_NAME} and restart on all nodes,",
        )
        group.add_argument("-route", action="store_const", const=RouteCli, dest="command", help="Fire defined routes")
        group.add_argument(
            "-shutdown",
            action="store_const",
            const="shutdown",
            dest="command",
            help=f"Quit {PROGRAM_NAME} and shutdown all nodes",
        )
        group.add_argument(
            "-sounds",
            action="store_const",
            const=SoundEffectsCli,
            dest="command",
            help="Issue engine/train RailSound effects commands",
        )
        group.add_argument("-switch", action="store_const", const=SwitchCli, dest="command", help="Throw switches")

        group.add_argument(
            "-update",
            action="store_const",
            const="update",
            dest="command",
            help=f"Quit {PROGRAM_NAME} and update all nodes to latest release,",
        )
        group.add_argument(
            "-upgrade",
            action="store_const",
            const="upgrade",
            dest="command",
            help=f"Quit {PROGRAM_NAME}, upgrade the OS on all nodes, and update to latest release,",
        )
        group.add_argument(
            "-uptime",
            action="store_const",
            const="uptime",
            dest="command",
            help=f"Elapsed time this instance of {PROGRAM_NAME} has been active,",
        )
        group.add_argument(
            "-version",
            action="store_const",
            const="version",
            dest="command",
            help=f"Show current {PROGRAM_NAME} version,",
        )
        return command_parser


class ButtonsFileLoader(threading.Thread):
    """
    We run the startup-script reader so that we can continue with
    main program execution while the script is loading
    """

    def __init__(self, buttons_file: str) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Buttons Script Loader")
        self._buttons_file = buttons_file
        self.start()

    def run(self) -> None:
        if os.path.isfile(self._buttons_file):
            print(f"Loading buttons file: {self._buttons_file}...")
            with open(self._buttons_file, mode="r", encoding="utf-8") as script:
                code = script.read()
                try:
                    exec(code)
                    print("Buttons registered...")
                except Exception as e:
                    log.error(f"Problem loading buttons file {self._buttons_file} (see logs)")
                    log.exception(e)
        else:
            log.warning(f'Buttons file "{self._buttons_file}" not found, continuing...')


class PyTrainExitStatus(Mixins):
    QUIT = 0
    REBOOT = 11
    RESTART = 12
    SHUTDOWN = 13
    UPDATE = 14
    UPGRADE = 15


class PyTrainExitException(Exception):
    def __init__(self, reason: PyTrainExitStatus) -> None:
        super().__init__(f"PyTrain Exiting: {reason.name}")
        self.reason = reason


set_up_logging()
log = logging.getLogger(__name__)
