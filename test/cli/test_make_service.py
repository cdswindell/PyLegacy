from unittest import mock

import builtins
import pytest

from src.pytrain.cli.make_service import MakeService
from ..test_base import TestBase


class TestMakeService(TestBase):
    def test_parser(self):
        # test successful options
        for i in range(2, len("-version")):
            li = ["-version"][:i]
            with pytest.raises(SystemExit) as e:
                MakeService(li)
            assert e.value.code == 0

        with pytest.raises(SystemExit) as e:
            MakeService(["-h"])
        assert e.value.code == 0

        with pytest.raises(SystemExit) as e:
            MakeService(["--help"])
        assert e.value.code == 0

        with mock.patch.object(builtins, "input", return_value="n"):
            # test some positive cases
            assert MakeService("-client".split()) is not None
            assert MakeService("-client -echo".split()) is not None
            assert MakeService("-client -buttons".split()) is not None
            assert MakeService("-client -buttons -start".split()) is not None
            assert MakeService("-server -base -ser2 -echo -buttons_f".split()) is not None

            # test some negative cases
            # neither client nor server specified
            with pytest.raises(SystemExit) as e:
                MakeService("-echo -buttons -start".split())
            assert e.value.code == 2

            # bad arguments
            with pytest.raises(SystemExit) as e:
                MakeService("-service".split())
            assert e.value.code == 2
