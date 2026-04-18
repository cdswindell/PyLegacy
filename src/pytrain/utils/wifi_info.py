#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import re
import subprocess

MACOS_AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
PROC_NET_WIFI_FILES = ("/proc/net/wifi", "/proc/net/wireless")

IW_INTERFACE_RE = re.compile(r"^\s*Interface\s+(?P<interface>\S+)\s*$")
IW_CONNECTED_RE = re.compile(r"^Connected to (?P<bssid>\S+)(?: \(on (?P<interface>\S+)\))?$")


@dataclass(frozen=True)
class WiFiSnapshot:
    interface: str | None = None
    ssid: str | None = None
    bssid: str | None = None
    signal_dbm: float | None = None
    noise_dbm: float | None = None
    quality: int | None = None
    frequency_mhz: float | None = None
    channel: str | None = None
    connected: bool = False
    source: str | None = None

    @property
    def quality_label(self) -> str:
        return WiFiInfo.quality_label(self.quality)


class WiFiInfo:
    def __init__(self, system: str | None = None) -> None:
        self._system = system or platform.system()
        self._interface: str | None = None
        self._linux_source: str | None = None

    def query(self) -> WiFiSnapshot:
        if self._system == "Darwin":
            return self._query_macos() or WiFiSnapshot()
        if self._system == "Linux":
            return self._query_linux() or WiFiSnapshot()
        return WiFiSnapshot()

    @staticmethod
    def dbm_to_quality(signal_dbm: float | int | None) -> int | None:
        if signal_dbm is None:
            return None
        best_signal_dbm = -35.0
        worst_signal_dbm = -100.0
        if signal_dbm <= worst_signal_dbm:
            return 0
        if signal_dbm >= best_signal_dbm:
            return 100
        quality = ((float(signal_dbm) - worst_signal_dbm) / (best_signal_dbm - worst_signal_dbm)) * 100.0
        return int(round(quality))

    @staticmethod
    def quality_label(quality: int | None) -> str:
        if quality is None:
            return "Unknown"
        if quality >= 80:
            return "Excellent"
        if quality >= 60:
            return "Very Good"
        if quality >= 40:
            return "Good"
        if quality >= 20:
            return "Fair"
        return "Poor"

    def _query_linux(self) -> WiFiSnapshot | None:
        if self._linux_source == "iw" and self._interface:
            snapshot = self._query_linux_with_iw(self._interface)
            if snapshot is not None:
                return snapshot

        if self._linux_source and self._linux_source.startswith("procfs:") and self._interface:
            snapshot = self._read_procfs_snapshot(self._linux_source.removeprefix("procfs:"), self._interface)
            if snapshot is not None:
                return snapshot

        return self._query_linux_with_iw() or self._query_linux_with_procfs()

    def _query_linux_with_iw(self, interface: str | None = None) -> WiFiSnapshot | None:
        interfaces = [interface] if interface else self._discover_iw_interfaces()
        first_snapshot = None
        for interface in interfaces:
            link_result = self._run_command(["iw", "dev", interface, "link"])
            if link_result is None or link_result.returncode != 0:
                continue
            snapshot = self._parse_iw_link(interface, link_result.stdout)
            if snapshot is None:
                continue
            self._remember_snapshot(snapshot)
            if snapshot.connected:
                return snapshot
            if first_snapshot is None:
                first_snapshot = snapshot
        return first_snapshot

    def _query_linux_with_procfs(self) -> WiFiSnapshot | None:
        for path in PROC_NET_WIFI_FILES:
            snapshot = self._read_procfs_snapshot(path)
            if snapshot is not None:
                self._remember_snapshot(snapshot)
                return snapshot
        return None

    def _discover_iw_interfaces(self) -> list[str]:
        result = self._run_command(["iw", "dev"])
        if result is None or result.returncode != 0:
            return []
        return self._parse_iw_interfaces(result.stdout)

    def _query_macos(self) -> WiFiSnapshot | None:
        result = self._run_command([MACOS_AIRPORT, "-I"])
        if result is None or result.returncode != 0:
            return None

        values: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()

        signal_dbm = self._to_float(values.get("agrCtlRSSI"))
        noise_dbm = self._to_float(values.get("agrCtlNoise"))
        connected = values.get("state") == "running" and bool(values.get("SSID"))
        return WiFiSnapshot(
            ssid=values.get("SSID"),
            bssid=values.get("BSSID"),
            signal_dbm=signal_dbm,
            noise_dbm=noise_dbm,
            quality=self.dbm_to_quality(signal_dbm),
            channel=values.get("channel"),
            connected=connected,
            source="airport",
        )

    @classmethod
    def _parse_iw_interfaces(cls, output: str) -> list[str]:
        interfaces = list()
        for line in output.splitlines():
            match = IW_INTERFACE_RE.match(line)
            if match:
                interfaces.append(match.group("interface"))
        return interfaces

    @classmethod
    def _parse_iw_link(cls, interface: str, output: str) -> WiFiSnapshot | None:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not lines:
            return None

        connected = False
        bssid = None
        signal_dbm = None
        ssid = None
        frequency_mhz = None

        match = IW_CONNECTED_RE.match(lines[0])
        if match:
            connected = True
            bssid = match.group("bssid")
            interface = match.group("interface") or interface

        for line in lines[1:] if connected else lines:
            if line.startswith("SSID:"):
                ssid = line.split(":", 1)[1].strip()
            elif line.startswith("freq:"):
                frequency_mhz = cls._to_float(line.split(":", 1)[1].strip())
            elif line.startswith("signal:"):
                signal_text = line.split(":", 1)[1].replace("dBm", "").strip()
                signal_dbm = cls._to_float(signal_text)

        return WiFiSnapshot(
            interface=interface,
            ssid=ssid,
            bssid=bssid,
            signal_dbm=signal_dbm,
            quality=cls.dbm_to_quality(signal_dbm),
            frequency_mhz=frequency_mhz,
            connected=connected,
            source="iw",
        )

    def _read_procfs_snapshot(self, path: str, interface: str | None = None) -> WiFiSnapshot | None:
        if not os.path.exists(path):
            return None

        try:
            with open(path) as fp:
                lines = fp.readlines()
        except OSError:
            return None

        for line in lines[2:]:
            if ":" not in line:
                continue
            line_interface, payload = line.split(":", 1)
            line_interface = line_interface.strip()
            if interface is not None and line_interface != interface:
                continue
            stats = payload.split()
            if len(stats) < 3:
                continue

            signal_dbm = self._to_float(stats[2].rstrip("."))
            if signal_dbm is None:
                continue

            noise_dbm = self._to_float(stats[3].rstrip(".")) if len(stats) > 3 else None
            return WiFiSnapshot(
                interface=line_interface,
                ssid=self._query_linux_ssid(line_interface),
                signal_dbm=signal_dbm,
                noise_dbm=noise_dbm,
                quality=self.dbm_to_quality(signal_dbm),
                connected=True,
                source=f"procfs:{path}",
            )
        return None

    def _query_linux_ssid(self, interface: str) -> str | None:
        result = self._run_command(["iwgetid", interface, "--raw"])
        if result is None or result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None

    @staticmethod
    def _run_command(command: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(command, capture_output=True, text=True)
        except OSError:
            return None

    @staticmethod
    def _to_float(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _remember_snapshot(self, snapshot: WiFiSnapshot) -> None:
        if snapshot.interface:
            self._interface = snapshot.interface
        if snapshot.source:
            self._linux_source = snapshot.source
