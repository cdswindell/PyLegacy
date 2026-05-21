from src.pytrain.cli.cache import CacheCli


def test_cache_parser_accepts_delete_file_command() -> None:
    args = CacheCli.command_parser().parse_args(["delete", "42.jpg"])

    assert args.command == "delete"
    assert args.file == "42.jpg"
