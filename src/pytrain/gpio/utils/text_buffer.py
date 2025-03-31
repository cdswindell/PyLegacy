class TextBuffer:
    def __init__(self, rows: int = 4, cols: int = 20) -> None:
        self._rows = rows
        self._cols = cols
        self._cursor_pos = (0, 0)
        self._buffer: list[str] = list()

    def __repr__(self) -> str:
        return "\n".join(self._buffer)

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def cursor_pos(self) -> tuple[int, int]:
        return self._cursor_pos

    @cursor_pos.setter
    def cursor_pos(self, pos: tuple[int, int]) -> None:
        if isinstance(pos, tuple) and len(pos) == 2:
            if pos[0] < 0 or pos[0] >= self.rows:
                raise AttributeError(f"Invalid row position: {pos[0]}")
            if pos[1] < 0 or pos[1] >= self.cols:
                raise AttributeError(f"Invalid column position: {pos[1]}")
            self._cursor_pos = pos
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

    def clear(self) -> None:
        self._buffer.clear()
        self._cursor_pos = (0, 0)

    def add(self, row: str) -> bool:
        if len(self._buffer) < self.rows:
            self._buffer.append(row)
            return True
        return False

    def write_chr(self, int_chr: int, at: tuple[int, int] = None) -> None:
        if isinstance(int_chr, int) and 0 <= int_chr <= 255:
            self.write(chr(int_chr), at=at)

    def write(self, c: int | str, at: tuple[int, int] = None, format: str = None) -> None:
        at = at if isinstance(at, tuple) and len(at) == 2 else self._cursor_pos
        if len(self._buffer) <= at[0]:
            for _ in range(at[0] + 1 - len(self._buffer)):
                self._buffer.append("")

        if format is not None:
            fmt = f"{format[1:] if format.startswith(':') else format}"
        else:
            fmt = None

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
        row = self._buffer[at[0]]
        if len(row) <= at[1]:
            row += " " * (at[1] - len(self._buffer[at[0]])) + s
        elif at[1] + len(s) > len(row):
            row = row[: at[1]] + s
        else:
            row = row[: at[1]] + s + row[at[1] + len(s) :]
        self._buffer[at[0]] = row
        self._cursor_pos = (at[0], len(row))
