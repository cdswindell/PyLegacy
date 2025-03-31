import random
from typing import TypeVar

from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.multibyte.multibyte_constants import *
from src.pytrain.protocol.tmcc1.tmcc1_constants import *
from src.pytrain.protocol.tmcc2.tmcc2_constants import *
from src.pytrain.utils.validations import Validations

T = TypeVar("T", TMCC1Enum, TMCC2Enum)


# noinspection PyMethodMayBeStatic
class TestBase:
    thread_exceptions = {}

    def teardown_method(self, test_method):
        pass

    def setup_method(self, test_method):
        pass

    def clear_thread_exceptions(self):
        self.thread_exceptions.clear()

    def custom_excepthook(self, args):
        new_exception = {
            "thread": args.thread,
            "exception": {"type": args.exc_type, "value": args.exc_value, "traceback": args.exc_traceback},
        }
        thread_name = args.thread.name
        if thread_name in self.thread_exceptions:
            self.thread_exceptions[thread_name].append(new_exception)
        else:
            self.thread_exceptions[thread_name] = [new_exception]

    def build_request(self, cmd, address: int = None, data: int = None, scope: CommandScope = None) -> CommandReq:
        if address is None:
            address = self.generate_random_address(cmd, scope=scope)
        if data is None:
            if cmd.value.is_data > 0:
                data = self.generate_random_data(cmd)
            else:
                data = 0
        return CommandReq.build(cmd, address, data, scope)

    @property
    def all_command_enums(self) -> List[T]:
        return [
            TMCC1HaltCommandEnum,
            TMCC1RouteCommandEnum,
            TMCC1AuxCommandEnum,
            TMCC1SwitchCommandEnum,
            TMCC1EngineCommandEnum,
            TMCC2HaltCommandEnum,
            TMCC2RouteCommandEnum,
            TMCC2EngineCommandEnum,
            TMCC2RailSoundsDialogControl,
            TMCC2EffectsControl,
            TMCC2LightingControl,
        ]

    def generate_random_address(self, cmd: CommandDefEnum, scope: CommandScope = None) -> int:
        if cmd.syntax == CommandSyntax.TMCC:
            if scope == CommandScope.TRAIN or cmd.scope == CommandScope.ROUTE:
                address = random.randint(1, 10)
            else:
                address = random.randint(1, 99)
        else:
            address = random.randint(1, 99)
        return address

    def generate_random_data(self, cmd: CommandDefEnum) -> int:
        command_def = cmd.value
        if command_def.data_max != 0:
            data = random.randint(command_def.data_min, command_def.data_max)
        elif command_def.data_map:
            data = random.randint(min(command_def.data_map), max(command_def.data_map))
        elif command_def.num_data_bits == 0:
            data = 0
        else:
            raise ValueError(f"Invalid command def: {cmd.name}")
        return data


# noinspection PyUnusedLocal
class MockCommandReq:
    @classmethod
    def _enqueue_command(
        cls,
        cmd: bytes,
        repeat: int,
        delay: float,
        baudrate: int,
        port: str,
        server: str,
        buffer,
        original_req: "MockCommandReq",
    ) -> bytes:
        repeat = Validations.validate_int(repeat, min_value=1, label="repeat")
        delay = Validations.validate_float(delay, min_value=0, label="delay")
        print(f"In MockCommandRequest._enqueue_command: {cmd.hex()} {repeat}, {delay}, {baudrate}")

        cmd_bytes: bytes = bytes()
        for _ in range(repeat):
            cmd_bytes += cmd
        return cmd_bytes


# noinspection PyMethodMayBeStatic
class MockCommBuffer:
    _instance = None

    def __init__(self, baudrate: int, port: str):
        if MockCommBuffer._instance.__initialized:
            return
        else:
            MockCommBuffer._instance.__initialized = True
        self.baudrate = baudrate
        self.port = port

    def __new__(cls, *args, **kwargs):
        """
        Provides singleton functionality. We only want one instance
        of this class in the system
        """
        if not cls._instance:
            cls._instance = super(MockCommBuffer, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def enqueue_command(self, command: bytes) -> bytes:
        return command
