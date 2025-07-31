import atexit
from threading import Condition, RLock, Thread
from typing import Callable

from guizero import App

from ..comm.command_listener import CommandDispatcher
from ..db.component_state import RouteState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope


class RouteGui(Thread):
    def __init__(self, width: int = 800, height: int = 480) -> None:
        super().__init__(daemon=True, name="Route GUI")
        self.width = width
        self.height = height
        self._cv = Condition(RLock())
        self._routes = None
        self.app = None

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

            # get all routes
            self._routes = self._state_store.get_all(CommandScope.ROUTE)
            for route in self._routes:
                StateWatcher(route, self._route_action(route))

            # start GUI
            self.start()

            # listen for state updates
            # self._dispatcher.subscribe(self, CommandScope.SWITCH)
            # self._dispatcher.subscribe(self, CommandScope.ROUTE)

    def __call__(self, cmd: CommandReq) -> None:
        with self._cv:
            print(f"RouteGui: {cmd} {type(cmd)}")

    def run(self) -> None:
        GpioHandler.cache_handler(self)
        self.app = app = App(title="Launch Pad", width=self.width, height=self.height)
        app.full_screen = True

        # display GUI and start event loop; call blocks
        self.app.display()

    def update_route(self, route: RouteState) -> None:
        print(f"RouteGui: {route}")

    def _route_action(self, route: RouteState) -> Callable:
        def ur():
            self.update_route(route)

        return ur
