#!/usr/bin/env python3
#
from __future__ import annotations

import argparse
import os
import readline

from datetime import datetime
from typing import List

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
from src.pdi.pdi_listener import PdiListener
from src.pdi.pdi_req import PdiReq, AllReq
from src.pdi.pdi_state_store import PdiStateStore
from src.protocol.command_req import CommandReq
from src.protocol.constants import DEFAULT_SERVER_PORT, CommandScope, BROADCAST_TOPIC, DEFAULT_BASE3_PORT
from src.utils.argument_parser import ArgumentParser, StripPrefixesHelpFormatter

DEFAULT_SCRIPT_FILE: str = "buttons.py"
PROGRAM_NAME: str = "PyTrain"


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
        self._no_ser2 = args.no_ser2
        self._server, self._port = CommBuffer.parse_server(args.server, args.port, args.server_port)
        if args.base3 is not None:
            base3_pieces = args.base3.split(":")
            self._base3_addr = args.base3 = base3_pieces[0]
            self._base3_port = base3_pieces[1] if len(base3_pieces) > 1 else DEFAULT_BASE3_PORT
        else:
            if self._no_ser2:
                raise AttributeError("PyTrain requires either an LCS SER2 and/or Base 3 connection")
            self._base3_addr = self._base3_port = None
        self._pdi_buffer = None
        self._tmcc_buffer = CommBuffer.build(
            baudrate=self._baudrate, port=self._port, server=self._server, no_ser2=self._no_ser2
        )
        listeners = []
        if isinstance(self.buffer, CommBufferSingleton):
            if self._no_ser2:
                print(f"Sending commands directly to Lionel Base 3 at {self._base3_addr}:{self._base3_port}...")
            else:
                print(f"Sending commands directly to Lionel LCS Ser2 on {self._port} {self._baudrate} baud...")
            # listen for client connections
            print(f"Listening for client broadcasts on port {self._args.server_port}...")
            self._receiver = EnqueueProxyRequests(self.buffer, self._args.server_port)
            self._tmcc_listener = CommandListener.build(build_serial_reader=not self._no_ser2)
            listeners.append(self._tmcc_listener)
            if self._base3_addr is not None:
                print(f"Listening for Base3 broadcasts on  {self._base3_addr}:{self._base3_port}...")
                self._pdi_buffer = PdiListener.build(self._base3_addr, self._base3_port)
                listeners.append(self._pdi_buffer)
        else:
            print(f"Sending commands to {PROGRAM_NAME} server at {self._server}:{self._port}...")
            print(f"Listening for state updates on {self._args.server_port}...")
            self._tmcc_listener = ClientStateListener.build()
            listeners.append(self._tmcc_listener)
        # register listeners
        self._state_store: ComponentStateStore = ComponentStateStore(listeners=tuple(listeners))
        if self._args.echo:
            self._handle_echo()
        if self._args.no_listeners is True:
            print("Ignoring events...")
        else:
            print("Registering listeners...")
            self._state_store.listen_for(CommandScope.ENGINE)
            self._state_store.listen_for(CommandScope.TRAIN)
            self._state_store.listen_for(CommandScope.SWITCH)
            self._state_store.listen_for(CommandScope.ACC)

        if self._pdi_buffer is not None:
            print(f"Determining initial system state from Lionel Base 3 at {self._base3_addr}:{self._base3_port}...")
            self._pdi_state_store = PdiStateStore()
            self._get_system_state()

        # Start the command line processor
        self.run()

    def __call__(self, cmd: CommandReq | PdiReq) -> None:
        """
        Callback specified in the Subscriber protocol used to send events to listeners
        """
        if self._echo:
            print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {cmd}")

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
        while True:
            try:
                ui: str = input(">> ")
                readline.add_history(ui)  # provides limited command line recall and editing
                self._handle_command(ui)
            except SystemExit:
                pass
            except argparse.ArgumentError:
                pass
            except KeyboardInterrupt:
                try:
                    CommBuffer.stop()
                except Exception as e:
                    print(f"Error closing command buffer, continuing shutdown: {e}")
                try:
                    CommandListener.stop()
                except Exception as e:
                    print(f"Error closing TMCC listener, continuing shutdown: {e}")
                try:
                    PdiListener.stop()
                except Exception as e:
                    print(f"Error closing PDI listener, continuing shutdown: {e}")
                try:
                    ComponentStateStore.reset()
                except Exception as e:
                    print(f"Error resetting state store, continuing shutdown: {e}")
                try:
                    GpioHandler.reset_all()
                except Exception as e:
                    print(f"Error releasing GPIO, continuing shutdown: {e}")
                break

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
                    if args.command == "pdi":
                        self._do_pdi(ui_parts[1:])
                        return
                    if args.command == "echo":
                        self._handle_echo(ui_parts)
                        return
                    ui_parser = args.command.command_parser()
                    ui_parser.remove_args(["baudrate", "port", "server"])
                    cli_cmd = args.command(ui_parser, ui_parts[1:], False)
                    if cli_cmd.command is None:
                        raise argparse.ArgumentError(None, f"'{ui}' is not a valid command")
                    cli_cmd.send()
                except argparse.ArgumentError as e:
                    print(f"{e}")

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
                        print(f"Error while loading startup script: {e}")
            elif self._startup_script != DEFAULT_SCRIPT_FILE:
                print(f"Startup script file {self._startup_script} not found, continuing...")

    def _query_status(self, param) -> None:
        try:
            if len(param) > 1:
                scope = CommandScope(param[0].upper())
                address = int(param[1])
                state = self._state_store.query(scope, address)
                if state is not None:
                    print(state)
                    return
            print("No data")
        except Exception as e:
            print(e)

    def _handle_echo(self, ui_parts: List[str] = None):
        if ui_parts is None:
            ui_parts = ["echo"]
        if len(ui_parts) == 1 or (len(ui_parts) > 1 and ui_parts[1].lower() == "on"):
            if self._echo is False:
                self._tmcc_listener.listen_for(self, BROADCAST_TOPIC)
                print("TMCC command echoing ENABLED..")
                if self._pdi_buffer:
                    self._pdi_buffer.listen_for(self, BROADCAST_TOPIC)
                    print("PDI command echoing ENABLED")
            self._echo = True
        else:
            if self._echo is True:
                self._tmcc_listener.unsubscribe(self, BROADCAST_TOPIC)
                print("TMCC command echoing DISABLED...")
                if self._pdi_buffer:
                    self._pdi_buffer.unsubscribe(self, BROADCAST_TOPIC)
                    print("PDI command echoing DISABLED")
            self._echo = False

    def _do_pdi(self, param):
        agr = AllReq()
        self._pdi_buffer.enqueue_command(agr)

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
            "-engine", action="store_const", const=EngineCli, dest="command", help="Issue engine/train commands"
        )
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
        description="Send TMCC and Legacy-formatted commands to a Lionel LCS SER2",
        parents=[parser, CliBase.cli_parser()],
    )
    parser.add_argument("-base3", type=str, help="IP Address of Lionel Base 3")
    parser.add_argument("-echo", action="store_true", help="Echo received TMCC commands to console")
    parser.add_argument("-no_listeners", action="store_true", help="Do not listen for events")
    parser.add_argument("-no_ser2", action="store_true", help="Do not send or receive TMCC commands from an LCS SER2")
    parser.add_argument(
        "-server_port",
        type=int,
        default=DEFAULT_SERVER_PORT,
        help=f"Port to use for remote connections, if client (default: {DEFAULT_SERVER_PORT})",
    )
    try:
        PyTrain(parser.parse_args())
    except Exception as ex:
        print(ex)
