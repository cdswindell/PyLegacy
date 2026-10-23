from unittest.mock import patch

import pytest

from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.base3_db_refresh_manager import Base3DbRefreshManager

from .ramp_test_support import RampWorkers


@pytest.fixture
def ramp_workers(ramp_target_update, ramp_refresh_scheduling, pdi_send):
    """Finish owned workers before their database and transport isolation is removed."""
    workers = RampWorkers()
    yield workers
    workers.cleanup()


@pytest.fixture
def ramp_refresh_scheduling():
    """Record ramp refresh scheduling without starting the refresh worker."""
    with (
        patch.object(Base3DbRefreshManager, "flush", autospec=True) as flush,
        patch.object(Base3DbRefreshManager, "request_refresh", autospec=True) as request_refresh,
    ):
        yield {"flush": flush, "request_refresh": request_refresh}


@pytest.fixture
def ramp_target_update(request, ramp_refresh_scheduling):
    """Record database updates; indirect False keeps real dispatch with refresh isolation."""
    if getattr(request, "param", True) is False:
        yield None
    else:
        with patch.object(BaseReq, "do_update_field", autospec=True) as update:
            yield update


@pytest.fixture(autouse=True)
def pdi_send():
    """Keep in-memory sequence tests off the real PDI transport while recording requests."""
    # send() is inherited from PdiReq; patch this subclass to leave other PDI requests alone.
    # noinspection PyUnresolvedReferences
    with patch.object(BaseReq, "send", autospec=True) as send:
        yield send
