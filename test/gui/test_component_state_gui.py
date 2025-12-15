import time
from threading import Event

import pytest

import src.pytrain.gui.component_state_gui

# Target module
from src.pytrain.gui import state_based_gui as mod
from src.pytrain.gui import power_district_gui as pd_mod
from src.pytrain.gui import routes_gui as ro_mod
from src.pytrain.gui import switches_gui as sw_mod


class DummyGui:
    """
    Minimal stand-in for the concrete GUI classes used by ComponentStateGui.
    It avoids any tkinter/guizero usage but mimics the required interface:
      - __init__(label, width, height, aggrigator=None)
      - close()
      - destroy_complete: Event that becomes set after close() is called
    """

    # Keep simple traceability for assertions
    instances = []
    closed = []

    def __init__(
        self,
        label=None,
        width=None,
        height=None,
        aggrigator=None,
        scale_by: float = 1.0,
        exclude_unnamed: bool = False,
    ):
        self.label = label
        self.width = width
        self.height = height
        self.aggrigator = aggrigator
        self.destroy_complete = Event()
        self._closed = False
        self._scale_by = scale_by
        self._exclude_unnamed = exclude_unnamed

        # track instance lifecycle for tests
        DummyGui.instances.append(self)

    def close(self):
        self._closed = True
        DummyGui.closed.append(self)
        # Simulate fast teardown
        self.destroy_complete.set()

    def join(self, timeout=None):
        return

    # Some code checks is_alive() on threads; be safe
    @staticmethod
    def is_alive():
        return False


@pytest.fixture(autouse=True)
def patch_gui_classes(monkeypatch):
    """
    Replace the real GUI classes with dummy stand-ins so tests don't require tkinter/guizero.
    Do this before constructing ComponentStateGui, so its internal mapping points at DummyGui.
    """
    DummyGui.instances.clear()
    DummyGui.closed.clear()

    monkeypatch.setattr(pd_mod, "PowerDistrictsGui", DummyGui, raising=True)
    monkeypatch.setattr(sw_mod, "SwitchesGui", DummyGui, raising=True)
    monkeypatch.setattr(ro_mod, "RoutesGui", DummyGui, raising=True)

    # Ensure switching calls actually close our DummyGui
    def fake_release_handler(handler):
        # Simulate the effect we need in tests
        if hasattr(handler, "close"):
            handler.close()

    monkeypatch.setattr(mod.GpioHandler, "release_handler", staticmethod(fake_release_handler), raising=True)

    yield

    # Cleanup between tests
    DummyGui.instances.clear()
    DummyGui.closed.clear()


def wait_for(predicate, timeout=2.0, interval=0.01):
    """Utility to wait until predicate() is True or timeout occurs."""
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_invalid_initial_gui_raises():
    with pytest.raises(ValueError):
        # Pass a bogus initial name which is not present in the _guis map
        src.pytrain.gui.component_state_gui.ComponentStateGui(label="X", initial="Not A GUI", width=100, height=100)


# noinspection PyTypeHints
def test_initial_gui_is_created_and_aggregator_set():
    # Using default initial "Power Districts" which we patched to DummyGui
    comp = src.pytrain.gui.component_state_gui.ComponentStateGui(label="My Label", width=320, height=240)

    # Wait until the ComponentStateGui thread creates the initial GUI
    assert wait_for(lambda: len(DummyGui.instances) == 1), "Initial GUI instance was not created"

    inst = DummyGui.instances[0]
    # Ensure the 'aggregator' reference is set so combo-box can call back
    assert inst.aggrigator is comp
    # Ensure dimensions/label plumb through
    assert inst.label == "My Label"
    assert inst.width == 320
    assert inst.height == 240


# noinspection PyTypeHints
def test_cycle_gui_switches_and_closes_previous():
    comp = src.pytrain.gui.component_state_gui.ComponentStateGui(label=None, width=640, height=480)

    # initial GUI created
    assert wait_for(lambda: len(DummyGui.instances) == 1)

    first = DummyGui.instances[0]
    assert first._closed is False

    # Request switch to "Routes" (also patched to DummyGui)
    comp.cycle_gui("Routes")

    # After switch, we should have a second instance created
    assert wait_for(lambda: len(DummyGui.instances) == 2), "Second GUI instance was not created"

    # The first instance should have been closed and its destroy_complete set
    assert first._closed is True
    assert first in DummyGui.closed

    # ComponentStateGui should now point to the second instance
    assert comp._gui is DummyGui.instances[1]


# noinspection PyTypeHints
def test_cycle_gui_ignores_unknown_key():
    comp = src.pytrain.gui.component_state_gui.ComponentStateGui(width=200, height=200)

    assert wait_for(lambda: len(DummyGui.instances) == 1)

    # Try to cycle to an unknown GUI; nothing should change
    comp.cycle_gui("Unknown GUI")
    # Give a small window in case anything erroneously happens
    time.sleep(0.1)
    assert len(DummyGui.instances) == 1
    assert comp._gui is DummyGui.instances[0]


def test_guis_property_lists_expected_entries():
    comp = src.pytrain.gui.component_state_gui.ComponentStateGui(width=200, height=200)

    # The keys come from ComponentStateGui._guis dict
    names = comp.guis
    assert isinstance(names, list)
    assert "Power Districts" in names
    assert "Switches" in names
    assert "Routes" in names
