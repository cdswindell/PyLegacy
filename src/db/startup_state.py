from __future__ import annotations

import time
from datetime import datetime
from threading import Thread

from .component_state_store import ComponentStateStore
from ..pdi.constants import CommonAction
from ..pdi.pdi_listener import PdiListener
from ..pdi.pdi_req import PdiReq, AllReq


class StartupState(Thread):
    def __init__(self, listener: PdiListener, state_store: ComponentStateStore) -> None:
        super().__init__(daemon=True, name="PyTrain Startup State Sniffer")
        self.listener = listener
        self.state_store = state_store
        self.start()

    def __call__(self, cmd: PdiReq) -> None:
        """
        Callback specified in the Subscriber protocol used to send events to listeners
        """
        if cmd.is_lcs and cmd.action.bits == CommonAction.CONFIG.bits:
            self.state_store.register_lcs_device(cmd)
            print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {cmd}")

    def run(self) -> None:
        self.listener.subscribe_any(self)
        self.listener.enqueue_command(AllReq())
        total_time = 0
        while total_time < 60:  # only listen for a minute
            time.sleep(0.1)
            total_time += 0.1
