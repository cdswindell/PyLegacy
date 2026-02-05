#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from tkinter import Widget

from guizero import Box, PushButton

from .accessories.accessory_type import AccessoryType
from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui
from ..db.accessory_state import AccessoryState
from ..protocol.command_req import CommandReq
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.path_utils import find_file


class StationGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.STATION

    def __init__(
        self,
        power: int,
        platform: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a K-Line Freight/Passenger Station.

        :param int power:
            TMCC ID of the ACS2 port used to power the freight depot.

        :param int platform:
            TMCC ID of the ACS2 port used to control the platform.

        :param str variant:
            Optional; Specifies the variant (Middletown, Military, etc.).
        """

        # identify the accessory
        self._power = power
        self._platform = platform
        self._variant = variant
        self.power_button = self.platform_button = None
        self.power_state = self.platform_state = None

        # self._platform_text = None
        # self.brews_image = find_file("brews-waiting.png")
        # self.freight_image = find_file("freight-waiting.jpg")
        # self.people_image = find_file("passengers-waiting.png")
        # self.empty_image = find_file("loaded.png")
        # Main title + image + eject image (resolved in bind_variant)
        self._title: str | None = None
        self._image: str | None = None
        self._empty_image: str | None = None
        self._full_image: str | None = None
        self._empty_label: str | None = None
        self._full_label: str | None = None

        super().__init__(self._title, self._image, aggregator=aggregator)

    def bind_variant(self) -> None:
        """
        Resolve all metadata (title, main image, op images) via registry + configure_accessory().

        This keeps the public constructor signature stable while moving all metadata
        to your centralized registry/config pipeline.
        """
        self.configure_from_registry(
            self.ACCESSORY_TYPE,
            self._variant,
            tmcc_ids={"power": self._power, "platform": self._platform},
        )

        # Pre-resolve action image (platform empty)
        self._empty_image = find_file(self.config.off_image_for("platform", "loaded.png"))
        self._empty_label = self.config.off_label_for("platform", "Depart")

        self._full_image = find_file(self.config.on_image_for("platform"))
        self._full_label = self.config.on_label_for("platform", "Arrive")

    def get_target_states(self) -> list[S]:
        assert self.config is not None

        self.power_state = self.state_for("power")
        self.platform_state = self.state_for("platform")
        return [
            self.power_state,
            self.platform_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        with self._cv:
            self.toggle_latch(state)
            self.after_state_change(None, state)

    def after_state_change(self, button: PushButton | None, state: AccessoryState) -> None:
        # Updates platform button based on platform state
        if state == self.power_state:
            self.gate_widget_on_power(self.power_state, self.platform_button)
        elif state == self.platform_state:
            if self.is_active(self.platform_state):
                self.set_button_inactive(self.platform_button)
            else:
                self.set_button_active(self.platform_button)

    def build_accessory_controls(self, box: Box) -> None:
        assert self.config is not None
        power_label, _ = self.config.labels_for("power", "platform")
        max_text_len = max(len(power_label), len(self._empty_label), len(self._full_label)) + 2

        self.power_button = self.make_power_button(self.power_state, power_label, 0, max_text_len, box)

        self.platform_button = self.make_power_button(self.platform_state, self._empty_label, 1, max_text_len, box)
        self.platform_button.update_command(self.when_platform_button_pressed)

        self.after_state_change(None, self.platform_state)
        self.after_state_change(None, self.power_state)

    def when_platform_button_pressed(self) -> None:
        with self._cv:
            if not self.is_active(self.power_state):
                self.queue_message(lambda: self.platform_button.disable())
            else:
                if self.platform_button.image == self._empty_image:
                    self.set_button_active(self.platform_button)
                else:
                    self.set_button_inactive(self.platform_button)
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, self.platform_state.tmcc_id).send()

    # noinspection PyTypeChecker
    def set_button_inactive(self, widget: Widget):
        if widget is None:
            return
        elif widget == self.platform_button:
            self.set_boxed_button_label(widget, self._empty_label)
            self.platform_button.image = self._empty_image
            self.platform_button.height = self.platform_button.width = self.s_72
        else:
            super().set_button_inactive(widget)

    # noinspection PyTypeChecker
    def set_button_active(self, widget: Widget):
        if widget is None:
            return
        elif widget == self.platform_button:
            self.set_boxed_button_label(widget, self._full_label)
            self.platform_button.image = self._full_image
            self.platform_button.height = self.platform_button.width = self.s_72
        else:
            super().set_button_active(widget)
