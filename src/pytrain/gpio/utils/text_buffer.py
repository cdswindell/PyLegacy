from threading import Condition, RLock


class TextBuffer:
    def __init__(self, rows: int = 4, cols: int = 0, auto_update: bool = True) -> None:
        super().__init__()
        self._rows = rows
        self._cols = cols
        self._cursor_pos = (0, 0)
        self._buffer: list[str] = list()
        self._cv = Condition(RLock())
        self._auto_update = auto_update
        self._changed_rows: set[int] = set()

    def __repr__(self) -> str:
        with self._cv:
            return "\n".join(self._buffer)

    def __len__(self) -> int:
        with self._cv:
            return len(self._buffer)

    def __getitem__(self, index: int):
        with self._cv:
            if 0 <= index < len(self._buffer):
                return self._buffer[index]
            else:
                raise IndexError(f"Index {index} out of range")

    def __setitem__(self, index: int, value: str):
        with self._cv:
            if self.rows > index >= len(self._buffer):
                for _ in range(index - len(self._buffer) + 1):
                    self._buffer.append("")
            if 0 <= index < self.rows:
                if self._buffer[index] != value:
                    self._buffer[index] = value
                    self._changed_rows.add(index)
                    self._cursor_pos = (index, len(value))
                    self.__do_notify()
            else:
                raise IndexError(f"Index {index} out of range")

    def __delitem__(self, index: int | slice):
        with self._cv:
            del self._buffer[index]
            self._changed_rows = set(range(self.rows))
            self.__do_notify()

    def __iter__(self):
        return iter(self._buffer)

    def insert(self, index, item):
        with self._cv:
            if index >= self.rows or index < 0 or (len(self) + 1) > self.rows:
                raise IndexError(f"Index {index} out of range")
            self._buffer.insert(index, item)
            self._changed_rows = set(range(index, self.rows))
            self.__do_notify()

    def index(self, item, start=0, end=None):
        with self._cv:
            return self._buffer.index(item, start, end if end is not None else len(self._buffer))

    def count(self, item: str):
        with self._cv:
            return self._buffer.count(item)

    def __contains__(self, item: str):
        with self._cv:
            return item in self._buffer

    def reverse(self):
        with self._cv:
            self._buffer.reverse()
            self._changed_rows = set(range(len(self._buffer)))
            self.__do_notify()

    def append(self, item: str):
        self.add(item)

    def copy(self):
        raise NotImplementedError

    def pop(self, index=-1):
        raise NotImplementedError

    def extend(self, iterable):
        raise NotImplementedError

    @property
    def auto_update(self) -> bool:
        return self._auto_update

    @auto_update.setter
    def auto_update(self, value: bool) -> None:
        self._auto_update = value

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def synchronizer(self) -> Condition:
        return self._cv

    @property
    def cursor_pos(self) -> tuple[int, int]:
        return self._cursor_pos

    @cursor_pos.setter
    def cursor_pos(self, pos: tuple[int, int] | int, col: int = None) -> None:
        with self.synchronizer:
            if isinstance(pos, int) and isinstance(col, int):
                pos = (pos, col)
            self._vet_cursor_pos(pos)
            self._cursor_pos = pos

    def _vet_cursor_pos(self, pos):
        if isinstance(pos, tuple) and len(pos) == 2:
            if pos[0] < 0 or pos[0] >= self.rows:
                raise AttributeError(f"Invalid row position: {pos[0]}")
            if self.cols and (pos[1] < 0 or pos[1] >= self.cols):
                raise AttributeError(f"Invalid column position: {pos[1]}")
        else:
            raise AttributeError(f"Invalid cursor position: {pos}")

    @property
    def row(self) -> int:
        return self._cursor_pos[0]

    @property
    def col(self) -> int:
        return self._cursor_pos[1]

    @property
    def buffer(self) -> list[str]:
        return self._buffer.copy()

    @property
    def is_dirty(self) -> bool:
        return len(self._changed_rows) > 0

    @property
    def changed_rows(self) -> list[int]:
        with self._cv:
            changes = sorted(self._changed_rows)
            self._changed_rows.clear()
            return changes

    def clear(self, notify: bool = True) -> None:
        with self._cv:
            for i, row in enumerate(self._buffer):
                if row:
                    self._changed_rows.add(i)
            self._buffer.clear()
            self._cursor_pos = (0, 0)
            if notify is True:
                self.__do_notify()

    def add(self, row: str) -> bool:
        with self._cv:
            if len(self._buffer) < self.rows:
                self._buffer.append(row)
                row_no = len(self._buffer) - 1
                self._cursor_pos = (row_no, len(row))
                self._changed_rows.add(row_no)
                self.__do_notify()
                return True
            return False

    def write_chr(self, int_chr: int, at: tuple[int, int] = None) -> None:
        if isinstance(int_chr, int) and 0 <= int_chr <= 255:
            self.write(chr(int_chr), at=at)

    def write(
        self,
        c: int | str,
        at: tuple[int, int] | int = None,
        fmt: str = None,
        center: bool = False,
    ) -> None:
        with self._cv:
            if isinstance(at, int):
                at = (at, 0)
            elif isinstance(at, tuple) and len(at) == 2:
                pass
            else:
                at = self._cursor_pos
            self._vet_cursor_pos(at)

            if len(self._buffer) <= at[0]:
                for _ in range(at[0] + 1 - len(self._buffer)):
                    self._buffer.append("")

            if fmt is not None:
                fmt = f"{fmt[1:] if fmt.startswith(':') else fmt}"

            if isinstance(c, int):
                if fmt:
                    s = f"{c:{fmt}}"
                    fmt = None
                else:
                    s = str(c)
            else:
                s = str(c)
            if fmt is not None:
                s = f"{s:{fmt}}"
            # append new data to buffer
            row = orig_row = self[at[0]]
            if center is True:
                pad_chrs = int((self.cols - len(s)) / 2)
                row = (" " * pad_chrs if pad_chrs > 0 else "") + s
                col = len(row)
            elif len(row) <= at[1]:
                # pad row with spaces, if cursor pos is > current row length
                row += " " * (at[1] - len(self[at[0]])) + s
                col = len(row)
            elif at[1] + len(s) > len(row):
                # overwrite portion of the row
                row = row[: at[1]] + s
                col = len(row)
            else:
                # row = row[: at[1]] + s + row[at[1] + len(s) :]
                remainder = row[at[1] + len(s) :]
                row = row[: at[1]] + s
                col = len(row)
                row += remainder
            # the cursor position might have changed even
            # if the string is the same
            self._cursor_pos = (at[0], col)
            # if the row contents didn't change, don't do any work
            if row != orig_row:
                self._buffer[at[0]] = row  # calling setitem changes cursor
                self._changed_rows.add(at[0])
                self.__do_notify()

    def __do_notify(self) -> None:
        """
        Notify all waiting threads that the buffer has changed.
        Must be called from within the synchronizer's lock.
        """
        if self._auto_update is True:
            self._cv.notify_all()
