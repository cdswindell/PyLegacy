#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import socketserver
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from time import monotonic
from typing import Callable

from . import prod_info
from ..protocol.constants import DEFAULT_SERVER_PORT, PROGRAM_NAME

log = logging.getLogger(__name__)

DEFAULT_CACHE_SYNC_DEBOUNCE = float(os.environ.get("PYTRAIN_CACHE_SYNC_DEBOUNCE", "1.0"))
DEFAULT_CACHE_SYNC_POLL = float(os.environ.get("PYTRAIN_CACHE_SYNC_POLL", "10.0"))
DEFAULT_CACHE_SYNC_TIMEOUT = float(os.environ.get("PYTRAIN_CACHE_SYNC_TIMEOUT", "30.0"))
DEFAULT_CACHE_SYNC_CONNECT_TIMEOUT = float(os.environ.get("PYTRAIN_CACHE_SYNC_CONNECT_TIMEOUT", "2.0"))
DEFAULT_CACHE_SYNC_USER = os.environ.get("PYTRAIN_CACHE_SYNC_USER", "")
DEFAULT_CACHE_SYNC_SSH_OPTS = os.environ.get(
    "PYTRAIN_CACHE_SYNC_SSH_OPTS",
    "-oBatchMode=yes -oConnectTimeout=5",
)


class CacheSyncEvent(Enum):
    LOCAL_CHANGED = "local_changed"
    LOCAL_CLEARED = "local_cleared"
    REMOTE_CHANGED = "remote_changed"
    CLIENT_CONNECTED = "client_connected"


@dataclass(frozen=True)
class CachePeer:
    host: str
    port: int


@dataclass(frozen=True)
class CacheSyncPaths:
    engine_info: Path | None
    engine_images: Path | None

    @classmethod
    def current(cls, create: bool = False) -> "CacheSyncPaths":
        paths = cls(
            cls._path(prod_info.ENGINE_INFO_CACHE_DIR),
            cls._path(prod_info.ENGINE_IMAGES_CACHE_DIR),
        )
        if create:
            for path in paths.iter_existing_or_configured():
                path.mkdir(parents=True, exist_ok=True)
        return paths

    @staticmethod
    def _path(value: str | None) -> Path | None:
        return Path(value).expanduser().resolve() if value else None

    def as_wire_dict(self) -> dict[str, str | None]:
        return {
            "engine_info": str(self.engine_info) if self.engine_info else None,
            "engine_images": str(self.engine_images) if self.engine_images else None,
        }

    @classmethod
    def from_wire_dict(cls, data: dict) -> "CacheSyncPaths":
        return cls(cls._path(data.get("engine_info")), cls._path(data.get("engine_images")))

    def iter_pairs(self, remote: "CacheSyncPaths"):
        if self.engine_info and remote.engine_info:
            yield "engine_info", self.engine_info, remote.engine_info
        if self.engine_images and remote.engine_images:
            yield "engine_images", self.engine_images, remote.engine_images

    def iter_existing_or_configured(self):
        for path in (self.engine_info, self.engine_images):
            if path is not None:
                yield path


class CacheSyncTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, request_handler_class, manager: "CacheSyncManager"):
        self.manager = manager
        super().__init__(server_address, request_handler_class)


class CacheSyncHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        manager: CacheSyncManager = self.server.manager
        try:
            raw = self.rfile.readline(4096)
            request = json.loads(raw.decode("utf-8")) if raw else {}
            command = request.get("command")
            if command == "hello":
                response = {
                    "ok": True,
                    "program": PROGRAM_NAME,
                    "cache_sync": True,
                    "paths": CacheSyncPaths.current(create=True).as_wire_dict(),
                }
            elif command == "changed":
                manager.enqueue(CacheSyncEvent.REMOTE_CHANGED)
                response = {"ok": True}
            else:
                response = {"ok": False, "error": "unsupported command"}
        except Exception as e:
            log.debug("Cache sync sidecar request failed: %s", e)
            response = {"ok": False, "error": str(e)}
        self.wfile.write((json.dumps(response) + "\n").encode("utf-8"))


class RsyncCacheTransport:
    def __init__(
        self,
        *,
        user: str = DEFAULT_CACHE_SYNC_USER,
        ssh_opts: str = DEFAULT_CACHE_SYNC_SSH_OPTS,
        timeout: float = DEFAULT_CACHE_SYNC_TIMEOUT,
    ) -> None:
        self._user = user.strip()
        self._ssh_opts = ssh_opts.strip()
        self._timeout = timeout
        rsync_name: str = "rsync"
        # noinspection PyDeprecation
        self._rsync: str | None = shutil.which(rsync_name)
        self._warned_missing = False

    @property
    def available(self) -> bool:
        return self._rsync is not None

    def sync_to_peer(
        self,
        host: str,
        local_paths: CacheSyncPaths,
        remote_paths: CacheSyncPaths,
        *,
        delete: bool,
    ) -> bool:
        if not self.available:
            if not self._warned_missing:
                log.warning("Cache sync disabled: rsync not found")
                self._warned_missing = True
            return False
        ok = True
        for cache_name, local_path, remote_path in local_paths.iter_pairs(remote_paths):
            if not local_path.is_dir():
                continue
            cmd = self.build_command(host, local_path, remote_path, cache_name=cache_name, delete=delete)
            try:
                completed = subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout, check=False)
                if completed.returncode != 0:
                    ok = False
                    stderr = completed.stderr.strip() or completed.stdout.strip()
                    log.warning("Cache sync rsync failed for %s to %s: %s", cache_name, host, stderr)
            except Exception as e:
                ok = False
                log.warning("Cache sync rsync failed for %s to %s: %s", cache_name, host, e)
        return ok

    def build_command(
        self,
        host: str,
        local_path: Path,
        remote_path: Path,
        *,
        cache_name: str,
        delete: bool,
    ) -> list[str]:
        remote_host = f"{self._user}@{host}" if self._user else host
        cmd = [self._rsync or "rsync", "-az"]
        if self._ssh_opts:
            cmd.extend(["-e", f"ssh {self._ssh_opts}"])
        if delete:
            cmd.append("--delete")
            if cache_name == "engine_images":
                cmd.extend(["--filter", "P /[0-9]*.jpg"])
        cmd.extend([f"{local_path}/", f"{remote_host}:{remote_path}/"])
        return cmd


class CacheSyncManager(Thread):
    _instance: "CacheSyncManager | None" = None
    _lock = Lock()

    @classmethod
    def build(
        cls,
        *,
        enabled: bool,
        is_server: bool,
        sync_port: int,
        server_ip: str | None = None,
        server_sync_port: int | None = None,
        server_advertised_sync: bool | None = None,
        clients_provider: Callable[[], set[tuple[str, int]]] | None = None,
        transport: RsyncCacheTransport | None = None,
    ) -> "CacheSyncManager | None":
        if not enabled:
            return None
        with cls._lock:
            if cls._instance is None:
                cls._instance = CacheSyncManager(
                    is_server=is_server,
                    sync_port=sync_port,
                    server_ip=server_ip,
                    server_sync_port=server_sync_port,
                    server_advertised_sync=server_advertised_sync,
                    clients_provider=clients_provider,
                    transport=transport,
                )
            return cls._instance

    @classmethod
    def current(cls) -> "CacheSyncManager | None":
        return cls._instance

    @classmethod
    def notify_cache_changed(cls) -> None:
        if cls._instance is not None:
            cls._instance.enqueue(CacheSyncEvent.LOCAL_CHANGED)

    @classmethod
    def notify_cache_cleared(cls) -> None:
        if cls._instance is not None:
            cls._instance.enqueue(CacheSyncEvent.LOCAL_CLEARED)

    @classmethod
    def stop(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown()
                cls._instance = None

    def __init__(
        self,
        *,
        is_server: bool,
        sync_port: int,
        server_ip: str | None,
        server_sync_port: int | None,
        server_advertised_sync: bool | None,
        clients_provider: Callable[[], set[tuple[str, int]]] | None,
        transport: RsyncCacheTransport | None,
        debounce: float = DEFAULT_CACHE_SYNC_DEBOUNCE,
        poll_interval: float = DEFAULT_CACHE_SYNC_POLL,
    ) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Cache Sync Manager")
        self._is_server = is_server
        self._sync_port = sync_port
        self._server_ip = server_ip
        self._server_sync_port = server_sync_port or sync_port
        self._server_advertised_sync = server_advertised_sync
        self._clients_provider = clients_provider or (lambda: set())
        self._transport = transport or RsyncCacheTransport()
        self._debounce = debounce
        self._poll_interval = poll_interval
        self._queue: Queue[tuple[CacheSyncEvent, CachePeer | None]] = Queue()
        self._shutdown = Event()
        self._server: CacheSyncTCPServer | None = None
        self._server_thread: Thread | None = None
        self._manifest = self._cache_manifest()
        self._sidecar_available = self._start_sidecar()
        self.start()

    @property
    def sidecar_available(self) -> bool:
        return self._sidecar_available

    @property
    def available(self) -> bool:
        return self._sidecar_available and (not self._is_server or self._transport.available)

    def enqueue(self, event: CacheSyncEvent, peer: CachePeer | None = None) -> None:
        self._queue.put((event, peer))

    def force_sync(self) -> None:
        if not self._is_server and self._server_advertised_sync is False:
            log.info("Cache sync skipped: server does not advertise cache sync support")
            return
        if not self._sidecar_available:
            log.info("Cache sync skipped: local cache sync sidecar is unavailable")
            return
        if self._is_server:
            self._sync_to_clients()
        else:
            self._sync_to_server()
        self._manifest = self._cache_manifest()

    def shutdown(self) -> None:
        self._shutdown.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self.is_alive():
            self.join(timeout=2.0)

    def _start_sidecar(self) -> bool:
        try:
            self._server = CacheSyncTCPServer(("", self._sync_port), CacheSyncHandler, self)
            self._server_thread = Thread(
                target=self._server.serve_forever,
                daemon=True,
                name=f"{PROGRAM_NAME} Cache Sync Sidecar",
            )
            self._server_thread.start()
            log.info("Cache sync sidecar listening on port %s", self._sync_port)
            return True
        except OSError as e:
            log.warning("Cache sync disabled: unable to listen on port %s: %s", self._sync_port, e)
            return False

    def run(self) -> None:
        if not self._is_server and self._server_ip and self._server_advertised_sync is not False:
            self.enqueue(CacheSyncEvent.LOCAL_CHANGED)

        next_poll = monotonic() + self._poll_interval
        while not self._shutdown.is_set():
            timeout = max(0.1, min(0.5, next_poll - monotonic()))
            try:
                event, peer = self._queue.get(timeout=timeout)
            except Empty:
                if monotonic() >= next_poll:
                    self._poll_for_changes()
                    next_poll = monotonic() + self._poll_interval
                continue
            try:
                self._drain_debounce()
                self._handle_event(event, peer)
                self._manifest = self._cache_manifest()
            finally:
                self._queue.task_done()

    def _drain_debounce(self) -> None:
        deadline = monotonic() + self._debounce
        while not self._shutdown.is_set():
            remaining = deadline - monotonic()
            if remaining <= 0:
                return
            try:
                self._queue.get(timeout=remaining)
                self._queue.task_done()
                deadline = monotonic() + self._debounce
            except Empty:
                return

    def _handle_event(self, event: CacheSyncEvent, peer: CachePeer | None) -> None:
        if self._is_server:
            if event == CacheSyncEvent.CLIENT_CONNECTED and peer is not None:
                self._sync_to_client(peer)
            else:
                self._sync_to_clients()
        elif event in {CacheSyncEvent.LOCAL_CHANGED, CacheSyncEvent.LOCAL_CLEARED}:
            self._sync_to_server()

    def _poll_for_changes(self) -> None:
        manifest = self._cache_manifest()
        if manifest != self._manifest:
            self.enqueue(CacheSyncEvent.LOCAL_CHANGED)
            self._manifest = manifest

    def _sync_to_server(self) -> None:
        if not self._server_ip:
            return
        remote_paths = self._probe(self._server_ip, self._server_sync_port)
        if remote_paths is None:
            return
        if self._transport.sync_to_peer(
            self._server_ip, CacheSyncPaths.current(create=True), remote_paths, delete=False
        ):
            self._notify_peer_changed(self._server_ip, self._server_sync_port)

    def _sync_to_clients(self) -> None:
        for client_ip, _client_port in self._clients_provider():
            self._sync_to_client(CachePeer(client_ip, self._sync_port))

    def _sync_to_client(self, peer: CachePeer) -> None:
        remote_paths = self._probe(peer.host, peer.port)
        if remote_paths is None:
            return
        self._transport.sync_to_peer(peer.host, CacheSyncPaths.current(create=True), remote_paths, delete=True)

    def _probe(self, host: str, port: int) -> CacheSyncPaths | None:
        try:
            response = self._sidecar_request(host, port, {"command": "hello"})
            if response.get("ok") is True and response.get("cache_sync") is True:
                return CacheSyncPaths.from_wire_dict(response.get("paths") or {})
        except OSError:
            log.debug("Cache sync peer unavailable at %s:%s", host, port)
        except Exception as e:
            log.debug("Cache sync probe failed for %s:%s: %s", host, port, e)
        return None

    def _notify_peer_changed(self, host: str, port: int) -> None:
        try:
            self._sidecar_request(host, port, {"command": "changed"})
        except Exception as e:
            log.debug("Cache sync changed notification failed for %s:%s: %s", host, port, e)

    @staticmethod
    def _sidecar_request(host: str, port: int, payload: dict) -> dict:
        with socket.create_connection((host, port), timeout=DEFAULT_CACHE_SYNC_CONNECT_TIMEOUT) as sock:
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            with sock.makefile("rb") as f:
                raw = f.readline(4096)
        return json.loads(raw.decode("utf-8")) if raw else {}

    @staticmethod
    def _cache_manifest() -> tuple[tuple[str, int, int], ...]:
        entries: list[tuple[str, int, int]] = []
        paths = CacheSyncPaths.current(create=False)
        for cache_name, root in (("engine_info", paths.engine_info), ("engine_images", paths.engine_images)):
            if root is None or not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                try:
                    stat = path.stat()
                    rel = path.relative_to(root).as_posix()
                    entries.append((f"{cache_name}/{rel}", stat.st_size, stat.st_mtime_ns))
                except OSError:
                    continue
        return tuple(sorted(entries))


def default_cache_sync_port(server_port: int = DEFAULT_SERVER_PORT) -> int:
    return int(server_port) + 100
