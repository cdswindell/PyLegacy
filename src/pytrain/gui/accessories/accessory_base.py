#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import logging
import re
from abc import ABC, ABCMeta, abstractmethod
from threading import Event, Thread
from typing import Any, Callable, Generic, TypeVar, cast

# noinspection PyPackageRequirements
from PIL import Image
from guizero import App, Box, Combo, Picture, PushButton, Text
from guizero.base import Widget
from guizero.event import EventData

from .accessory_registry import AccessoryRegistry
from .accessory_type import AccessoryType
from .config import ConcreteAccessory, configure_accessory
from .configured_accessory import ConfiguredAccessory
from ..components.hold_button import HoldButton
from ..guizero_base import GuiZeroBase
from ...db.accessory_state import AccessoryState
from ...db.component_state import ComponentState
from ...db.state_watcher import StateWatcher
from ...pdi.asc2_req import Asc2Req
from ...pdi.constants import Asc2Action, PdiCommand
from ...protocol.command_req import CommandReq
from ...protocol.constants import CommandScope
from ...protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ...utils.path_utils import find_file

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)

HYPHEN_CLEANUP = re.compile(r"(?<=[A-Za-z])-+(?=[A-Za-z])")
SPACE_CLEANUP = re.compile(r"\s{2,}")


class AccessoryBase(GuiZeroBase, Generic[S], ABC):
    __metaclass__ = ABCMeta

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @abstractmethod
    def __init__(
        self,
        title: str | None,
        image_file: str = None,
        width: int = None,
        height: int = None,
        aggregator: Any = None,
        enabled_bg: str = "green",
        disabled_bg: str = "black",
        enabled_text: str = "black",
        disabled_text: str = "lightgrey",
        scale_by: float = 1.0,
        max_image_width: float = 0.80,
        max_image_height: float = 0.45,
    ) -> None:
        # these instance variables must be defined before calling super().__init__()
        self._stand_alone = aggregator is None or not isinstance(aggregator, GuiZeroBase)
        self._aggregator = aggregator
        self._menu_label: str | None = None
        """Defines abstract accessory base class for GUI elements"""
        GuiZeroBase.__init__(
            self,
            title=title,
            scale_by=scale_by,
            width=width if self._stand_alone else aggregator.width,
            height=height if self._stand_alone else aggregator.height,
            enabled_bg=enabled_bg,
            disabled_bg=disabled_bg,
            enabled_text=enabled_text,
            disabled_text=disabled_text,
            stand_alone=self._stand_alone,
        )

        if self._stand_alone:
            self._max_image_width = max_image_width
            if self.height > 320 and max_image_height == 0.45:
                max_image_height = 0.55
            self._max_image_height = max_image_height
        else:
            self._max_image_width = 1.0
            self._max_image_height = 1.0

        self.image_file = image_file
        self._image = None
        self._text_size: int = 24

        self.box = self.acc_box = self.y_offset = None
        self.aggregator_combo = None
        self.turn_on_image = find_file("on_button.jpg")
        self.turn_off_image = find_file("off_button.jpg")
        self.alarm_on_image = find_file("Breaking-News-Emoji.gif")
        self.alarm_off_image = find_file("red_light_off.jpg")
        self.left_arrow_image = find_file("left_arrow.jpg")
        self.right_arrow_image = find_file("right_arrow.jpg")

        # States
        self._states = dict[int, S]()
        self._state_buttons = dict[int, Widget | set[Widget]]()
        self._state_watchers = dict[int, StateWatcher]()

        # New: configured model (definition + resolved assets + tmcc wiring)
        self._cfg: ConcreteAccessory | None = None
        self._registry: AccessoryRegistry | None = None
        self.init_complete()

    # noinspection PyUnnecessaryCast
    @property
    def host(self) -> GuiZeroBase:
        """
        The GuiZeroBase that should service base-level calls.

        - If embedded inside EngineGui: host == EngineGui
        - If standalone: host == self
        """
        agg = self._aggregator
        if agg is None or not isinstance(agg, GuiZeroBase):
            return self
        else:
            return cast(GuiZeroBase, agg)

    @property
    def app(self) -> App:
        return self.host._app

    @property
    def menu_label(self) -> str:
        return self._menu_label or (self.title or "")

    @menu_label.setter
    def menu_label(self, value: str):
        self._menu_label = value

    @property
    def destroy_complete(self) -> Event:
        return self._ev

    @property
    def registry(self) -> AccessoryRegistry:
        with self._cv:
            if self._registry is None:
                self._registry = AccessoryRegistry.instance()
                self._registry.bootstrap()
        return self._registry

    def configure_from_registry(
        self,
        accessory_type: AccessoryType,
        variant: str | None,
        *,
        tmcc_ids: dict[str, int] | None = None,
        operation_images: dict[str, str] | None = None,
        instance_id: str | None = None,
        display_name: str | None = None,
        tmcc_id: int | None = None,
    ) -> ConcreteAccessory:
        with self._cv:
            if self._cfg is None:
                """Configures accessory from registry; returns configured accessory"""
                definition = self.registry.get_definition(accessory_type, variant)
                cfg = configure_accessory(
                    definition,
                    tmcc_ids=tmcc_ids,
                    operation_images=operation_images,
                    instance_id=instance_id,
                    display_name=display_name,
                    tmcc_id=tmcc_id,
                )

                if display_name:
                    self._menu_label = display_name
                self.title = cfg.title
                self.image_file = find_file(cfg.definition.variant.image)
                self._cfg = cfg
        return self._cfg

    def state_for(self, key: str, scope: CommandScope = CommandScope.ACC) -> S:
        assert self._cfg is not None
        tmcc_id = self._cfg.tmcc_id_for(key)
        return self.host.state_store.get_state(scope, tmcc_id)

    def states_for(self, *keys: str, scope: CommandScope = CommandScope.ACC) -> list[S]:
        return [self.state_for(k, scope) for k in keys]

    def state_for_accessory(self, scope: CommandScope = CommandScope.ACC) -> S:
        assert self._cfg is not None
        return self.host.state_store.get_state(scope, self._cfg.tmcc_id)

    def gate_widget_on_power(
        self,
        power_state: AccessoryState,
        widget: PushButton | None,
        on_enable: Callable = None,
        on_disable: Callable = None,
    ) -> None:
        """Enables/disables widget based on power state"""
        if widget is None:
            return
        on_enable = on_enable or widget.enable
        on_disable = on_disable or widget.disable
        if power_state.is_aux_on:
            self.queue_message(on_enable)
        else:
            self.queue_message(on_disable)

    @property
    def config(self) -> ConcreteAccessory:
        return self._cfg

    # noinspection PyTypeChecker
    @staticmethod
    def toggle_latch(state: S) -> None:
        CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()

    # noinspection PyTypeChecker
    def update_button(self, tmcc_id: int) -> None:
        with self._cv:
            pd: S = self._states[tmcc_id]
            pb = self._state_buttons.get(tmcc_id, None)
            if pb:
                if self.is_active(pd):
                    self.set_button_active(pb)
                else:
                    self.set_button_inactive(pb)
            # call child's after state change hook
            self.after_state_change(pb, pd)

    # noinspection PyTypeChecker
    def set_button_inactive(self, widget: Widget):
        if isinstance(widget, PowerButton):
            widget.image = self.turn_on_image
            widget.height = widget.width = self.s_72
        else:
            widget.bg = self._disabled_bg
            widget.text_color = self._disabled_text

    # noinspection PyTypeChecker
    def set_button_active(self, widget: Widget):
        if isinstance(widget, PowerButton):
            widget.image = self.turn_off_image
            widget.height = widget.width = self.s_72
        else:
            widget.bg = self._enabled_bg
            widget.text_color = self._enabled_text

    def on_state_change_action(self, tmcc_id: int) -> Callable:
        def upd():
            if not self._shutdown_flag.is_set():
                self.queue_message(self.update_button, tmcc_id)

        return upd

    def queue_message(self, message: Callable, *args: Any) -> None:
        self.host._message_queue.put((message, args))

    @staticmethod
    def normalize(text: str) -> str:
        text = text.strip().lower()
        text = HYPHEN_CLEANUP.sub(" ", text)
        text = SPACE_CLEANUP.sub(" ", text)
        return text

    def calc_image_box_size(self) -> tuple[int, int | Any]:
        pass

    # noinspection PyTypeChecker
    def build_gui(self, container: Box = None, *, acc: ConfiguredAccessory = None) -> None:
        # TODO: refactor this method into AccessoryGui
        # initialize registry
        assert self.registry is not None
        assert self.registry.is_bootstrapped

        # bind variant to gui
        self.bind_variant()
        if acc:
            self.menu_label = acc.label

        self._create_state_watchers()

        if container:
            assert container.layout == "grid"
            self.box = box = container
        else:
            assert self._stand_alone
            self.box = box = Box(self.host.app, layout="grid")

        # ts = self._text_size
        row_num = 0
        _ = Text(box, text=" ", grid=[0, row_num, 1, 1], size=6, height=1, bold=True)
        row_num += 1
        ats = int(round(23 * self._scale_by))
        if self._aggregator:
            # customize label
            cb = self.aggregator_combo = Combo(
                box,
                options=self._aggregator.guis,
                selected=self.menu_label,
                grid=[0, row_num],
                command=self.on_combo_change,
            )
            cb.text_size = ats
            cb.text_bold = True
            row_num += 1
        else:
            # customize label
            cb = Combo(
                box,
                options=[self.menu_label],
                selected=self.menu_label,
                grid=[0, row_num],
            )
            cb.text_size = ats
            cb.text_bold = True
            row_num += 1

        self._image = None
        if self.image_file:
            iw, ih = self.get_scaled_jpg_size(self.image_file)
            self._image = Picture(self.host.app, image=self.image_file, width=iw, height=ih)

        self.host.app.update()

        # build state buttons
        self.acc_box = acc_box = Box(self.host.app, border=2, align="bottom", layout="grid")
        self.build_accessory_controls(acc_box)

    def _create_state_watchers(self):
        # get all target states; watch for state changes
        accs = self.get_target_states()
        for acc in accs:
            if isinstance(acc, ComponentState):  # helps eliminate pycharm warning
                self._states[acc.tmcc_id] = acc
                self._state_watchers[acc.tmcc_id] = StateWatcher(acc, self.on_state_change_action(acc.tmcc_id))
        # clear any existing state buttons
        if self._state_buttons:
            self._reset_state_buttons()

    def mount_gui(self, container: Box = None, *, add_spacer: bool = True) -> None:
        self.bind_variant()
        self._create_state_watchers()

        if container:
            if container.layout == "grid":
                if bool(add_spacer):
                    container.tk.grid_configure(pady=(40, 0))
                self.box = box = container
            else:
                if bool(add_spacer):
                    container.tk.pack_configure(pady=(40, 0))
                self.box = box = Box(container, layout="grid")
        else:
            assert self._stand_alone
            self.box = box = Box(self.host.app, layout="grid")
        self.build_accessory_controls(box)

    def destroy_gui(self):
        # Explicitly drop references to tkinter/guizero objects on the Tk thread
        if self._aggregator:
            for sw in self._state_watchers.values():
                sw.shutdown()
            self._state_watchers.clear()
        self.aggregator_combo = None
        self.box = None
        self.acc_box = None
        self._image = None
        self._state_buttons.clear()
        self._state_buttons = None

    # noinspection PyTypeChecker
    def register_widget(self, state: S, widget: Widget) -> None:
        with self._cv:
            if state.tmcc_id in self._state_buttons:
                contents = self._state_buttons[state.tmcc_id]
                if contents == widget:
                    pass  # already registered
                elif isinstance(contents, Widget):
                    contents = {contents}
                    contents.add(widget)
                    self._state_buttons[state.tmcc_id] = contents
                elif isinstance(contents, set) and widget not in contents:
                    contents.add(widget)
            else:
                self._state_buttons[state.tmcc_id] = widget
            widget.component_state = state
            self.update_button(state.tmcc_id)

    def make_power_button(self, state: S, label: str, col: int, text_len: int, container: Box) -> PowerButton:
        btn_box = Box(container, layout="auto", border=2, grid=[col, 0], align="top")
        tb = Text(btn_box, text=label, align="top", size=self.s_16, underline=True)
        tb.width = text_len
        button = PowerButton(
            btn_box,
            image=self.turn_on_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        button.tmcc_id = state.tmcc_id
        button.update_command(self.switch_state, [state])
        self.register_widget(state, button)
        return button

    def make_push_button(
        self,
        container: Box,
        *,
        state: S,
        label: str | None,
        col: int,
        text_len: int | None = None,
        image: str | None = None,
        width: int | None = None,
        height: int | None = None,
        button_cls=HoldButton,
        is_momentary: bool = True,
    ) -> PushButton:
        if label:
            b = Box(container, layout="auto", border=2, grid=[col, 0], align="top")
            t = Text(b, text=label, align="top", size=self.s_16, underline=True)
            t.width = text_len
            btn = button_cls(b, image=image, align="top", width=width or self.s_72, height=height or self.s_72)
        else:
            btn = button_cls(
                container,
                image=image,
                align="top",
                grid=[col, 0],
                width=width or self.s_72,
                height=height or self.s_72,
            )
        if is_momentary:
            btn.when_left_button_pressed = self.when_pressed
            btn.when_left_button_released = self.when_released
        else:
            btn.when_left_button_pressed = None
            btn.when_left_button_released = None
        self.register_widget(state, btn)
        return btn

    @staticmethod
    def get_boxed_button_label(widget: Widget) -> str | None:
        """Extracts label from boxed button widget"""
        if widget is None:
            return None
        for child in widget.master.children:
            if isinstance(child, Text):
                return child.value
        return None

    @staticmethod
    def set_boxed_button_label(widget: Widget, label: str):
        """Extracts label from boxed button widget"""
        if widget is None:
            return
        for child in widget.master.children:
            if isinstance(child, Text):
                child.value = label

    def on_combo_change(self, option: str) -> None:
        if option == self.menu_label:
            return  # Noop
        else:
            self._aggregator.cycle_gui(option)

    # noinspection PyUnusedLocal
    def _reset_state_buttons(self) -> None:
        for pdb in self._state_buttons.values():
            if not isinstance(pdb, list):
                pdb = [pdb]
            for widget in pdb:
                if hasattr(widget, "component_state"):
                    widget.component_state = None
                if hasattr(widget, "when_left_button_pressed"):
                    widget.when_left_button_pressed = None
                if hasattr(widget, "when_left_button_released"):
                    widget.when_left_button_released = None
                widget.hide()
                widget.destroy()
        self._state_buttons.clear()

    def scale(self, value: int, factor: float = None) -> int:
        orig_value = value
        value = max(orig_value, int(value * self.host.width / 480))
        if factor is not None and self.host.width > 480:
            value = max(orig_value, int(factor * value))
        return value

    @staticmethod
    def get_jpg_size(image_file: str):
        """
        Retrieves the native width and height of a JPG image.

        Args:
            image_file (str): The path to the JPG image file.

        Returns:
            tuple: A tuple containing the width and height (width, height)
                   in pixels, or (None, None) if an error occurs.
        """
        try:
            with Image.open(image_file) as img:
                width, height = img.size
                return width, height
        except FileNotFoundError as e:
            log.exception(f"Error: Image file not found at {image_file}", exc_info=e)
        except Exception as e:
            log.exception(f"An error occurred: {e}", exc_info=e)
        return None, None

    # noinspection PyTypeChecker
    def get_scaled_jpg_size(self, image_file: str) -> tuple[int, int]:
        iw, ih = self.get_jpg_size(image_file)
        if iw is None or ih is None:
            return None, None
        max_width = int(round(self.host.width * self._max_image_width))
        max_height = int(round(self.host.height * self._max_image_height))
        if ih > iw:
            scaled_height = max_height
            scale_factor = max_height / ih
            scaled_width = int(round(iw * scale_factor))
        else:
            scaled_width = max_width
            scale_factor = max_width / iw
            scaled_height = int(round(ih * scale_factor))
            # if the image takes up too much height, do more scaling
            if (scaled_height / self.host.height) > self._max_image_height:
                scaled_height = int(round(self.height * self._max_image_height))
                scale_factor = scaled_height / ih
                scaled_width = int(round(iw * scale_factor))
        return scaled_width, scaled_height

    def when_pressed(self, event: EventData) -> None:
        pb = event.widget
        if pb.enabled:
            state = pb.component_state
            if state.is_asc2:
                Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1).send()
            self.post_process_when_pressed(pb, state)

    def when_released(self, event: EventData) -> None:
        pb = event.widget
        if pb.enabled:
            state = pb.component_state
            if state.is_asc2:
                Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0).send()
            self.post_process_when_released(pb, state)

    def post_process_when_pressed(self, button: PushButton, state: S) -> None: ...

    def post_process_when_released(self, button: PushButton, state: S) -> None: ...

    def after_state_change(self, button: PushButton, state: S) -> None: ...

    @abstractmethod
    def bind_variant(self) -> None: ...

    @abstractmethod
    def get_target_states(self) -> list[S]: ...

    @abstractmethod
    def is_active(self, state: S) -> bool: ...

    @abstractmethod
    def switch_state(self, state: S) -> bool: ...

    @abstractmethod
    def build_accessory_controls(self, box: Box) -> None: ...


class MomentaryActionHandler(Thread, Generic[S]):
    def __init__(self, widget: PushButton, event: Event, state: S, timeout: float) -> None:
        super().__init__(daemon=True)
        self._widget = widget
        self._ev = event
        self._state = state
        self._timeout = timeout
        self.start()

    def run(self) -> None:
        while not self._ev.wait(self._timeout):
            if not self._ev.is_set():
                print("still pressed")
            else:
                break


class PowerButton(PushButton):
    pass


class AnimatedButton(PushButton):
    def start_animation(self) -> None:
        if self._image_player:
            self._image_player.start()

    def stop_animation(self) -> None:
        if self._image_player:
            self._image_player.stop()

    def _clear_image(self) -> None:
        self.stop_animation()
        super()._clear_image()
