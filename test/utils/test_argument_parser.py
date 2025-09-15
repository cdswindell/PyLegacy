#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# test/utils/argument_parser_test.py
import argparse

import pytest

from src.pytrain.utils.argument_parser import (
    IntRange,
    PyTrainArgumentParser,
    StripPrefixesHelpFormatter,
)


class TestPyTrainArgumentParser:
    def test_error_raises_without_exit_and_sets_message(self):
        parser = PyTrainArgumentParser(add_help=False)
        parser.clear_exit_on_error()
        with pytest.raises(argparse.ArgumentError) as ei:
            parser.error("boom!")
        assert parser.error_message == "boom!"
        # argparse.ArgumentError stores the message in .message
        assert getattr(ei.value, "message", "") == "boom!"

    def test_exit_raises_without_exit_and_sets_message(self):
        parser = PyTrainArgumentParser(add_help=False)
        parser.clear_exit_on_error()
        with pytest.raises(argparse.ArgumentError) as ei:
            parser.exit(2, "bye!")
        assert parser.error_message == "bye!"
        assert getattr(ei.value, "message", "") == "bye!"

    def test_validate_args_success_and_failure(self):
        parser = PyTrainArgumentParser(add_help=False)
        parser.add_argument("-n", type=int, required=True)

        # Success
        args, msg = parser.validate_args(["-n", "5"])
        assert msg is None
        assert args.n == 5

        # Failure (missing required)
        args, msg = parser.validate_args([])
        assert args == []
        assert isinstance(msg, str)
        assert "required" in msg.lower()

    def test_remove_args_makes_option_unrecognized(self):
        parser = PyTrainArgumentParser(add_help=False)
        parser.add_argument("-foo", type=int, dest="foo")

        # Ensure it parses before removal
        args, msg = parser.validate_args(["-foo", "1"])
        assert msg is None
        assert args.foo == 1

        # Remove and verify it's now unrecognized
        parser.remove_args(["-foo"])
        args, msg = parser.validate_args(["-foo", "1"])
        assert args == []
        assert isinstance(msg, str)
        assert "unrecognized" in msg.lower()

    def test_is_exit_on_error_inherits_from_parent(self):
        parent = PyTrainArgumentParser(add_help=False)
        parent.clear_exit_on_error()
        child = PyTrainArgumentParser(add_help=False, parent=parent)

        # Child should reflect parent's setting
        assert child.is_exit_on_error is False

        # And child.error should raise, not exit
        with pytest.raises(argparse.ArgumentError):
            child.error("child error")


class TestStripPrefixesHelpFormatter:
    def test_usage_strips_hyphens_from_options(self):
        parser = PyTrainArgumentParser(add_help=False, formatter_class=StripPrefixesHelpFormatter)
        parser.add_argument("-ab", action="store_true", help="ab flag")
        parser.add_argument("-cd", action="store_true", help="cd flag")

        usage = parser.format_usage()
        # Expect bare option names without '-' due to custom formatter
        assert "ab" in usage
        assert "cd" in usage
        assert "-ab" not in usage
        assert "-cd" not in usage


class TestIntRange:
    def test_no_bounds_accepts_ints_and_rejects_non_int(self):
        t = IntRange()
        assert t("12") == 12
        with pytest.raises(argparse.ArgumentTypeError) as ei:
            t("x")
        assert "integer" in str(ei.value).lower()

    def test_min_and_max_bounds(self):
        t = IntRange(1, 5)
        assert t("1") == 1
        assert t("5") == 5
        with pytest.raises(argparse.ArgumentTypeError) as ei_low:
            t("0")
        assert "[1 - 5]" in str(ei_low.value)
        with pytest.raises(argparse.ArgumentTypeError) as ei_high:
            t("6")
        assert "[1 - 5]" in str(ei_high.value)

    def test_min_only(self):
        t = IntRange(imin=3)
        assert t("3") == 3
        with pytest.raises(argparse.ArgumentTypeError) as ei:
            t("2")
        assert ">=" in str(ei.value)

    def test_max_only(self):
        t = IntRange(imax=7)
        assert t("7") == 7
        with pytest.raises(argparse.ArgumentTypeError) as ei:
            t("8")
        assert "<=" in str(ei.value)
