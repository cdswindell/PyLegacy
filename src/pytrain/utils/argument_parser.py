#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import argparse
from argparse import ArgumentError, ArgumentParser, ArgumentTypeError, HelpFormatter
from threading import Lock
from typing import List, cast


class PyTrainArgumentParser(ArgumentParser):
    def __init__(self, *args, **kwargs) -> None:
        self._parent = kwargs.pop("parent", None)
        self._exit_on_error: bool = True
        self._error_message: str | None = None
        self._lock = Lock()
        if "parents" in kwargs:
            parents = kwargs["parents"].copy()
        else:
            parents = []
        super().__init__(*args, **kwargs)
        for parent in parents:
            parent._parent = self

    @property
    def parent(self) -> ArgumentParser:
        return self._parent

    @property
    def is_exit_on_error(self) -> bool:
        if self._exit_on_error is True and self.parent and isinstance(self.parent, PyTrainArgumentParser):
            return cast(PyTrainArgumentParser, self.parent).is_exit_on_error
        return self._exit_on_error

    def error(self, message: str) -> None:
        self._error_message = message
        if self.is_exit_on_error:
            try:
                super().error(message)
            except AssertionError:
                raise ArgumentError(None, message)
        else:
            raise ArgumentError(None, message)

    def exit(self, status: int = 0, message: str = None) -> None:
        self._error_message = message
        if self.is_exit_on_error:
            super().exit(status, message)
        else:
            raise ArgumentError(None, message)

    @property
    def error_message(self) -> str | None:
        return self._error_message

    # noinspection PyArgumentList
    def validate_args(self, args=None):
        msg = None
        with self._lock:
            eoe = self._exit_on_error
            try:
                self._exit_on_error = False
                args = self.parse_args(args)
            except ArgumentError as e:
                msg = e.message
                args = []
            except Exception as e:
                msg = str(e)
                args = []
            finally:
                if eoe is not None:
                    self._exit_on_error = eoe
            return args, msg

    def clear_exit_on_error(self) -> None:
        with self._lock:
            self._exit_on_error = False

    def reset_exit_on_error(self) -> None:
        with self._lock:
            self._exit_on_error = True

    # noinspection PyProtectedMember
    def remove_args(self, args: List[str]) -> None:
        for arg in args:
            # Accept either "-foo" or "foo"
            arg_no_prefix = arg.lstrip("-")

            # Find ALL matching actions by option string or dest
            matches = []
            for action in list(getattr(self, "_actions", ())):
                option_strings = getattr(action, "option_strings", ())
                if arg in option_strings or getattr(action, "dest", None) == arg_no_prefix:
                    matches.append(action)

            if not matches:
                continue

            # All containers that might hold references to the action or its option mappings
            containers = [self]
            containers.extend(getattr(self, "_action_groups", ()))
            containers.extend(getattr(self, "_mutually_exclusive_groups", ()))

            for target_action in matches:
                # Capture the option strings before removal
                opt_strs = list(getattr(target_action, "option_strings", ()))

                # Remove from parser core structures
                self._remove_action(target_action)

                # Remove from action groups' lists
                for group in getattr(self, "_action_groups", ()):
                    ga = getattr(group, "_group_actions", None)
                    if ga and target_action in ga:
                        ga.remove(target_action)

                # Remove from mutually exclusive groups' lists
                for mex_group in getattr(self, "_mutually_exclusive_groups", ()):
                    mga = getattr(mex_group, "_group_actions", None)
                    if mga and target_action in mga:
                        mga.remove(target_action)

                # Purge option string mappings from all containers
                for container in containers:
                    mapping = getattr(container, "_option_string_actions", None)
                    if not mapping:
                        continue
                    for opt in opt_strs:
                        if mapping.get(opt) is target_action:
                            del mapping[opt]


class StripPrefixesHelpFormatter(HelpFormatter):
    """
    For help within PyTrain, we need to strip the "-" characters
    off of the names of the arguments, as the user doesn't need to
    enter them. ArgParse requires arguments to be hyphenated. We
    just want to hide this implementation detail from the user.
    """

    def add_usage(self, usage, actions, groups, prefix=None):
        for action in actions:
            opt_strs = []
            for option in action.option_strings:
                opt_strs.append(str(option).replace("-", ""))
            action.option_strings = opt_strs
        return super(StripPrefixesHelpFormatter, self).add_usage(usage, actions, groups, prefix)


# Custom argparse type representing a bounded int
class IntRange:
    def __init__(self, imin: int = None, imax: int = None):
        self.imin = imin
        self.imax = imax

    def __call__(self, arg):
        try:
            value = int(arg)
        except ValueError:
            raise self.exception()
        if (self.imin is not None and value < self.imin) or (self.imax is not None and value > self.imax):
            raise self.exception()
        return value

    def exception(self):
        if self.imin is not None and self.imax is not None:
            return argparse.ArgumentTypeError(f"Must be an integer in the range [{self.imin} - {self.imax}]")
        elif self.imin is not None:
            return argparse.ArgumentTypeError(f"Must be an integer >= {self.imin}")
        elif self.imax is not None:
            return argparse.ArgumentTypeError(f"Must be an integer <= {self.imax}")
        else:
            return argparse.ArgumentTypeError("Must be an integer")


class UniqueChoice:
    def __init__(self, prefixes: List[str]):
        self.prefixes = prefixes

    def __call__(self, arg):
        arg = arg.lower()
        matches = [c for c in self.prefixes if c.startswith(arg)]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ArgumentTypeError(f"invalid choice '{arg}'; choose from {', '.join(self.prefixes)}")
        raise ArgumentTypeError(f"ambiguous choice '{arg}': {', '.join(matches)}")


def ranged_int(min_value, max_value):
    def checker(value):
        i_value = int(value)
        if i_value < min_value or i_value > max_value:
            raise argparse.ArgumentTypeError(f"{i_value} is out of range [{min_value}–{max_value}]")
        return i_value

    return checker
