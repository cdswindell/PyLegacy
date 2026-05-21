#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import base64
import json
import logging
import os
import socket
import socketserver
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from queue import Empty, Queue
from threading import Event, Lock, Thread
from time import monotonic
from typing import Callable

from . import prod_info
from ..protocol.constants import DEFAULT_SERVER_PORT, PROGRAM_NAME

log = logging.getLogger(__name__)

DEFAULT_CACHE_SYNC_DEBOUNCE = float(os.environ.get("PYTRAIN_CACHE_SYNC_DEBOUNCE", "1.0"))
DEFAULT_CACHE_SYNC_POLL = float(os.environ.get("PYTRAIN_CACHE_SYNC_POLL", "30.0"))
DEFAULT_CACHE_SYNC_TIMEOUT = float(os.environ.get("PYTRAIN_CACHE_SYNC_TIMEOUT", "30.0"))
DEFAULT_CACHE_SYNC_CONNECT_TIMEOUT = float(os.environ.get("PYTRAIN_CACHE_SYNC_CONNECT_TIMEOUT", "2.0"))
DEFAULT_CACHE_SYNC_MAX_PAYLOAD = int(os.environ.get("PYTRAIN_CACHE_SYNC_MAX_PAYLOAD", str(64 * 1024 * 1024)))


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
            elif command == "sync":
                content_length = int(request.get("content_length") or 0)
                if content_length < 0 or content_length > DEFAULT_CACHE_SYNC_MAX_PAYLOAD:
                    response = {"ok": False, "error": "cache sync payload too large"}
                else:
                    payload_raw = self.rfile.read(content_length)
                    payload = json.loads(payload_raw.decode("utf-8")) if payload_raw else {}
                    manager.apply_sync_payload(payload)
                    response = {"ok": True}
            elif command == "delete":
                deleted = manager.delete_cache_file(
                    request.get("file_name"),
                    propagate=bool(request.get("propagate", True)),
                )
                response = {"ok": True, "deleted": deleted}
            else:
                response = {"ok": False, "error": "unsupported command"}
        except Exception as e:
            log.debug("Engine info cache request failed: %s", e)
            response = {"ok": False, "error": str(e)}
        self.wfile.write((json.dumps(response) + "\n").encode("utf-8"))


class SidecarCacheTransport:
    def __init__(self, *, timeout: float = DEFAULT_CACHE_SYNC_TIMEOUT) -> None:
        self._timeout = timeout

    @property
    def available(self) -> bool:
        return True

    def sync_to_peer(
        self,
        host: str,
        port: int,
        local_paths: CacheSyncPaths,
        remote_paths: CacheSyncPaths,
        *,
        delete: bool,
    ) -> bool:
        try:
            body = json.dumps(self.build_payload(local_paths, remote_paths, delete=delete)).encode("utf-8")
            if len(body) > DEFAULT_CACHE_SYNC_MAX_PAYLOAD:
                log.warning(
                    "Cache sync skipped for %s: payload is larger than %s bytes",
                    host,
                    DEFAULT_CACHE_SYNC_MAX_PAYLOAD,
                )
                return False
            response = CacheSyncManager.sidecar_request(
                host,
                port,
                {"command": "sync", "content_length": len(body)},
                body,
                timeout=self._timeout,
            )
            if response.get("ok"):
                return True
            log.warning(
                "Engine info cache rejected sync to %s:%s: %s",
                host,
                port,
                response.get("error", "unknown error"),
            )
        except Exception as e:
            log.warning("Engine info cache transfer failed to %s:%s: %s", host, port, e)
        return False

    def delete_from_peer(self, host: str, port: int, file_name: str, *, propagate: bool) -> bool:
        try:
            response = CacheSyncManager.sidecar_request(
                host,
                port,
                {"command": "delete", "file_name": self._safe_file_name(file_name), "propagate": propagate},
                timeout=self._timeout,
            )
            if response.get("ok"):
                return True
            log.warning(
                "Engine info cache rejected delete request to %s:%s: %s",
                host,
                port,
                response.get("error", "unknown error"),
            )
        except Exception as e:
            log.warning("Engine info cache delete request failed to %s:%s: %s", host, port, e)
        return False

    @classmethod
    def build_payload(cls, local_paths: CacheSyncPaths, remote_paths: CacheSyncPaths, *, delete: bool) -> dict:
        payload = {"delete": delete, "caches": [], "files": []}
        for cache_name, local_path, _remote_path in local_paths.iter_pairs(remote_paths):
            payload["caches"].append(cache_name)
            if not local_path.is_dir():
                continue
            for path in local_path.rglob("*"):
                if not path.is_file():
                    continue
                try:
                    rel = path.relative_to(local_path).as_posix()
                    content = base64.b64encode(path.read_bytes()).decode("ascii")
                    stat = path.stat()
                    payload["files"].append(
                        {
                            "cache": cache_name,
                            "path": rel,
                            "content": content,
                            "mtime_ns": stat.st_mtime_ns,
                        }
                    )
                except OSError as e:
                    log.debug("Skipping cache file %s during sync: %s", path, e)
        return payload

    @classmethod
    def apply_payload(cls, local_paths: CacheSyncPaths, payload: dict, skip_file_names: set[str] | None = None) -> None:
        roots = cls._roots(local_paths)
        caches = [cache_name for cache_name in payload.get("caches", []) if cache_name in roots]
        incoming: dict[str, set[str]] = {cache_name: set() for cache_name in caches}
        skip_file_names = skip_file_names or set()

        for item in payload.get("files", []):
            cache_name = item.get("cache")
            if cache_name not in roots:
                continue
            rel = cls._safe_relative_path(item.get("path"))
            if rel.name in skip_file_names:
                continue
            incoming.setdefault(cache_name, set()).add(rel.as_posix())
            target = roots[cache_name].joinpath(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(item.get("content") or ""))
            mtime_ns = item.get("mtime_ns")
            if isinstance(mtime_ns, int):
                os.utime(target, ns=(mtime_ns, mtime_ns))

        if payload.get("delete"):
            cls._delete_stale_files(roots, incoming)

    @classmethod
    def delete_matching_files(cls, local_paths: CacheSyncPaths, file_name: str) -> int:
        file_name = cls._safe_file_name(file_name)
        deleted = 0
        roots = cls._roots(local_paths)
        for root in roots.values():
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.name != file_name or not (path.is_file() or path.is_symlink()):
                    continue
                try:
                    path.unlink()
                    deleted += 1
                except OSError as e:
                    log.debug("Failed to delete cache file %s: %s", path, e)
        cls._delete_empty_dirs(roots)
        return deleted

    @staticmethod
    def _roots(paths: CacheSyncPaths) -> dict[str, Path]:
        roots: dict[str, Path] = {}
        if paths.engine_info is not None:
            roots["engine_info"] = paths.engine_info
        if paths.engine_images is not None:
            roots["engine_images"] = paths.engine_images
        return roots

    @staticmethod
    def _safe_relative_path(value: str | None) -> PurePosixPath:
        if not value:
            raise ValueError("cache sync file path is required")
        rel = PurePosixPath(value)
        if "\\" in value or rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
            raise ValueError(f"unsafe cache sync file path: {value}")
        return rel

    @staticmethod
    def _safe_file_name(value: str | None) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError("cache file name is required")
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError(f"unsafe cache file name: {value}")
        return value

    @staticmethod
    def _delete_stale_files(roots: dict[str, Path], incoming: dict[str, set[str]]) -> None:
        for cache_name, root in roots.items():
            keep = incoming.get(cache_name)
            if keep is None or not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(root).as_posix()
                if rel in keep or SidecarCacheTransport._preserve_file(cache_name, rel):
                    continue
                try:
                    path.unlink()
                except OSError as e:
                    log.debug("Failed to delete stale cache file %s: %s", path, e)
        SidecarCacheTransport._delete_empty_dirs(roots)

    @staticmethod
    def _delete_empty_dirs(roots: dict[str, Path]) -> None:
        for root in roots.values():
            if not root.is_dir():
                continue
            for path in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
                try:
                    path.rmdir()
                except OSError:
                    pass

    @staticmethod
    def _preserve_file(cache_name: str, rel: str) -> bool:
        path = PurePosixPath(rel)
        return cache_name == "engine_images" and path.stem.isdigit() and path.name.endswith(".jpg")


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
        transport: SidecarCacheTransport | None = None,
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
        from ..cli.pytrain import PyTrain

        if cls._instance is None:
            if PyTrain.current(raise_exception=False):
                if PyTrain.current().is_client:
                    log.warning(
                        "Cache sync skipped: the connected server does not advertise cache sync support. "
                        "Upgrade the server or restart it with cache sync enabled to accept client cache files."
                    )
                else:
                    log.warning(
                        "Cache sync skipped: cache sync is disabled or unavailable. Restart without -no_cache_sync."
                    )
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
        transport: SidecarCacheTransport | None,
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
        self._transport = transport or SidecarCacheTransport()
        self._debounce = debounce
        self._poll_interval = poll_interval
        self._queue: Queue[tuple[CacheSyncEvent, CachePeer | None]] = Queue()
        self._shutdown = Event()
        self._server: CacheSyncTCPServer | None = None
        self._server_thread: Thread | None = None
        self._delete_tombstones: dict[str, int] = {}
        self._delete_tombstone_lock = Lock()
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
            log.info("Cache sync skipped: local engine info cache listener is unavailable")
            return
        if self._is_server:
            self._sync_to_clients()
        else:
            self._sync_to_server()
        self._manifest = self._cache_manifest()

    def apply_sync_payload(self, payload: dict) -> None:
        skip_file_names = self._delete_tombstone_snapshot() if self._is_server else set()
        SidecarCacheTransport.apply_payload(
            CacheSyncPaths.current(create=True),
            payload,
            skip_file_names=skip_file_names,
        )
        self.mark_cache_synced()

    def delete_cache_file(self, file_name: str, *, propagate: bool = True) -> int:
        file_name = SidecarCacheTransport._safe_file_name(file_name)
        if propagate and self._is_server:
            self._add_delete_tombstone(file_name)
            try:
                deleted = self._delete_local_cache_file(file_name)
                self._delete_from_clients(file_name)
                return deleted
            finally:
                self._remove_delete_tombstone(file_name)
                self._manifest = self._cache_manifest()

        deleted = self._delete_local_cache_file(file_name)
        if propagate:
            self._delete_from_server(file_name)
        self._manifest = self._cache_manifest()
        return deleted

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
                name=f"{PROGRAM_NAME} Engine Info Cache",
            )
            self._server_thread.start()
            log.info("Engine info cache listening on port %s", self._sync_port)
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
            self._server_ip, self._server_sync_port, CacheSyncPaths.current(create=True), remote_paths, delete=False
        ):
            self._notify_peer_changed(self._server_ip, self._server_sync_port)

    def _sync_to_clients(self) -> None:
        for client_ip, _client_port in self._clients_provider():
            self._sync_to_client(CachePeer(client_ip, self._sync_port))

    def _sync_to_client(self, peer: CachePeer) -> None:
        remote_paths = self._probe(peer.host, peer.port)
        if remote_paths is None:
            return
        self._transport.sync_to_peer(
            peer.host,
            peer.port,
            CacheSyncPaths.current(create=True),
            remote_paths,
            delete=True,
        )

    def _delete_local_cache_file(self, file_name: str) -> int:
        deleted = SidecarCacheTransport.delete_matching_files(CacheSyncPaths.current(create=False), file_name)
        if deleted:
            log.info("Deleted %s cache file%s named %s", deleted, "" if deleted == 1 else "s", file_name)
        else:
            log.info("No cache files named %s found", file_name)
        return deleted

    def _delete_from_server(self, file_name: str) -> None:
        if not self._server_ip:
            return
        if self._server_advertised_sync is False:
            log.info("Cache delete propagation skipped: server does not advertise cache sync support")
            return
        self._transport.delete_from_peer(self._server_ip, self._server_sync_port, file_name, propagate=True)

    def _delete_from_clients(self, file_name: str) -> None:
        for client_ip, _client_port in self._clients_provider():
            self._transport.delete_from_peer(client_ip, self._sync_port, file_name, propagate=False)

    def _add_delete_tombstone(self, file_name: str) -> None:
        lock = self._get_delete_tombstone_lock()
        with lock:
            self._delete_tombstones[file_name] = self._delete_tombstones.get(file_name, 0) + 1

    def _remove_delete_tombstone(self, file_name: str) -> None:
        lock = self._get_delete_tombstone_lock()
        with lock:
            count = self._delete_tombstones.get(file_name, 0)
            if count <= 1:
                self._delete_tombstones.pop(file_name, None)
            else:
                self._delete_tombstones[file_name] = count - 1

    def _delete_tombstone_snapshot(self) -> set[str]:
        lock = self._get_delete_tombstone_lock()
        with lock:
            return set(self._delete_tombstones)

    def _get_delete_tombstone_lock(self) -> Lock:
        lock = getattr(self, "_delete_tombstone_lock", None)
        if lock is None:
            lock = Lock()
            self._delete_tombstone_lock = lock
        if not hasattr(self, "_delete_tombstones"):
            self._delete_tombstones = {}
        return lock

    def _probe(self, host: str, port: int) -> CacheSyncPaths | None:
        try:
            response = self.sidecar_request(host, port, {"command": "hello"})
            if response.get("ok") is True and response.get("cache_sync") is True:
                return CacheSyncPaths.from_wire_dict(response.get("paths") or {})
        except OSError:
            log.debug("Cache sync peer unavailable at %s:%s", host, port)
        except Exception as e:
            log.debug("Cache sync probe failed for %s:%s: %s", host, port, e)
        return None

    def _notify_peer_changed(self, host: str, port: int) -> None:
        try:
            self.sidecar_request(host, port, {"command": "changed"})
        except Exception as e:
            log.debug("Cache sync changed notification failed for %s:%s: %s", host, port, e)

    @staticmethod
    def sidecar_request(
        host: str,
        port: int,
        payload: dict,
        body: bytes | None = None,
        *,
        timeout: float = DEFAULT_CACHE_SYNC_CONNECT_TIMEOUT,
    ) -> dict:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            if body:
                sock.sendall(body)
            with sock.makefile("rb") as f:
                raw = f.readline(4096)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def mark_cache_synced(self) -> None:
        self._manifest = self._cache_manifest()

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
