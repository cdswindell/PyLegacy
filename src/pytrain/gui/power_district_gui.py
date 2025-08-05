import atexit
from threading import Condition, RLock, Thread
from typing import Callable

from guizero import App, Box, PushButton, Text

from ..comm.command_listener import CommandDispatcher
from ..db.accessory_state import AccessoryState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.path_utils import find_file


class PowerDistrictGui(Thread):
    def __init__(self, label: str = None, width: int = 800, height: int = 380) -> None:
        super().__init__(daemon=True, name="Power District GUI")
        self.width = width
        self.height = height
        self.label = label
        self._cv = Condition(RLock())
        self._max_name_len = 0
        self._districts = dict[int, AccessoryState]()
        self._power_district_buttons = dict[int, PushButton]()
        self._enabled_bg = "green"
        self._disabled_bg = "black"
        self._enabled_text = "black"
        self._disabled_text = "lightgrey"
        self.left_arrow = find_file("left_arrow.jpg")
        self.right_arrow = find_file("right_arrow.jpg")
        self.app = self.by_name = self.by_number = self.box = self.btn_box = self.y_offset = None
        self.left_scroll_btn = None

        # listen for state changes
        self._dispatcher = CommandDispatcher.get()
        self._state_store = ComponentStateStore.get()
        self._synchronized = False
        self._sync_state = self._state_store.get_state(CommandScope.SYNC, 99)
        if self._sync_state and self._sync_state.is_synchronized is True:
            self._sync_watcher = None
            self.on_sync()
        else:
            self._sync_watcher = StateWatcher(self._sync_state, self.on_sync)
        self._is_closed = False
        atexit.register(self.close)

    def close(self) -> None:
        with self._cv:
            if not self._is_closed:
                self._is_closed = True
                self.app.after(10, self.app.destroy)
                self.join()

    def reset(self) -> None:
        self.close()

    # noinspection PyTypeChecker,PyUnresolvedReferences
    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True

            # get all accessories; watch for state changes on power districts
            accs = self._state_store.get_all(CommandScope.ACC)
            for acc in accs:
                if acc.is_power_district is True and acc.road_name and acc.road_name.lower() != "unused":
                    self._districts[acc.tmcc_id] = acc
                    nl = len(acc.road_name)
                    self._max_name_len = nl if nl > self._max_name_len else self._max_name_len
                    StateWatcher(acc, self._power_district_action(acc))
            # start GUI
            self.start()

    # noinspection PyTypeChecker
    def run(self) -> None:
        GpioHandler.cache_handler(self)
        self.app = app = App(title="Power Districts", width=self.width, height=self.height)
        app.full_screen = True
        app.when_closed = self.close
        self.box = box = Box(app, layout="grid")
        app.bg = box.bg = "white"
        label = f"{self.label} " if self.label else ""
        _ = Text(box, text=" ", grid=[0, 0, 4, 1], size=6, height=1, bold=True)
        _ = Text(box, text=f"{label}Power Districts", grid=[0, 1, 4, 1], size=24, bold=True)
        self.by_number = PushButton(
            box,
            text="By TMCC ID",
            grid=[1, 2],
            command=self.sort_by_number,
            padx=5,
            pady=5,
        )
        self.by_name = PushButton(
            box,
            text="By Name",
            grid=[2, 2],
            width=len("By TMCC ID"),
            command=self.sort_by_name,
            padx=5,
            pady=5,
        )
        self.by_name.text_size = self.by_number.text_size = 18
        self.by_number.text_bold = True
        _ = Text(box, text=" ", grid=[0, 3, 4, 1], size=4, height=1, bold=True)
        self.app.update()

        # add scroll btns
        sort_btn_height = self.by_number.tk.winfo_height()
        self.left_scroll_btn = PushButton(
            box,
            grid=[0, 1, 1, 2],
            enabled=False,
            image=self.left_arrow,
            height=sort_btn_height * 2,
            width=sort_btn_height * 2,
        )

        self.y_offset = self.box.tk.winfo_y() + self.box.tk.winfo_height()

        # put the buttons in a separate box
        self.btn_box = Box(app, layout="grid")

        # define power district push buttons
        self.sort_by_number()

        # Display GUI and start event loop; call blocks
        self.app.display()

    def update_power_district(self, pd: AccessoryState) -> None:
        with self._cv:
            if pd.is_aux_on:
                self._power_district_buttons[pd.tmcc_id].bg = self._enabled_bg
                self._power_district_buttons[pd.tmcc_id].text_color = self._enabled_text
            else:
                self._power_district_buttons[pd.tmcc_id].bg = self._disabled_bg
                self._power_district_buttons[pd.tmcc_id].text_color = self._disabled_text

    def _power_district_action(self, pd: AccessoryState) -> Callable:
        def upd():
            self.update_power_district(pd)

        return upd

    def switch_power_district(self, pd: AccessoryState) -> None:
        with self._cv:
            if pd.is_aux_on:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, pd.tmcc_id).send()
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, pd.tmcc_id).send()

    def _reset_power_district_buttons(self) -> None:
        for pdb in self._power_district_buttons.values():
            pdb.destroy()
        self._power_district_buttons.clear()

    def _make_power_district_buttons(self, power_districts: list[AccessoryState] = None) -> None:
        with self._cv:
            self._reset_power_district_buttons()
            row = 4
            col = 0
            btn_h = btn_y = None
            self.btn_box.visible = False
            for pd in power_districts:
                if btn_h and btn_y and self.y_offset + btn_y + btn_h > self.height:
                    row = 4
                    col += 1
                self._power_district_buttons[pd.tmcc_id] = PushButton(
                    self.btn_box,
                    text=f"#{pd.tmcc_id:0>2} {pd.road_name}",
                    grid=[col, row],
                    width=self._max_name_len - 1,
                    command=self.switch_power_district,
                    args=[pd],
                    padx=0,
                )
                self._power_district_buttons[pd.tmcc_id].text_size = 15
                self._power_district_buttons[pd.tmcc_id].bg = self._enabled_bg if pd.is_aux_on else self._disabled_bg
                self._power_district_buttons[pd.tmcc_id].text_color = (
                    self._enabled_text if pd.is_aux_on else self._disabled_text
                )
                row += 1
                self.app.update()
                if btn_h is None:
                    btn_h = self._power_district_buttons[pd.tmcc_id].tk.winfo_height()
                btn_y = self._power_district_buttons[pd.tmcc_id].tk.winfo_y() + btn_h
            self.btn_box.visible = True

    def sort_by_number(self) -> None:
        self.by_number.text_bold = True
        self.by_name.text_bold = False

        # define power district push buttons
        states = sorted(self._districts.values(), key=lambda x: x.tmcc_id)
        self._make_power_district_buttons(states)

    def sort_by_name(self) -> None:
        self.by_name.text_bold = True
        self.by_number.text_bold = False

        # define power district push buttons
        states = sorted(self._districts.values(), key=lambda x: x.road_name.lower())
        self._make_power_district_buttons(states)
