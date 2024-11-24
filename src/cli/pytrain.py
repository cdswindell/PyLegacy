#!/usr/bin/env python3
#
from __future__ import annotations

import argparse
import logging.config
import os
import readline
import socket
import threading
from datetime import datetime
from signal import pause
from time import sleep
from typing import List, Tuple, Dict, Any

from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser, ServiceStateChange

from src.cli.acc import AccCli
from src.cli.cli_base import CliBase
from src.cli.dialogs import DialogsCli
from src.cli.effects import EffectsCli
from src.cli.engine import EngineCli
from src.cli.halt import HaltCli
from src.cli.lighting import LightingCli
from src.cli.route import RouteCli
from src.cli.sounds import SoundEffectsCli
from src.cli.switch import SwitchCli
from src.comm.comm_buffer import CommBuffer, CommBufferSingleton
from src.comm.command_listener import CommandListener
from src.comm.enqueue_proxy_requests import EnqueueProxyRequests
from src.db.client_state_listener import ClientStateListener
from src.db.component_state_store import ComponentStateStore
from src.db.startup_state import StartupState
from src.gpio.gpio_handler import GpioHandler
from src.pdi.base_req import BaseReq
from src.pdi.constants import PdiCommand, PDI_SOP
from src.pdi.pdi_listener import PdiListener
from src.pdi.pdi_req import PdiReq, AllReq
from src.pdi.pdi_state_store import PdiStateStore
from src.protocol.command_req import CommandReq
from src.protocol.constants import (
    BROADCAST_TOPIC,
    CommandScope,
    DEFAULT_BASE_PORT,
    DEFAULT_SERVER_PORT,
    PROGRAM_NAME,
    SERVICE_TYPE,
    SERVICE_NAME,
)
from src.utils.argument_parser import ArgumentParser, StripPrefixesHelpFormatter
from src.utils.dual_logging import set_up_logging
from src.utils.ip_tools import get_ip_address

set_up_logging()
log = logging.getLogger(__name__)
# logging.config.fileConfig("logging.ini", disable_existing_loggers=False)

DEFAULT_SCRIPT_FILE: str = "buttons.py"


class ServiceListener:
    @staticmethod
    def remove_service(zeroconf, type_, name):
        pass

    @staticmethod
    def add_service(zeroconf, type_, name):
        pass


class PyTrain:
    def __init__(self, args: argparse.Namespace) -> None:
        self._args = args
        self._startup_script = args.startup_script
        self._baudrate = args.baudrate
        self._port = args.port
        self._listener: CommandListener | ClientStateListener
        self._receiver = None
        self._state_store = None
        self._pdi_store = None
        self._echo = args.echo
        self._headless = args.headless
        self._no_ser2 = args.no_ser2
        self._service_info = None
        self._zeroconf = None
        self._pytrain_servers: List[ServiceInfo] = []
        self._server_discovered = threading.Event()
        self._server, self._port = CommBuffer.parse_server(args.server, args.port, args.server_port)
        self._client = args.client
        if self._server is None and args.client is True:
            # use avahi/zeroconf to locate a PyTrain server on the local network
            # raise exception and exit if none found
            info = self.get_service_info()
            if info is None:
                log.warning(f"No {PROGRAM_NAME} servers found on the local network, exiting")
                return
            self._server, self._port = info
        if args.base is not None:
            base_pieces = args.base.split(":")
            self._base_addr = args.base = base_pieces[0]
            self._base_port = base_pieces[1] if len(base_pieces) > 1 else DEFAULT_BASE_PORT
        else:
            if self._no_ser2:
                raise AttributeError(f"{PROGRAM_NAME} requires either an LCS SER2 and/or Base 2/3 connection")
            self._base_addr = self._base_port = None
        self._pdi_buffer = None
        # Based on the arguments, we are either connecting to n LCS Ser 2 or a named PyTrain server
        self._tmcc_buffer = CommBuffer.build(
            baudrate=self._baudrate, port=self._port, server=self._server, no_ser2=self._no_ser2
        )
        listeners = []
        if isinstance(self.buffer, CommBufferSingleton):
            # register avahi service
            self._zeroconf = Zeroconf()
            self._service_info = self.register_service(
                self._no_ser2 is False,
                self._base_addr is not None,
                self._args.server_port,
            )

            if self._no_ser2:
                print(f"Sending commands directly to Lionel Base at {self._base_addr}:{self._base_port}...")
            else:
                print(f"Sending commands directly to Lionel LCS Ser2 on {self._port} {self._baudrate} baud...")
            # listen for client connections
            print(f"Listening for client requests on port {self._args.server_port}...")
            self._receiver = EnqueueProxyRequests(self.buffer, self._args.server_port)
            self._tmcc_listener = CommandListener.build(ser2_receiver=not self._no_ser2)
            listeners.append(self._tmcc_listener)
            if self._base_addr is not None:
                print(f"Listening for Lionel Base broadcasts on  {self._base_addr}:{self._base_port}...")
                self._pdi_buffer = PdiListener.build(self._base_addr, self._base_port)
                listeners.append(self._pdi_buffer)
        else:
            print(f"Sending commands to {PROGRAM_NAME} server at {self._server}:{self._port}...")
            print(f"Listening for state updates on {self._args.server_port}...")
            self._tmcc_listener = ClientStateListener.build()
            listeners.append(self._tmcc_listener)
        # register listeners
        self._state_store: ComponentStateStore = ComponentStateStore(listeners=tuple(listeners))
        if self._args.echo:
            self.enable_echo()
        if self._args.no_listeners is True:
            print("Ignoring events...")
        else:
            print("Registering listeners...")
            self._state_store.listen_for(CommandScope.ENGINE)
            self._state_store.listen_for(CommandScope.TRAIN)
            self._state_store.listen_for(CommandScope.SWITCH)
            self._state_store.listen_for(CommandScope.ACC)
            self._state_store.listen_for(CommandScope.IRDA)
            self._state_store.listen_for(CommandScope.BASE)
            self._state_store.listen_for(CommandScope.SYNC)

        if self._pdi_buffer is not None:
            cycle = 0
            cursor = {0: "|", 1: "/", 2: "-", 3: "\\"}
            print(f"Loading roster from Lionel Base at {self._base_addr}... {cursor[cycle]}", end="\r")
            self._pdi_state_store = PdiStateStore()
            self._get_system_state()
            sync_state = self._state_store.get_state(CommandScope.SYNC, 99)
            if sync_state is not None:
                while not sync_state.is_synchronized:
                    cycle += 1
                    print(f"Loading roster from Lionel Base at {self._base_addr}... {cursor[cycle % 4]}", end="\r")
                    sleep(0.5)
                print(f"Loading roster from Lionel Base at {self._base_addr} ...Done")
            else:
                print("")

        # register as server so clients can connect without IP addr
        if isinstance(self.buffer, CommBufferSingleton):
            # register avahi service
            self._zeroconf = Zeroconf()
            self._service_info = self.register_service(
                self._no_ser2 is False,
                self._base_addr is not None,
                self._args.server_port,
            )

        # Start the command line processor
        self.run()

    def __call__(self, cmd: CommandReq | PdiReq) -> None:
        """
        Callback specified in the Subscriber protocol used to send events to listeners
        """
        if self._echo:
            log.info(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {cmd}")

    @property
    def is_server(self) -> bool:
        return isinstance(self.buffer, CommBufferSingleton)

    @property
    def is_client(self) -> bool:
        return not self.is_server

    @property
    def buffer(self) -> CommBuffer:
        return self._tmcc_buffer

    def run(self) -> None:
        # process startup script
        self._process_startup_scripts()
        # print opening line
        print(f"{PROGRAM_NAME}, Ver 0.1")
        try:
            while True:
                try:
                    if self._headless:
                        log.warning("Not accepting user input; background mode")
                        pause()  # essentially puts the job into the background
                    else:
                        ui: str = input(">> ")
                        readline.add_history(ui)  # provides limited command line recall and editing
                        self._handle_command(ui)
                except SystemExit:
                    pass
                except argparse.ArgumentError:
                    pass
                except KeyboardInterrupt:
                    try:
                        if self.is_client:
                            self._tmcc_buffer.disconnect()
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
                    break
        finally:
            if self._service_info and self._zeroconf:
                self._zeroconf.unregister_service(self._service_info)
                self._zeroconf.close()

    def _handle_command(self, ui: str) -> None:
        """
        Parse the user's input, reusing the individual CLI command parsers.
        If a valid command is specified, send it to the Lionel LCS SER2.
        """
        if ui is None:
            return
        ui = ui.lower().strip()
        if ui:
            # show help, if user enters '?'
            if ui == "?":
                ui = "h"
            # the argparse library requires the argument string to be presented as a list
            ui_parts = ui.split()
            if ui_parts[0]:
                # parse the first token
                try:
                    # if the keyboard input starts with a valid command, args.command
                    # is set to the corresponding CLI command class, or the verb 'quit'
                    args = self._command_parser().parse_args(["-" + ui_parts[0]])
                    if args.command == "quit":
                        raise KeyboardInterrupt()
                    elif args.command == "help":
                        self._command_parser().parse_args(["-help"])
                    if args.command == "db":
                        self._query_status(ui_parts[1:])
                        return
                    if args.command == "decode":
                        self._decode_command(ui_parts[1:])
                        return
                    if args.command == "pdi":
                        try:
                            self._do_pdi(ui_parts[1:])
                        except Exception as e:
                            log.warning(e)
                        return
                    if args.command == "echo":
                        self._handle_echo(ui_parts)
                        return
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
                    cli_cmd = args.command(ui_parser, ui_parts[1:], False)
                    if cli_cmd.command is None:
                        raise argparse.ArgumentError(None, f"'{ui}' is not a valid command")
                    cli_cmd.send()
                except argparse.ArgumentError as e:
                    log.warning(e)

    def _get_system_state(self):
        self._startup_state = StartupState(self._pdi_buffer, self._pdi_state_store)

    def _process_startup_scripts(self) -> None:
        if self._startup_script is not None:
            if os.path.isfile(self._startup_script):
                print(f"Loading startup script: {self._startup_script}...")
                with open(self._startup_script, mode="r", encoding="utf-8") as script:
                    code = script.read()
                    try:
                        exec(code)
                    except Exception as e:
                        log.error(f"Error loading startup script {self._startup_script} (see logs)")
                        log.exception(e)
            elif self._startup_script != DEFAULT_SCRIPT_FILE:
                log.warning(f"Startup script file {self._startup_script} not found, continuing...")

    def _query_status(self, param) -> None:
        try:
            if len(param) >= 1:
                scope = CommandScope.by_prefix(param[0])
                if scope is not None:
                    if len(param) > 1:
                        address = int(param[1])
                        state = self._state_store.query(scope, address)
                        if state is not None:
                            print(state)
                            return
                    elif scope in self._state_store:
                        for state in self._state_store.get_all(scope):
                            print(state)
                        return
            print("No data")
        except Exception as e:
            log.exception(e)

    def _handle_echo(self, ui_parts: List[str] = None):
        if ui_parts is None:
            ui_parts = ["echo"]
        if len(ui_parts) == 1 or (len(ui_parts) > 1 and ui_parts[1].lower() == "on"):
            if self._echo is False:
                self.enable_echo()
        else:
            if self._echo is True:
                self.disable_echo()

    def disable_echo(self):
        self._tmcc_listener.unsubscribe(self, BROADCAST_TOPIC)
        print("TMCC command echoing DISABLED...")
        if self._pdi_buffer:
            self._pdi_buffer.unsubscribe(self, BROADCAST_TOPIC)
            print("PDI command echoing DISABLED")
        self._echo = False

    def enable_echo(self):
        self._tmcc_listener.listen_for(self, BROADCAST_TOPIC)
        print("TMCC command echoing ENABLED..")
        if self._pdi_buffer:
            self._pdi_buffer.listen_for(self, BROADCAST_TOPIC)
            print("PDI command echoing ENABLED")
        self._echo = True

    def register_service(self, ser2, base3, server_port) -> ServiceInfo:
        port = server_port
        properties = {
            "version": "1.0",
            "Ser2": "1" if ser2 is True else "0",
            "Base3": "1" if base3 is True else "0",
        }
        server_ips = get_ip_address()
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
        try:
            # listens for services on a background thread
            ServiceBrowser(z, [SERVICE_TYPE], handlers=[self.on_service_state_change])
            waiting = 30
            while waiting > 0:
                print(f"Looking for {PROGRAM_NAME} servers{'.' * ((30 - waiting) + 1)}", end="\r")
                waiting -= 1
                if self._server_discovered.wait(1) is True:
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
                        if is_ser2 is True and is_base3 is True:
                            waiting = 0
                            break
                self._server_discovered.clear()
        except Exception as e:
            log.warning(e)
        finally:
            z.close()
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

    def _do_pdi(self, param: List[str]) -> None:
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
            from src.pdi.pdi_device import PdiDevice
            from src.pdi.constants import CommonAction, IrdaAction
            from src.pdi.irda_req import IrdaReq, IrdaSequence

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
                agr = dev.identify(tmcc_id, ident)
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
            self._pdi_buffer.enqueue_command(agr)

    @staticmethod
    def _decode_command(param: List[str]) -> None:
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

    def _command_parser(self) -> ArgumentParser:
        """
        Parse the first token of the user's input
        """
        command_parser = ArgumentParser(
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
        if self.is_server:
            group.add_argument("-pdi", action="store_const", const="pdi", dest="command", help="Sent PDI commands")
        group.add_argument("-route", action="store_const", const=RouteCli, dest="command", help="Fire defined routes")
        group.add_argument(
            "-sounds",
            action="store_const",
            const=SoundEffectsCli,
            dest="command",
            help="Issue engine/train RailSound effects commands",
        )
        group.add_argument("-switch", action="store_const", const=SwitchCli, dest="command", help="Throw switches")
        group.add_argument("-quit", action="store_const", const="quit", dest="command", help=f"Quit {PROGRAM_NAME}")
        return command_parser


if __name__ == "__main__":
    parser = ArgumentParser(add_help=False)
    parser.add_argument(
        "-startup_script",
        type=str,
        default=DEFAULT_SCRIPT_FILE,
        help=f"Run the commands in the specified file at start up (default: {DEFAULT_SCRIPT_FILE})",
    )

    parser = ArgumentParser(
        prog="pytrain.py",
        description="Send TMCC and Legacy-formatted commands to a Lionel Base 3 and/or LCS Ser2",
        parents=[parser, CliBase.cli_parser()],
    )
    parser.add_argument("-base", type=str, help="IP Address of Lionel Base 2/3")
    parser.add_argument("-echo", action="store_true", help="Echo received TMCC/PDI commands to console")
    parser.add_argument("-headless", action="store_true", help="Do not prompt for user input (run in the background)")
    parser.add_argument("-no_listeners", action="store_true", help="Do not listen for events")
    parser.add_argument("-no_ser2", action="store_true", help="Do not send or receive TMCC commands from an LCS SER2")
    parser.add_argument("-client", action="store_true", help=f"Connect to an available {PROGRAM_NAME} server")
    parser.add_argument(
        "-server_port",
        type=int,
        default=DEFAULT_SERVER_PORT,
        help=f"Port to use for remote connections, if client (default: {DEFAULT_SERVER_PORT})",
    )
    try:
        PyTrain(parser.parse_args())
    except Exception as ex:
        log.exception(ex)
