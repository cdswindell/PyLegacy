from types import SimpleNamespace

import pytest

from src.pytrain.gui.components import scroll_input as mod


@pytest.mark.parametrize("dx,dy", [(0, 0), (1, -1), (-1, 1), (-32768, 32767), (32767, -32768)])
@pytest.mark.parametrize("signed", [False, True])
def test_precise_delta_decodes_both_axes(dx, dy, signed):
    packed = ((dx & 0xFFFF) << 16) | (dy & 0xFFFF)
    if signed and packed >= 0x80000000:
        packed -= 0x100000000
    assert mod.precise_scroll_deltas(SimpleNamespace(delta=packed)) == (dx, dy)


@pytest.mark.parametrize("event", [None, SimpleNamespace(), SimpleNamespace(delta="??"), SimpleNamespace(delta=None)])
def test_missing_or_invalid_delta_is_ignored(event):
    assert mod.precise_scroll_deltas(event) == (0, 0)
    assert mod.wheel_scroll_pixels(event) == 0


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
@pytest.mark.parametrize("delta", [-240, -120, 120, 240])
def test_wheel_notches_remain_proportional(platform, delta, monkeypatch):
    monkeypatch.setattr(mod, "platform", platform)
    assert mod.wheel_scroll_pixels(SimpleNamespace(delta=delta)) == -delta * 48 / 120


def test_small_mac_wheel_deltas_are_not_lost(monkeypatch):
    monkeypatch.setattr(mod, "platform", "darwin")
    assert mod.wheel_scroll_pixels(SimpleNamespace(delta=-1)) == 8
    assert mod.wheel_scroll_pixels(SimpleNamespace(delta=2)) == -16


def test_sub_row_motion_accumulates_and_resets_on_reversal_or_idle(monkeypatch):
    now = [10.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: now[0])
    accumulator = mod.ScrollAccumulator()
    assert accumulator.consume(1, 20) == 0
    assert accumulator.consume(18, 20) == 0
    assert accumulator.consume(2, 20) == 1
    assert accumulator.consume(-19, 20) == 0
    assert accumulator.consume(-1, 20) == -1
    assert accumulator.consume(19, 20) == 0
    now[0] += 1
    assert accumulator.consume(1, 20) == 0
    assert accumulator.consume(39, 20) == 2
    accumulator.reset()
    assert accumulator.consume(0, 20) == 0
