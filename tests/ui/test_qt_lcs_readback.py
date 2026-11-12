"""Verify Qt LCS configuration readback without hardware or wall-clock delays."""

from unittest.mock import Mock

import pytest

from pytrain.comm.command_listener import Channel
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.pdi.asc2_req import Asc2Req
from pytrain.pdi.constants import Asc2Action, PdiCommand
from pytrain.pdi.pdi_listener import PdiDispatcher
from pytrain.pdi.pdi_req import PdiReq
from pytrain.protocol.command_req import CommandReq


@pytest.fixture
def lcs_readback(monkeypatch):
    module = pytest.importorskip("pytrain_ui.qt.lcs_controller")
    # The Qt extra is optional, and the imported class name is part of its API.
    # noinspection PyPackageRequirements,SpellCheckingInspection
    from PySide6.QtCore import QCoreApplication, QTimer as Timer

    app = QCoreApplication.instance() or QCoreApplication([])
    channel = Channel()
    monkeypatch.setattr(ComponentStateStore, "get_state", Mock(return_value=None))
    dispatcher = Mock(spec=PdiDispatcher)
    dispatcher.subscribe.side_effect = lambda subscriber, *_args, **_kwargs: channel.subscribe(subscriber)
    dispatcher.unsubscribe.side_effect = lambda subscriber, *_args, **_kwargs: channel.unsubscribe(subscriber)
    monkeypatch.setattr(PdiDispatcher, "is_built", lambda: True)
    monkeypatch.setattr(PdiDispatcher, "get", lambda: dispatcher)
    monkeypatch.setattr(CommandReq, "send", Mock())
    send = Mock()
    monkeypatch.setattr(PdiReq, "send", send)
    single_shot = Mock()
    monkeypatch.setattr(Timer, "singleShot", single_shot)

    controller = module.LcsConfigController()
    controller.selectDevice("asc2")
    controller.selectMode("sw_momentary")
    controller.setBaseId(20)
    yield controller, app, channel, dispatcher, send, single_shot
    controller.clearConfigureStatus()


def asc2_config_reply(address: int) -> Asc2Req:
    packet = Asc2Req(address, PdiCommand.ASC2_RX, Asc2Action.CONFIG, mode=2)
    return Asc2Req(packet.as_bytes)


def test_first_config_reply_is_verified_without_an_existing_switch_state(lcs_readback) -> None:
    controller, app, channel, dispatcher, send, single_shot = lcs_readback
    reply = asc2_config_reply(20)

    def respond_to_first_request(**_kwargs) -> None:
        channel.publish(reply)
        send.side_effect = None

    send.side_effect = respond_to_first_request
    assert controller.configure() == ""
    app.processEvents()
    assert controller.configureState == "success"

    subscriber = dispatcher.subscribe.call_args.args[0]
    dispatcher.subscribe.assert_called_once_with(subscriber, PdiCommand.ASC2_RX, action=Asc2Action.CONFIG)
    dispatcher.unsubscribe.assert_called_once_with(subscriber, PdiCommand.ASC2_RX, command=Asc2Action.CONFIG)
    single_shot.call_args.args[1]()
    assert controller.configureState == "success"


def test_reply_from_another_address_does_not_confirm_configuration(lcs_readback) -> None:
    controller, app, channel, dispatcher, _, single_shot = lcs_readback
    assert controller.configure() == ""
    channel.publish(asc2_config_reply(21))
    app.processEvents()
    assert controller.configureState == "polling"

    single_shot.call_args.args[1]()
    assert controller.configureState == "error"
    assert "no configuration reported" in controller.configureStatus
    dispatcher.unsubscribe.assert_called_once()


def test_queued_reply_from_previous_attempt_does_not_confirm_retry(lcs_readback) -> None:
    controller, app, channel, dispatcher, _, _ = lcs_readback
    assert controller.configure() == ""
    channel.publish(asc2_config_reply(20))

    assert controller.configure() == ""
    app.processEvents()
    assert controller.configureState == "polling"
    dispatcher.unsubscribe.assert_called_once()

    channel.publish(asc2_config_reply(20))
    app.processEvents()
    assert controller.configureState == "success"
    assert dispatcher.unsubscribe.call_count == 2


def test_reply_in_other_switch_mode_reports_mode_mismatch(lcs_readback) -> None:
    controller, app, channel, dispatcher, _, _ = lcs_readback
    controller.selectMode("sw_latching")
    assert controller.configure() == ""

    channel.publish(asc2_config_reply(20))
    app.processEvents()
    assert controller.configureState == "error"
    assert "not set as sent: Mode" in controller.configureStatus
    dispatcher.unsubscribe.assert_called_once()
