from __future__ import annotations

import time
from threading import Thread

from ..pdi.pdi_listener import PdiListener
from ..pdi.pdi_req import PdiReq, AllReq
from ..pdi.pdi_state_store import PdiStateStore


class StartupState(Thread):
    def __init__(self, listener: PdiListener, state_store: PdiStateStore) -> None:
        super().__init__(daemon=True, name="PyTrain Startup State Sniffer")
        self.listener = listener
        self.state_store = state_store
        self.start()

    def __call__(self, cmd: PdiReq) -> None:
        """
        Callback specified in the Subscriber protocol used to send events to listeners
        """
        if isinstance(cmd, PdiReq) and cmd.action is not None and cmd.action.is_config:
            # register the device; registration returns a list of pdi commands
            # to send to get device state
            state_requests = self.state_store.register_pdi_device(cmd)
            if state_requests:
                for state_request in state_requests:
                    self.listener.enqueue_command(state_request)

    def run(self) -> None:
        self.listener.subscribe_any(self)
        self.listener.enqueue_command(AllReq())
        total_time = 0
        while total_time < 60:  # only listen for a minute
            time.sleep(0.1)
            total_time += 0.1
        self.listener.unsubscribe_any(self)
