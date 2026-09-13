from dataclasses import FrozenInstanceError

import pytest

from src.pytrain_ui.contracts import EngineViewState


def test_engine_view_state_is_immutable() -> None:
    state = EngineViewState(scope="ENGINE", tmcc_id=12, road_name="NYC", speed=20)

    assert state.scope == "ENGINE"
    assert state.tmcc_id == 12
    assert state.road_name == "NYC"
    assert state.speed == 20

    with pytest.raises(FrozenInstanceError):
        state.speed = 21  # type: ignore[misc]
