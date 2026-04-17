#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from io import StringIO
import subprocess
from typing import Any

from pytest import MonkeyPatch

from src.pytrain.utils.wifi_info import WiFiInfo


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def test_dbm_to_quality_clamps_to_zero_and_one_hundred():
    assert WiFiInfo.dbm_to_quality(-120) == 0
    assert WiFiInfo.dbm_to_quality(-100) == 0
    assert WiFiInfo.dbm_to_quality(-75) == 50
    assert WiFiInfo.dbm_to_quality(-50) == 100
    assert WiFiInfo.dbm_to_quality(-20) == 100


def test_linux_iw_uses_discovered_interface_not_wlan0(monkeypatch: MonkeyPatch) -> None:
    def fake_run(
        command: list[str], capture_output: bool = True, text: bool = True
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        if command == ["iw", "dev"]:
            return _completed(
                stdout="phy#0\n\tInterface wlp2s0\n\t\tifindex 4\n\t\taddr aa:bb:cc:dd:ee:ff\n\t\ttype managed\n"
            )
        if command == ["iw", "dev", "wlp2s0", "link"]:
            return _completed(
                stdout=(
                    "Connected to 11:22:33:44:55:66 (on wlp2s0)\n\tSSID: Layout WiFi\n\tfreq: 5180\n\tsignal: -61 dBm\n"
                )
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("src.pytrain.utils.wifi_info.subprocess.run", fake_run)

    snapshot = WiFiInfo(system="Linux").query()

    assert snapshot.source == "iw"
    assert snapshot.interface == "wlp2s0"
    assert snapshot.connected is True
    assert snapshot.ssid == "Layout WiFi"
    assert snapshot.bssid == "11:22:33:44:55:66"
    assert snapshot.signal_dbm == -61
    assert snapshot.frequency_mhz == 5180
    assert snapshot.quality == 78
    assert snapshot.quality_label == "Very Good"


def test_linux_iw_reuses_cached_interface_on_later_queries(monkeypatch: MonkeyPatch) -> None:
    calls = {"iw_dev": 0, "iw_link": 0}

    def fake_run(
        command: list[str], capture_output: bool = True, text: bool = True
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        if command == ["iw", "dev"]:
            calls["iw_dev"] += 1
            return _completed(stdout="phy#0\n\tInterface wlp2s0\n")
        if command == ["iw", "dev", "wlp2s0", "link"]:
            calls["iw_link"] += 1
            return _completed(
                stdout=(
                    "Connected to 11:22:33:44:55:66 (on wlp2s0)\n\tSSID: Layout WiFi\n\tfreq: 5180\n\tsignal: -61 dBm\n"
                )
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("src.pytrain.utils.wifi_info.subprocess.run", fake_run)

    wifi = WiFiInfo(system="Linux")
    first = wifi.query()
    second = wifi.query()

    assert first.interface == "wlp2s0"
    assert second.interface == "wlp2s0"
    assert calls["iw_dev"] == 1
    assert calls["iw_link"] == 2


def test_linux_procfs_fallback_reads_signal_from_proc_net_wireless(monkeypatch: MonkeyPatch) -> None:
    procfs = (
        "Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE\n"
        " face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22\n"
        "wlan1: 0000   70.  -42.  -92.        0      0      0      0      0        0\n"
    )

    def fake_run(
        command: list[str], capture_output: bool = True, text: bool = True
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        if command == ["iw", "dev"]:
            return _completed(returncode=1)
        if command == ["iwgetid", "wlan1", "--raw"]:
            return _completed(stdout="Fallback WiFi\n")
        raise AssertionError(f"unexpected command: {command}")

    def fake_exists(path: str) -> bool:
        return path == "/proc/net/wireless"

    def fake_open(path: str, *_args: Any, **_kwargs: Any) -> StringIO:
        if path == "/proc/net/wireless":
            return StringIO(procfs)
        raise FileNotFoundError(path)

    monkeypatch.setattr("src.pytrain.utils.wifi_info.subprocess.run", fake_run)
    monkeypatch.setattr("src.pytrain.utils.wifi_info.os.path.exists", fake_exists)
    monkeypatch.setattr("builtins.open", fake_open)

    snapshot = WiFiInfo(system="Linux").query()

    assert snapshot.source == "procfs:/proc/net/wireless"
    assert snapshot.interface == "wlan1"
    assert snapshot.connected is True
    assert snapshot.ssid == "Fallback WiFi"
    assert snapshot.signal_dbm == -42
    assert snapshot.noise_dbm == -92
    assert snapshot.quality == 100
    assert snapshot.quality_label == "Excellent"


def test_macos_airport_output_is_parsed(monkeypatch: MonkeyPatch) -> None:
    airport_output = (
        "     agrCtlRSSI: -67\n"
        "     agrCtlNoise: -92\n"
        "     state: running\n"
        "     SSID: Yard Network\n"
        "     BSSID: 66:55:44:33:22:11\n"
        "     channel: 149,1\n"
    )

    def fake_run(
        command: list[str], capture_output: bool = True, text: bool = True
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        assert command == [
            "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
            "-I",
        ]
        return _completed(stdout=airport_output)

    monkeypatch.setattr("src.pytrain.utils.wifi_info.subprocess.run", fake_run)

    snapshot = WiFiInfo(system="Darwin").query()

    assert snapshot.source == "airport"
    assert snapshot.connected is True
    assert snapshot.ssid == "Yard Network"
    assert snapshot.bssid == "66:55:44:33:22:11"
    assert snapshot.signal_dbm == -67
    assert snapshot.noise_dbm == -92
    assert snapshot.channel == "149,1"
    assert snapshot.quality == 66
