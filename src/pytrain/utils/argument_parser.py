#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

import argparse
from typing import List


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._error_message: str | None = None

    def error(self, message: str) -> None:
        self._error_message = message
        super().error(message)

    @property
    def error_message(self) -> str | None:
        return self._error_message

    def validate_args(self, args=None, namespace=None):
        msg = None
        try:
            args, argv = self.parse_known_args(args, namespace)
            if argv:
                msg = "Unrecognized arguments: %s" % " ".join(argv)
        except SystemExit:
            msg = self._error_message
        except argparse.ArgumentError as e:
            msg = e.message
        return args, msg

    # noinspection PyProtectedMember
    def remove_args(self, args: List[str]) -> None:
        for arg in args:
            for action in self._actions:
                opts = action.option_strings
                if (opts and opts[0] == arg) or action.dest == arg:
                    self._remove_action(action)
                    break

            for action in self._action_groups:
                for group_action in action._group_actions:
                    opts = group_action.option_strings
                    if (opts and opts[0] == arg) or group_action.dest == arg:
                        action._group_actions.remove(group_action)
                        break


class StripPrefixesHelpFormatter(argparse.HelpFormatter):
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
