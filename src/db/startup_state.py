from __future__ import annotations

import time
from threading import Thread

from ..pdi.base_req import BaseReq
from ..pdi.constants import PdiCommand
from ..pdi.pdi_listener import PdiListener
from ..pdi.pdi_req import PdiReq, AllReq
from ..pdi.pdi_state_store import PdiStateStore
from ..protocol.constants import PROGRAM_NAME


class StartupState(Thread):
    def __init__(self, listener: PdiListener, state_store: PdiStateStore) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Startup State Sniffer")
        self.listener = listener
        self.state_store = state_store
        self._processed_configs = set()
        self.start()

    def __call__(self, cmd: PdiReq) -> None:
        """
        Callback specified in the Subscriber protocol used to send events to listeners
        """
        if isinstance(cmd, PdiReq):
            if isinstance(cmd, BaseReq):
                # we request engine/sw/acc roster at startup; do this by asking for
                # Eng/Train/Acc/Sw #100 then examining the rev links returned until
                # we find one out of range; make a request for each discovered entity
                fwd_link = cmd.forward_link if cmd.forward_link is not None else 0
                if 0 < fwd_link < 100:
                    self.listener.enqueue_command(BaseReq(fwd_link, cmd.pdi_command))
            elif cmd.action and cmd.action.is_config and self._config_key(cmd) not in self._processed_configs:
                # register the device; registration returns a list of pdi commands
                # to send to get device state
                state_requests = self.state_store.register_pdi_device(cmd)
                self._processed_configs.add(self._config_key(cmd))
                if state_requests:
                    for state_request in state_requests:
                        self.listener.enqueue_command(state_request)

    @staticmethod
    def _config_key(cmd: PdiReq) -> bytes:
        byte_str = cmd.pdi_command.as_bytes
        byte_str += cmd.tmcc_id.to_bytes(1, byteorder="big")
        byte_str += cmd.action.as_bytes
        return byte_str

    def run(self) -> None:
        self.listener.subscribe_any(self)
        self.listener.enqueue_command(AllReq())
        self.listener.enqueue_command(BaseReq(0, PdiCommand.BASE))
        self.listener.enqueue_command(BaseReq(101, PdiCommand.BASE_ENGINE))
        self.listener.enqueue_command(BaseReq(101, PdiCommand.BASE_TRAIN))
        self.listener.enqueue_command(BaseReq(101, PdiCommand.BASE_ACC))
        self.listener.enqueue_command(BaseReq(101, PdiCommand.BASE_ROUTE))
        self.listener.enqueue_command(BaseReq(101, PdiCommand.BASE_SWITCH))
        total_time = 0
        while total_time < 120:  # only listen for 2 minutes
            time.sleep(0.1)
            total_time += 0.1
        self.listener.unsubscribe_any(self)
