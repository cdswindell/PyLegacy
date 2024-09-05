import pytest

from src.protocol.command_base import CommandBase


class TestCommandBase:
    def test_can_not_instantiate_command_base(self) -> None:
        with pytest.raises(TypeError):
            CommandBase(1)
