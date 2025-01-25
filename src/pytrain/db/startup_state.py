from __future__ import annotations

import time
from threading import Thread

from ..comm.command_listener import SYNCING, CommandDispatcher
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
        CommandDispatcher.build().offer(SYNCING)
        self.start()

    def __call__(self, cmd: PdiReq) -> None:
        """
        Callback specified in the Subscriber protocol used to send events to listeners
        """
        if isinstance(cmd, PdiReq):
            if cmd.action and cmd.action.is_config and self._config_key(cmd) not in self._processed_configs:
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
        # we request engine/sw/acc roster at startup; do this by asking for
        # Eng/Train/Acc/Sw #100 then examining the rev links returned until
        # we find one out of range; make a request for each discovered entity
        for tmcc_id in range(1, 99):
            self.listener.enqueue_command(BaseReq(tmcc_id, PdiCommand.BASE_ENGINE))
            time.sleep(0.05)
            self.listener.enqueue_command(BaseReq(tmcc_id, PdiCommand.BASE_TRAIN))
        time.sleep(0.05)
        for tmcc_id in range(1, 99):
            self.listener.enqueue_command(BaseReq(tmcc_id, PdiCommand.BASE_ACC))
            time.sleep(0.05)
            self.listener.enqueue_command(BaseReq(tmcc_id, PdiCommand.BASE_SWITCH))
            time.sleep(0.05)
            self.listener.enqueue_command(BaseReq(tmcc_id, PdiCommand.BASE_ROUTE))
        total_time = 0
        while total_time < 120:  # only listen for 2 minutes
            time.sleep(0.25)
            total_time += 0.25
        self.listener.unsubscribe_any(self)
