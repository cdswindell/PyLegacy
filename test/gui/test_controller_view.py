from __future__ import annotations

import time
from types import SimpleNamespace

from src.pytrain.gui.controller.controller_view import ControllerView


class DummyCell:
    def __init__(self, text: str, delay_s: float = 0.0) -> None:
        self.text = text
        self._delay_s = delay_s
        self.show_calls = 0
        self.hide_calls = 0

    def show(self) -> None:
        self.show_calls += 1
        if self._delay_s:
            time.sleep(self._delay_s)

    def hide(self) -> None:
        self.hide_calls += 1
        if self._delay_s:
            time.sleep(self._delay_s)


def test_show_keys_for_type_traces_show_hide_timings() -> None:
    events: list[tuple[str, dict[str, object]]] = []
    keypad_box = SimpleNamespace(
        visible=True,
        hide_calls=0,
        show_calls=0,
    )
    keypad_box.hide = lambda: (
        setattr(keypad_box, "hide_calls", keypad_box.hide_calls + 1),
        setattr(keypad_box, "visible", False),
    )
    keypad_box.show = lambda: (
        setattr(keypad_box, "show_calls", keypad_box.show_calls + 1),
        setattr(keypad_box, "visible", True),
    )
    shared = DummyCell("shared", delay_s=0.001)
    added = DummyCell("added")
    removed = DummyCell("removed", delay_s=0.001)
    host = SimpleNamespace(
        _last_engine_type="d",
        controller_keypad_box=keypad_box,
        gui_trace_slow_ms=10_000,
        trace_transition_phase=lambda phase, **fields: events.append((phase, fields)),
    )
    view = ControllerView(host)
    view._engine_type_key_map = {
        "d": {shared, removed},
        "s": {shared, added},
    }
    view._all_engine_btns = {shared, added, removed}

    shown_count, hidden_count, skipped = view._show_keys_for_type("s")

    assert (shown_count, hidden_count, skipped) == (1, 1, False)
    trace = [fields for phase, fields in events if phase == "controller.show_keys_for_type"][-1]
    assert trace["engine_type"] == "s"
    assert trace["previous_engine_type"] == "d"
    assert trace["shown_count"] == 1
    assert trace["hidden_count"] == 1
    assert trace["batched_container_hidden"] is True
    assert trace["show_ms"] >= 0
    assert trace["hide_ms"] >= 0
    assert trace["slowest_show_widget"] == "added"
    assert trace["slowest_hide_widget"] == "removed"
    assert keypad_box.hide_calls == 1
    assert keypad_box.show_calls == 1
    assert shared.show_calls == 0
    assert shared.hide_calls == 0
