class PdiReq:
    def __init__(self, data: bytes):
        self._data = data

    def __repr__(self) -> str:
        return self._data.hex(':')

    @property
    def as_bytes(self) -> bytes:
        return self._data
