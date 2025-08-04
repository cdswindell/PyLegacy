import atexit
from threading import Condition, RLock, Thread
from typing import Callable

from guizero import App, Box, PushButton, Text

from .. import AccessoryState, CommandReq, TMCC1AuxCommandEnum
from ..comm.command_listener import CommandDispatcher
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..protocol.constants import CommandScope


class PowerDistrictGui(Thread):
    def __init__(self, width: int = 800, height: int = 480) -> None:
        super().__init__(daemon=True, name="Power District GUI")
        self.width = width
        self.height = height
        self._cv = Condition(RLock())
        self._max_name_len = 0
        self._districts = dict[int, AccessoryState]()
        self._power_district_buttons = dict[int, PushButton]()
        self.app = self.by_name = self.by_number = None

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
        atexit.register(self.close)

    def close(self) -> None:
        pass

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

    def run(self) -> None:
        GpioHandler.cache_handler(self)
        self.app = app = App(title="Power Districts", width=self.width, height=self.height)
        app.full_screen = True
        box = Box(app, layout="grid")
        box.bg = "white"
        _ = Text(box, text="Power Districts", grid=[0, 0, 2, 1], size=24, bold=True)
        self.by_name = PushButton(box, text="By Name", grid=[0, 1], width=len("By TMCC ID"))
        self.by_number = PushButton(box, text="By TMCC ID", grid=[1, 1])
        self.by_name.text_size = self.by_number.text_size = 18

        # define power district push buttons
        row = 1
        col = 0
        for pd in self._districts.values():
            row = row + 1 if col == 0 else row
            self._power_district_buttons[pd.tmcc_id] = PushButton(
                box,
                text=f"#{pd.tmcc_id:0>2} {pd.road_name}",
                grid=[col, row],
                width=self._max_name_len,
                command=self.switch_power_district,
                args=[pd],
            )
            self._power_district_buttons[pd.tmcc_id].text_size = 14
            self._power_district_buttons[pd.tmcc_id].bg = "grey" if pd.is_aux_on is False else "green"
            self._power_district_buttons[pd.tmcc_id].text_color = "black"
            col = col + 1 if col == 0 else 0

        # display GUI and start event loop; call blocks
        self.app.display()

    def switch_power_district(self, pd: AccessoryState) -> None:
        with self._cv:
            if pd.is_aux_on:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, pd.tmcc_id).send()
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, pd.tmcc_id).send()

    def update_power_district(self, pd: AccessoryState) -> None:
        with self._cv:
            self._power_district_buttons[pd.tmcc_id].bg = "grey" if pd.is_aux_on is False else "green"

    def _power_district_action(self, pd: AccessoryState) -> Callable:
        def upd():
            self.update_power_district(pd)

        return upd
