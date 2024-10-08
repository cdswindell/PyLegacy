from __future__ import annotations

import threading
from collections import deque
from queue import Queue
from threading import Thread

from .constants import PDI_SOP, PDI_STF, PDI_EOP
from .pdi_req import PdiReq
from ..protocol.constants import DEFAULT_QUEUE_SIZE, DEFAULT_BASE3_PORT


class PdiListener(Thread):
    _instance: None = None
    _lock = threading.RLock()

    @classmethod
    def build(cls,
              base3: str,
              base3_port: int = DEFAULT_BASE3_PORT,
              queue_size: int = DEFAULT_QUEUE_SIZE) -> PdiListener:
        """
            Factory method to create a CommandListener instance
        """
        return PdiListener(base3, base3_port, queue_size)

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_built(cls) -> bool:
        return cls._instance is not None

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_running(cls) -> bool:
        # noinspection PyProtectedMember
        return cls._instance is not None and cls._instance._is_running

    @classmethod
    def enqueue_command(cls, data: bytes | PdiReq) -> None:
        if cls._instance is not None and data:
            if isinstance(data, PdiReq):
                data = data.as_bytes
            # noinspection PyProtectedMember
            cls._instance._base3.send(data)

    @classmethod
    def stop(cls) -> None:
        with cls._lock:
            if cls._instance:
                cls._instance.shutdown()

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in a process
        """
        with cls._lock:
            if PdiListener._instance is None:
                PdiListener._instance = super(PdiListener, cls).__new__(cls)
                PdiListener._instance._initialized = False
            return PdiListener._instance

    def __init__(self,
                 base3_addr: str,
                 base3_port: int = DEFAULT_BASE3_PORT,
                 queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        self._base3_addr = base3_addr
        self._base3_port = base3_port
        super().__init__(daemon=True, name="PyLegacy PDI Listener")

        # open a connection to our Base 3
        from .base3_buffer import Base3Buffer
        self._base3 = Base3Buffer(base3_addr, base3_port, queue_size, self)

        # create the thread

        # prep our consumer(s)
        self._cv = threading.Condition()
        self._deque = deque(maxlen=DEFAULT_QUEUE_SIZE)
        self._is_running = True
        self._dispatcher = PdiDispatcher.build(queue_size)

        # start listener thread
        self.start()

    def run(self) -> None:
        while self._is_running:
            # process bytes, as long as there are any
            with self._cv:
                if not self._deque:
                    self._cv.wait()  # wait to be notified
            # check if the first bite is in the list of allowable command prefixes
            dq_len = len(self._deque)
            while dq_len > 0:  # may indicate thread is exiting
                # we now begin a state machine where we look for an SOP/EOP pair. Throw away
                # bytes until we see an SOP
                if self._deque[0] == PDI_SOP:
                    # we've found the possible start of a PDI command sequence. Check if we've found
                    # a PDI_EOP byte, or a "stuff" byte; we handle each situation separately
                    try:
                        eop_pos = self._deque.index(PDI_EOP)
                    except ValueError:
                        # no luck, wait for more bytes; should we impose a maximum byte count?
                        dq_len = -1  # to bypass inner while loop; we need more data
                        continue
                    # make sure preceding byte isn't a stuff byte
                    if eop_pos - 1 > 0:
                        if self._deque[eop_pos - 1] == PDI_STF:
                            print("*** we found an unhandled stuff-it")
                            continue  # this isn't really an EOF
                        # we found a complete PDI packet! Queue it for processing
                        req_bytes = bytes()
                        for _ in range(eop_pos + 1):
                            req_bytes += self._deque.popleft().to_bytes(1, byteorder='big')
                            dq_len -= 1
                        try:
                            self._dispatcher.offer(PdiReq.from_bytes(req_bytes))
                        except Exception as e:
                            print(f"Failed to dispatch request {req_bytes.hex(':')}: {e}")
                        continue  # with while dq_len > 0 loop
                # pop this byte and continue; we either received unparsable input
                # or started receiving data mid-command
                print(f"Ignoring {hex(self._deque.popleft())}")
                dq_len -= 1
        # shut down the dispatcher
        if self._dispatcher:
            self._dispatcher.shutdown()

    def offer(self, data: bytes) -> None:
        if data:
            with self._cv:
                self._deque.extend(data)
                self._cv.notify()

    def shutdown(self) -> None:
        if hasattr(self, "_cv"):
            with self._cv:
                self._is_running = False
                self._cv.notify()
        if hasattr(self, "_dispatcher"):
            if self._dispatcher:
                self._dispatcher.shutdown()
        if hasattr(self, "_base3"):
            if self._base3:
                self._base3.shutdown()
        PdiListener._instance = None


class PdiDispatcher(Thread):
    """
        The PdiDispatcher thread receives parsed PdiReqs from the
        PdiListener and dispatches them to subscribing listeners
    """
    _instance = None
    _lock = threading.RLock()

    @classmethod
    def build(cls, queue_size: int = DEFAULT_QUEUE_SIZE) -> PdiDispatcher:
        """
            Factory method to create a CommandDispatcher instance
        """
        return PdiDispatcher(queue_size)

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_running(cls) -> bool:
        # noinspection PyProtectedMember
        return cls._instance is not None and cls._instance._is_running

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_built(cls) -> bool:
        return cls._instance is not None

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in a process
        """
        with cls._lock:
            if PdiDispatcher._instance is None:
                PdiDispatcher._instance = super(PdiDispatcher, cls).__new__(cls)
                PdiDispatcher._instance._initialized = False
            return PdiDispatcher._instance

    def __init__(self, queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name="PyLegacy Pdi Dispatcher")
        self._cv = threading.Condition()
        self._is_running = True
        self._queue = Queue[PdiReq](queue_size)
        self.start()

    def run(self) -> None:
        while self._is_running:
            with self._cv:
                if self._queue.empty():
                    self._cv.wait()
            if self._queue.empty():  # we need to do a second check in the event we're being shutdown
                continue
            cmd: PdiReq = self._queue.get()
            try:
                # publish dispatched pdi commands to listeners
                if isinstance(cmd, PdiReq):
                    print(cmd)
            except Exception as e:
                print(e)
            finally:
                self._queue.task_done()

    def offer(self, pdi_req: PdiReq) -> None:
        """
            Receive a command from the listener thread and dispatch it to subscribers.
            We do this in a separate thread so that the listener thread doesn't fall behind
        """
        if pdi_req is not None and isinstance(pdi_req, PdiReq) and not pdi_req.is_ping:
            with self._cv:
                self._queue.put(pdi_req)
                self._cv.notify()  # wake up receiving thread

    def shutdown(self) -> None:
        with self._cv:
            self._is_running = False
            self._cv.notify()
        PdiDispatcher._instance = None
