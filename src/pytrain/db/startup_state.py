#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import logging
import time
from threading import Thread, Condition, Event

from ..db.component_state_store import ComponentStateStore
from ..comm.command_listener import SYNCING, CommandDispatcher, SYNC_COMPLETE
from ..pdi.base_req import BaseReq
from ..pdi.constants import PdiCommand, D4Action
from ..pdi.d4_req import D4Req
from ..pdi.pdi_listener import PdiListener
from ..pdi.pdi_req import PdiReq, AllReq
from ..pdi.pdi_state_store import PdiStateStore
from ..protocol.constants import PROGRAM_NAME, CommandScope

log = logging.getLogger(__name__)


class StartupState(Thread):
    def __init__(self, listener: PdiListener, dispatcher: CommandDispatcher, pdi_state_store: PdiStateStore) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Startup State Sniffer")
        self.listener = listener
        self.pdi_state_store = pdi_state_store
        self._cv = Condition()
        self._ev = Event()
        self._waiting_for = dict()
        self._processed_configs = set()
        self._sync_state = ComponentStateStore.get_state(CommandScope.SYNC, 99)
        self._dispatcher = dispatcher
        self._dispatcher.offer(SYNCING)
        self.start()

    def __call__(self, cmd: PdiReq) -> None:
        """
        Callback specified in the Subscriber protocol used to send events to listeners
        """

        if cmd:
            with self._cv:
                self._waiting_for.pop(cmd.as_key, None)
        else:
            return
        if isinstance(cmd, PdiReq):
            req = None
            if cmd.action and cmd.action.is_config and self._config_key(cmd) not in self._processed_configs:
                # register the device; registration returns a list of pdi commands
                # to send to get device state
                state_requests = self.pdi_state_store.register_pdi_device(cmd)
                self._processed_configs.add(self._config_key(cmd))
                if state_requests:
                    for state_request in state_requests:
                        self.listener.enqueue_command(state_request)
            elif isinstance(cmd, BaseReq) and cmd.pdi_command == PdiCommand.BASE_MEMORY:
                if cmd.scope == CommandScope.TRAIN and cmd.tmcc_id == 98:
                    self._dispatcher.offer(SYNC_COMPLETE)
                # send a request to the base to get the next engine/train/acc/switch/route record (0x26)
                if cmd.tmcc_id < 98 and cmd.data_length == PdiReq.scope_record_length(cmd.scope):
                    req = BaseReq(cmd.tmcc_id + 1, PdiCommand.BASE_MEMORY, scope=cmd.scope)
            elif isinstance(cmd, D4Req):
                req = None
                if cmd.action == D4Action.COUNT and cmd.count:
                    # request first record of D4 engines/trains
                    req = D4Req(0, cmd.pdi_command, D4Action.FIRST_REC)
                elif cmd.action in {D4Action.FIRST_REC, D4Action.NEXT_REC}:
                    if cmd.next_record_no == 0xFFFF:
                        pass
                    elif cmd.next_record_no is not None:
                        # query current state of 4-digit engine/train
                        req = D4Req(
                            cmd.next_record_no,
                            cmd.pdi_command,
                            D4Action.QUERY,
                            start=0,
                            data_length=0xC0,
                        )
                        with self._cv:
                            self._waiting_for[req.as_key] = req
                        self.listener.enqueue_command(req)
                        # get the record number of the next engine/train
                        req = D4Req(cmd.next_record_no, cmd.pdi_command, D4Action.NEXT_REC)
            if req:
                with self._cv:
                    self._waiting_for[req.as_key] = req
                self.listener.enqueue_command(req)
            else:
                with self._cv:
                    if not self._waiting_for:
                        self._ev.set()
                        self._cv.notify_all()

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
        for pdi_command in [PdiCommand.D4_ENGINE, PdiCommand.D4_TRAIN]:
            req = D4Req(0, pdi_command, D4Action.COUNT)
            with self._cv:
                self._waiting_for[req.as_key] = req
            self.listener.enqueue_command(req)
        # Request engine/sw/acc roster at startup; do this by asking for
        # Eng/Train/Acc/Sw/Route then examining the rev links returned until
        # we find one out of range; make a request for each discovered entity
        for scope in [
            CommandScope.ENGINE,
            CommandScope.TRAIN,
            CommandScope.SWITCH,
            CommandScope.ACC,
            CommandScope.ROUTE,
        ]:
            req = BaseReq(1, PdiCommand.BASE_MEMORY, scope=scope)
            with self._cv:
                self._waiting_for[req.as_key] = req
            self.listener.enqueue_command(req)

        # now wait for all responses; this will not track LCS devices reporting their config
        # because of the AllReq
        total_time = 0
        now = time.time()
        ev_set = False
        while total_time < 120:  # only listen for 2 minutes
            self._ev.wait(0.25)
            if self._ev.is_set() or (ev_set is True):
                self._ev.clear()
                ev_set = True
                if round(time.time() - now) >= 0:
                    log.info(f"Initial state loaded from Base 3: {time.time() - now:.2f} seconds elapsed.")
                    break
            total_time += 0.25
        for k, v in self._waiting_for.items():
            log.info(f"Failed to receive {k} state: {v}")
        self.listener.unsubscribe_any(self)
