import logging
from unittest.mock import Mock

import pytest

from src.pytrain.cli import pytrain as module


@pytest.fixture
def command_train(bare_pytrain, monkeypatch):
    monkeypatch.setattr(module.PyTrain, "_current", bare_pytrain)
    monkeypatch.setattr(module.Thread, "start", Mock(side_effect=AssertionError("Unexpected background thread")))
    monkeypatch.setattr(module.CommBuffer, "build", Mock(side_effect=AssertionError("Unexpected transport")))
    bare_pytrain._state_store = Mock(spec=module.ComponentStateStore)
    bare_pytrain._state_store.get_state.return_value = None
    bare_pytrain._tmcc_buffer = Mock(spec=module.CommBufferSingleton)
    bare_pytrain._dispatcher = Mock()
    return bare_pytrain


@pytest.mark.parametrize(
    "name,target",
    [
        ("accessory", module.AccCli),
        ("asc2", module.Asc2Cli),
        ("amc2", module.Amc2Cli),
        ("bpc2", module.Bpc2Cli),
        ("cache", module.CacheCli),
        ("clear", module.ClearCli),
        ("csv", module.CsvCli),
        ("dialogs", module.DialogsCli),
        ("effects", module.EffectsCli),
        ("engine", module.EngineCli),
        ("eng", module.EngineCli),
        ("train", module.EngineCli),
        ("tr", module.EngineCli),
        ("halt", module.HaltCli),
        ("lighting", module.LightingCli),
        ("reindex", module.ReindexCli),
        ("route", module.RouteCli),
        ("sounds", module.SoundEffectsCli),
        ("switch", module.SwitchCli),
        ("sw", module.SwitchCli),
        *[
            (name, name)
            for name in [
                "db",
                "decode",
                "debug",
                "echo",
                "info",
                "pdi",
                "quit",
                "reboot",
                "restart",
                "resync",
                "send",
                "shutdown",
                "update",
                "upgrade",
                "uptime",
                "version",
            ]
        ],
    ],
)
def test_command_registry(name, target):
    assert module.PyTrain._command_parser().parse_args([f"-{name}"]).command == target


@pytest.mark.parametrize(
    "text,method,args",
    [
        ("DB ENGINE 7", "_do_db", ["engine", "7"]),
        ("info 7", "_get_engine_info", ["7"]),
        ("decode FE:00:00", "decode_command", ["fe:00:00"]),
        ("send FE0000", "send_command", ["fe0000"]),
        ("pdi base", "_do_pdi", ["base"]),
        ("debug ON", "_handle_debug", ["debug", "on"]),
        ("echo OFF", "_handle_echo", ["echo", "off"]),
    ],
)
def test_special_routing(command_train, monkeypatch, text, method, args):
    handler = Mock()
    monkeypatch.setattr(command_train, method, handler)
    assert command_train._handle_command(text) is None
    handler.assert_called_once_with(args)


def test_special_outputs_and_pdi_error(command_train, monkeypatch, capsys, caplog):
    command_train._started_at = 10
    monkeypatch.setattr(module, "timer", lambda: 75)
    command_train._handle_command("uptime")
    assert capsys.readouterr().out.strip() == "0:01:05"
    command_train._version = "1.2.3"
    command_train._tmcc_buffer.base3_address = None
    command_train._handle_command("version")
    assert "1.2.3" in capsys.readouterr().out
    monkeypatch.setattr(command_train, "_do_pdi", Mock(side_effect=ValueError("invalid PDI")))
    command_train._handle_command("pdi invalid")
    assert "invalid PDI" in caplog.text


@pytest.mark.parametrize("text", ["", " ", "\n"])
def test_empty_command(command_train, text):
    assert command_train._handle_command(text) is None
    command_train._tmcc_buffer.enqueue_command.assert_not_called()


def test_missing_and_admin_parse(command_train):
    assert command_train._handle_command(None) == "No command specified."
    assert command_train.parse_cli("") == "No command specified."
    for name in module.ADMIN_COMMAND_TO_ACTION_MAP:
        assert command_train.parse_cli(name.upper()) == f"Unrecognized command: {name.upper()}"


@pytest.mark.parametrize(
    "text", ["unknown", "s", "engine invalid", "engine invalid -b", "engine 7 -invalid", "engine 10000 -b", "cache"]
)
def test_parse_errors(command_train, capsys, text):
    result = command_train.parse_cli(text)
    assert isinstance(result, str)
    assert result
    if text == "unknown":
        assert "unrecognized arguments" in result
        assert "-unknown" in result
    elif text == "s":
        assert "ambiguous option" in result
        assert "-s" in result
    assert capsys.readouterr().err == ""
    command_train._tmcc_buffer.enqueue_command.assert_not_called()


@pytest.mark.parametrize("invalid,diagnostic", [("unknown", "unrecognized arguments"), ("s", "ambiguous option")])
@pytest.mark.parametrize("help_text", ["?", "help", "engine -h"])
def test_parse_failure_mode_isolation(command_train, monkeypatch, capsys, invalid, diagnostic, help_text):
    command_parser = module.PyTrain._command_parser
    parsers = []

    def track_parser():
        parser = command_parser()
        assert parser.is_exit_on_error
        monkeypatch.setattr(parser, "clear_exit_on_error", Mock(wraps=parser.clear_exit_on_error))
        parsers.append(parser)
        return parser

    monkeypatch.setattr(command_train, "_command_parser", track_parser)
    send = Mock(side_effect=AssertionError("parse-only and help must not send"))
    monkeypatch.setattr(module.EngineCli, "send", send)

    result = command_train.parse_cli(invalid)
    assert isinstance(result, str)
    assert diagnostic in result
    assert f"-{invalid}" in result
    assert capsys.readouterr().err == ""

    request = command_train.parse_cli("engine 7 -b")
    assert isinstance(request, module.CommandReq)
    assert request.address == 7
    assert request.scope == module.CommandScope.ENGINE
    assert request.is_tmcc1
    assert capsys.readouterr().err == ""

    with pytest.raises(SystemExit) as exc:
        command_train._handle_command(help_text)
    assert exc.value.code == 0
    output = capsys.readouterr()
    assert "usage:" in output.out
    assert output.err == ""

    assert len(parsers) == 3
    assert len({id(parser) for parser in parsers}) == 3
    for parser in parsers[:2]:
        parser.clear_exit_on_error.assert_called_once_with()
        assert not parser.is_exit_on_error
    parsers[2].clear_exit_on_error.assert_not_called()
    assert parsers[2].is_exit_on_error
    send.assert_not_called()
    command_train._tmcc_buffer.enqueue_command.assert_not_called()


@pytest.mark.parametrize(
    "text,scope,tmcc",
    [
        ("engine 7 -b", module.CommandScope.ENGINE, True),
        ("train 7 -b", module.CommandScope.TRAIN, True),
        ("tr 7 -train -b", module.CommandScope.TRAIN, True),
        ("train 7 -legacy -b", module.CommandScope.TRAIN, False),
        ("engine 7 -tmcc -b", module.CommandScope.ENGINE, True),
        ("engine 7 -legacy -b", module.CommandScope.ENGINE, False),
    ],
)
def test_real_parse_only(command_train, monkeypatch, text, scope, tmcc):
    send = Mock(side_effect=AssertionError("parse-only must not send"))
    monkeypatch.setattr(module.EngineCli, "send", send)
    request = command_train.parse_cli(text)
    assert isinstance(request, module.CommandReq)
    assert request.address == 7
    assert request.scope == scope
    assert request.is_tmcc1 is tmcc
    command_train._state_store.get_state.assert_called_once_with(scope, 7, False)
    send.assert_not_called()


@pytest.mark.parametrize("is_tmcc", [True, False])
def test_infer_engine_mode(command_train, is_tmcc):
    state = Mock(spec=module.EngineState)
    state.is_tmcc = is_tmcc
    command_train._state_store.get_state.return_value = state
    request = command_train.parse_cli("engine 7 -b")
    assert isinstance(request, module.CommandReq)
    assert request.is_tmcc1 is is_tmcc


@pytest.mark.parametrize("text", ["engine 7 -b", "engine 7 -invalid"])
def test_parser_restored(command_train, monkeypatch, text):
    parser = module.EngineCli.command_parser()
    reset = Mock(wraps=parser.reset_exit_on_error)
    monkeypatch.setattr(parser, "reset_exit_on_error", reset)
    monkeypatch.setattr(module.EngineCli, "command_parser", lambda: parser)
    command_train.parse_cli(text)
    reset.assert_called_once_with()
    assert parser.is_exit_on_error


def test_normal_send(command_train, monkeypatch, caplog):
    send = Mock()
    monkeypatch.setattr(module.EngineCli, "send", send)
    with caplog.at_level(logging.DEBUG, logger=module.__name__):
        command_train._handle_command("engine 7 -b")
    send.assert_called_once_with()
    assert "Sending" in caplog.text


@pytest.mark.parametrize("text", ["?", "help", "engine -h"])
def test_help(command_train, capsys, text):
    with pytest.raises(SystemExit) as exc:
        command_train._handle_command(text)
    assert exc.value.code == 0
    assert "usage:" in capsys.readouterr().out


@pytest.mark.parametrize("server,target", [(True, ""), (False, ""), (False, "server")])
def test_quit_routing(command_train, server, target):
    if not server:
        command_train._tmcc_buffer = Mock()
    if target:
        command_train._handle_command("quit server")
        expected = module.CommandReq(module.TMCC1SyncCommandEnum.QUIT)
        command_train._tmcc_buffer.enqueue_command.assert_called_once_with(expected.as_bytes)
    else:
        with pytest.raises(KeyboardInterrupt):
            command_train._handle_command("quit")
        assert command_train._dispatcher.signal_clients.call_count == int(server)


def test_admin_routing(command_train, monkeypatch):
    resync = Mock()
    admin = Mock()
    monkeypatch.setattr(command_train, "_get_system_state", resync)
    monkeypatch.setattr(command_train, "do_admin_cmd", admin)
    command_train._handle_command("resync")
    resync.assert_called_once_with()
    command_train._handle_command("restart me")
    admin.assert_called_once_with(module.TMCC1SyncCommandEnum.RESTART, ["me"])


@pytest.mark.parametrize("pdi", [False, True])
def test_decode_and_send(command_train, monkeypatch, capsys, pdi):
    request = (
        module.BaseReq(0, module.PdiCommand.BASE) if pdi else module.CommandReq(module.TMCC1SyncCommandEnum.RESYNC)
    )
    raw = request.as_bytes
    text = ["0x" + ":".join(f"{b:02X}" for b in raw)]
    decoded_bytes, decoded = command_train.decode_command(text)
    assert decoded_bytes == raw
    assert decoded.as_bytes == raw
    assert raw.hex() in capsys.readouterr().out
    send = Mock()
    monkeypatch.setattr(module.PdiReq if pdi else module.CommandReq, "send", send)
    command_train.send_command(text)
    send.assert_called_once_with()


@pytest.mark.parametrize("text", [[], ["invalid"], ["0x"], ["ff"]])
def test_decode_invalid(command_train, monkeypatch, text):
    send = Mock()
    monkeypatch.setattr(module.CommandReq, "send", send)
    assert command_train.decode_command(text) == (b"", None)
    command_train.send_command(text)
    send.assert_not_called()


@pytest.mark.parametrize("parse_only", [False, True])
def test_invalid_constructed_command(command_train, caplog, parse_only):
    result = command_train._handle_command("engine 10000 -b", parse_only=parse_only)
    if parse_only:
        assert result == "'engine 10000 -b' is not a valid command"
    else:
        assert result is None
        assert "is not a valid command" in caplog.text


@pytest.mark.parametrize("prefix", ["train", "engine"])
def test_subparser_mode_inference(command_train, prefix):
    request = command_train.parse_cli(f"{prefix} 7 speed 2 -relative")
    assert isinstance(request, module.CommandReq)
    assert request.address == 7
    assert request.data == 2
    assert request.scope == (module.CommandScope.TRAIN if prefix == "train" else module.CommandScope.ENGINE)
    assert request.is_tmcc1


def test_send_without_debug(command_train, monkeypatch, caplog):
    send = Mock()
    monkeypatch.setattr(module.EngineCli, "send", send)
    with caplog.at_level(logging.INFO, logger=module.__name__):
        command_train._handle_command("engine 7 -b")
    send.assert_called_once_with()
    assert "Sending" not in caplog.text


@pytest.mark.parametrize("text", [None, "", "invalid"])
def test_invalid_admin_enum(text):
    with pytest.raises(ValueError, match="Unrecognized admin command"):
        module.PyTrain._admin_enum(text)


def test_client_resync_routing(command_train, monkeypatch):
    command_train._tmcc_buffer = Mock()
    admin = Mock()
    monkeypatch.setattr(command_train, "do_admin_cmd", admin)
    command_train._handle_command("resync server")
    admin.assert_called_once_with(module.TMCC1SyncCommandEnum.RESYNC, ["server"])
