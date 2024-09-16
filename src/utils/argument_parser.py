import argparse
from typing import List


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    # noinspection PyProtectedMember
    def remove_args(self,  args: List[str]) -> None:
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
