#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# test/utils/test_dual_logging.py
import io
import logging
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from src.pytrain.utils.dual_logging import set_up_logging


def _reset_root_logger():
    logger = logging.getLogger()
    # close and remove handlers to avoid cross-test interference and file locks
    for h in list(logger.handlers):
        try:
            h.flush()
        except (OSError, ValueError, io.UnsupportedOperation):
            pass
        try:
            h.close()
        except (OSError, ValueError, io.UnsupportedOperation):
            pass
        logger.removeHandler(h)
    logging.shutdown()


@pytest.fixture(autouse=True)
def clean_logging():
    # ensure a clean logger before and after each test
    _reset_root_logger()
    yield
    _reset_root_logger()


def test_set_up_logging_stdout_and_file_levels_and_color(tmp_path: Path, capsys):
    log_file = tmp_path / "test_pytrain.log"
    # route console to stdout, info level; file uses default INFO level
    ok = set_up_logging(
        console_log_output="stdout",
        console_log_level="INFO",
        console_log_color=True,
        logfile_file=str(log_file),
        logfile_log_level="INFO",
        logfile_log_color=False,
        logfile_template="%(levelname)s %(message)s",
    )
    assert ok is True

    # capture stdout
    logging.debug("debug should not appear")
    logging.info("hello info")
    logging.warning("warn here")

    captured = capsys.readouterr()
    out = captured.out
    err = captured.err
    assert err == ""  # using stdout, so stderr should be empty
    # colorized output should include ANSI codes around messages
    assert "hello info" in out
    assert "warn here" in out
    assert "\x1b[" in out  # ANSI escape introduced by color formatter
    assert "debug should not appear" not in out  # console level is INFO

    # file should exist and contain INFO/WARNING but not DEBUG
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "INFO hello info" in content
    assert "WARNING warn here" in content
    assert "debug should not appear" not in content
    # no ANSI escapes expected in file when logfile_log_color=False
    assert "\x1b[" not in content


def test_set_up_logging_stderr_and_invalid_console_level(tmp_path: Path):
    # invalid console level
    ok = set_up_logging(
        console_log_output="stderr",
        console_log_level="NOPE",
        logfile_file=str(tmp_path / "x.log"),
    )
    assert ok is False


def test_set_up_logging_invalid_console_output(tmp_path: Path):
    # invalid console output
    ok = set_up_logging(
        console_log_output="nowhere",
        console_log_level="INFO",
        logfile_file=str(tmp_path / "x.log"),
    )
    assert ok is False


def test_set_up_logging_invalid_file_level(tmp_path: Path):
    # valid console settings; invalid logfile level should return False
    ok = set_up_logging(
        console_log_output="stdout",
        console_log_level="INFO",
        logfile_file=str(tmp_path / "x.log"),
        logfile_log_level="BANANAS",
    )
    assert ok is False


def test_console_formatter_includes_exception_trace(tmp_path: Path):
    # capture stdout by redirecting before setting up logging, so the handler binds to the redirected stream
    f = io.StringIO()
    with redirect_stdout(f):
        assert set_up_logging(
            console_log_output="stdout",
            console_log_level="INFO",
            logfile_file=str(tmp_path / "t.log"),
            logfile_template="%(message)s",
        )

        try:
            raise RuntimeError("boom")
        except RuntimeError:
            logging.exception("had an error")  # exc_info=True path

    out = f.getvalue()
    # message and traceback should appear
    assert "had an error" in out
    assert "Traceback" in out
    assert "RuntimeError: boom" in out


def test_rotating_file_handler_rollover_when_file_exists(tmp_path: Path):
    log_file = tmp_path / "roll.log"
    # pre-create a file to trigger rollover
    log_file.write_text("old content\n", encoding="utf-8")

    assert set_up_logging(
        console_log_output="stdout",
        console_log_level="WARNING",
        logfile_file=str(log_file),
        logfile_log_level="INFO",
        logfile_log_color=False,
        logfile_template="%(levelname)s %(message)s",
    )

    # after setup, existing file should have been rotated to .1 and a new file created
    rotated = tmp_path / "roll.log.1"
    assert rotated.exists()
    assert "old content" in rotated.read_text(encoding="utf-8")

    # new file should receive fresh logs
    logging.info("fresh")
    content = log_file.read_text(encoding="utf-8")
    assert "INFO fresh" in content
