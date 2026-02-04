#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from guizero import Box, PushButton, Text

from .accessories.accessory_type import AccessoryType
from .accessories.config import ConfiguredAccessory, configure_accessory
from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui
from ..db.accessory_state import AccessoryState
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.path_utils import find_file


class GasStationGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.GAS_STATION

    def __init__(
        self,
        power: int,
        action: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a MTH Gas Station.

        :param int power:
            TMCC ID of the ACS2 port used to power the station.

        :param int action:
            TMCC ID of the ACS2 port used to trigger the Animation.

        :param str variant:
            Optional; Specifies the variant (Sinclair, Texaco, etc.).
        """
        # identify the accessory
        self._power = int(power)
        self._action = int(action)
        self._variant = variant
        self.power_button = self.action_button = None
        self.power_state = self.action_state = None

        # New: configured model (definition + resolved assets + tmcc wiring)
        self._cfg: ConfiguredAccessory | None = None

        # Main title + image + eject image (resolved in bind_variant)
        self._title: str | None = None
        self._image: str | None = None
        self._action_image: str | None = None
        super().__init__(self._title, self._image, aggregator=aggregator)

    def bind_variant(self) -> None:
        """
        Resolve all metadata (title, main image, op images) via registry + configure_accessory().

        This keeps the public constructor signature stable while moving all metadata
        to your centralized registry/config pipeline.
        """
        definition = self.registry.get_definition(self.ACCESSORY_TYPE, self._variant)

        # Bind wiring (TMCC ids) to the definition
        self._cfg = configure_accessory(
            definition,
            tmcc_ids={
                "power": self._power,
                "action": self._action,
            },
            # per-instance overrides can be added later without changing signature
            operation_images=None,
            instance_id=None,
            display_name=None,
        )
        # make sure we have a configuration
        assert self._cfg is not None

        # Apply main title/image to the AccessoryBase fields
        self.title = self._title = self._cfg.title
        self.image_file = self._image = find_file(self._cfg.definition.variant.image)

        # Pre-resolve action image (momentary)
        action_op = self._cfg.operation("action")
        self._action_image = find_file(action_op.image or "gas-station-car.png")

    def get_target_states(self) -> list[S]:
        power_id = self._cfg.tmcc_id_for("power")
        action_id = self._cfg.tmcc_id_for("action")

        self.power_state = self._state_store.get_state(CommandScope.ACC, power_id)
        self.action_state = self._state_store.get_state(CommandScope.ACC, action_id)

        return [
            self.power_state,
            self.action_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        if state == self.action_state:
            return  # Action is momentary (press/release handlers)
        with self._cv:
            # a bit confusing, but sending this command toggles the power
            CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
            self.after_state_change(None, self.power_state)

    def after_state_change(self, button: PushButton | None, state: AccessoryState) -> None:
        if state == self.power_state:
            if self.action_button is None:
                return  # defensive programming
            # If power is off, disable action; if power is on, enable action
            if state.is_aux_on:
                self.queue_message(lambda: self.action_button.enable())
            else:
                self.queue_message(lambda: self.action_button.disable())

    def build_accessory_controls(self, box: Box) -> None:
        power_label = self._cfg.operation("power").label
        action_label = self._cfg.operation("action").label

        max_text_len = max(len(power_label), len(action_label)) + 2

        self.power_button = self.make_power_button(self.power_state, power_label, 0, max_text_len, box)

        alarm_box = Box(box, layout="auto", border=2, grid=[1, 0], align="top")
        tb = Text(alarm_box, text=action_label, align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.action_button = PushButton(
            alarm_box,
            image=self._action_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        self.action_button.bg = "white"
        self.action_button.when_left_button_pressed = self.when_pressed
        self.action_button.when_left_button_released = self.when_released
        self.register_widget(self.action_state, self.action_button)

        # Robust initial gating
        self.after_state_change(None, self.power_state)
