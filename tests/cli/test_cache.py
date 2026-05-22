from types import SimpleNamespace

from src.pytrain.cli.cache import CacheCli
import src.pytrain.cli.pytrain as pytrain_module
from src.pytrain.cli.pytrain import PyTrain
from src.pytrain.utils.argument_parser import PyTrainArgumentParser, UniqueChoice


def test_cache_parser_accepts_delete_file_command() -> None:
    args = CacheCli.command_parser().parse_args(["delete", "42.jpg"])

    assert args.command == "delete"
    assert args.file == "42.jpg"


def test_interactive_cache_delete_preserves_filename_case(monkeypatch) -> None:
    class DummyCacheCli:
        @classmethod
        def command_parser(cls):
            parser = PyTrainArgumentParser(add_help=False)
            parser.add_argument("command", type=UniqueChoice(["clear", "delete", "sync"]))
            parser.add_argument("file", nargs="?")
            return PyTrainArgumentParser("Cache options", parents=[parser])

        def __init__(self, arg_parser, cmd_line, do_fire):
            args = arg_parser.parse_args(cmd_line)
            self.command = SimpleNamespace(command_req=args.file)

        def send(self):
            pass

    def command_parser():
        parser = PyTrainArgumentParser(exit_on_error=False)
        parser.add_argument("-cache", action="store_const", const=DummyCacheCli, dest="command")
        return parser

    monkeypatch.setattr(pytrain_module, "CacheCli", DummyCacheCli)
    monkeypatch.setattr(PyTrain, "_command_parser", staticmethod(command_parser))

    pytrain = object.__new__(PyTrain)

    assert pytrain._handle_command("cache del lc_20576F_2533952.png", parse_only=True) == "lc_20576F_2533952.png"
