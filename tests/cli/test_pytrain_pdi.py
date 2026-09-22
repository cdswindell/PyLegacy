import logging
from unittest.mock import Mock

import pytest

from src.pytrain.cli import pytrain as module
from src.pytrain.pdi.constants import Amc2Action, IrdaAction
from src.pytrain.pdi.irda_req import IrdaReq, IrdaSequence
from src.pytrain.pdi.pdi_device import PdiDevice


@pytest.fixture
def transport(bare_pytrain):
    bare_pytrain._tmcc_buffer = Mock(spec=module.CommBufferSingleton)
    bare_pytrain._pdi_buffer = Mock(spec=module.PdiListener)
    return bare_pytrain


@pytest.mark.parametrize("mode", ["server", "client", "server_without_pdi"])
@pytest.mark.parametrize(
    "text,expected",
    [
        ("", module.AllReq()),
        ("base", module.BaseReq(0, module.PdiCommand.BASE)),
        *[
            (f"{name} 7", module.BaseReq(7, command))
            for name, command in [
                ("engine", module.PdiCommand.BASE_ENGINE),
                ("train", module.PdiCommand.BASE_TRAIN),
                ("accessory", module.PdiCommand.BASE_ACC),
                ("switch", module.PdiCommand.BASE_SWITCH),
                ("route", module.PdiCommand.BASE_ROUTE),
            ]
        ],
        (
            "memory 7",
            module.BaseReq(
                7, module.PdiCommand.BASE_MEMORY, scope=module.CommandScope.ENGINE, start=0, data_length=192
            ),
        ),
        *[
            (
                f"memory {record} train {start} {length}",
                module.BaseReq(
                    7, module.PdiCommand.BASE_MEMORY, scope=module.CommandScope.TRAIN, start=2, data_length=4
                ),
            )
            for record, start, length in [("7", "2", "4"), ("0x7", "0x2", "0x4")]
        ],
        ("d4_engine count", module.D4Req(0, module.PdiCommand.D4_ENGINE, action=module.D4Action.COUNT)),
        ("d4_engine count 7", module.D4Req(0, module.PdiCommand.D4_ENGINE, action=module.D4Action.COUNT)),
        ("d4_train first_rec", module.D4Req(0, module.PdiCommand.D4_TRAIN, action=module.D4Action.FIRST_REC)),
        ("d4_engine map 1234", module.D4Req(0, module.PdiCommand.D4_ENGINE, action=module.D4Action.MAP, tmcc_id=1234)),
        ("d4_engine next_rec 7", module.D4Req(7, module.PdiCommand.D4_ENGINE, action=module.D4Action.NEXT_REC)),
        *[
            (
                f"d4_engine {action} 7",
                module.D4Req(7, module.PdiCommand.D4_ENGINE, action=module.D4Action.QUERY, start=0, data_length=192),
            )
            for action in ["query", "update"]
        ],
        *[
            (
                f"d4_engine update {values}",
                module.D4Req(
                    7,
                    module.PdiCommand.D4_ENGINE,
                    action=module.D4Action.UPDATE,
                    start=2,
                    data_length=2,
                    data_bytes=b"\x34\x12",
                ),
            )
            for values in ["7 2 2 4660", "0x7 0x2 0x2 0x1234"]
        ],
        *[
            (f"asc2 7 {action}", getattr(PdiDevice.ASC2, action)(7))
            for action in ["firmware", "status", "info", "config", "clear_errors", "reset"]
        ],
        ("asc2 7 identify", PdiDevice.ASC2.identify(7, ident=1)),
        ("asc2 -7 identify", PdiDevice.ASC2.identify(7, ident=0)),
        *[
            (
                f"irda 7 sequence {value}",
                IrdaReq(7, module.PdiCommand.IRDA_SET, IrdaAction.SEQUENCE, sequence=IrdaSequence.BELL_NONE),
            )
            for value in ["bell_none", "3"]
        ],
        *[
            (
                f"asc2 7 {action.name} {value}".strip(),
                module.Asc2Req(7, module.PdiCommand.ASC2_SET, action, values=int(value or 1)),
            )
            for action in [module.Asc2Action.CONTROL1, module.Asc2Action.CONTROL5]
            for value in ["", "0"]
        ],
        ("amc2 7 motor 1", module.Amc2Req(7, module.PdiCommand.AMC2_GET, Amc2Action.MOTOR, motor=1)),
        ("amc2 7 lamp 1", module.Amc2Req(7, module.PdiCommand.AMC2_GET, Amc2Action.LAMP, lamp=1)),
        ("amc2 7 lamp 1 50", module.Amc2Req(7, module.PdiCommand.AMC2_SET, Amc2Action.LAMP, lamp=1, level=50)),
        (
            "amc2 7 motor 1 50 forward",
            module.Amc2Req(
                7, module.PdiCommand.AMC2_SET, Amc2Action.MOTOR, motor=1, speed=50, direction=module.Direction.FORWARD
            ),
        ),
        ("irda 7 data", PdiDevice.IRDA.build_req(7, IrdaAction.DATA)),
        ("asc2 7 control2", PdiDevice.ASC2.build_req(7, module.Asc2Action.CONTROL2)),
    ],
)
def test_pdi_requests(transport, text, expected, mode, caplog):
    if mode == "client":
        transport._tmcc_buffer = Mock()
    elif mode == "server_without_pdi":
        transport._pdi_buffer = None
    with caplog.at_level(logging.INFO, logger=module.__name__):
        transport._do_pdi(text.split())
    if mode == "server":
        transport._pdi_buffer.enqueue_command.assert_called_once()
        actual = transport._pdi_buffer.enqueue_command.call_args.args[0]
        assert type(actual) is type(expected)
        assert actual.as_bytes == expected.as_bytes
        transport._tmcc_buffer.enqueue_command.assert_not_called()
    else:
        transport._tmcc_buffer.enqueue_command.assert_called_once_with(expected.as_bytes)


@pytest.mark.parametrize("text", ["unknown", "unknown 7", "d4_engine map", "irda 7 sequence"])
def test_incomplete_pdi_is_noop(transport, text):
    transport._do_pdi(text.split())
    transport._pdi_buffer.enqueue_command.assert_not_called()
    transport._tmcc_buffer.enqueue_command.assert_not_called()


@pytest.mark.parametrize(
    "text,error",
    [
        ("d4_engine map 99", "4-digit"),
        ("unknown 7 status", "Device"),
        ("asc2 7 nonsense", "Action"),
        ("irda 7 sequence nonsense", "Sequence"),
        ("irda 7 sequence 99", "Sequence"),
        ("amc2 7 motor", "Must specify"),
        ("amc2 7 lamp", "Must specify"),
        ("amc2 7 motor 1 50", "parameter count"),
        ("amc2 7 lamp 1 50 forward", "parameter count"),
    ],
)
def test_invalid_pdi(transport, text, error):
    with pytest.raises(AttributeError, match=error):
        transport._do_pdi(text.split())
    transport._pdi_buffer.enqueue_command.assert_not_called()
    transport._tmcc_buffer.enqueue_command.assert_not_called()


@pytest.mark.parametrize(
    "text",
    [
        "engine nope",
        "memory nope",
        "memory 7 invalid",
        "d4_engine query nope",
        "d4_engine invalid",
        "dinosaur count",
        "asc2 nope status",
    ],
)
def test_invalid_pdi_values(transport, text):
    with pytest.raises(ValueError):
        transport._do_pdi(text.split())
    transport._pdi_buffer.enqueue_command.assert_not_called()


def test_debug_base_record_current_failure(transport, caplog):
    """BaseReq's debug representation currently accesses an unset run level."""
    with caplog.at_level(logging.DEBUG, logger=module.__name__):
        with pytest.raises(AttributeError, match="_run_level"):
            transport._do_pdi(["engine", "7"])
    transport._pdi_buffer.enqueue_command.assert_not_called()


def test_debug_pdi_dispatch(transport, caplog):
    with caplog.at_level(logging.DEBUG, logger=module.__name__):
        transport._do_pdi([])
    assert "Sending" in caplog.text
    transport._pdi_buffer.enqueue_command.assert_called_once()


def test_d4_clear_is_currently_noop(transport):
    transport._do_pdi(["d4_engine", "clear", "7"])
    transport._pdi_buffer.enqueue_command.assert_not_called()
    transport._tmcc_buffer.enqueue_command.assert_not_called()
