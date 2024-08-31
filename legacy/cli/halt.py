import argparse

from legacy.cli.cli_base import CliBase
from legacy.cli.cli_base import cli_parser_factory
from legacy.protocol.halt_cmd import HaltCmd


class HaltCli(CliBase):
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        try:
            HaltCmd(baudrate=self.args.baudrate, port=self.args.port).fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Fire specified route (1 - 99)",
                                     parents=[cli_parser_factory()])

    args = parser.parse_args()
    HaltCli(parser)
