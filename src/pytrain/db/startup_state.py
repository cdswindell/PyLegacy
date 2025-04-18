#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import time
from threading import Thread

from ..comm.command_listener import SYNCING, CommandDispatcher, SYNC_COMPLETE
from ..pdi.base_req import BaseReq
from ..pdi.constants import PdiCommand, D4Action
from ..pdi.d4_req import D4Req
from ..pdi.pdi_listener import PdiListener
from ..pdi.pdi_req import AllReq, PdiReq
from ..pdi.pdi_state_store import PdiStateStore
from ..protocol.constants import PROGRAM_NAME, CommandScope


class StartupState(Thread):
    def __init__(self, listener: PdiListener, state_store: PdiStateStore) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Startup State Sniffer")
        self.listener = listener
        self.state_store = state_store
        self._processed_configs = set()
        CommandDispatcher.get().offer(SYNCING)
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
            elif cmd.pdi_command == PdiCommand.BASE_MEMORY:
                # send a request to the base to get the next engine or train record (0x26)
                if cmd.tmcc_id < 99:
                    time.sleep(0.05)
                    self.listener.enqueue_command(BaseReq(cmd.tmcc_id + 1, PdiCommand.BASE_MEMORY, scope=cmd.scope))
                if cmd.scope == CommandScope.TRAIN and cmd.tmcc_id == 98:
                    CommandDispatcher.get().offer(SYNC_COMPLETE)
            elif isinstance(cmd, D4Req):
                if cmd.action == D4Action.COUNT and cmd.count:
                    # request first record of D4 engines/trains
                    self.listener.enqueue_command(D4Req(0, cmd.pdi_command, D4Action.FIRST_REC))
                elif cmd.action in {D4Action.FIRST_REC, D4Action.NEXT_REC}:
                    if cmd.next_record_no == 0xFFFF:
                        pass
                    elif cmd.next_record_no is not None:
                        # query current state of 4-digit engine/train
                        self.listener.enqueue_command(
                            D4Req(
                                cmd.next_record_no,
                                cmd.pdi_command,
                                D4Action.QUERY,
                                start=0,
                                data_length=0xC0,
                            )
                        )
                        # get the record number of the next engine/train
                        self.listener.enqueue_command(D4Req(cmd.next_record_no, cmd.pdi_command, D4Action.NEXT_REC))

    @staticmethod
    def _config_key(cmd: PdiReq) -> bytes:
        """
        Generates a unique configuration key based on the provided PdiReq command.

        Summary:
        This static method combines the byte representations of various attributes
        from a PdiReq command object to generate a unique byte key. The resulting
        key is composed of the PdiReq command's bytes, tmcc_id converted to a single
        byte, and the action's bytes.

        Args:
        cmd (PdiReq): The command object containing the attributes to be used in
        constructing the configuration key.

        Returns:
        bytes: The concatenated byte string representing the configuration key.
        """
        byte_str = cmd.pdi_command.as_bytes
        byte_str += cmd.tmcc_id.to_bytes(1, byteorder="big")
        byte_str += cmd.action.as_bytes
        return byte_str

    def run(self) -> None:
        self.listener.subscribe_any(self)
        self.listener.enqueue_command(AllReq())
        self.listener.enqueue_command(BaseReq(0, PdiCommand.BASE))
        self.listener.enqueue_command(D4Req(0, PdiCommand.D4_ENGINE, D4Action.COUNT))
        self.listener.enqueue_command(D4Req(0, PdiCommand.D4_TRAIN, D4Action.COUNT))
        # Request engine/sw/acc roster at startup; do this by asking for
        # Eng/Train/Acc/Sw #100 then examining the rev links returned until
        # we find one out of range; make a request for each discovered entity
        self.listener.enqueue_command(BaseReq(1, PdiCommand.BASE_MEMORY, scope=CommandScope.ENGINE))
        time.sleep(0.05)
        self.listener.enqueue_command(BaseReq(1, PdiCommand.BASE_MEMORY, scope=CommandScope.TRAIN))
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
