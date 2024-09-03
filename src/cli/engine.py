#!/usr/bin/env python3
#
import argparse

from src.cli.cli_base import CliBaseTMCC, cli_parser
from src.cli.cli_base import command_format_parser
from src.protocol.constants import EngineOption, TMCC1EngineOption, TMCC2EngineOption
from src.protocol.tmcc1.engine_cmd import EngineCmd as EngineCmdTMCC1
from src.protocol.tmcc2.engine_cmd import EngineCmd as EngineCmdTMCC2


class EngineCli(CliBaseTMCC):
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        engine: int = self._args.engine
        option: EngineOption = self._args.option
        option_data: int = self._args.option_data if 'option_data' in self._args else 0
        try:
            if self.is_train_command or self.use_tmcc2_format:
                scope = self._determine_scope()
                cmd = EngineCmdTMCC2(engine,
                                     TMCC2EngineOption(option),
                                     option_data,
                                     scope,
                                     baudrate=self._args.baudrate,
                                     port=self._args.port)
            else:
                cmd = EngineCmdTMCC1(engine,
                                     TMCC1EngineOption(option),
                                     option_data,
                                     baudrate=self._args.baudrate,
                                     port=self._args.port)
            cmd.fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Fire specified route (1 - 99)",
                                     parents=[cli_parser(), command_format_parser()])
    parser.add_argument("engine", metavar='Train/Engine', type=int, help="route to fire")
    EngineCli(parser)
