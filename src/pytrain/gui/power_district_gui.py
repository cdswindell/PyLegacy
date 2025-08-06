import atexit
from abc import abstractmethod, ABCMeta, ABC
from threading import Condition, RLock, Thread
from typing import Callable, TypeVar, cast

from guizero import App, Box, PushButton, Text

from ..comm.command_listener import CommandDispatcher
from ..db.accessory_state import AccessoryState
from ..db.component_state import ComponentState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.path_utils import find_file

S = TypeVar("S", bound=ComponentState)


class StateBasedGui[S](ABC):
    __metaclass__ = ABCMeta

    def __init__(self, label: str = None, width: int = None, height: int = None) -> None:
        self._cv = Condition(RLock())
        if width is None or height is None:
            app = App(title="Screen Size Detector")
            # Access the underlying tkinter root window
            tkinter_root = app.tk
            # Get the screen width and height
            self.width = tkinter_root.winfo_screenwidth()
            self.height = tkinter_root.winfo_screenheight()
            app.destroy()
        else:
            self.width = width
            self.height = height
        self.label = label

        self._enabled_bg = "green"
        self._disabled_bg = "black"
        self._enabled_text = "black"
        self._disabled_text = "lightgrey"
        self.left_arrow = find_file("left_arrow.jpg")
        self.right_arrow = find_file("right_arrow.jpg")
        self.app = self.by_name = self.by_number = self.box = self.btn_box = self.y_offset = None
        self.pd_button_height = self.left_scroll_btn = self.right_scroll_btn = None
        self._max_name_len = 0
        self._max_button_rows = self._max_button_cols = None
        self._first_button_col = 0
        self.sort_func = None

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
                self.app.after(50, self.app.destroy)
                if isinstance(self, Thread):
                    self.join()

    def reset(self) -> None:
        self.close()

    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True

            # get all target states; watch for state changes
            accs = self.get_target_states()
            for acc in accs:
                nl = len(acc.road_name)
                self._max_name_len = nl if nl > self._max_name_len else self._max_name_len
                StateWatcher(acc, self.on_state_change_action(acc))
            # start GUI
            if isinstance(self, Thread):
                self.start()

    @abstractmethod
    def get_target_states(self) -> list[S]: ...

    @abstractmethod
    def on_state_change_action(self, state: S) -> Callable: ...


class PowerDistrictGui(Thread, StateBasedGui):
    def __init__(self, label: str = None, width: int = None, height: int = None) -> None:
        self._districts = dict[int, AccessoryState]()
        self._power_district_buttons = dict[int, PushButton]()

        # customize label
        label = f"{label} Power Districts" if label else "Power Districts"

        Thread.__init__(self, daemon=True, name="Power District GUI")
        StateBasedGui.__init__(self, label, width, height)

    def get_target_states(self) -> list[AccessoryState]:
        pds: list[AccessoryState] = []
        accs = self._state_store.get_all(CommandScope.ACC)
        for acc in accs:
            acc = cast(AccessoryState, acc)
            if acc.is_power_district is True and acc.road_name and acc.road_name.lower() != "unused":
                pds.append(acc)
                self._districts[acc.tmcc_id] = acc
        return pds

    # noinspection PyTypeChecker
    def run(self) -> None:
        GpioHandler.cache_handler(self)
        self.app = app = App(title="Power Districts", width=self.width, height=self.height)
        app.full_screen = True
        app.when_closed = self.close

        self.box = box = Box(app, layout="grid")
        app.bg = box.bg = "white"

        _ = Text(box, text=" ", grid=[0, 0, 6, 1], size=6, height=1, bold=True)
        _ = Text(box, text="    ", grid=[1, 1], size=24)
        _ = Text(box, text=self.label, grid=[2, 1, 2, 1], size=24, bold=True)
        _ = Text(box, text="    ", grid=[4, 1], size=24)
        self.by_number = PushButton(
            box,
            text="By TMCC ID",
            grid=[2, 2],
            command=self.sort_by_number,
            padx=5,
            pady=5,
        )
        self.by_name = PushButton(
            box,
            text="By Name",
            grid=[3, 2],
            width=len("By TMCC ID"),
            command=self.sort_by_name,
            padx=5,
            pady=5,
        )
        self.by_name.text_size = self.by_number.text_size = 18
        self.by_number.text_bold = True
        _ = Text(box, text=" ", grid=[0, 3, 6, 1], size=4, height=1, bold=True)
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
            align="left",
            command=self.scroll_left,
        )
        self.right_scroll_btn = PushButton(
            box,
            grid=[5, 1, 1, 2],
            enabled=False,
            image=self.right_arrow,
            height=sort_btn_height * 2,
            width=sort_btn_height * 2,
            align="right",
            command=self.scroll_right,
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

    def on_state_change_action(self, pd: AccessoryState) -> Callable:
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

    def _make_state_buttons(self, power_districts: list[AccessoryState] = None) -> None:
        with self._cv:
            self._reset_power_district_buttons()
            active_cols = {self._first_button_col, self._first_button_col + 1}
            row = 4
            col = 0

            btn_h = self.pd_button_height
            btn_y = 0
            self.right_scroll_btn.disable()
            self.left_scroll_btn.disable()

            self.btn_box.visible = False
            for pd in power_districts:
                if btn_h is not None and btn_y is not None and self.y_offset + btn_y + btn_h > self.height:
                    if self._max_button_rows is None:
                        self._max_button_rows = row - 4
                    btn_y = 0
                    row = 4
                    col += 1
                if col in active_cols:
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
                    self._power_district_buttons[pd.tmcc_id].bg = (
                        self._enabled_bg if pd.is_aux_on else self._disabled_bg
                    )
                    self._power_district_buttons[pd.tmcc_id].text_color = (
                        self._enabled_text if pd.is_aux_on else self._disabled_text
                    )
                    # recalculate height
                    self.app.update()
                    if self.pd_button_height is None:
                        btn_h = self.pd_button_height = self._power_district_buttons[pd.tmcc_id].tk.winfo_height()
                    btn_y = self._power_district_buttons[pd.tmcc_id].tk.winfo_y() + btn_h
                else:
                    btn_y += btn_h
                row += 1
            if max(active_cols) < col:
                self.right_scroll_btn.enable()
            else:
                self.right_scroll_btn.disable()
            if max(active_cols) > 1:
                self.left_scroll_btn.enable()
            else:
                self.left_scroll_btn.disable()

            self.btn_box.visible = True

    def sort_by_number(self) -> None:
        self.by_number.text_bold = True
        self.by_name.text_bold = False

        # define power district push buttons
        self.sort_func = lambda x: x.tmcc_id
        states = sorted(self._districts.values(), key=self.sort_func)
        self._first_button_col = 0
        self._make_state_buttons(states)

    def sort_by_name(self) -> None:
        self.by_name.text_bold = True
        self.by_number.text_bold = False

        # define power district push buttons
        self.sort_func = lambda x: x.road_name.lower()
        states = sorted(self._districts.values(), key=self.sort_func)
        self._first_button_col = 0
        self._make_state_buttons(states)

    def scroll_left(self) -> None:
        self._first_button_col -= 1

        states = sorted(self._districts.values(), key=self.sort_func)
        self._make_state_buttons(states)

    def scroll_right(self) -> None:
        self._first_button_col += 1

        states = sorted(self._districts.values(), key=self.sort_func)
        self._make_state_buttons(states)
