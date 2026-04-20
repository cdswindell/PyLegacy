#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import threading
import logging
import sys
import traceback


log = logging.getLogger(__name__)


def log_threads(prefix: str = "") -> None:
    threads = threading.enumerate()
    log.warning("%s threads=%d", prefix, len(threads))
    for t in threads:
        log.warning("%s thread name=%r ident=%r daemon=%r alive=%r", prefix, t.name, t.ident, t.daemon, t.is_alive())


def log_thread_counts() -> None:
    log_threads("thread counts")


def dump_all_thread_stacks(prefix: str = "") -> None:
    frames = sys._current_frames()
    by_ident = {t.ident: t for t in threading.enumerate()}
    for ident, frame in frames.items():
        t = by_ident.get(ident)
        name = t.name if t else f"unknown-{ident}"
        log.warning("%s stack for thread %r ident=%r", prefix, name, ident)
        stack = "".join(traceback.format_stack(frame))
        log.warning("%s%s", prefix, stack)
