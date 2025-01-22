#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

import os
import socket

#
# PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#
# SPDX-License-Identifier: LPGL
#
from queue import Queue
from typing import Any


class PollableQueue(Queue):
    def __init__(self, maxsize) -> None:
        super().__init__(maxsize)

        # Create a pair of connected sockets
        if os.name == "posix":
            self._put_socket, self._get_socket = socket.socketpair()
        else:
            # compatibility on non-POSIX systems
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            self._put_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._put_socket.connect(server.getsockname())
            self._get_socket, _ = server.accept()
            server.close()

    def fileno(self) -> int:
        return self._get_socket.fileno()

    def put(self, item: Any, block: bool = True, timeout: float = None) -> None:
        super().put(item, block=block, timeout=timeout)
        self._put_socket.send(b"x")

    def get(self, block: bool = True, timeout: float = None) -> Any:
        self._get_socket.recv(1)
        return super().get(block=block, timeout=timeout)
