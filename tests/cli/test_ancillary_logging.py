# SPDX-License-Identifier: LGPL-3.0-only
"""Verify every installed ancillary entry point explicitly starts logging."""

import importlib

import pytest

from src.pytrain.utils.logging_manager import LoggingManager


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    [
        ("pycab", "PyCabCli"),
        ("configure", "Configure"),
        ("lcs", "LcsCli"),
        ("make_gui", "MakeGui"),
        ("make_service", "MakeService"),
        ("cache", "CacheCli"),
        ("clear", "ClearCli"),
        ("routes", "RoutesCli"),
        ("piconfig", "PiConfig"),
        ("reindex", "ReindexCli"),
    ],
)
def test_ancillary_entry_point_initializes_logging(monkeypatch, module_name, class_name):
    module = importlib.import_module(f"src.pytrain.cli.{module_name}")
    events = []

    def initialize(**kwargs):
        events.append("logging")
        return True

    def construct(*args, **kwargs):
        events.append("application")

    monkeypatch.setattr(LoggingManager, "initialize", initialize)
    monkeypatch.setattr(module, class_name, construct)
    assert module.main([]) == 0
    assert events == ["logging", "application"]
