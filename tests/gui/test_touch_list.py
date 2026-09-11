from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.gui.components import touch_list as mod


class Widget:
    def __init__(self, parent=None, **kwargs):
        self.bindings = {}
        self.options = kwargs
        self.children = []
        if isinstance(parent, Widget):
            parent.children.append(self)
        self.y = 0
        self.total = 1000

    def bind(self, sequence, handler, add=None):
        self.bindings[sequence] = handler

    def pack(self, **_kwargs):
        pass

    def pack_propagate(self, _value):
        pass

    def config(self, **kwargs):
        self.options.update(kwargs)

    def create_window(self, *_args, **_kwargs):
        return 1

    def winfo_children(self):
        return self.children[:]

    def destroy(self):
        self.bindings.clear()

    def bbox(self, _item):
        return 0, 0, 200, self.total

    def winfo_height(self):
        return 200

    def canvasy(self, y):
        return self.y + y

    def yview_moveto(self, fraction):
        self.y = fraction * self.total


@pytest.fixture
def touch_list(monkeypatch):
    # Keep the real TouchList methods while substituting only Tk's display surfaces.
    monkeypatch.setattr(mod.TouchList.__bases__[0], "__init__", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod.TouchList, "bind", Widget.bind)
    monkeypatch.setattr(mod.TouchList, "bindings", {}, raising=False)
    monkeypatch.setattr(mod.tk, "Frame", Widget)
    monkeypatch.setattr(mod.tk, "Canvas", Widget)
    monkeypatch.setattr(mod.tk, "Label", Widget)
    monkeypatch.setattr(mod.ttk, "Separator", Widget)
    return mod.TouchList(None, on_select=Mock())


def test_surface_binds_locally_to_canvas_and_every_row(touch_list):
    touch_list.set_items(["First", {"title": "Second", "subtitle": "Details"}])
    widgets = [touch_list, touch_list.canvas, touch_list.inner]
    for child in touch_list.inner.children:
        widgets.extend([child, *child.children])
    for widget in widgets:
        assert {"<MouseWheel>", "<TouchpadScroll>", "<Button-4>", "<Button-5>"} <= widget.bindings.keys()
        touch_list.canvas.y = 100
        assert widget.bindings["<TouchpadScroll>"](SimpleNamespace(delta=0xFFFF)) == "break"
        assert touch_list.canvas.y == pytest.approx(101)
    touch_list.on_select.assert_not_called()
    touch_list.set_items(["Replacement"])
    label = touch_list.inner.children[-2].children[0]
    assert "<TouchpadScroll>" in label.bindings


@pytest.mark.parametrize("dx,dy", [(0, 1), (0, -1), (0, -50), (-50, 0), (50, -2), (0, 0)])
def test_precise_pixels_and_axis_filter(touch_list, dx, dy):
    touch_list.canvas.y = 100
    event = SimpleNamespace(delta=(dx << 16) | (dy & 0xFFFF))
    assert touch_list._on_touchpad_scroll(event) == "break"
    assert touch_list.canvas.y == pytest.approx(100 - dy)


def test_surface_clamps_and_empty_list_does_not_scroll(touch_list):
    touch_list._on_touchpad_scroll(SimpleNamespace(delta=0x8000))
    assert touch_list.canvas.y == 800
    touch_list._on_touchpad_scroll(SimpleNamespace(delta=32767))
    assert touch_list.canvas.y == 0
    touch_list.canvas.total = 0
    assert touch_list._on_touchpad_scroll(SimpleNamespace(delta=0xFFFF)) == "break"
    assert touch_list.canvas.y == 0


def test_older_tk_preserves_local_wheel_support(touch_list, monkeypatch):
    from pytrain.gui.components import scroll_input

    monkeypatch.setattr(scroll_input, "platform", "darwin")
    bind = Widget.bind

    def old_bind(self, sequence, handler, add=None):
        if sequence == "<TouchpadScroll>":
            raise mod.tk.TclError("unknown event")
        bind(self, sequence, handler, add)

    monkeypatch.setattr(Widget, "bind", old_bind)
    widget = Widget()
    touch_list._bind_scrolling(widget)
    assert "<TouchpadScroll>" not in widget.bindings
    widget.bindings["<MouseWheel>"](SimpleNamespace(delta=-1))
    assert touch_list.canvas.y == 8
    widget.bindings["<Button-5>"](None)
    assert touch_list.canvas.y == 56
