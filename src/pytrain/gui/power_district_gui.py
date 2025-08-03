import atexit
from threading import Condition, RLock, Thread
from typing import Callable

from guizero import App, Box, PushButton, Text

from .. import AccessoryState
from ..cli.bpc2 import Bpc2Cmd
from ..comm.command_listener import CommandDispatcher
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..pdi.pdi_req import PdiReq
from ..protocol.constants import CommandScope


class PowerDistrictGui(Thread):
    def __init__(self, width: int = 800, height: int = 480) -> None:
        super().__init__(daemon=True, name="Power District GUI")
        self.width = width
        self.height = height
        self._cv = Condition(RLock())
        self._districts = list[AccessoryState]()
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

    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True

            # get all accessories; watch for state changes on power districts
            accs = self._state_store.get_all(CommandScope.ACC)
            for acc in accs:
                if acc.is_power_district is True:
                    self._districts.append(acc)
                    StateWatcher(acc, self._power_district_action(acc))

            # start GUI
            self.start()

    def __call__(self, cmd: PdiReq) -> None:
        with self._cv:
            if isinstance(cmd, Bpc2Cmd):
                print(f"PowerDistrictGui: {cmd} {type(cmd)}")

    def run(self) -> None:
        GpioHandler.cache_handler(self)
        self.app = app = App(title="Power Districts", width=self.width, height=self.height)
        app.full_screen = True
        box = Box(app, layout="grid")
        _ = Text(box, text="Power Districts", grid=[0, 0, 5, 1], size=18, bold=True)
        self.by_name = PushButton(box, text="By Name", grid=[0, 1])
        self.by_number = PushButton(box, text="By TMCC ID", grid=[1, 1])

        # display GUI and start event loop; call blocks
        self.app.display()

    def update_power_district(self, pd: AccessoryState) -> None:
        print(f"Power District: {pd}")

    def _power_district_action(self, pd: AccessoryState) -> Callable:
        def upd():
            self.update_power_district(pd)

        return upd
