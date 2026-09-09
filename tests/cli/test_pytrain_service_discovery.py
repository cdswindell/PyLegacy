#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import logging
from threading import Event

import pytest
from zeroconf import ServiceInfo, ServiceStateChange

from src.pytrain.cli.pytrain import PyTrain

SERVICE_TYPE = "_pytrain._tcp.local."
SERVICE_NAME = f"PyTrain.{SERVICE_TYPE}"


class _StubZeroconf:
    """Stands in for Zeroconf: on_service_state_change only calls get_service_info."""

    def __init__(self, info: ServiceInfo | None) -> None:
        self._info = info
        self.calls: list[tuple[str, str]] = []

    def get_service_info(self, service_type: str, name: str) -> ServiceInfo | None:
        self.calls.append((service_type, name))
        return self._info


def _service_info() -> ServiceInfo:
    return ServiceInfo(
        type_=SERVICE_TYPE,
        name=SERVICE_NAME,
        addresses=[bytes([192, 168, 1, 10])],
        port=5110,
        properties={},
        server="pytrain.local.",
    )


def _pytrain() -> PyTrain:
    # on_service_state_change touches only these two attributes, so skip __init__,
    # which would stand up listeners, buffers and a Tk app.
    pytrain = PyTrain.__new__(PyTrain)
    pytrain._pytrain_servers = []
    pytrain._server_discovered = Event()
    return pytrain


@pytest.fixture
def root_at_info():
    """Run with the root logger at INFO, the level Step 5 lowers it to.

    Discovery used to be gated by `if info and log.isEnabledFor(logging.DEBUG)`, so it
    worked only because dual_logging pinned the root at DEBUG.
    """
    root = logging.getLogger()
    previous = root.level
    root.setLevel(logging.INFO)
    try:
        yield
    finally:
        root.setLevel(previous)


def test_added_service_is_recorded_with_the_root_logger_at_info(root_at_info) -> None:
    pytrain = _pytrain()
    info = _service_info()
    zc = _StubZeroconf(info)

    pytrain.on_service_state_change(zc, SERVICE_TYPE, SERVICE_NAME, ServiceStateChange.Added)

    assert pytrain._pytrain_servers == [info]
    assert pytrain._server_discovered.is_set()
    assert zc.calls == [(SERVICE_TYPE, SERVICE_NAME)]


def test_added_service_is_recorded_with_the_root_logger_at_debug(caplog) -> None:
    pytrain = _pytrain()
    info = _service_info()

    with caplog.at_level(logging.DEBUG):
        pytrain.on_service_state_change(_StubZeroconf(info), SERVICE_TYPE, SERVICE_NAME, ServiceStateChange.Added)

    assert pytrain._pytrain_servers == [info]
    assert pytrain._server_discovered.is_set()


def test_added_service_without_info_is_a_no_op(root_at_info) -> None:
    pytrain = _pytrain()

    pytrain.on_service_state_change(_StubZeroconf(None), SERVICE_TYPE, SERVICE_NAME, ServiceStateChange.Added)

    assert pytrain._pytrain_servers == []
    assert not pytrain._server_discovered.is_set()


@pytest.mark.parametrize("state_change", [ServiceStateChange.Removed, ServiceStateChange.Updated])
def test_other_state_changes_do_not_query_or_record(root_at_info, state_change) -> None:
    pytrain = _pytrain()
    zc = _StubZeroconf(_service_info())

    pytrain.on_service_state_change(zc, SERVICE_TYPE, SERVICE_NAME, state_change)

    assert zc.calls == []
    assert pytrain._pytrain_servers == []
    assert not pytrain._server_discovered.is_set()
