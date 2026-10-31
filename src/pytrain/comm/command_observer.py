#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Asynchronous observation of commands transmitted to the Base 3."""

from __future__ import annotations

import logging
from collections import defaultdict
from enum import Enum
from queue import SimpleQueue
from threading import RLock, Thread
from typing import Callable

from ..pdi.constants import KEEP_ALIVE_CMD, PDI_SOP, PdiCommand
from ..pdi.pdi_req import PdiReq, TmccReq
from ..protocol.command_req import CommandReq, TMCC_FIRST_BYTE_TO_INTERPRETER

log = logging.getLogger(__name__)

CommandHandler = Callable[[CommandReq], None]


class CommandObserver(Thread):
    """Decode sent bytes off the Base 3 transmission thread and notify handlers."""

    _instance: CommandObserver | None = None
    _lock = RLock()

    @classmethod
    def get(cls) -> CommandObserver:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def offer(cls, data: bytes) -> None:
        """Nonblocking producer; do not decode or call handlers on the sender."""
        if data and data != KEEP_ALIVE_CMD:
            cls.get()._queue.put(bytes(data))

    @classmethod
    def register(cls, command: Enum, handler: CommandHandler) -> None:
        observer = cls.get()
        with observer._handlers_lock:
            observer._handlers[command].add(handler)

    @classmethod
    def unregister(cls, command: Enum, handler: CommandHandler) -> None:
        with cls._lock:
            observer = cls._instance
        if observer is not None:
            with observer._handlers_lock:
                observer._handlers[command].discard(handler)

    @classmethod
    def stop(cls) -> None:
        with cls._lock:
            observer = cls._instance
            cls._instance = None
        if observer is not None:
            observer._queue.put(None)
            if observer is not observer.current_thread():
                observer.join(timeout=2)

    def __init__(self) -> None:
        super().__init__(daemon=True, name="PyTrain Command Observer")
        self._queue: SimpleQueue[bytes | None] = SimpleQueue()
        self._handlers: dict[Enum, set[CommandHandler]] = defaultdict(set)
        self._handlers_lock = RLock()
        self.start()

    @staticmethod
    def _decode(data: bytes) -> list[CommandReq]:
        if data[0] == PDI_SOP:
            if len(data) < 4 or data[1] not in {PdiCommand.TMCC_TX, PdiCommand.TMCC4_TX}:
                return []
            request = PdiReq.from_bytes(data)
            return [request.tmcc_command] if isinstance(request, TmccReq) else []

        commands = []
        sequence = bytearray()
        for byte in data:
            if byte in TMCC_FIRST_BYTE_TO_INTERPRETER and len(sequence) >= 3:
                commands.append(CommandReq.from_bytes(bytes(sequence)))
                sequence.clear()
            sequence.append(byte)
        if sequence:
            commands.append(CommandReq.from_bytes(bytes(sequence)))
        return commands

    def run(self) -> None:
        while True:
            data = self._queue.get()
            if data is None:
                return
            try:
                for request in self._decode(data):
                    with self._handlers_lock:
                        handlers = tuple(self._handlers.get(request.command, ()))
                    for handler in handlers:
                        try:
                            handler(request)
                        except Exception:
                            log.exception("Command observer handler failed for %s", request)
            except (ValueError, NotImplementedError):
                log.debug("Ignoring unrecognized outgoing command: %s", data.hex())
            except Exception:
                log.exception("Failed to observe outgoing command: %s", data.hex())
