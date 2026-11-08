# SPDX-License-Identifier: LGPL-3.0-only
import logging
import os

from src.pytrain.utils.logging_manager import LoggingManager


def test_explicit_initialization_is_idempotent(tmp_path):
    root = logging.getLogger()
    previous_handlers = tuple(root.handlers)
    previous_level = root.level
    old_pid, old_handlers = LoggingManager._pid, LoggingManager._handlers
    path = tmp_path / "pytrain.log"
    try:
        assert LoggingManager.initialize(logfile_file=str(path))
        first_handlers = LoggingManager._handlers
        assert len(first_handlers) == 2
        assert LoggingManager.is_initialized()
        logging.info("first message")
        assert LoggingManager.initialize(logfile_file=str(path))
        assert LoggingManager._handlers == first_handlers
        assert not (tmp_path / "pytrain.log.1").exists()
    finally:
        for handler in LoggingManager._handlers:
            root.removeHandler(handler)
            handler.close()
        root.setLevel(previous_level)
        LoggingManager._pid, LoggingManager._handlers = old_pid, old_handlers
        assert all(handler in root.handlers for handler in previous_handlers)


def test_inherited_pid_is_not_treated_as_initialized(tmp_path):
    root = logging.getLogger()
    previous_handlers = tuple(root.handlers)
    previous_level = root.level
    old_pid, old_handlers = LoggingManager._pid, LoggingManager._handlers
    path = tmp_path / "pytrain.log"
    try:
        assert LoggingManager.initialize(logfile_file=str(path))
        assert LoggingManager.is_initialized()
        LoggingManager._pid = os.getpid() + 1
        assert not LoggingManager.is_initialized()
    finally:
        for handler in LoggingManager._handlers:
            root.removeHandler(handler)
            handler.close()
        root.setLevel(previous_level)
        LoggingManager._pid, LoggingManager._handlers = old_pid, old_handlers
        assert all(handler in root.handlers for handler in previous_handlers)
