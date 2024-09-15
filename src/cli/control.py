import argparse

from src.cli.cli_base import cli_parser
from src.cli.acc import AccCli
from src.cli.engine import EngineCli
from src.cli.halt import HaltCli
from src.cli.route import RouteCli
from src.cli.switch import SwitchCli
from src.comm.comm_buffer import CommBuffer, comm_buffer_factory

command_parser = argparse.ArgumentParser(add_help=False)
group = command_parser.add_mutually_exclusive_group()
group.add_argument("-accessory",
                   action="store_const",
                   const=AccCli,
                   dest="command")
group.add_argument("-engine",
                   action="store_const",
                   const=EngineCli,
                   dest="command")
group.add_argument("-halt",
                   action="store_const",
                   const=HaltCli,
                   dest="command")
group.add_argument("-route",
                   action="store_const",
                   const=RouteCli,
                   dest="command")
group.add_argument("-switch",
                   action="store_const",
                   const=SwitchCli,
                   dest="command")
group.add_argument("-quit",
                   action="store_const",
                   const="quit",
                   dest="command")


class TrainControl:
    def __init__(self, args: argparse.Namespace) -> None:
        self._args = args
        self.run()

    def run(self) -> None:
        # configure command buffer
        comm_buffer_factory(baudrate=self._args.baudrate, port=self._args.port)
        while True:
            try:
                ui: str = input(">> ")
                self._handle_command(ui)
            except SystemExit:
                pass
            except argparse.ArgumentError:
                pass
            except KeyboardInterrupt:
                CommBuffer().shutdown()
                break

    @staticmethod
    def _handle_command(ui: str) -> None:
        """
            Parse the user's input, reusing the individual CLI command parsers.
            If a valid command is specified, send it to the Lionel LCS SER2.
        """
        if ui is None:
            return
        ui = ui.lower().strip()
        if ui:
            # the argparse library requires the argument string to be presented as a list
            ui_parts = ui.split()
            if ui_parts[0]:
                # parse the first token
                try:
                    # if the keyboard input starts with a valid command, args.command
                    # is set to the corresponding CLI command class, or the verb 'quit'
                    args = command_parser.parse_args(['-'+ui_parts[0]])
                    if args.command == 'quit':
                        raise KeyboardInterrupt()
                    ui_parser = args.command.command_parser()
                    cli = args.command(ui_parser, ui_parts[1:], False).command
                    cli.send()
                except argparse.ArgumentError:
                    print(f"{ui} is not a valid command")
                    return


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Send TMCC and Legacy-formatted commands to a LCS SER2",
                                     parents=[cli_parser()])
    TrainControl(parser.parse_args())
