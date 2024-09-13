from src.protocol.command_req import CommandReq, ParameterCommandReq
from src.protocol.constants import CommandScope, TMCC2ParameterEnum
from src.protocol.validations import Validations


# noinspection PyMethodMayBeStatic
class TestBase:
    def teardown_method(self, test_method):
        pass

    def setup_method(self, test_method):
        pass

    def build_request(self, cmd, address: int, data: int = 0, scope: CommandScope = None) -> CommandReq:
        if isinstance(cmd, TMCC2ParameterEnum):
            req = ParameterCommandReq(cmd, address, data, scope)
        else:
            req = CommandReq(cmd, address, data, scope)
        return req


# noinspection PyUnusedLocal
class MockCommandReq:
    @classmethod
    def _enqueue_command(cls,
                         cmd: bytes,
                         repeat: int,
                         delay: int,
                         baudrate: int,
                         port: str) -> bytes:
        repeat = Validations.validate_int(repeat, min_value=1, label="repeat")
        delay = Validations.validate_int(delay, min_value=0, label="delay")
        print(f"In MockCommandRequest._enqueue_command: {cmd.hex()} {repeat}, {delay}, {baudrate}")

        cmd_bytes: bytes = bytes()
        for _ in range(repeat):
            cmd_bytes += cmd
        return cmd_bytes


# noinspection PyMethodMayBeStatic
class MockCommBuffer:
    _instance = None

    def __init__(self, baudrate: int, port: str):
        self.baudrate = baudrate
        self.port = port

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in the system
        """
        if not cls._instance:
            cls._instance = super(MockCommBuffer, cls).__new__(cls)
        return cls._instance

    def enqueue_command(self, command: bytes) -> bytes:
        return command
