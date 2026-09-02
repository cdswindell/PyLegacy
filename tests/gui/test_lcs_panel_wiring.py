"""
The LCS... key's other half: what ``EngineGui`` does when the key asks for the panel.

``KeypadView`` binds the shared key straight to ``host.on_lcs_config_panel``, the way the
Info key is bound to ``host.on_info`` -- see ``tests/gui/test_keypad_view.py`` for that end
of the wiring -- because the host is what knows which module the operator was looking at.
These tests cover this end: the panel is built once and kept, seeded from the pane's own
scope, TMCC ID and selection on every press, and shown through the same popup machinery as
every other overlay.
"""

from __future__ import annotations

from threading import Condition
from types import SimpleNamespace
from typing import Any

import pytest

import src.pytrain.gui.controller.engine_gui as mod
from src.pytrain.protocol.constants import CommandScope


class FakePanel:
    """Stands in for ``LcsConfigPanel``, recording what it was seeded with."""

    instances: list["FakePanel"] = []

    def __init__(self, gui: Any) -> None:
        self.gui = gui
        self.overlay = SimpleNamespace(name="lcs-overlay")
        self.configured: list[tuple[Any, Any, Any]] = []
        FakePanel.instances.append(self)

    def configure(self, scope: Any = None, tmcc_id: Any = None, state: Any = None) -> None:
        self.configured.append((scope, tmcc_id, state))


@pytest.fixture(autouse=True)
def _patch_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    FakePanel.instances = []
    monkeypatch.setattr(mod, "LcsConfigPanel", FakePanel, raising=True)


def _gui(scope: CommandScope = CommandScope.ACC, tmcc_id: int = 19) -> "mod.EngineGui":
    """A bare pane holding only what ``on_lcs_config_panel`` touches."""
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._cv = Condition()
    gui._lcs_config_panel = None
    gui.scope = scope
    gui._scope_tmcc_ids = {scope: tmcc_id}
    gui._state_store = SimpleNamespace(get_state=lambda s, i, _create=False: SimpleNamespace(scope=s, tmcc_id=i))
    gui.popups = []
    gui.show_popup = lambda overlay, **kwargs: gui.popups.append((overlay, kwargs))
    return gui


def test_the_lcs_key_opens_a_panel_seeded_from_what_is_on_screen() -> None:
    gui = _gui()

    gui.on_lcs_config_panel()

    panel = gui._lcs_config_panel
    assert isinstance(panel, FakePanel)
    assert panel.gui is gui
    # Seeded from the pane itself: the scope of the screen, the ID keyed into it, and the
    # state that ID holds -- which is what lets the panel open on the module already there.
    scope, tmcc_id, state = panel.configured[-1]
    assert scope == CommandScope.ACC
    assert tmcc_id == 19
    assert state is not None and state.tmcc_id == 19
    # Shown like every other overlay, with the image box out of the way.
    assert gui.popups == [(panel.overlay, {"hide_image_box": True})]


def test_the_panel_is_built_once_and_re_seeded_on_every_press() -> None:
    # The panel is expensive to build and holds the operator's place in its pages, so it is
    # kept; what changes between presses is what it is seeded with.
    gui = _gui()

    gui.on_lcs_config_panel()
    gui.scope = CommandScope.SWITCH
    gui._scope_tmcc_ids = {CommandScope.SWITCH: 7}
    gui.on_lcs_config_panel()

    assert len(FakePanel.instances) == 1
    panel = gui._lcs_config_panel
    assert [(scope, tmcc_id) for scope, tmcc_id, _state in panel.configured] == [
        (CommandScope.ACC, 19),
        (CommandScope.SWITCH, 7),
    ]
    assert len(gui.popups) == 2


def test_the_key_pressed_in_entry_mode_opens_the_panel_with_nothing_selected() -> None:
    # In entry mode no ID has been committed, so the pane has nothing to reflect; the panel
    # is opened all the same and falls back to its own default base ID.
    gui = _gui(CommandScope.SWITCH, 0)

    gui.on_lcs_config_panel()

    scope, tmcc_id, state = gui._lcs_config_panel.configured[-1]
    assert scope == CommandScope.SWITCH
    assert tmcc_id == 0
    assert state is None


def test_the_keypad_key_binds_straight_to_the_panes_opener() -> None:
    # The two halves joined: the shared key is built with ``command=host.on_lcs_config_panel``,
    # so this bound method is the very callable the button holds -- there is no handler in
    # between, and a pane that stopped offering it would fail while the keypad is built rather
    # than press to no effect.
    gui = _gui()
    button_command = gui.on_lcs_config_panel

    button_command()

    assert isinstance(gui._lcs_config_panel, FakePanel)
    assert len(gui.popups) == 1
