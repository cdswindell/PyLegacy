#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from guizero import Box, Text

from ..db.accessory_state import AccessoryState
from ..protocol.constants import CommandScope
from ..utils.path_utils import find_file
from .accessory_base import AccessoryBase, AnimatedButton, PowerButton, S
from .accessory_gui import AccessoryGui

VARIANTS = {
    "backhoe construction scene K42416": "Backhoe-Construction-Scene-K42416.gif",
}

TITLES = {
    "Backhoe-Construction-Scene-K42416.gif": "Backhoe Construction Scene",
}


class BackhoeGui(AccessoryBase):
    def __init__(
        self,
        backhoe: int,
        variant: str = None,
        *,
        aggrigator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a K-Line Backhoe Construction Scene.

        :param int backhoe:
            TMCC ID of the culvert loader/unloader.

        :param str variant:
            Optional; Specifies the variant (Backhoe).
        """

        # identify the accessory
        self._title, self.image_key = self.get_variant(variant)
        image = find_file(self.image_key)
        self._backhoe = backhoe
        self.backhoe_state = None

        self._variant = variant
        self.action_button = None
        self.backhoe_image = find_file("animated_backhoe.gif")
        super().__init__(self._title, image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "backhoe"
        variant = BackhoeGui.normalize(variant)
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, v
        raise ValueError(f"Unsupported construction scene: {variant}")

    def get_target_states(self) -> list[S]:
        self.backhoe_state = self._state_store.get_state(CommandScope.ACC, self._backhoe)
        return [self.backhoe_state]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        pass

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len("Dig") + 2
        col = 0
        button_box = Box(box, layout="auto", border=2, grid=[col, 0], align="top")
        col += 1
        tb = Text(button_box, text="Dig", align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.action_button = action = AnimatedButton(
            button_box,
            image=self.backhoe_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        action.stop_animation()
        self.register_widget(self.backhoe_state, action)
        action.when_left_button_pressed = self.when_pressed
        action.when_left_button_released = self.when_released

    def set_button_active(self, button: AnimatedButton) -> None:
        with self._cv:
            if isinstance(button, PowerButton):
                super().set_button_active(button)
            else:
                button.start_animation()

    def set_button_inactive(self, button: AnimatedButton) -> None:
        with self._cv:
            if isinstance(button, PowerButton):
                super().set_button_inactive(button)
            else:
                button.image = self.backhoe_image
                button.height = button.width = self.s_72
                button.stop_animation()
