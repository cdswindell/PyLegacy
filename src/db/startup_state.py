from __future__ import annotations

import time
from threading import Thread

from ..pdi.base_req import BaseReq
from ..pdi.constants import PdiCommand
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
        if isinstance(cmd, PdiReq):
            if isinstance(cmd, BaseReq):
                # we request engine/sw/acc roster at startup; do this by asking for
                # Eng/Acc/Sw #100 then examining the rev links returned until we find
                # one out of range; make a request for each discovered entity
                rev_link = cmd.reverse_link if cmd.forward_link is not None else 0
                if 0 < rev_link < 100:
                    self.listener.enqueue_command(BaseReq(rev_link, cmd.pdi_command))
            elif cmd.action is not None and cmd.action.is_config:
                # register the device; registration returns a list of pdi commands
                # to send to get device state
                state_requests = self.state_store.register_pdi_device(cmd)
                if state_requests:
                    for state_request in state_requests:
                        self.listener.enqueue_command(state_request)

    def run(self) -> None:
        self.listener.subscribe_any(self)
        self.listener.enqueue_command(AllReq())
        self.listener.enqueue_command(BaseReq(100, PdiCommand.BASE_ENGINE))
        self.listener.enqueue_command(BaseReq(100, PdiCommand.BASE_ACC))
        self.listener.enqueue_command(BaseReq(100, PdiCommand.BASE_SWITCH))
        total_time = 0
        while total_time < 60:  # only listen for a minute
            time.sleep(0.1)
            total_time += 0.1
        self.listener.unsubscribe_any(self)
