from src.pytrain import get_version
from .test_base import TestBase


class TestPyTrain(TestBase):
    def test_get_version(self):
        assert get_version() is not None
        assert get_version().startswith("v")
