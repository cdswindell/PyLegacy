from .tmcc1_command import TMCC1Command
from ..constants import TMCC1EngineCommandDef, DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope, \
    TMCC1_TRAIN_COMMAND_MODIFIER, TMCC1_TRAIN_COMMAND_PURIFIER


class EngineCmd(TMCC1Command):
    def __init__(self,
                 engine: int,
                 option: TMCC1EngineCommandDef,
                 option_data: int = 0,
                 scope: CommandScope = CommandScope.ENGINE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if scope == CommandScope.ENGINE:
            if engine < 1 or engine > 99:
                raise ValueError("Engine must be between 1 and 99")
        elif scope == CommandScope.TRAIN:
            if engine < 1 or engine > 10:
                raise ValueError("Train must be between 1 and 10")
        super().__init__(engine, baudrate, port)
        self._option = option
        self.data = option_data
        self._scope = scope
        self._command = self._build_command()

    def __repr__(self):
        data = f" [{self.data}] " if self._option.value.num_data_bits else ''
        return f"<Engine {self.address} {self._option.name}{data}: 0x{self.command_bytes.hex()}>"

    def _build_command(self) -> bytes:
        command_op = self._apply_data()
        if self._scope == CommandScope.TRAIN:
            command_op &= TMCC1_TRAIN_COMMAND_PURIFIER  # remove unwanted bits from ENG command
            command_op |= TMCC1_TRAIN_COMMAND_MODIFIER  # add bits to specify train command
        return self.command_prefix + self._encode_address(command_op)

    def _apply_data(self) -> int:
        """
            For commands that take parameters, such as engine speed and brake level,
            apply the data bits to the command op bytes to form the complete byte
            set to send to the Lionel LCS SER2.
        """
        data = self.data
        cmd = self._option.command_def
        if cmd.num_data_bits and data is None:
            raise ValueError("Data is required")
        if cmd.num_data_bits == 0:
            return cmd.bits
        elif cmd.data_map:
            d_map = cmd.data_map
            if data in d_map:
                data = d_map[data]
            else:
                raise ValueError(f"Invalid data value: {data} (not in map)")
        elif data < cmd.data_min or data > cmd.data_max:
            raise ValueError(f"Invalid data value: {data} (not in range)")
        # sanitize data so we don't set bits we shouldn't
        filtered_data = data & (2 ** cmd.num_data_bits - 1)
        if data != filtered_data:
            raise ValueError(f"Invalid data value: {data} (not in range)")
        return cmd.bits | data
