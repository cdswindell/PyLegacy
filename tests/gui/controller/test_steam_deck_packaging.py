import json

from pathlib import Path

from src.pytrain.gui.controller.accessory_bindings import KNOWN_VERBS
from src.pytrain.gui.controller.steam_deck_input import (
    DPAD_ACTIONS,
    DPAD_DIRECTIONS,
    ControlProfile,
)


ROOT = Path(__file__).parents[3]
BUNDLED_PROFILE = ROOT / "src/pytrain/gui/controller/steam_deck_default.json"


def test_runtime_dependencies_and_profile_are_packaged() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-nogpio.txt").read_text(encoding="utf-8")

    assert '"pygame-ce >=' in pyproject
    assert "pygame-ce>=" in requirements
    assert '"*.json"' in pyproject


def test_launch_artifacts_preserve_gamescope_display_and_describe_kde_entry() -> None:
    launch = (ROOT / "src/pytrain/installation/launch_pytrain.bash.template").read_text(encoding="utf-8")
    desktop = (ROOT / "src/pytrain/installation/pytrain_desktop.template").read_text(encoding="utf-8")

    assert 'if [ -z "$DISPLAY" ]' in launch
    assert "export DISPLAY" in launch
    assert "Terminal=false" in desktop
    assert "Categories=Game;Utility;" in desktop


def test_bundled_profile_declares_the_dpad_rather_than_leaving_it_hard_coded() -> None:
    # The D-pad's boost/brake/smoke behavior used to live in the router. It is a default now,
    # not a law, so it has to be visible in the profile a user copies and edits.
    data = json.loads(BUNDLED_PROFILE.read_text(encoding="utf-8"))

    dpad = data["dpad"]
    assert set(dpad) == set(DPAD_DIRECTIONS)
    assert dpad["up"] == {"action": "boost", "target": "focused", "repeat": True}
    assert dpad["down"] == {"action": "brake", "target": "focused", "repeat": True}
    assert dpad["left"] == {"action": "smoke_down", "target": "focused"}
    assert dpad["right"] == {"action": "smoke_up", "target": "focused"}


def test_bundled_profile_sections_are_all_ones_the_loader_understands() -> None:
    data = json.loads(BUNDLED_PROFILE.read_text(encoding="utf-8"))

    for entry in data["dpad"].values():
        assert entry["action"] in DPAD_ACTIONS
    for name, context in data.get("contexts", {}).items():
        assert isinstance(name, str)
        for dispatch in (context.get("bindings") or {}).values():
            assert dispatch is None or dispatch["verb"] in KNOWN_VERBS


def test_bundled_profile_loads_with_the_dpad_and_context_tables_populated() -> None:
    profile = ControlProfile.load()

    assert profile.dpad["dpad_up"].action == "boost"
    assert profile.dpad["dpad_up"].repeat is True
    assert profile.dpad["dpad_left"].action == "smoke_down"
    assert profile.dpad["dpad_left"].repeat is False
    # The Python defaults are behind the profile, so the switch/route tables are there even
    # though the bundled JSON says nothing about them.
    assert {"switch", "route"} <= set(profile.contexts)
