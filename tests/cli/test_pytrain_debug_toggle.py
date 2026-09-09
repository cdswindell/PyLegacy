#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# tests/cli/test_pytrain_debug_toggle.py
import logging

import pytest

from src.pytrain.cli.pytrain import PyTrain


@pytest.fixture
def root_at_info():
    """Put the root logger and its handlers at INFO, as a default setup leaves them."""
    root = logging.getLogger()
    saved = (root.level, [(h, h.level) for h in root.handlers])
    root.setLevel(logging.INFO)
    for handler in root.handlers:
        handler.setLevel(logging.INFO)
    yield root
    root.setLevel(saved[0])
    for handler, level in saved[1]:
        handler.setLevel(level)


def _stub_pytrain() -> PyTrain:
    obj = PyTrain.__new__(PyTrain)
    obj._debug = False
    return obj


def test_debug_toggle_moves_every_module_logger(root_at_info):
    # a module logger that is not pytrain.cli.pytrain: it can only gain DEBUG via the root
    other = logging.getLogger("src.pytrain.comm.comm_buffer")
    assert other.level == logging.NOTSET
    assert other.isEnabledFor(logging.DEBUG) is False

    obj = _stub_pytrain()
    obj._enable_debug()
    assert obj.debug is True
    assert root_at_info.level == logging.DEBUG
    assert all(h.level == logging.DEBUG for h in root_at_info.handlers)
    assert other.isEnabledFor(logging.DEBUG) is True

    obj._disable_debug()
    assert obj.debug is False
    assert root_at_info.level == logging.INFO
    assert all(h.level == logging.INFO for h in root_at_info.handlers)
    assert other.isEnabledFor(logging.DEBUG) is False


def test_debug_property_toggles_through_the_same_path(root_at_info):
    other = logging.getLogger("src.pytrain.comm.comm_buffer")
    obj = _stub_pytrain()

    obj.debug = True
    assert other.isEnabledFor(logging.DEBUG) is True

    obj.debug = False
    assert other.isEnabledFor(logging.DEBUG) is False
