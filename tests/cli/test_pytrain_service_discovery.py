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
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from zeroconf import ServiceInfo, ServiceStateChange

from src.pytrain.cli import pytrain as module
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


@pytest.fixture
def discovery(bare_pytrain, monkeypatch):
    p = bare_pytrain
    p._headless = False
    p._pytrain_servers = []
    p._server_cache_sync_capable = None
    p._server_cache_sync_port = None
    p._server_discovered = Mock(spec=Event)
    # An exhausted sequence fails instead of allowing an accidental blocking wait.
    p._server_discovered.wait.side_effect = [False] * 480
    network = Mock(return_value=True)
    zeroconf = Mock(spec=module.Zeroconf)
    browser = Mock(spec=module.ServiceBrowser)
    factory = Mock(return_value=zeroconf)
    browse = Mock(return_value=browser)
    monkeypatch.setattr(module, "wait_for_network", network)
    monkeypatch.setattr(module, "Zeroconf", factory)
    monkeypatch.setattr(module, "ServiceBrowser", browse)
    monkeypatch.setattr(module, "sleep", Mock(side_effect=AssertionError("Unexpected sleep")))
    return SimpleNamespace(p=p, network=network, z=zeroconf, browser=browser, factory=factory, browse=browse)


def _advertisement(properties, address="192.0.2.10", port=5110):
    return ServiceInfo(
        SERVICE_TYPE,
        SERVICE_NAME,
        parsed_addresses=[address],
        port=port,
        properties=properties,
        server="pytrain.local.",
    )


def test_discovery_requires_network_readiness(discovery, caplog):
    discovery.network.return_value = False
    assert discovery.p.get_service_info() is None
    discovery.network.assert_called_once_with()
    discovery.factory.assert_not_called()
    discovery.browse.assert_not_called()
    discovery.p._server_discovered.wait.assert_not_called()
    assert "Network not ready" in caplog.text


@pytest.mark.parametrize("headless", [False, True])
@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO, logging.WARNING])
def test_discovery_prefers_combined_server_and_records_cache_capability(discovery, caplog, headless, level):
    p = discovery.p
    p._headless = headless
    base = _advertisement({"Base3": "1", "Ser2": "0"})
    combined = _advertisement(
        {"Ser2": "1", "Base3": "1", "CacheSync": "1", "CacheSyncPort": "6100", "unused": None},
        "192.0.2.20",
        5200,
    )
    p._pytrain_servers = [base, combined]
    p._server_discovered.wait.side_effect = [True]
    with caplog.at_level(level, logger=module.log.name):
        assert p.get_service_info() == ("192.0.2.20", 5200)
    assert (p._server_cache_sync_capable, p._server_cache_sync_port) == (True, 6100)
    discovery.factory.assert_called_once_with(ip_version=module.IPVersion.V4Only)
    discovery.browse.assert_called_once_with(discovery.z, [module.SERVICE_TYPE], handlers=[p.on_service_state_change])
    p._server_discovered.wait.assert_called_once_with(0.5)
    p._server_discovered.clear.assert_called_once_with()
    discovery.browser.cancel.assert_called_once_with()
    discovery.z.close.assert_called_once_with()
    if headless and level <= logging.INFO:
        assert "Found PyTrain Server at pytrain.local." in caplog.text


def test_discovery_allows_combined_server_to_arrive_after_base_only(discovery):
    p = discovery.p
    base = _advertisement({"Base3": "1"})
    combined = _advertisement({"Base3": "1", "Ser2": "1"}, "192.0.2.30")
    polls = iter([[base], None, [base, combined]])

    def poll(timeout):
        assert timeout == 0.5
        services = next(polls)
        if services is not None:
            p._pytrain_servers = services
        return services is not None

    p._server_discovered.wait.side_effect = poll
    assert p.get_service_info() == ("192.0.2.30", 5110)
    assert p._server_discovered.wait.call_count == 3
    assert p._server_discovered.clear.call_count == 2


def test_discovery_falls_back_to_base_only_after_more_than_fifteen_seconds(discovery):
    p = discovery.p
    p._pytrain_servers = [_advertisement({"Base3": "1", "Ser2": None})]
    p._server_discovered.wait.side_effect = [True] + [False] * 31
    assert p.get_service_info() == ("192.0.2.10", 5110)
    assert p._server_discovered.wait.call_args_list == [call(0.5)] * 32
    p._server_discovered.clear.assert_called_once_with()
    assert (p._server_cache_sync_capable, p._server_cache_sync_port) == (False, 5210)
    discovery.browser.cancel.assert_called_once_with()
    discovery.z.close.assert_called_once_with()


@pytest.mark.parametrize("headless", [False, True])
@pytest.mark.parametrize("properties", [None, {}, {"Ser2": "1", "Base3": "0"}])
def test_discovery_timeout_is_bounded_and_rejects_servers_without_base(discovery, caplog, headless, properties):
    p = discovery.p
    p._headless = headless
    if properties is not None:
        p._pytrain_servers = [_advertisement(properties)]
        p._server_discovered.wait.side_effect = [True] + [False] * 479
    with caplog.at_level(logging.INFO, logger=module.log.name):
        assert p.get_service_info() is None
    assert p._server_discovered.wait.call_args_list == [call(0.5)] * 480
    assert p._server_discovered.clear.call_count == (properties is not None)
    assert p._server_cache_sync_capable is p._server_cache_sync_port is None
    discovery.browser.cancel.assert_called_once_with()
    discovery.z.close.assert_called_once_with()
    if headless:
        assert "No PyTrain Server found" in caplog.text


@pytest.mark.parametrize("source", ["browser", "wait", "property"])
def test_discovery_errors_are_logged_and_resources_closed(discovery, caplog, source):
    if source == "browser":
        discovery.browse.side_effect = RuntimeError("discovery failed")
    elif source == "wait":
        discovery.p._server_discovered.wait.side_effect = RuntimeError("discovery failed")
    else:
        discovery.p._pytrain_servers = [_advertisement({b"Base3": b"\xff"})]
        discovery.p._server_discovered.wait.side_effect = [True]
    assert discovery.p.get_service_info() is None
    assert caplog.records
    assert "discovery failed" in caplog.text if source != "property" else "decode" in caplog.text
    assert discovery.browser.cancel.call_count == (source != "browser")
    discovery.z.close.assert_called_once_with()


@pytest.mark.parametrize("source", ["cancel", "close"])
def test_discovery_cleanup_errors_propagate_but_cancel_failure_still_closes(discovery, source):
    discovery.browse.side_effect = None
    discovery.p._server_discovered.wait.side_effect = RuntimeError("stop polling")
    target = discovery.browser.cancel if source == "cancel" else discovery.z.close
    target.side_effect = RuntimeError(source)
    with pytest.raises(RuntimeError, match=source):
        discovery.p.get_service_info()
    discovery.browser.cancel.assert_called_once_with()
    discovery.z.close.assert_called_once_with()


def test_zeroconf_construction_error_propagates_without_starting_browser(discovery):
    discovery.factory.side_effect = RuntimeError("no multicast socket")
    with pytest.raises(RuntimeError, match="no multicast socket"):
        discovery.p.get_service_info()
    discovery.browse.assert_not_called()


@pytest.mark.parametrize("state_change", [ServiceStateChange.Removed, ServiceStateChange.Updated])
def test_other_state_changes_do_not_query_or_record(root_at_info, state_change) -> None:
    pytrain = _pytrain()
    zc = _StubZeroconf(_service_info())

    pytrain.on_service_state_change(zc, SERVICE_TYPE, SERVICE_NAME, state_change)

    assert zc.calls == []
    assert pytrain._pytrain_servers == []
    assert not pytrain._server_discovered.is_set()
