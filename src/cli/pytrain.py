#!/usr/bin/env python3
#
import argparse
import os
import readline

from src.cli.cli_base import cli_parser
from src.cli.acc import AccCli
from src.cli.effects import EffectsCli
from src.cli.engine import EngineCli
from src.cli.halt import HaltCli
from src.cli.lighting import LightingCli
from src.cli.route import RouteCli
from src.cli.sounds import SoundEffectsCli
from src.cli.switch import SwitchCli
from src.comm.comm_buffer import CommBuffer, CommBufferSingleton
from src.comm.enqueue_proxy_requests import EnqueueProxyRequests
from src.gpio.gpio_handler import GpioHandler
from src.protocol.constants import DEFAULT_SERVER_PORT
from src.utils.argument_parser import ArgumentParser, StripPrefixesHelpFormatter

DEFAULT_SCRIPT_FILE: str = "buttons.py"
PROGRAM_NAME: str = "PyTrain"


class PyTrain:
    def __init__(self, args: argparse.Namespace) -> None:
        self._args = args
        self._startup_script = args.startup_script
        self._baudrate = args.baudrate
        self._server, self._port = CommBuffer.parse_server(args.server, args.port, args.server_port)
        self._comm_buffer = CommBuffer.build(baudrate=self._baudrate,
                                             port=self._port,
                                             server=self._server)
        if isinstance(self.buffer, CommBufferSingleton):
            print("Sending commands directly to Lionel LCS Ser2...")
            # listen for client connections, unless user used --no_clients flag
            if not self._args.no_clients:
                print(f"Listening for client connections on port {self._args.server_port}...")
                self.receiver_thread = EnqueueProxyRequests(self.buffer, self._args.server_port)
        else:
            print(f"Sending commands to {PROGRAM_NAME} server at {self._server}:{self._port}...")
        self.run()

    @property
    def buffer(self) -> CommBuffer:
        return self._comm_buffer

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
                    self._comm_buffer.shutdown()
                except Exception as e:
                    print(f"Error closing command buffer, continuing shutdown: {e}")
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
            if ui == '?':
                ui = 'h'
            # the argparse library requires the argument string to be presented as a list
            ui_parts = ui.split()
            if ui_parts[0]:
                # parse the first token
                try:
                    # if the keyboard input starts with a valid command, args.command
                    # is set to the corresponding CLI command class, or the verb 'quit'
                    args = self._command_parser().parse_args(['-' + ui_parts[0]])
                    if args.command == 'quit':
                        raise KeyboardInterrupt()
                    elif args.command == 'help':
                        self._command_parser().parse_args(["-help"])
                    ui_parser = args.command.command_parser()
                    ui_parser.remove_args(['baudrate', 'port', 'server'])
                    cmd = args.command(ui_parser, ui_parts[1:], False).command
                    if cmd is None:
                        return
                    cmd.send(buffer=self.buffer)
                except argparse.ArgumentError:
                    print(f"'{ui}' is not a valid command")
                    return

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

    @staticmethod
    def _command_parser() -> ArgumentParser:
        """
            Parse the first token of the user's input
        """
        command_parser = ArgumentParser(prog="",
                                        description="Valid commands:",
                                        epilog="Commands can be abbreviated, so long as they are unique; e.g., 'en', "
                                               "or 'eng' are the same as typing 'engine'. Help on a specific command "
                                               "is also available by typing the command name (or abbreviation), "
                                               "followed by '-h', e.g., 'sw -h'",
                                        formatter_class=StripPrefixesHelpFormatter,
                                        exit_on_error=False)
        group = command_parser.add_mutually_exclusive_group()
        group.add_argument("-accessory",
                           action="store_const",
                           const=AccCli,
                           dest="command",
                           help="Issue accessory commands")
        group.add_argument("-effects",
                           action="store_const",
                           const=EffectsCli,
                           dest="command",
                           help="Issue engine/train effects commands")
        group.add_argument("-engine",
                           action="store_const",
                           const=EngineCli,
                           dest="command",
                           help="Issue engine/train commands")
        group.add_argument("-halt",
                           action="store_const",
                           const=HaltCli,
                           dest="command",
                           help="Emergency stop")
        group.add_argument("-lighting",
                           action="store_const",
                           const=LightingCli,
                           dest="command",
                           help="Issue engine/train lighting effects commands")
        group.add_argument("-route",
                           action="store_const",
                           const=RouteCli,
                           dest="command",
                           help="Fire defined routes")
        group.add_argument("-sounds",
                           action="store_const",
                           const=SoundEffectsCli,
                           dest="command",
                           help="Issue engine/train RailSound effects commands")
        group.add_argument("-switch",
                           action="store_const",
                           const=SwitchCli,
                           dest="command",
                           help="Throw switches")
        group.add_argument("-quit",
                           action="store_const",
                           const="quit",
                           dest="command",
                           help=f"Quit {PROGRAM_NAME}")
        return command_parser


if __name__ == '__main__':
    parser = ArgumentParser(add_help=False)
    parser.add_argument("-s", "--startup_script",
                        type=str,
                        default=DEFAULT_SCRIPT_FILE,
                        help=f"Run the commands in the specified file at start up (default: {DEFAULT_SCRIPT_FILE})")

    parser = ArgumentParser(prog="pytrain.py",
                            description="Send TMCC and Legacy-formatted commands to a Lionel LCS SER2",
                            parents=[parser, cli_parser()])
    parser.add_argument("-no", "--no_clients",
                        action="store_true",
                        help=f"Do not listen for client connections on port {DEFAULT_SERVER_PORT}")
    parser.add_argument("-sp", "--server_port",
                        type=int,
                        default=DEFAULT_SERVER_PORT,
                        help=f"Port to use for remote connections, if client (default: {DEFAULT_SERVER_PORT})")
    PyTrain(parser.parse_args())
