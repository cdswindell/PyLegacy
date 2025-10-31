#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from guizero import Box, PushButton, Text

from ..db.accessory_state import AccessoryState
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.path_utils import find_file
from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui

VARIANTS = {
    "lionelville culvert loader 6-82029": "Lionelville-Culvert-Loader-6-82029.jpg",
    "lionelville culvert unloader 6-82030": "Lionelville-Culvert-Unloader-6-82030.jpg",
}

TITLES = {
    "Lionelville-Culvert-Loader-6-82029.jpg": "Lionelville Culvert Loader",
    "Lionelville-Culvert-Unloader-6-82030.jpg": "Lionelville Culvert Unloader",
}

LOADERS = {
    "Lionelville-Culvert-Loader-6-82029.jpg",
}

UNLOADERS = {
    "Lionelville-Culvert-Unloader-6-82030.jpg",
}

USE_AUX2 = {
    "Lionelville-Culvert-Loader-6-82029.jpg",
    "Lionelville-Culvert-Unloader-6-82030.jpg",
}


class CulvertGui(AccessoryBase):
    def __init__(
        self,
        tmcc_id: int,
        variant: str = None,
        *,
        aggrigator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a Lionel Command Control Culvert Loader/Unloader.

        :param int tmcc_id:
            TMCC ID of the culvert loader/unloader.

        :param str variant:
            Optional; Specifies the variant (Moose Pond, Dairymen's League, Mountain View).
        """

        # identify the accessory
        self._title, self.image_key = self.get_variant(variant)
        image = find_file(self.image_key)
        self._tmcc_id = tmcc_id
        self.culvert_state = None

        self._variant = variant
        self.action_button = None
        self.load_image = find_file("load_culvert.png")
        self.unload_image = find_file("unload_culvert.png")
        super().__init__(self._title, image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "culvert unloader"
        variant = CulvertGui.normalize(variant)
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, v
        raise ValueError(f"Unsupported culvert loader/unloader: {variant}")

    def get_target_states(self) -> list[S]:
        self.culvert_state = self._state_store.get_state(CommandScope.ACC, self._tmcc_id)
        return [self.culvert_state]

    def is_active(self, state: AccessoryState) -> bool:
        return False

    def switch_state(self, state: AccessoryState) -> None:
        pass

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len("Unload") + 2
        col = 0
        button_box = Box(box, layout="auto", border=2, grid=[col, 0], align="top")
        col += 1
        label = "Load" if self.is_loader else "Unload"
        tb = Text(button_box, text=label, align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.action_button = action = PushButton(
            button_box,
            image=self.action_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
            command=self.on_action,
        )
        action.tk.config(borderwidth=0)
        self.register_widget(self.culvert_state, action)

    def on_action(self) -> None:
        if self.is_use_aux2:
            CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, self._tmcc_id).send()

    @property
    def action_image(self) -> str:
        if self.is_loader:
            return self.load_image
        elif self.is_unloader:
            return self.unload_image
        raise ValueError(f"Unsupported image: {self.image_key}")

    @property
    def is_loader(self) -> bool:
        return self.image_key in LOADERS

    @property
    def is_unloader(self) -> bool:
        return self.image_key in UNLOADERS

    @property
    def is_use_aux2(self) -> bool:
        return self.image_key in USE_AUX2
