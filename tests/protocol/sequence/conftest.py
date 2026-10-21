from unittest.mock import patch

import pytest

from src.pytrain.pdi.base_req import BaseReq


@pytest.fixture
def ramp_target_update():
    """Record database-update requests only in ramp unit tests that opt in."""
    with patch.object(BaseReq, "do_update_field", autospec=True) as update:
        yield update


@pytest.fixture(autouse=True)
def pdi_send():
    """Keep in-memory sequence tests off the real PDI transport while recording requests."""
    # send() is inherited from PdiReq; patch this subclass to leave other PDI requests alone.
    # noinspection PyUnresolvedReferences
    with patch.object(BaseReq, "send", autospec=True) as send:
        yield send
