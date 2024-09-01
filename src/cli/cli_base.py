import argparse


class CliBase:
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        self.args = args = arg_parser.parse_args()


def cli_parser_factory():
    # define arguments common to all Legacy CLI commands
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument('-b', '--baudrate', action='store',
                        type=int, default=9600, help='''Baud Rate (9600)''')
    parser.add_argument('-p', '--port', action='store',
                        default="/dev/ttyUSB0", help='''Serial Port (/dev/ttyUSB0)''')

    return parser
