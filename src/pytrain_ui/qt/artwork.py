"""Cache engine artwork with conservative vertical whitespace trimming."""

from __future__ import annotations

import hashlib
import logging
import os
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from queue import Queue
from threading import Thread
from weakref import ReferenceType, ref
from tempfile import NamedTemporaryFile

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QImage, QImageReader

from pytrain.utils.path_utils import cache_directory

log = logging.getLogger(__name__)


def cached_artwork(source: str | Path | None, *, directory: str | Path | None = None) -> str | None:
    """Return a trimmed display copy, retaining the original if preparation fails."""
    if source is None:
        return None
    try:
        path = Path(source).resolve()
        stat = path.stat()
        destination = Path(directory) if directory is not None else cache_directory("qt_artwork")
        key = (str(path), stat.st_mtime_ns, stat.st_size, str(destination.resolve()))
        result = _prepare(*key)
        if result != str(path) and not Path(result).is_file():
            _prepare.cache_clear()
            result = _prepare(*key)
        return result
    except OSError as error:
        log.warning("Unable to prepare engine artwork %s: %s", source, error)
        return str(source)


@lru_cache(maxsize=256)
def _prepare(source: str, modified: int, size: int, directory: str) -> str:
    fingerprint = hashlib.sha256(f"vertical-trim-v1\0{source}\0{modified}\0{size}".encode()).hexdigest()
    target = Path(directory) / f"{fingerprint}.png"
    if target.is_file():
        return str(target)
    temporary = None
    try:
        reader = QImageReader(source)
        # Do not turn an animated product image into a single-frame preview.
        if reader.supportsAnimation():
            return source
        image = reader.read()
        if image.isNull():
            return source
        pixels = image.convertToFormat(QImage.Format.Format_RGBA8888)
        data = pixels.constBits()
        stride = pixels.bytesPerLine()

        def blank_row(row: int) -> bool:
            start = row * stride
            end = start + pixels.width() * 4
            return all(
                alpha <= 16 or (red >= 245 and green >= 245 and blue >= 245)
                for red, green, blue, alpha in zip(
                    data[start:end:4], data[start + 1 : end : 4], data[start + 2 : end : 4], data[start + 3 : end : 4]
                )
            )

        top, bottom = 0, pixels.height()
        while top < bottom and blank_row(top):
            top += 1
        if top == bottom:
            return source
        while bottom > top and blank_row(bottom - 1):
            bottom -= 1
        # Retain two pixels around the content, including pale smoke and fine lines.
        top = max(0, top - 2)
        bottom = min(pixels.height(), bottom + 2)
        if top == 0 and bottom == pixels.height():
            return source
        target.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=target.parent, prefix=".artwork-", suffix=".png", delete=False) as handle:
            temporary = Path(handle.name)
        if not image.copy(0, top, image.width(), bottom - top).save(str(temporary)):
            raise OSError("Unable to save trimmed artwork")
        os.replace(temporary, target)
        return str(target)
    except OSError as error:
        log.warning("Unable to cache trimmed engine artwork %s: %s", source, error)
        return source
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


class ArtworkLoader(QObject):
    artworkReady = Signal(str)
    prepared = Signal(object, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._results: dict[tuple[str, int, int], str] = {}
        self._pending: set[tuple[str, int, int]] = set()
        self._requests: Queue[tuple[str, int, int] | None] = Queue()
        self._worker: Thread | None = None
        self._closed = False
        self.prepared.connect(self._record, Qt.ConnectionType.QueuedConnection)

    def request(self, source: str | Path | None) -> str | None:
        """Return immediately; prepare any missing display image in the worker."""
        if source is None:
            return None
        try:
            path = Path(source).resolve()
            stat = path.stat()
        except OSError:
            return str(source)
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        result = self._results.get(key)
        if result is not None and Path(result).is_file():
            return result
        if not self._closed and key not in self._pending:
            self._pending.add(key)
            self._requests.put(key)
            if self._worker is None:
                self._worker = Thread(target=_load_requests, args=(self._requests, ref(self)), daemon=True)
                self._worker.start()
        return str(source)

    @Slot(object, str)
    def _record(self, key: tuple[str, int, int], result: str) -> None:
        self._pending.discard(key)
        if not self._closed:
            self._results[key] = result
            self.artworkReady.emit(key[0])

    def close(self) -> None:
        """Never wait for image work during GUI shutdown."""
        self._closed = True
        self._requests.put(None)


def _load_requests(requests: Queue, receiver: ReferenceType[ArtworkLoader]) -> None:
    while (key := requests.get()) is not None:
        loader = receiver()
        if loader is None or loader._closed:
            return
        del loader
        result = cached_artwork(key[0]) or key[0]
        loader = receiver()
        if loader is None:
            return
        try:
            loader.prepared.emit(key, result)
        except RuntimeError:
            # The Qt owner may already be destroyed; this daemon must not hold up exit.
            return
        del loader
