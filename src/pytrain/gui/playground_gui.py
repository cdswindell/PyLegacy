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
from .accessory_base import AccessoryBase, AnimatedButton, S
from .accessory_gui import AccessoryGui

VARIANTS = {
    "tire swing 6-82105": "Tire-Swing-6-82105.jpg",
    "tug of war 6-82107": "Tug-of-War-6-82107.jpg",
    "Playground-6-82104.jpg": "Playground-6-82104.jpg",
    "Swing-6-14199.jpg": "Swing-6-14199.jpg",
}

TITLES = {
    "Tire-Swing-6-82105.jpg": "Tire Swing",
    "Tug-of-War-6-82107.jpg": "Tug of War",
    "Playground-6-82104.jpg": "Playground",
    "Swing-6-14199.jpg": "Swings",
}

MOTION_IMAGE = {
    "Tire-Swing-6-82105.jpg": "tire-swing-child.jpg",
    "Tug-of-War-6-82107.jpg": "tug-of-war.jpg",
    "Playground-6-82104.jpg": "motion.gif",
    "Swing-6-14199.jpg": "swing.gif",
}

MOTION_TEXT = {
    "Tire-Swing-6-82105.jpg": "Swing",
    "Tug-of-War-6-82107.jpg": "Tug of War",
    "Playground-6-82104.jpg": "Motion",
    "Swing-6-14199.jpg": "Swing",
}


class PlaygroundGui(AccessoryBase):
    def __init__(
        self,
        motion: int,
        variant: str = None,
        *,
        aggrigator: AccessoryGui = None,
    ):
        """
        Create a GUI to control Lionel Plug n Play Playground Accessories.

        :param int motion:
            MCC ID of the ACS2 port used for motion.

        :param str variant:
            Optional; Specifies the variant (Tree Swing).
        """

        # identify the accessory
        self._title, self.image_key = self.get_variant(variant)
        image = find_file(self.image_key)
        self._motion = motion
        self.motion_state = None

        self._variant = variant
        self.motion_button = None
        super().__init__(self._title, image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "tire swing"
        variant = PlaygroundGui.normalize(variant)
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, v
        raise ValueError(f"Unsupported playground: {variant}")

    def get_target_states(self) -> list[S]:
        self.motion_state = self._state_store.get_state(CommandScope.ACC, self._motion)
        return [self.motion_state]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        pass

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len(self.motion_text) + 2
        col = 0
        button_box = Box(box, layout="auto", border=2, grid=[col, 0], align="top")
        col += 1
        tb = Text(button_box, text=self.motion_text, align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.motion_button = action = AnimatedButton(
            button_box,
            image=self.motion_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        self.register_widget(self.motion_state, action)
        action.when_left_button_pressed = self.when_pressed
        action.when_left_button_released = self.when_released

    @property
    def motion_image(self) -> str:
        return find_file(MOTION_IMAGE.get(self.image_key, "motion.gif"))

    @property
    def motion_text(self) -> str:
        return MOTION_TEXT.get(self.image_key, "Motion")
